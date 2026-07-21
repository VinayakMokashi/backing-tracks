"""Central configuration: paths, external tools, and settings."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR = PROJECT_ROOT / "data"
AUDIO_DIR = DATA_DIR / "audio"          # per-track working folders (gitignored)
STATIC_DIR = PROJECT_ROOT / "static"


def _find_ffmpeg() -> str:
    """PATH first; fall back to winget's install dir (PATH updates don't reach
    already-running shells)."""
    import os
    import shutil

    if shutil.which("ffmpeg"):
        return "ffmpeg"
    packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if packages.exists():
        hits = sorted(packages.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"))
        if hits:
            return str(hits[0])
    return "ffmpeg"


FFMPEG_EXE = _find_ffmpeg()             # used for download extraction + pitch/tempo

# Downloads, vocal removal, and pitch/tempo can each take minutes on CPU.
PROCESS_TIMEOUT_S = 3600

# Some sites (especially Instagram) require you to be logged in to download.
# If a link fails with a login/private error, set COOKIES_FROM_BROWSER to the
# browser you're logged into that site in — yt-dlp reuses those cookies.
# e.g. "chrome", "edge", "firefox", "brave". Or point COOKIES_FILE at an
# exported cookies.txt. Leave both None for anonymous (YouTube usually works).
COOKIES_FROM_BROWSER: str | None = None
COOKIES_FILE: str | None = None

HOST = "127.0.0.1"
PORT = 8765


def ensure_dirs() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
