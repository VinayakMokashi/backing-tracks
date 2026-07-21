"""Vocal removal via Demucs (two-stem: vocals vs. everything else).

Runs the Demucs CLI on CPU and returns the vocals-removed ("no_vocals") stem.
First run downloads the model (a few hundred MB); later runs skip that.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class SeparateError(Exception):
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint


def separate_instrumental(in_wav: Path, work_dir: Path) -> Path:
    """Split `in_wav` into vocals / no-vocals; return the no-vocals WAV path."""
    work_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "demucs", "--two-stems", "vocals",
           "-d", "cpu", "-o", str(work_dir), str(in_wav)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired as exc:
        raise SeparateError("Vocal removal timed out.",
                            "Try a shorter clip.") from exc
    if proc.returncode != 0:
        raise SeparateError(
            f"Vocal removal failed: {(proc.stderr or proc.stdout or '')[-400:]}",
            "Make sure Demucs installed (pip install demucs).",
        )
    hits = list(work_dir.glob("**/no_vocals.*"))
    if not hits:
        raise SeparateError("Vocal removal produced no output stem.", "")
    return hits[0]
