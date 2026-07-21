"""Estimate the musical key (Krumhansl-Schmuckler on chroma) and BPM.

An estimate, not ground truth — good for clear tonal tracks; the user can
override. Returns the tonic pitch class so transposition is exact regardless
of the estimated mode.
"""
from __future__ import annotations

from pathlib import Path

from .notes import key_name

# Krumhansl-Kessler key profiles (tonic at index 0).
_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def _corr(a, b) -> float:
    import numpy as np
    a = np.asarray(a, float) - np.mean(a)
    b = np.asarray(b, float) - np.mean(b)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(a.dot(b) / denom)


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
    profile = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)

    scored = []
    for tonic in range(12):
        for minor, prof in ((False, _MAJOR), (True, _MINOR)):
            scored.append((_corr(profile, np.roll(prof, tonic)), tonic, minor))
    scored.sort(reverse=True)
    score, tonic, minor = scored[0]
    margin = scored[0][0] - scored[1][0]

    return {
        "pitch_class": tonic,
        "minor": minor,
        "key": key_name(tonic, minor),
        "bpm": bpm,
        "score": round(score, 3),
        "confidence": "high" if margin > 0.06 else "medium" if margin > 0.02 else "low",
    }
