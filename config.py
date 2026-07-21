"""Central configuration: absolute paths and render settings.

Everything the app needs to find on disk is resolved here, once.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
SONGS_DIR = DATA_DIR / "songs"
RENDERS_DIR = DATA_DIR / "renders"
STATIC_DIR = PROJECT_ROOT / "static"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

_SF_DIR = PROJECT_ROOT / "assets" / "soundfonts"
SOUNDFONT = _SF_DIR / "GeneralUser-GS.sf2"          # General MIDI (mixed / drums / fallback)
PIANO_SOUNDFONT = _SF_DIR / "Abbey-Steinway-D.sf2"  # real-sampled Steinway (solo piano)
GUITAR_SOUNDFONT = _SF_DIR / "Nylon-Steel-Guitars.sf2"  # real-sampled guitars (solo guitar)

# The dedicated guitar font isn't GM-mapped, so remap GM programs to its presets:
# 24 (nylon) -> 0 "Nylon Pro Guitar", 25 (steel) -> 3 "Steel Guitar".
GUITAR_SF_PROGRAMS = {24: 0, 25: 3}


def _find_fluidsynth() -> Path | None:
    hits = sorted((PROJECT_ROOT / "tools").glob("**/fluidsynth.exe"))
    return hits[0] if hits else None


FLUIDSYNTH_EXE = _find_fluidsynth()


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


FFMPEG_EXE = _find_ffmpeg()  # MP3 output is optional

SAMPLE_RATE = 44100
# Explicit gain: fast-render can clip at the default on dense arrangements
# (FluidSynth issue #219).
GAIN = 0.6
RENDER_TIMEOUT_S = 120

# Chorus OFF — it adds the detuned synthetic "shimmer" that reads as cheap MIDI
# on a solo instrument. Gentle reverb only, and high polyphony so a sustained
# piano (pedal + release/resonance samples) never drops voices. These settings
# are what let the real-sampled fonts actually sound natural.
FLUIDSYNTH_SETTINGS = {
    "synth.chorus.active": "0",
    "synth.reverb.active": "1",
    "synth.reverb.damp": "0.3",
    "synth.reverb.level": "0.5",
    "synth.reverb.room-size": "0.6",
    "synth.reverb.width": "0.8",
    "synth.polyphony": "512",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Some sites (especially Instagram) require you to be logged in to download.
# If a link fails with a login/private error, set COOKIES_FROM_BROWSER to the
# browser you're logged into that site in — yt-dlp reuses those cookies.
# e.g. "chrome", "edge", "firefox", "brave". Or export a cookies.txt and point
# COOKIES_FILE at it. Leave both None for anonymous (YouTube usually works).
COOKIES_FROM_BROWSER: str | None = None
COOKIES_FILE: str | None = None
FETCH_MIN_INTERVAL_S = 1.0  # politeness: at most one outbound fetch per second

# Optional GetSongBPM auto-tempo lookup (getsongbpm.com/api). Best-effort only:
# register a free key + place the required backlink (see README). Leave None to
# skip the lookup entirely — style defaults still fill in the tempo.
GETSONGBPM_API_KEY: str | None = None
GETSONGBPM_TIMEOUT_S = 2.0

HOST = "127.0.0.1"
PORT = 8765

# Timing inference: how many characters of chord-over-lyric width map to one
# bar. Lower = more bars per line (chords change faster). This is the main knob
# for how well durations track a song's real harmonic rhythm; tune to taste.
CHARS_PER_BAR = 20


def ensure_dirs() -> None:
    for d in (CACHE_DIR, SONGS_DIR, RENDERS_DIR):
        d.mkdir(parents=True, exist_ok=True)
