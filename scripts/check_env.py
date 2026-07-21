"""Verify the environment for the Key Shifter and print fixes for anything missing.

Run:  .venv\\Scripts\\python.exe scripts\\check_env.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402


def report(label: str, ok: bool, detail: str, fix: str = "") -> bool:
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}: {detail}")
    if not ok and fix:
        print(f"         fix: {fix}")
    return ok


def importable(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    print("Key Shifter environment check\n")
    ok = True

    py = sys.version_info
    ok &= report("Python", py[:2] == (3, 12), f"{py.major}.{py.minor}.{py.micro}",
                 "Use Python 3.12 (py -3.12 -m venv .venv).")

    for mod, pkg in [("fastapi", "fastapi"), ("uvicorn", "uvicorn"),
                     ("yt_dlp", "yt-dlp"), ("librosa", "librosa"),
                     ("soundfile", "soundfile"), ("demucs", "demucs")]:
        ok &= report(mod, importable(mod), "installed" if importable(mod) else "missing",
                     f".venv\\Scripts\\python.exe -m pip install {pkg}")

    ffmpeg_ok = shutil.which(config.FFMPEG_EXE) is not None or Path(config.FFMPEG_EXE).exists()
    ok &= report("ffmpeg", ffmpeg_ok, config.FFMPEG_EXE if ffmpeg_ok else "not found",
                 "winget install -e --id Gyan.FFmpeg")

    print(f"\nResult: {'ALL GREEN' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
