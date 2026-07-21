# Key Shifter 🎚️

Turn any **YouTube or Instagram** track into a **karaoke backing track in your
key and at your speed** — vocals removed, ready to sing over.

Paste a link, and the app:

1. **Downloads** the audio,
2. **Removes the vocals** (Demucs AI) → leaves the instrumental,
3. **Detects the key and BPM**,
4. **Pitch-shifts it into the key you sing in** and **stretches it to the speed
   you want** — pitch and tempo are independent, and the tempo change doesn't
   affect the pitch (or vice-versa).

Because it starts from the real recording, the backing track actually *sounds*
like the song — it isn't instruments re-synthesized from chords.

---

## Quick start (Windows 11)

```powershell
# 1. Python 3.12 + dependencies
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. ffmpeg (required — used for download + pitch/tempo)
winget install -e --id Gyan.FFmpeg

# 3. Check everything is in place
.venv\Scripts\python.exe scripts\check_env.py   # -> ALL GREEN

# 4. Run it (opens http://127.0.0.1:8765)
run.bat
```

> The **first** time you remove vocals, Demucs downloads its AI model
> (a few hundred MB, one time). After that it's cached.

---

## Using it

1. **Paste a link** (YouTube or Instagram) and click **Analyze**.
   - "Remove vocals" is on by default. Uncheck it if the video is *already* an
     instrumental/karaoke track (saves the slow separation step).
   - This step is the slow one: download + vocal removal + analysis takes a few
     minutes on CPU. The status line tells you what stage it's on.
2. It shows the **detected key** (with a confidence badge) and the **estimated
   BPM**.
3. Pick **the key you sing in** and, optionally, drag the **Speed** slider
   (50–150%). The resulting BPM updates live.
4. Click **Create my track** → the shifted/stretched MP3 plays inline and there's
   a **Download** link.

Re-picking a different key or speed for the same link is instant — the download
and vocal removal are cached per link.

### Instagram links need a login

Instagram usually requires you to be logged in to download. If a reel fails with
a login/private error, open **`config.py`** and set:

```python
COOKIES_FROM_BROWSER = "chrome"   # or "edge", "firefox", "brave" — whatever
                                  # browser you're logged into Instagram in
```

yt-dlp then reuses your existing Instagram session. YouTube works without this.

---

## How it works (under the hood)

| Stage | Tool | Notes |
|---|---|---|
| Download | [yt-dlp](https://github.com/yt-dlp/yt-dlp) + ffmpeg | Extracts audio to WAV; supports YouTube, Instagram, and many more sites |
| Vocal removal | [Demucs](https://github.com/adefossez/demucs) (`htdemucs`, two-stem) | Runs on CPU; keeps the "no-vocals" stem |
| Key detection | [librosa](https://librosa.org) | Chroma + Krumhansl–Schmuckler profiles → tonic + major/minor |
| BPM estimate | librosa | Best-effort tempo estimate (shown as a reference) |
| Pitch + tempo | ffmpeg **rubberband** filter | One pass; pitch and tempo are independent, tempo-preserving pitch shift |

Transposition always takes the **shorter direction** (≤ 6 semitones) so the
audio stays clean.

---

## Project structure

```
config.py             # paths, ffmpeg location, cookies, timeouts
run.py / run.bat      # launch the server + open the browser
requirements.txt
keyshift/
  api.py              # FastAPI app — endpoints only
  pipeline.py         # orchestration: analyze() + transpose()
  download.py         # yt-dlp -> WAV
  separate.py         # Demucs vocal removal
  keydetect.py        # librosa key + BPM
  pitch.py            # ffmpeg rubberband pitch/tempo
  notes.py            # note-name / pitch-class helpers
static/               # single-page UI (index.html, app.js, style.css)
scripts/check_env.py  # environment check
tests/                # pure-logic tests (notes, shifts)
data/                 # per-track working folders (gitignored)
```

The pipeline is a plain library — every module works without the web server, so
you can script it too:

```python
from keyshift import pipeline
meta = pipeline.analyze("https://youtu.be/...", remove_vocals=True)
result = pipeline.transpose(meta["id"], target_pc=7, tempo_pct=90)  # 7 = G
print(result["audio_url"])
```

---

## Tests

```powershell
.venv\Scripts\python.exe -m pytest
```

Covers the pure logic (note parsing, key spelling, shortest-shift). The audio
stages are validated by running the app on real links.

---

## Honest limitations

- **Vocal removal is very good but not perfect** — some tracks leave faint vocal
  "ghosts." Demucs is the same tech the paid tools use, so this is about as good
  as free/local gets.
- **Key and BPM are estimates** — best on clear, full-arrangement tracks. If the
  detected key is wrong, just pick your target relative to the key you *know* the
  song is in.
- **Big pitch shifts smear** — beyond ~5–6 semitones you'll hear artifacts; the
  app already takes the shorter direction to minimise this.
- **CPU speed** — vocal removal is a few minutes per song. A CUDA GPU would be
  much faster, but the default install is CPU-only for simplicity.

## Notes on use

Personal-practice tool: you supply the link, the audio stays local on your
machine, and nothing is redistributed. Downloading is subject to the source
site's terms.
