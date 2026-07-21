"""Orchestration: URL -> analyze (download + key) -> transpose to a target key.

Source audio and outputs live under data/audio/<url-hash>/ so re-transposing to
a new key never re-downloads.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import config

from ..chords import NOTE_TO_PC
from . import download, keydetect, pitch, separate

AUDIO_DIR = config.DATA_DIR / "audio"
_ROOT_RE = None  # (kept simple; parsing below)


def source_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def parse_target(note: str) -> tuple[int, bool]:
    """'G', 'F#', 'Bb', 'Em', 'C#m' -> (pitch_class, is_minor)."""
    s = note.strip().replace("♯", "#").replace("♭", "b")
    minor = s.lower().endswith("m") and not s.lower().endswith("maj")
    root = s[:-1] if minor and len(s) > 1 else s
    root = root[0].upper() + root[1:]
    if root not in NOTE_TO_PC:
        raise ValueError(f"Unrecognised key: {note!r}")
    return NOTE_TO_PC[root], minor


def analyze(url: str, remove_vocals: bool = True) -> dict:
    sid = source_id(url)
    folder = AUDIO_DIR / sid
    meta_path = folder / "meta.json"
    src = folder / "source.wav"
    if src.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("vocals_removed") == remove_vocals:
            return meta
        # Setting changed: rebuild source + drop stale transposes.
        for old in folder.glob("key_*.mp3"):
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
        "from_key": keydetect.key_name(meta["pitch_class"], meta["minor"]),
        "to_key": keydetect.key_name(target_pc, meta["minor"]),
        "tempo_pct": tempo_pct,
        "target_bpm": round(src_bpm * tempo) if src_bpm else 0,
    }
