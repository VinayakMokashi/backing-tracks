# Backing Tracks

Personal local web app that turns a song's chord chart into a transposable
piano/guitar backing track: chords in → multi-track MIDI → SoundFont-rendered
audio in the browser, with MIDI/WAV/MP3 downloads.

Enter a song name (or an Ultimate Guitar / CifraClub URL, or paste a chart) →
it fetches and parses the chords → generates guitar strumming + piano
accompaniment (+ optional drums) → renders audio you can play and download,
in any key.

Full design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Setup (Windows 11)

1. **Python 3.12** — `py -3.12 -m venv .venv`, then
   `.venv\Scripts\python.exe -m pip install -r requirements.txt`
2. **FluidSynth 2.5.6** — download
   [fluidsynth-v2.5.6-win10-x64-cpp11.zip](https://github.com/FluidSynth/fluidsynth/releases/download/v2.5.6/fluidsynth-v2.5.6-win10-x64-cpp11.zip)
   and extract into `tools\fluidsynth\` (if the cpp11 build misbehaves, use the
   `-glib` flavor from the same release page).
3. **SoundFonts** — download into `assets\soundfonts\`:
   - [GeneralUser-GS.sf2](https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2)
     — General MIDI bank, used for mixed/drum renders and as fallback.
   - **Real piano** (solo-piano renders): [Abbey-Steinway-D-v1.9.sf2](https://huggingface.co/datasets/projectlosangeles/soundfonts4u/resolve/main/Abbey-Steinway-D-v1.9.sf2)
     → save as `Abbey-Steinway-D.sf2` (a real Steinway sampled in a church; ~40 MB).
   - **Real guitar** (solo-guitar renders): [Nylon and Steeel Guitars-4U-v2.sf2](https://huggingface.co/datasets/projectlosangeles/soundfonts4u/resolve/main/Nylon%20and%20Steeel%20Guitars-4U-v2.sf2)
     → save as `Nylon-Steel-Guitars.sf2` (~37 MB).

   The dedicated piano/guitar fonts are what make solo renders sound natural
   rather than "MIDI"; the app falls back to GeneralUser GS if they're absent.
4. **ffmpeg** (optional, enables MP3 downloads) —
   `winget install -e --id Gyan.FFmpeg`
5. Verify: `.venv\Scripts\python.exe scripts\check_env.py` → ALL GREEN
6. Offline sound check: `.venv\Scripts\python.exe scripts\smoke_render.py`

## Run

Double-click `run.bat` (or `.venv\Scripts\python.exe run.py`) — opens
http://127.0.0.1:8765/

## Using it

1. **Find** — type a song name to search Ultimate Guitar, or paste a chords URL,
   or click *Paste chords instead* to paste a chart. Previously loaded songs are
   in the *Saved songs* dropdown.
2. **Song panel** — fix the style, tempo, time signature, or capo if the parse
   guessed wrong (chord durations use a one-chord-per-bar heuristic you can
   refine). Changes save automatically.
3. **Arrangement** — pick the key you want to sing in (or nudge with the
   transpose stepper), choose how the capo is handled, toggle guitar/piano/drums
   and the guitar tone, then **Generate**.
4. **Play & download** — the player streams WAV; download MIDI, WAV, or MP3.
   The chord sheet below transposes with the key so what you see matches what you
   hear.

### Capo handling

- **Keep shapes** — keeps the written chord shapes and moves the capo (best for
  playing along; the sheet shows shapes + a capo badge).
- **Auto-capo** — picks the capo that turns the most chords into easy open
  shapes.
- **No capo** — transposes the actual shapes, no capo.

## Tests

`.venv\Scripts\python.exe -m pytest` — offline suite (chords, parser, arranger,
auto-capo, pruning). No network needed.

## Notes

- Chord sheets are fetched once per song, cached locally in `data/cache/`,
  rate-limited to 1 request/second, and never republished. Personal use only.
- Optional auto-tempo lookup via [GetSongBPM.com](https://getsongbpm.com): set
  `GETSONGBPM_API_KEY` in `config.py` (free key) — a visible backlink to
  GetSongBPM.com is required by their terms, which is why the link is here.
