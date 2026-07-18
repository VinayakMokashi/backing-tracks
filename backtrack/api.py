"""FastAPI app: endpoints only, zero business logic.

Endpoints are sync ``def`` on purpose — FastAPI runs them in its threadpool,
which absorbs the multi-second render without a job queue.
"""
from __future__ import annotations

import hashlib
import re
import threading

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config

from . import chords, render, sheet_parser, store
from .arrange import arrange
from .model import RenderOptions, options_hash, song_to_dict
from .sources import SourceError, get_sheet

config.ensure_dirs()
app = FastAPI(title="Backing Tracks")

# song_id is always a slugify() product; anything else (e.g. '..\\' traversal
# attempts) is rejected before it can touch a path.
_SLUG_RE = re.compile(r"^[a-z0-9-]+$")

# Serializes the exists()-check + render so concurrent requests can't race a
# second FluidSynth onto the same output file. Coarse but fine for one user.
_render_lock = threading.Lock()


class SongRequest(BaseModel):
    url: str | None = None
    paste: str | None = None
    title: str = ""
    artist: str = ""


class RenderRequest(BaseModel):
    transpose: int = 0
    guitar: bool = True
    piano: bool = True
    drums: bool = False
    count_in: bool = True
    style: str | None = None
    bpm: float | None = Field(default=None, gt=0, le=400)
    guitar_program: int = 25
    capo_mode: str = "keep"


def _error(status: int, code: str, message: str, hint: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "hint": hint}},
    )


# Bad client input is 422; only genuine upstream faults stay 502.
_SOURCE_STATUS = {"unsupported_source": 422, "parse_failed": 422}


@app.exception_handler(SourceError)
def _source_error(_request, exc: SourceError):
    return _error(_SOURCE_STATUS.get(exc.code, 502), exc.code, exc.message, exc.hint)


@app.exception_handler(render.RenderError)
def _render_error(_request, exc: render.RenderError):
    return _error(500, "render_failed", exc.message, exc.hint)


@app.exception_handler(Exception)
def _unhandled(_request, exc: Exception):
    return _error(500, "internal",
                  f"Unexpected server error: {exc.__class__.__name__}",
                  "Check the server console for the traceback.")


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return render.check_environment()


@app.post("/api/songs")
def create_song(req: SongRequest):
    if not req.url:
        return _error(
            400, "not_implemented",
            "Only URL input is wired up so far (paste arrives in M2).",
            "Provide an Ultimate Guitar chords URL.",
        )
    raw = get_sheet(req.url)
    song = sheet_parser.parse(raw, title=req.title, artist=req.artist)
    if not song.sections:
        return _error(
            422, "parse_failed",
            "No chords found on that page.",
            "Make sure it is a Chords page (URL contains '/tab/'), not Pro/Official.",
        )
    existing = store.load_song(song.id)
    if existing is not None and existing.source_url != song.source_url:
        # Same artist+title from a different chart: disambiguate instead of
        # silently overwriting the saved song.
        suffix = hashlib.sha1(
            (song.source_url or song.sheet_text).encode("utf-8")
        ).hexdigest()[:6]
        song.id = f"{song.id}-{suffix}"
    store.save_song(song)
    return song_to_dict(song)


@app.get("/api/songs")
def list_songs():
    return {"songs": store.list_songs()}


@app.get("/api/songs/{song_id}")
def get_song(song_id: str):
    song = store.load_song(song_id) if _SLUG_RE.match(song_id) else None
    if song is None:
        return _error(404, "not_found", f"No song {song_id!r}.",
                      "Create it first via the Find box.")
    return song_to_dict(song)


@app.post("/api/songs/{song_id}/render")
def render_song(song_id: str, req: RenderRequest):
    song = store.load_song(song_id) if _SLUG_RE.match(song_id) else None
    if song is None:
        return _error(404, "not_found", f"No song {song_id!r}.",
                      "Create it first via the Find box.")

    opts = RenderOptions(**req.model_dump())
    ohash = options_hash(song, opts)
    out_dir = config.RENDERS_DIR / song_id
    wav_path = out_dir / f"{ohash}.wav"
    with _render_lock:
        cached = wav_path.exists()
        if cached:
            seconds = 0.0
            mp3_exists = (out_dir / f"{ohash}.mp3").exists()
        else:
            result = render.render(arrange(song, opts), song_id, ohash)
            seconds = result.seconds
            mp3_exists = result.mp3_path is not None

    shift = song.capo + opts.transpose
    key_parsed = chords.parse_symbol(song.key)
    if key_parsed is not None and not key_parsed.is_rest:
        minor = chords.key_is_minor(song.key)
        flats = chords.prefer_flats_for(key_parsed.root_pc + shift, minor)
        sounding_key = chords.transpose_symbol(song.key, shift, flats)
    else:
        sounding_key = song.key

    return {
        "midi_url": f"/media/{song_id}/{ohash}.mid",
        "wav_url": f"/media/{song_id}/{ohash}.wav",
        "mp3_url": f"/media/{song_id}/{ohash}.mp3" if mp3_exists else None,
        "cached": cached,
        "sounding_key": sounding_key,
        "bpm": opts.bpm or song.bpm,
        "render_seconds": seconds,
    }


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
app.mount("/media", StaticFiles(directory=config.RENDERS_DIR), name="media")
