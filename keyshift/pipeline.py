"""Orchestration: URL -> analyze (download, remove vocals, detect key/BPM) ->
transpose to a target key and speed.

Source audio and outputs live under data/audio/<url-hash>/ so re-transposing to
a new key/speed never re-downloads or re-separates.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import config

from . import download, keydetect, pitch, separate
from .notes import key_name, parse_note

AUDIO_DIR = config.AUDIO_DIR


def source_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def analyze(url: str, remove_vocals: bool = True) -> dict:
    """Download the audio, optionally remove vocals, and estimate key + BPM."""
    sid = source_id(url)
    folder = AUDIO_DIR / sid
    meta_path = folder / "meta.json"
    src = folder / "source.wav"
    if src.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("vocals_removed") == remove_vocals:
            return meta
        for old in folder.glob("key_*.mp3"):  # setting changed -> drop stale outputs
            old.unlink(missing_ok=True)

    raw, title = download.download_audio(url, folder, "raw")
    if remove_vocals:
        instrumental = separate.separate_instrumental(raw, folder / "sep")
        shutil.move(str(instrumental), str(src))
        shutil.rmtree(folder / "sep", ignore_errors=True)
    else:
        shutil.move(str(raw), str(src))
    for leftover in folder.glob("raw.*"):
        leftover.unlink(missing_ok=True)

    detected = keydetect.detect_key(src)
    meta = {"id": sid, "url": url, "title": title,
            "vocals_removed": remove_vocals, **detected}
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return meta


def transpose(sid: str, target_pc: int, tempo_pct: int = 100) -> dict:
    """Pitch-shift the (vocals-removed) source to `target_pc` and `tempo_pct`."""
    folder = AUDIO_DIR / sid
    src = folder / "source.wav"
    meta_path = folder / "meta.json"
    if not src.exists() or not meta_path.exists():
        raise FileNotFoundError("source not analysed yet")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    semis = pitch.shortest_shift(meta["pitch_class"], target_pc)
    tempo = tempo_pct / 100.0
    out = folder / f"key_{target_pc}_t{tempo_pct}.mp3"
    if not out.exists():
        pitch.transform(src, out, semitones=semis, tempo=tempo, to_mp3=True)

    src_bpm = meta.get("bpm") or 0
    return {
        "audio_url": f"/audio/{sid}/{out.name}",
        "semitones": semis,
        "from_key": key_name(meta["pitch_class"], meta["minor"]),
        "to_key": key_name(target_pc, meta["minor"]),
        "tempo_pct": tempo_pct,
        "target_bpm": round(src_bpm * tempo) if src_bpm else 0,
    }


def parse_target(note: str) -> tuple[int, bool]:
    return parse_note(note)
