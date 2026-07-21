"""FastAPI app for the Key Shifter — endpoints only, no business logic.

Endpoints are sync `def` on purpose: FastAPI runs them in its threadpool, which
absorbs the slow download / vocal-removal / transform steps without a job queue.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config

from . import pipeline
from .download import DownloadError
from .pitch import PitchError
from .separate import SeparateError

config.ensure_dirs()
app = FastAPI(title="Key Shifter")


def _error(status: int, code: str, message: str, hint: str) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": {"code": code, "message": message,
                                           "hint": hint}})


@app.exception_handler(DownloadError)
def _download_error(_request, exc: DownloadError):
    return _error(502, "download_failed", exc.message, exc.hint)


@app.exception_handler(SeparateError)
def _separate_error(_request, exc: SeparateError):
    return _error(500, "separation_failed", exc.message, exc.hint)


@app.exception_handler(PitchError)
def _pitch_error(_request, exc: PitchError):
    return _error(500, "transform_failed", exc.message, exc.hint)


@app.exception_handler(RequestValidationError)
def _validation_error(_request, exc: RequestValidationError):
    first = (exc.errors() or [{}])[0]
    loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    return _error(422, "bad_request",
                  f"Invalid value for {loc!r}." if loc else "Invalid request.",
                  first.get("msg", "Check the field values and try again."))


@app.exception_handler(Exception)
def _unhandled(_request, exc: Exception):
    return _error(500, "internal", f"Unexpected error: {exc.__class__.__name__}",
                  "Check the server console for the traceback.")


class AnalyzeRequest(BaseModel):
    url: str
    remove_vocals: bool = True


class TransposeRequest(BaseModel):
    id: str
    target: str
    tempo_pct: int = Field(default=100, ge=50, le=150)


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    def importable(mod: str) -> bool:
        try:
            __import__(mod)
            return True
        except Exception:  # noqa: BLE001
            return False

    ffmpeg_ok = shutil.which(config.FFMPEG_EXE) is not None or Path(config.FFMPEG_EXE).exists()
    return {
        "ffmpeg": ffmpeg_ok,
        "yt_dlp": importable("yt_dlp"),
        "librosa": importable("librosa"),
        "demucs": importable("demucs"),
        "ok": ffmpeg_ok and importable("yt_dlp") and importable("librosa"),
    }


@app.post("/api/audio/analyze")
def audio_analyze(req: AnalyzeRequest):
    """Download the audio, remove vocals (default), estimate key + BPM.
    Slow (download + separation + analysis); runs in the threadpool."""
    url = req.url.strip()
    if not url:
        return _error(400, "bad_request", "Provide a video URL.",
                      "Paste a YouTube or Instagram link.")
    return pipeline.analyze(url, remove_vocals=req.remove_vocals)


@app.post("/api/audio/transpose")
def audio_transpose(req: TransposeRequest):
    try:
        target_pc, _ = pipeline.parse_target(req.target)
    except ValueError as exc:
        return _error(422, "bad_key", str(exc), "Use a note like G, F#, Bb, Em.")
    try:
        return pipeline.transpose(req.id, target_pc, req.tempo_pct)
    except FileNotFoundError:
        return _error(404, "not_found", "That track hasn't been analysed yet.",
                      "Paste the link and Analyze first.")


config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
app.mount("/audio", StaticFiles(directory=config.AUDIO_DIR), name="audio")
