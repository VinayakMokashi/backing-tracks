"""Pitch-shift audio by N semitones without changing tempo (ffmpeg rubberband).

rubberband is a high-quality phase-vocoder; small shifts are clean, large
shifts (beyond ~5-6 semitones) start to smear — the caller should prefer the
shorter transposition direction.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import config


class PitchError(Exception):
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint


def shortest_shift(from_pc: int, to_pc: int) -> int:
    """Semitones from one pitch class to another, in [-6, +6]."""
    d = (to_pc - from_pc) % 12
    return d - 12 if d > 6 else d


def shift_semitones(in_path: Path, out_path: Path, semitones: float,
                    to_mp3: bool = False) -> Path:
    if abs(semitones) < 1e-6:
        # no shift: still transcode so callers get a consistent output file
        ratio = 1.0
    else:
        ratio = 2.0 ** (semitones / 12.0)

    # Keep the real extension on the temp file so ffmpeg infers the format.
    tmp = out_path.with_name(f"{out_path.stem}.part{out_path.suffix}")
    fmt = "mp3" if to_mp3 else "wav"
    cmd = [config.FFMPEG_EXE, "-y", "-i", str(in_path),
           "-af", f"rubberband=pitch={ratio:.6f}:pitchq=quality", "-f", fmt]
    if to_mp3:
        cmd += ["-codec:a", "libmp3lame", "-b:a", "192k"]
    cmd += [str(tmp)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=config.RENDER_TIMEOUT_S * 3)
    except subprocess.TimeoutExpired as exc:
        tmp.unlink(missing_ok=True)
        raise PitchError("Pitch-shift timed out.", "Try a shorter clip.") from exc
    if proc.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise PitchError(f"ffmpeg pitch-shift failed: {(proc.stderr or '')[-300:]}",
                         "Check the input audio file.")
    import os
    os.replace(tmp, out_path)
    return out_path
