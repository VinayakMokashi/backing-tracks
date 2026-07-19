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

SOUNDFONT = PROJECT_ROOT / "assets" / "soundfonts" / "GeneralUser-GS.sf2"


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

# GeneralUser GS author's recommended FluidSynth reverb/chorus settings.
FLUIDSYNTH_SETTINGS = {
    "synth.reverb.damp": "0.3",
    "synth.reverb.level": "0.7",
    "synth.reverb.room-size": "0.5",
    "synth.reverb.width": "0.8",
    "synth.chorus.depth": "3.6",
    "synth.chorus.level": "0.55",
    "synth.chorus.nr": "4",
    "synth.chorus.speed": "0.36",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
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
