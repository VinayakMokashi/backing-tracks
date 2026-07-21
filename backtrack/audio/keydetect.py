"""Estimate the musical key of an audio file (Krumhansl-Schmuckler on chroma).

An estimate, not ground truth — good for clear tonal tracks; the user can
override. Returns the tonic pitch class so transposition is exact regardless
of the estimated mode.
"""
from __future__ import annotations

from pathlib import Path

# Krumhansl-Kessler key profiles (tonic at index 0).
_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
_FLAT_KEYS = {5, 10, 3, 8, 1}  # F Bb Eb Ab Db spelled with flats


def _corr(a, b) -> float:
    import numpy as np
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    a = a - a.mean()
    b = b - b.mean()
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(a.dot(b) / denom)


def key_name(pitch_class: int, minor: bool) -> str:
    names = FLAT_NAMES if pitch_class % 12 in _FLAT_KEYS else SHARP_NAMES
    return f"{names[pitch_class % 12]}{'m' if minor else ''}"


def detect_key(wav_path: Path, max_seconds: float = 150.0) -> dict:
    import librosa
    import numpy as np

    y, sr = librosa.load(str(wav_path), mono=True, duration=max_seconds)
    if y.size == 0:
        raise ValueError("empty audio")

    try:  # tempo estimate on the full signal (needs the percussive content)
        bpm = round(float(np.atleast_1d(
            librosa.feature.rhythm.tempo(y=y, sr=sr))[0]))
    except Exception:  # noqa: BLE001 — best-effort
        bpm = 0

    y = librosa.effects.harmonic(y)  # de-emphasise drums/percussion for key
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    profile = chroma.mean(axis=1)

    best = None
    for tonic in range(12):
        for minor, prof in ((False, _MAJOR), (True, _MINOR)):
            score = _corr(profile, np.roll(prof, tonic))
            if best is None or score > best[0]:
                best = (score, tonic, minor)
    score, tonic, minor = best

    # confidence: gap to the runner-up tonic/mode
    scores = sorted(
        _corr(profile, np.roll(_MINOR if m else _MAJOR, t))
        for t in range(12) for m in (False, True)
    )
    margin = scores[-1] - scores[-2]
    return {
        "pitch_class": tonic,
        "minor": minor,
        "key": key_name(tonic, minor),
        "bpm": bpm,
        "score": round(score, 3),
        "confidence": "high" if margin > 0.06 else "medium" if margin > 0.02 else "low",
    }
