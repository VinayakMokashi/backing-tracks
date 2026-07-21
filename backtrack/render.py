"""MIDI -> audio via the FluidSynth CLI (subprocess; no ctypes bindings).

Fast-render flags: -ni -T wav -F out.wav <soundfont> <midi>. Subprocess
isolation means a synth crash cannot take down the FastAPI process.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pretty_midi

import config


class RenderError(Exception):
    def __init__(self, message: str, hint: str):
        super().__init__(message)
        self.message = message
        self.hint = hint


@dataclass
class RenderResult:
    midi_path: Path
    wav_path: Path
    mp3_path: Path | None
    seconds: float


def _fluidsynth_cmd(mid_path: Path, wav_path: Path, soundfont: Path) -> list[str]:
    cmd = [str(config.FLUIDSYNTH_EXE), "-ni",
           "-g", str(config.GAIN), "-r", str(config.SAMPLE_RATE)]
    for key, value in config.FLUIDSYNTH_SETTINGS.items():
        cmd += ["-o", f"{key}={value}"]
    cmd += ["-T", "wav", "-F", str(wav_path), str(soundfont), str(mid_path)]
    return cmd


def plan_soundfont(pm: pretty_midi.PrettyMIDI) -> Path:
    """Pick the best SoundFont for what's in this arrangement, and remap
    programs when routing through a dedicated (non-GM) font.

    Solo piano  -> real Steinway;  solo guitar -> real guitar bank (programs
    remapped to its presets); anything mixed or with drums -> the GM bank so
    every instrument (incl. the count-in click) still sounds.
    """
    voiced = [i for i in pm.instruments if i.notes]
    names = {i.name for i in voiced}
    has_drums = any(i.is_drum for i in voiced)
    if names == {"Piano"} and config.PIANO_SOUNDFONT.exists():
        return config.PIANO_SOUNDFONT
    if names == {"Guitar"} and not has_drums and config.GUITAR_SOUNDFONT.exists():
        for inst in voiced:
            inst.program = config.GUITAR_SF_PROGRAMS.get(inst.program, 0)
        return config.GUITAR_SOUNDFONT
    return config.SOUNDFONT


def render(pm: pretty_midi.PrettyMIDI, song_id: str, ohash: str,
           soundfont: Path | None = None) -> RenderResult:
    if config.FLUIDSYNTH_EXE is None:
        raise RenderError(
            "fluidsynth.exe not found under tools/",
            "Run scripts/check_env.py for setup instructions.",
        )
    if soundfont is None:
        soundfont = plan_soundfont(pm)
    if not soundfont.exists():
        raise RenderError(
            f"SoundFont missing: {soundfont}",
            "Run scripts/check_env.py for setup instructions.",
        )

    out_dir = config.RENDERS_DIR / song_id
    out_dir.mkdir(parents=True, exist_ok=True)
    mid_path = out_dir / f"{ohash}.mid"
    wav_path = out_dir / f"{ohash}.wav"
    wav_tmp = out_dir / f"{ohash}.wav.part"

    started = time.monotonic()
    pm.write(str(mid_path))
    try:
        proc = subprocess.run(
            _fluidsynth_cmd(mid_path, wav_tmp, soundfont),
            capture_output=True, text=True, timeout=config.RENDER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        wav_tmp.unlink(missing_ok=True)
        raise RenderError(
            f"FluidSynth timed out after {config.RENDER_TIMEOUT_S}s",
            "The arrangement may be very long; raise RENDER_TIMEOUT_S in config.py.",
        ) from None
    if proc.returncode != 0 or not wav_tmp.exists():
        tail = (proc.stderr or proc.stdout or "").strip()[-500:]
        wav_tmp.unlink(missing_ok=True)
        raise RenderError(
            f"FluidSynth failed (exit {proc.returncode}): {tail}",
            "Run scripts/check_env.py to diagnose the audio toolchain.",
        )
    # Atomic promote: the final .wav name only ever exists complete, so the
    # API's exists() check doubles as a completeness check.
    os.replace(wav_tmp, wav_path)

    mp3_path = None
    if shutil.which(config.FFMPEG_EXE):
        candidate = out_dir / f"{ohash}.mp3"
        mp3_tmp = out_dir / f"{ohash}.mp3.part"
        try:
            ff = subprocess.run(
                [config.FFMPEG_EXE, "-y", "-i", str(wav_path), "-f", "mp3",
                 "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_tmp)],
                capture_output=True, text=True, timeout=config.RENDER_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            ff = None
        if ff is not None and ff.returncode == 0 and mp3_tmp.exists():
            os.replace(mp3_tmp, candidate)
            mp3_path = candidate  # MP3 is best-effort; WAV completes the core loop
        else:
            mp3_tmp.unlink(missing_ok=True)

    return RenderResult(
        midi_path=mid_path, wav_path=wav_path, mp3_path=mp3_path,
        seconds=round(time.monotonic() - started, 1),
    )


def check_environment() -> dict:
    fluidsynth_version = None
    if config.FLUIDSYNTH_EXE is not None:
        try:
            out = subprocess.run(
                [str(config.FLUIDSYNTH_EXE), "--version"],
                capture_output=True, text=True, timeout=10,
            )
            first = (out.stdout or "").splitlines()
            fluidsynth_version = first[0].strip() if first else None
        except (OSError, subprocess.TimeoutExpired):
            fluidsynth_version = None
    soundfont_ok = config.SOUNDFONT.exists()
    return {
        "fluidsynth": fluidsynth_version,
        "fluidsynth_path": str(config.FLUIDSYNTH_EXE) if config.FLUIDSYNTH_EXE else None,
        "soundfont": soundfont_ok,
        "ffmpeg": shutil.which(config.FFMPEG_EXE) is not None,
        "ok": fluidsynth_version is not None and soundfont_ok,
    }
