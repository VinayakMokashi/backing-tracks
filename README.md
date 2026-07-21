# Backing Track — Key Shifter

Paste a YouTube link (an instrumental / karaoke / backing-track video), and get
that **real audio** shifted into **your** key to sing over. It downloads the
audio, estimates its musical key, and pitch-shifts it — without changing tempo.

Because it uses the real recording's audio, it actually *sounds* like the track
(unlike generating instruments from chords). It transposes whatever is in the
video — it does **not** remove vocals, so pick an instrumental/karaoke video if
you want a clean bed.

## How it works

1. **Paste a link** → the app downloads the audio (yt-dlp).
2. **It detects the key** and tells you (an estimate — correct it if it's off).
3. **Pick the key you sing in** → it pitch-shifts the audio (ffmpeg's rubberband,
   high quality, tempo preserved) and gives you an MP3 to play and download.

Small shifts stay clean; it always takes the shorter direction (≤ 6 semitones).

## Setup (Windows 11)

1. **Python 3.12** — `py -3.12 -m venv .venv`, then
   `.venv\Scripts\python.exe -m pip install -r requirements.txt`
2. **ffmpeg** (required — download + pitch-shift both use it) —
   `winget install -e --id Gyan.FFmpeg`
3. Run: double-click `run.bat` (or `.venv\Scripts\python.exe run.py`) — opens
   http://127.0.0.1:8765/

## Tests

`.venv\Scripts\python.exe -m pytest`

## Notes

- Personal-practice tool: you supply the link, the audio stays local, nothing is
  redistributed. Downloading is subject to the source site's terms.
- Key detection is automatic and best on clear, full-arrangement tracks; you can
  always pick a different target key by ear.

---

### Legacy: chord → MIDI backing-track generator

The earlier approach (scrape chords from Ultimate Guitar → generate guitar/piano
MIDI → render with SoundFonts) still lives in `backtrack/` (arrange, sources,
sheet_parser, render) and its tests. It was set aside because generated MIDI
can't sound like a real recording; the key-shifter above is the current app.
See `docs/ARCHITECTURE.md` for that design.
