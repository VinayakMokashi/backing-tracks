"""Verify the audio toolchain and print fix instructions for anything missing.

Run:  .venv\\Scripts\\python.exe scripts\\check_env.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402

FLUIDSYNTH_URL = ("https://github.com/FluidSynth/fluidsynth/releases/download/"
                  "v2.5.6/fluidsynth-v2.5.6-win10-x64-cpp11.zip")
SOUNDFONT_URL = ("https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/"
                 "main/GeneralUser-GS.sf2")


def report(label: str, ok: bool, detail: str, fix: str = "") -> bool:
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}: {detail}")
    if not ok and fix:
        print(f"         fix: {fix}")
    return ok


def main() -> int:
    print("Backing Tracks environment check\n")
    all_ok = True

    py = sys.version_info
    all_ok &= report(
        "Python", py[:2] == (3, 12), f"{py.major}.{py.minor}.{py.micro}",
        "Use Python 3.12 (py -3.12 -m venv .venv) — the project pins it.",
    )

    try:
        import fastapi, pretty_midi, pychord, requests, bs4  # noqa: F401
        all_ok &= report("Python deps", True, "fastapi, pretty_midi, pychord, requests, bs4")
    except ImportError as exc:
        all_ok &= report("Python deps", False, str(exc),
                         ".venv\\Scripts\\python.exe -m pip install -r requirements.txt")
        print("\nResult: FAIL")
        return 1

    from backtrack.render import check_environment  # noqa: E402
    env = check_environment()
    all_ok &= report(
        "FluidSynth", env["fluidsynth"] is not None,
        env["fluidsynth"] or "fluidsynth.exe not found under tools/",
        f"Download {FLUIDSYNTH_URL} and extract into tools\\fluidsynth\\",
    )
    all_ok &= report(
        "SoundFont", env["soundfont"], str(config.SOUNDFONT),
        f"Download {SOUNDFONT_URL} into assets\\soundfonts\\",
    )
    report(
        "ffmpeg (optional)", env["ffmpeg"],
        "found on PATH" if env["ffmpeg"] else "not found — MP3 downloads disabled, WAV still works",
        "winget install -e --id Gyan.FFmpeg",
    )

    print(f"\nResult: {'ALL GREEN' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
