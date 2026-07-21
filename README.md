# Backing Track — Key Shifter

Paste a YouTube link and get the **backing track** (vocals removed) shifted into
**your** key to sing over. It downloads the audio, removes the vocals, estimates
the key, and pitch-shifts it — without changing tempo. Because it starts from the
real recording, it actually *sounds* like the track.

## How it works

1. **Paste a link** → the app downloads the audio (yt-dlp).
2. **Removes the vocals** (Demucs AI) → leaves the instrumental backing track.
   Slow on CPU (a few minutes/song; first run also downloads the model). Uncheck
   "Remove vocals" if the video is already an instrumental/karaoke track.
3. **Detects the key** and tells you (an estimate — correct it if it's off).
4. **Pick the key you sing in** → it pitch-shifts (ffmpeg's rubberband, high
   quality, tempo preserved) and gives you an MP3 to play and download.

Small shifts stay clean; it always takes the shorter direction (≤ 6 semitones).
Vocal removal is very good but not perfect — some tracks leave faint ghosts.

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
