"""Pitch-shift and time-stretch audio with ffmpeg's rubberband filter.

Pitch and tempo are independent: changing one never affects the other. Small
shifts are clean; large shifts (beyond ~5-6 semitones) start to smear, so
callers prefer the shorter transposition direction.
"""
from __future__ import annotations

import os
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


def transform(in_path: Path, out_path: Path, semitones: float = 0.0,
              tempo: float = 1.0, to_mp3: bool = False) -> Path:
    """Pitch-shift by `semitones` and/or time-stretch by `tempo` (1.0 = original
    speed, 1.1 = 10% faster) in a single rubberband pass."""
    pitch_ratio = 2.0 ** (semitones / 12.0) if abs(semitones) > 1e-6 else 1.0
    tempo_ratio = tempo if abs(tempo - 1.0) > 1e-6 else 1.0

    # Keep the real extension on the temp file so ffmpeg infers the format.
    tmp = out_path.with_name(f"{out_path.stem}.part{out_path.suffix}")
    fmt = "mp3" if to_mp3 else "wav"
    af = f"rubberband=pitch={pitch_ratio:.6f}:tempo={tempo_ratio:.6f}:pitchq=quality"
    cmd = [config.FFMPEG_EXE, "-y", "-i", str(in_path), "-af", af, "-f", fmt]
    if to_mp3:
        cmd += ["-codec:a", "libmp3lame", "-b:a", "192k"]
    cmd += [str(tmp)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=config.PROCESS_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        tmp.unlink(missing_ok=True)
        raise PitchError("Audio transform timed out.", "Try a shorter clip.") from exc
    if proc.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise PitchError(f"ffmpeg transform failed: {(proc.stderr or '')[-300:]}",
                         "Check the input audio file.")
    os.replace(tmp, out_path)
    return out_path
