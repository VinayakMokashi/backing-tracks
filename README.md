# Backing Tracks

Personal local web app that turns a song's chord chart into a transposable
piano/guitar backing track: chords in → multi-track MIDI → SoundFont-rendered
audio in the browser, with MIDI/WAV downloads.

Full design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Setup (Windows 11)

1. **Python 3.12** — `py -3.12 -m venv .venv`, then
   `.venv\Scripts\python.exe -m pip install -r requirements.txt`
2. **FluidSynth 2.5.6** — download
   [fluidsynth-v2.5.6-win10-x64-cpp11.zip](https://github.com/FluidSynth/fluidsynth/releases/download/v2.5.6/fluidsynth-v2.5.6-win10-x64-cpp11.zip)
   and extract into `tools\fluidsynth\` (if the cpp11 build misbehaves, use the
   `-glib` flavor from the same release page).
3. **SoundFont** — download
   [GeneralUser-GS.sf2](https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2)
   into `assets\soundfonts\` (free for any use; we host our own copy per its
   license — see the [GeneralUser GS project](https://github.com/mrbumpy409/GeneralUser-GS)).
4. **ffmpeg** (optional, enables MP3 downloads) —
   `winget install -e --id Gyan.FFmpeg`
5. Verify: `.venv\Scripts\python.exe scripts\check_env.py` → ALL GREEN
6. Offline sound check: `.venv\Scripts\python.exe scripts\smoke_render.py`

## Run

Double-click `run.bat` (or `.venv\Scripts\python.exe run.py`) — opens
http://127.0.0.1:8765/

## Notes

- Chord sheets are fetched once per song, cached locally in `data/cache/`,
  rate-limited to 1 request/second, and never republished. Personal use only.
- Tempo auto-fill (planned) is provided by [GetSongBPM.com](https://getsongbpm.com).
