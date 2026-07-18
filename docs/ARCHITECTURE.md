# Backing-Track Generator — Final Architecture (v1.0, decided)

Personal-use local web app for one musician: song name (or chord-page URL, or pasted chart) in → transposable guitar/piano backing track out (multi-track MIDI + SoundFont-rendered audio). Python 3.12 + FastAPI backend, vanilla HTML/JS frontend, Windows 11, no Docker, no DB, no job queue. All library/site facts reflect the July 2026 verified research.

**Divergence resolutions** (where proposals A and B differed; one-line tiebreaks):

1. Layout: single `backtrack/` package (B) plus A's `tests/fixtures` — one importable namespace, cleaner than five top-level packages.
2. Launcher: `run.py` + one-line `run.bat` wrapper — cross-platform command *and* double-clickable, costs one line.
3. Search is `GET /api/search?q=` (A) — idempotent read, simpler than B's POST.
4. No auto-pick of the top search result (A); B's `{"query"}` shortcut dropped — user-generated chord data demands human confirmation.
5. Song edits via `PATCH` (A) — partial-update semantics match the field-by-field UI.
6. Render outputs keyed by `options_hash` per song (A) with B's pruning policy — flipping back to a previously heard key is instant.
7. `capo_mode: "keep"|"auto"|"none"` enum (B) over A's `auto_capo` bool — richer control at zero cost; default `"keep"` until auto-capo ships (M6), then flip default to `"auto"`.
8. music21 dropped entirely (B) — the regex + triad-fallback path already guarantees no crash; a heavyweight dep buys marginal parse coverage.
9. Player streams **WAV** (A); MP3 is an optional download when ffmpeg is present — keeps ffmpeg out of the core loop.
10. `GET /api/health`, `scripts/check_env.py`, `scripts/smoke_render.py` adopted (B) — cheap, front-loaded de-risking of the binary toolchain.
11. `Song.style` persisted (A) *and* `Song.applicature` persisted (B) — both are cheap and useful.
12. Error contract: A's snake_case codes with B's `hint` field — the hint drives the recovery UI.
13. Milestones: A's ordering (transposition proven before the arranger; search early) with B's guitar/piano engine split — finer testable checkpoints on the musically hard part.

---

## 1. Tech Stack

| Component | Choice | Justification |
|---|---|---|
| Python | **3.12** (pin) | All chosen libs verified on it; avoids the pydub/audioop 3.13 trap and mido's unlisted 3.14; security-supported to Oct 2028. |
| Web framework | **FastAPI + uvicorn** | Approved constraint; sync (`def`) endpoints run in the threadpool, absorbing the 5–25 s render without a job queue. |
| HTTP fetching | **requests + beautifulsoup4** | Exactly what actively-maintained freetar (pushed 2026-05-31) uses against UG's `js-store`; a Chrome desktop UA suffices as of July 2026. |
| Chord parse/transpose | **pychord ≥1.4.0** (2026-04-29) | Small, maintained, MIT; covers maj7/m7b5/sus/7sus4/add9/69/slash chords with built-in semitone transpose. Own regex fallback for anything it rejects; no music21. |
| MIDI writing | **pretty_midi ≥0.2.11** (pin strictly) | Seconds-based API makes 12–18 ms strum staggers and CC64 pedal timing trivial; single fixed tempo per render so its weak tempo-map authoring is irrelevant; 0.2.11 fixed Py3.12 `pkg_resources` breakage. |
| Audio synthesis | **FluidSynth 2.5.6 CLI via `subprocess`** | Official GitHub `win10-x64` zip (no winget package exists; Chocolatey lags at 2.4.7). Fast-render (`-ni -T wav -F`) avoids pyFluidSynth's fragile DLL discovery; a synth crash can't kill FastAPI. |
| SoundFont | **GeneralUser GS v2.0.3** (~31 MB) | Actively maintained (Feb 2026), free for any use, explicitly tuned for FluidSynth 2.4+; better-balanced guitars than the 141 MB unmaintained FluidR3_GM (kept only as an optional "big piano" alternative). Self-hosted copy, never hotlinked, per its license. |
| MP3 encode (optional) | **ffmpeg via `subprocess`** (`winget install -e --id Gyan.FFmpeg`) | pydub is dead and broken on 3.13+; direct ffmpeg is one `subprocess.run` line. WAV alone completes the core loop. |
| BPM autofill (optional) | **GetSongBPM API** (`api.getsong.co`, free key) | Verified live free API; best-effort with 2 s timeout, silent fallback, never blocks generation; mandatory backlink placed in README + About. |
| Frontend | **Vanilla HTML/CSS/JS, zero libraries, no build step** | Approved constraint; `fetch()` + `<audio controls>` covers everything. html-midi-player rejected: CDN + Google-hosted soundfonts break offline use and sound worse than the server render. |
| Storage | **JSON + media files on disk** | Single user; `data/` folders are the database. |

**Deliberately rejected:** mingus, MIDIUtil, chords2midi, midi2audio (all dead — but chords2midi's pattern-preset/humanize *ideas* are copied), pyFluidSynth (DLL fragility), pydub (dead), music21 (heavyweight), mido as primary writer (tick math buys nothing here), React, websockets/job queues/DB/Docker.

---

## 2. Project Layout

```
backing-tracks/
├── run.py                      # uvicorn launcher → http://127.0.0.1:8765
├── run.bat                     # one line: python run.py  (double-clickable)
├── requirements.txt            # pinned: fastapi, uvicorn, requests, beautifulsoup4,
│                               #         pychord>=1.4.0, pretty_midi>=0.2.11
├── config.py                   # absolute paths: FLUIDSYNTH_EXE, SOUNDFONT, FFMPEG, DATA_DIR;
│                               # gain, sample rate, UA string, style defaults
├── README.md                   # Windows setup (FluidSynth zip, sf2 download), GetSongBPM backlink
│
├── backtrack/                  # the Python package — every module importable without the server
│   ├── __init__.py
│   ├── api.py                  # FastAPI app: endpoints only, zero business logic
│   ├── model.py                # Song / Section / ChordEvent / RenderOptions / ParsedChord (+ JSON I/O)
│   ├── chords.py               # normalize, parse_symbol, transpose_symbol, enharmonic spelling
│   ├── sheet_parser.py         # RawSheet (UG content / CifraClub / pasted text) → Song
│   ├── tempo.py                # BPM chain: UG strummings → GetSongBPM (2 s timeout) → style default
│   ├── store.py                # ALL disk persistence: fetch cache (URL-hash), song JSONs,
│   │                           # render outputs (options_hash), 1 req/s rate limiter, prune policy
│   │
│   ├── sources/
│   │   ├── __init__.py         # dispatcher: search(query) / get_sheet(url); domain registry
│   │   ├── ultimate_guitar.py  # js-store fetch+parse + search.php (~80 lines, freetar-style)
│   │   └── cifraclub.py        # fallback: data-chord-name attrs + Brazilian-notation map  (M6)
│   │
│   ├── arrange/
│   │   ├── __init__.py         # arrange(song, opts) -> pretty_midi.PrettyMIDI  (the one seam)
│   │   ├── patterns.py         # DATA ONLY: strum/piano/drum tables + STYLES registry
│   │   ├── voicings.py         # guitar open-chord dict, E/A barre formulas, slash-bass, quality→intervals
│   │   ├── guitar.py           # strum engine: stagger, up/down, chucks, capo offset, humanize
│   │   ├── piano.py            # comping engine: nearest-inversion voice-leading, LH/RH, CC64
│   │   └── drums.py            # optional channel-index-9 track, section crashes  (M6)
│   │
│   └── render.py               # pm.write → fluidsynth subprocess → optional ffmpeg; timeouts
│
├── static/
│   ├── index.html              # the single page
│   ├── app.js                  # all frontend logic, plain fetch(), ~300 lines
│   └── style.css
│
├── assets/
│   └── soundfonts/GeneralUser-GS.sf2    # gitignored; README says where to get it
│
├── data/                       # gitignored; created on first run
│   ├── cache/                  # raw fetched sheets: <sha1(url)>.json   (fetch once, ever)
│   ├── songs/                  # song models: <song_id>.json  (user edits persist here)
│   └── renders/<song_id>/      # <options_hash>.mid / .wav / .mp3
│
├── scripts/
│   ├── check_env.py            # verifies fluidsynth.exe / ffmpeg / sf2 exist & run; prints fixes
│   └── smoke_render.py         # C–Am–F–G → MIDI → WAV, no network, no server
│
└── tests/
    ├── fixtures/               # saved js-store JSON (Wonderwall, Let It Be, capo-less, slash-heavy)
    ├── test_parser.py          # sections, preamble skip, [tab] blocks, bar heuristic
    ├── test_chords.py          # normalization, transposition, spelling, edge-case symbols
    └── test_arranger.py        # MIDI note-count/timing/voice-leading sanity (offline)
```

**Maintainability rule:** `patterns.py` and `voicings.py` are pure data + tiny helpers — the musician-developer's tuning surface. Engines read that data and never hardcode musical constants.

---

## 3. Core Data Model

Chords are stored **as written symbols** (shape chords when capo > 0); only root and slash-bass pitch classes are ever transposed, so quality text survives losslessly. Beats are in time-signature-denominator units. `bpm` is **always quarter-note BPM** (MIDI `set_tempo` semantics) — the UI converts for 6/8. `RenderOptions` never mutates the saved Song.

```python
# backtrack/model.py
from dataclasses import dataclass, field, asdict

@dataclass
class ChordEvent:
    symbol: str                 # verbatim chart symbol: 'Am7', 'D/F#', 'C69', 'N.C.'
    beat: float                 # onset from section start, in denominator beat units
    duration_beats: float       # parser default: one bar; user-editable

@dataclass
class Section:
    name: str                   # 'Intro', 'Verse 1', 'Chorus', ...
    chords: list[ChordEvent] = field(default_factory=list)
    bars: int = 0
    repeat: int = 1

@dataclass
class Song:
    id: str                     # slug; filename in data/songs/ and folder in data/renders/
    title: str
    artist: str = ''
    sections: list[Section] = field(default_factory=list)
    bpm: float = 100.0          # ALWAYS quarter-note BPM
    time_signature: tuple[int, int] = (4, 4)     # list in JSON, tuple restored on load
    key: str = 'C'              # SHAPE key as printed; sounding key = key + capo
    capo: int = 0               # semitones (UG meta.get('capo', 0) — key ABSENT when no capo!)
    style: str = 'pop'          # persisted default: pop|folk|ballad|muted_pop|waltz|six_eight
    sheet_text: str = ''        # cleaned chord-over-lyric text for display
    applicature: dict | None = None   # UG per-chord voicings (MIDI note lists) when available
    source_url: str | None = None

@dataclass
class RenderOptions:            # per-render knobs, applied at arrange time only
    transpose: int = 0          # semitones vs. original SOUNDING key
    guitar: bool = True
    piano: bool = True
    drums: bool = False
    style: str | None = None    # override Song.style
    bpm: float | None = None    # override Song.bpm
    guitar_program: int = 25    # GM byte (0-indexed!): 25 steel (default), 24 nylon
    capo_mode: str = 'keep'     # 'keep' | 'auto' | 'none'   (default flips to 'auto' once M6 ships)

@dataclass
class ParsedChord:              # produced by chords.parse_symbol, consumed by arrangers
    root_pc: int                # 0–11
    quality: str                # opaque text: '', 'm', 'm7', 'sus4', 'm7b5', ...
    bass_pc: int | None = None  # slash bass
    is_rest: bool = False       # 'N.C.'

def options_hash(song: Song, opts: RenderOptions) -> str:
    """sha1 of (song content + resolved opts) → render cache key.
    Hash hit skips arrange AND render — previously heard keys replay instantly."""
```

Serialization: `asdict()` → JSON on disk; small `song_from_dict()` restores tuples. Pydantic models in `api.py` mirror these at the HTTP boundary only.

**Chord-symbol regex** (single source of truth in `chords.py`):
`^([A-G][#b]?)([^/]*)(?:/([A-G][#b]?))?$` → `(root, quality_verbatim, bass)`.
Quality maps to intervals **only at voicing time** (table in `voicings.py`):
`{'':[0,4,7],'m':[0,3,7],'7':[0,4,7,10],'maj7':[0,4,7,11],'m7':[0,3,7,10],'sus4':[0,5,7],'sus2':[0,2,7],'dim':[0,3,6],'dim7':[0,3,6,9],'aug':[0,4,8],'add9':[0,4,7,14],'6':[0,4,7,9],'69':[0,4,7,9,14],'m7b5':[0,3,6,10],'7sus4':[0,5,7,10],'m6':[0,3,7,9]}`.
Unknown quality → major (or minor if it starts with `m`) triad + logged warning — **never a crash on user-generated charts**. `N.C.` → rest.

---

## 4. Pipeline Design

```
song name ──► sources.search() ──► user picks result ─┐
URL ──────────────────────────────────────────────────┼─► sources.get_sheet(url) ─► RawSheet
pasted text ──────────────────────────────────────────┘     (store: cache + 1 req/s limit)
                                                                 │
                                              sheet_parser.parse(raw) ─► Song  (data/songs/<id>.json)
                                                                 │   tempo.resolve_bpm() fills Song.bpm
                                                                 │
                          user sets RenderOptions (key, style, instruments, bpm)
                                                                 │
                                     arrange.arrange(song, opts) ─► pretty_midi.PrettyMIDI
                                                                 │
                       render.render(pm, song_id, options_hash) ─► .mid / .wav (/ .mp3)
                                                                 │
                       browser ◄── /media/renders/...  (StaticFiles) ◄── <audio> + downloads
```

### 4.1 Retrieval — `backtrack/sources/`

```python
@dataclass
class SearchResult:
    title: str; artist: str; url: str; votes: int; rating: float; version: int; source: str

@dataclass
class RawSheet:                     # source-agnostic contract for the parser
    content: str                    # UG wiki_tab.content / CifraClub pre-text / pasted text
    meta: dict                      # capo (default 0), tonality, tuning, bpm (may be None)
    applicature: dict | None        # UG voicings when present
    source: str                     # 'ug' | 'cifraclub' | 'paste'
    url: str | None

def search(query: str, limit: int = 5) -> list[SearchResult]: ...
def get_sheet(url: str) -> RawSheet: ...      # dispatch by domain; raises SourceError
```

- **`ultimate_guitar.py`** (primary, ~80 lines modeled on freetar's `ug.py`, all verified live July 2026): GET with desktop Chrome UA → `soup.find('div', {'class': 'js-store'})` → `json.loads(html.unescape(data_content))`. Reads `tab_view.wiki_tab.content`, `tab_view.meta` (**`meta.get('capo', 0)`** — key absent when no capo; `tonality_name` may be `''`), `tab_view.applicature`, `tab_view.strummings[0].bpm` when present. Search via `www.ultimate-guitar.com/search.php?search_type=title&value=...` — **filter `type == 'Chords'` AND `'/tab/' in tab_url`** (drops Pro/Official promo rows with `type=null`), rank by `votes * rating`, return top 5. Never auto-pick.
- **`cifraclub.py`** (fallback, M6): parse `<pre data-chord-content>` / `<b data-chord-name>` **attributes** (build-hashed class names are unstable); Brazilian-notation normalization (`D4→Dsus4`, `A7(4)→A7sus4`) before storing.
- **`store.py`**: every successful fetch written to `data/cache/<sha1(url)>.json`; cache checked first; global 1 req/s throttle. Politeness *and* the ToS posture: fetch once, keep local, never republish.
- **Manual paste** is a first-class source, not an afterthought: `RawSheet(content=pasted_text, source='paste')` goes through the same parser (a line is a "chord line" if ≥80 % of its tokens parse as chords). This is the terminal, always-works fallback.

### 4.2 Parsing — `sheet_parser.py`

```python
def parse(raw: RawSheet, title: str, artist: str = '') -> Song: ...
```

- Split on `\r\n`; skip free-text preamble before the first bare `[Section]` header (real UG pages have it).
- Section headers: `^\[([^\]]+)\]$` on non-`[ch]`/`[tab]` lines.
- Chords: freetar's regex `\[ch\](?P<root>[A-G](#|b)?)(?P<quality>[^\[/]+)?(?P<bass>/[A-G](#|b)?)?\[/ch\]`; column offsets inside `[tab]` pairs preserved into `sheet_text` for display alignment only — the arranger works from the beat grid, the human reads the sheet.
- **Bar-position heuristic** (UG never gives durations): each chord defaults to one bar (`duration_beats = numerator`); a chord line with exactly 2 chords splits the bar evenly; chord-only intro lines with `|` barlines split across the line's bars. The parser is honest about guessing: durations/time-sig/style are user-editable via `PATCH`, and the UI (not smarter parsing) is the correction mechanism.
- BPM: `tempo.resolve_bpm()` — UG strummings → GetSongBPM (2 s timeout, silent fail) → style default (pop 100, rock 120, ballad 72, folk 104, waltz 90; 6/8 entered as dotted-quarter, stored ×1.5).

### 4.3 Chord math — `chords.py`

```python
def normalize(symbol: str) -> str          # '♯'→'#', '♭'→'b', 'C6/9'→'C69', strip parens, 'H'→'B'
def parse_symbol(symbol: str) -> ParsedChord   # pychord first; regex fallback; 'N.C.'→rest
def transpose_symbol(symbol: str, semitones: int, prefer_flats: bool) -> str
def prefer_flats_for(sounding_key_pc: int, minor: bool) -> bool  # F/Bb/Eb/Ab/Db/Gb + rel. minors
```

**Transposition is symbol-level + full MIDI regeneration — never note-number shifting.** Shifted MIDI loses idiomatic guitar voicings (an open-E shape +3 is not a playable G), breaks piano voice-leading, and desyncs the displayed sheet; regeneration costs milliseconds. This is how the hard requirement (any key, singer's range) is met.

**Capo semantics:** chart shows *shape* chords; sounding = shape + capo. Guitar builds voicings from shapes then offsets every guitar MIDI note by capo semitones (a capo'd guitar *is* open shapes pitched up). Piano/drums use sounding chords. On user transpose *t*:
- `'keep'` (default until M6): shape′ = shape + ((capo + t) mod 12), capo′ = 0.
- `'auto'` (M6, then default): try capo′ ∈ 0..7, score each candidate shape set by open-chord-dictionary coverage, pick max — output a guitarist recognizes.
- `'none'`: barre/nearest voicings, capo′ = 0.

### 4.4 Arranger — `backtrack/arrange/`

The single seam the API calls:

```python
def arrange(song: Song, opts: RenderOptions) -> pretty_midi.PrettyMIDI:
    """Apply transpose + capo_mode to symbols → flatten sections (honoring repeat) into an
    absolute beat timeline → beats→seconds at resolved BPM → hand timeline to each enabled
    track builder. Meta: initial_tempo, one TimeSignature, KeySignature of sounding key."""
```

**Pattern data — `patterns.py` (implementation-ready, musician-tunable literals):**

```python
# Strum events: (eighth_slot, event, velocity, duration_slots)
# event: 'D' down, 'U' up, 'X' muted chuck, 'BR' bass root string, 'B5' bass fifth string
STRUM_PATTERNS = {
    "pop_44":            [(0,"D",105,2),(2,"D",88,1),(3,"U",76,1),(5,"U",76,1),(6,"D",96,1),(7,"U",78,1)],  # D DU UDU
    "folk_boomchick_44": [(0,"BR",100,2),(2,"D",85,1),(3,"U",72,1),(4,"B5",95,2),(6,"D",85,1),(7,"U",72,1)],
    "ballad_44":         [(0,"D",98,4),(4,"D",88,3),(7,"U",70,1)],
    "muted_pop_44":      [(0,"D",100,2),(2,"X",82,0.25),(3,"U",74,1),(4,"X",90,0.25),(5,"U",74,1),(6,"D",88,1),(7,"U",76,1)],
    "waltz_34":          [(0,"BR",100,2),(2,"D",82,2),(4,"D",76,1),(5,"U",66,1)],   # 6 slots/bar
    "six_eight_68":      [(0,"D",102,2),(2,"U",72,1),(3,"D",88,2),(5,"U",72,1)],    # 6 slots/bar
}

# Piano events: LH/RH; 'R2' = root in octave 36–47; 'triad' = voice-led RH inversion
PIANO_PATTERNS = {
    "block_44":     [(0,"LH",["R2","R2+12"],92,4),(0,"RH","triad",88,2),(2,"RH","triad",78,2)],
    "broken8ths_44": "arp: slots 0..7 = [R2,R2+7,R3,third,fifth,third,R3,R2+7], vels [88,70,74,72,82,70,74,70], legato, CC64 held per chord",
    "ballad_44":    [(0,"LH",["R2"],90,2),(2,"LH",["R2+7"],84,2),(1,"RH","triad",76,1),(3,"RH","triad",74,1)],
    "waltz_34":     [(0,"LH",["R2"],92,1),(1,"RH","triad",76,1),(2,"RH","triad",70,1)],  # LH alternates root/fifth
    "arp_68":       "slots 0..5 = [R2,R2+7,R3,third,R3,R2+7], accents 86 on 0 and 3, others 68–72",
}

# Drum events: (slot, gm_note, velocity) — kick 36, snare 38, closed hat 42, side-stick 37, crash 49
DRUM_PATTERNS = {
    "pop_44":       {"kick":[(0,36,100),(4,36,96)], "snare":[(2,38,98),(6,38,98)], "hat":"slots 0-7 vel 62, accent 78 even"},
    "ballad_44":    {"kick":[(0,36,92)], "stick":[(2,37,72),(6,37,72)], "hat":"quarters vel 55"},
    "waltz_34":     {"kick":[(0,36,95)], "stick":[(2,37,68),(4,37,64)]},
    "six_eight_68": {"kick":[(0,36,98)], "snare":[(3,38,92)], "hat":"slots 0-5 vel 58, accent 0 and 3"},
}

STYLES = {   # style -> (strum, piano, drums, default_bpm, time_sig)
    "pop":       ("pop_44",            "block_44",     "pop_44",       100, (4,4)),
    "folk":      ("folk_boomchick_44", "broken8ths_44","pop_44",       104, (4,4)),
    "ballad":    ("ballad_44",         "ballad_44",    "ballad_44",     72, (4,4)),
    "muted_pop": ("muted_pop_44",      "block_44",     "pop_44",       100, (4,4)),
    "waltz":     ("waltz_34",          "waltz_34",     "waltz_34",      90, (3,4)),
    "six_eight": ("six_eight_68",      "arp_68",       "six_eight_68",  90, (6,8)),  # 90 = 60 dotted-q × 1.5
}
```

**Guitar** (`guitar.py` + `voicings.py`, GM program byte 25 steel / 24 nylon):
- Voicing selection: (1) exact hit in the open-chord dictionary → use it; (2) root reachable at fret 1–6 on the E string → E-shape barre; (3) else A-shape barre; (4) unknown quality → major/minor barre, drop unsupported extensions. When `Song.applicature` has an entry for the rendered *shape* symbol (i.e. shapes unchanged by the current capo_mode), its `notes` arrays seed the lookup first.
- Open-chord MIDI dictionary (low→high; standard tuning E2=40 A2=45 D3=50 G3=55 B3=59 E4=64):
  `E [40,47,52,56,59,64] · Em [40,47,52,55,59,64] · E7 [40,47,50,56,59,64] · Em7 [40,47,52,55,62,64] · A [45,52,57,61,64] · Am [45,52,57,60,64] · A7 [45,52,55,61,64] · Am7 [45,52,55,60,64] · Asus4 [45,52,57,62,64] · D [50,57,62,66] · Dm [50,57,62,65] · D7 [50,57,60,66] · Dm7 [50,57,60,65] · Dsus4 [50,57,62,67] · G [43,47,50,55,59,67] · G7 [43,47,50,55,59,65] · C [48,52,55,60,64] · C7 [48,52,58,60,64] · Cmaj7 [48,52,55,59,64] · B7 [47,51,57,59,66]`
- Barre formulas (R = root MIDI on barre string): E-shape (R∈41–51): maj `[R,R+7,R+12,R+16,R+19,R+24]`, min `[R,R+7,R+12,R+15,R+19,R+24]`, 7 `[R,R+7,R+10,R+16,R+19]`, m7 `[R,R+7,R+10,R+15,R+19]`. A-shape (R∈46–56): maj `[R,R+7,R+12,R+16,R+19]`, min `[R,R+7,R+12,R+15,R+19]`, 7 `[R,R+7,R+10,R+16]`, m7 `[R,R+7,R+10,R+15]`.
- Strum mechanics: down = full voicing low→high, ~15 ms/string stagger (±4 ms jitter, total spread 12–25 ms); up = **top 3–4 strings only**, high→low; chuck `X` = 40–60 ms gated notes at vel ~70. Velocity: accented downs 96–108, off-beat ups 15–25 lower, ±5 random per note, −2..3 per successive string within a strum. Sustain until next pattern event minus ~10 ms. Mid-pattern chord changes strum the new chord at the **next slot** — the pattern never restarts. Slash chords: replace the voicing's lowest note with the bass pitch placed in E2–D3 (40–50).
- Capo: add capo′ semitones to every guitar note after voicing from shapes.

**Piano** (`piano.py`, program byte 0):
- RH voicing by **nearest-top-note inversion**: keep `prev_top`; generate every inversion fully inside C4–C6 (60–84); pick minimal `abs(top − prev_top)`, tie-break on smallest total voice movement; first chord targets top ≈ G4 (67). (~15 lines.)
- LH root/fifth in 36–47; slash bass replaces LH root (bass pitch class placed in 36–47).
- **CC64 = 127 at chord onset, 0 at 20 ms before each change** — the single biggest realism win.

**Drums** (`drums.py`, optional, `Instrument(program=0, is_drum=True)` → channel index 9): per-style tables above, crash 49 vel 105 on beat 1 of each new section, ±4 velocity humanize.

### 4.5 Renderer — `render.py`

```python
def render(pm: pretty_midi.PrettyMIDI, song_id: str, ohash: str) -> RenderResult:
    # 1. pm.write(data/renders/<song_id>/<ohash>.mid)
    # 2. subprocess.run([FLUIDSYNTH_EXE, '-ni', '-g', '0.6', '-r', '44100',
    #                    '-T', 'wav', '-F', wav_path, SOUNDFONT, mid_path],
    #                   timeout=120, check=True, capture_output=True)
    #    + GeneralUser GS author's recommended reverb/chorus via -o options
    # 3. optional: ffmpeg -y -i wav -codec:a libmp3lame -b:a 192k mp3   (if ffmpeg found)

def check_environment() -> dict    # fluidsynth version, ffmpeg present, sf2 present
```

Explicit `-g 0.6` (fast-render can clip at default gain — FluidSynth issue #219). Runs inline in a **sync** endpoint (FastAPI threadpool); expected 5–25 s (unbenchmarked — measured in M1); single user needs no queue. A cache hit on `options_hash` skips arrange *and* render. Prune policy in `store.py`: keep the newest ~20 renders per song.

---

## 5. FastAPI Endpoints

All JSON under `/api`; `StaticFiles` mounts: `/` → `static/`, `/media` → `data/renders/` (read-only).

| Method & Path | Request | Response |
|---|---|---|
| `GET /` | — | `index.html` |
| `GET /api/health` | — | `{"fluidsynth": "2.5.6", "ffmpeg": true, "soundfont": true, "ok": true}` |
| `GET /api/search?q=oasis+wonderwall` | — | `{"results": [{"title","artist","url","votes","rating","version","source"}]}` (top 5, promo rows filtered, ranked votes×rating) |
| `POST /api/songs` | `{"url": "https://tabs.ultimate-guitar.com/..."}` **or** `{"paste": "<chart text>", "title": "...", "artist": "..."}` | Full **Song JSON** (incl. `id`, detected `key/capo/bpm`, `sections`, `sheet_text`) |
| `GET /api/songs` | — | `{"songs": [{"id","title","artist","key"}]}` — library = listing of `data/songs/` |
| `GET /api/songs/{id}` | — | Song JSON |
| `PATCH /api/songs/{id}` | Any subset: `{"bpm", "style", "time_signature", "key", "capo", "sections"}` (chord/duration/repeat edits) | Updated Song JSON, persisted |
| `GET /api/songs/{id}/sheet?transpose=3&capo_mode=keep` | — | `{"sheet_html": "...", "shape_key": "G", "capo": 2, "sounding_key": "Bb"}` — server owns enharmonic spelling; chords wrapped in `<span class="ch">` |
| `POST /api/songs/{id}/render` | `{"transpose": 3, "style": "pop", "guitar": true, "piano": true, "drums": false, "bpm": null, "guitar_program": 25, "capo_mode": "keep"}` (all optional) | `{"midi_url": "/media/<id>/<hash>.mid", "wav_url": "...", "mp3_url": "...|null", "cached": false, "sounding_key": "Bb", "bpm": 87, "render_seconds": 8.4}` |

**Error contract** (every failure): `{"error": {"code": "source_unreachable" | "not_found" | "parse_failed" | "render_failed", "message": "...", "hint": "Paste the chord chart manually"}}` with proper HTTP status — the frontend maps `code` to a specific recovery action (e.g. `source_unreachable` → open the paste box).

No websockets, no polling, no job IDs — the frontend shows a spinner for the one long call.

---

## 6. Frontend Outline

One `index.html`, one `app.js` (~300 lines), one `style.css`. Zero libraries, no build step. State = one plain JS object `{song, opts, lastRender}`; small DOM-update functions; nothing renders until Generate is pressed (hash cache makes repeats instant).

Layout, top to bottom:

1. **Find a song** — single text input (song name *or* URL, detected by `https://` prefix) + Find button. Name → `GET /api/search`, top-5 result cards (title / artist / rating / votes / version), click one → `POST /api/songs {url}`. URL → straight to `POST /api/songs`. "Paste chords instead" link toggles a `<textarea>` fallback — also auto-opened on any source error. Library dropdown of previously saved songs (`GET /api/songs`).
2. **Song panel** — title/artist; editable fields pre-filled from parse: original key + capo badge, BPM `<input type="number">` (**labeled "dotted-quarter BPM" when 6/8**, converted ×1.5 at the boundary — one conversion site, unit-tested), time-signature select, style select (pop / folk / ballad / muted-pop / waltz / 6-8). Edits `PATCH` on change.
3. **Arrangement controls** — **Key selector**: dropdown of all 12 sounding keys with "(original)" marked, plus a −6…+6 semitone stepper (both drive one `transpose` int); capo-mode select (Keep shapes / Auto-capo / No capo) with the "shapes in X, capo Y" readout from `/sheet`. Instrument checkboxes Guitar / Piano (≥1 enforced) + steel/nylon toggle + Drums checkbox. **Generate** → spinner ("Rendering… ~15 s").
4. **Player row** — `<audio controls>` on `wav_url`; plain `<a download>` buttons for **MIDI** and **WAV** (**MP3** shown when ffmpeg present).
5. **Chord sheet** — monospace `<pre>` of `sheet_html`; chord spans highlighted; re-fetched from `/sheet?transpose=` whenever the key changes so **eyes and ears always match**. Sheet stays local — never republished (UG ToS posture).

---

## 7. Build Milestones

**M0 — Environment (half a day).** Install Python 3.12; unzip `fluidsynth-v2.5.6-win10-x64-cpp11.zip` from GitHub releases (glib flavor documented as fallback); `winget install -e --id Gyan.FFmpeg` (optional); download GeneralUser-GS.sf2 from the official repo into `assets/soundfonts/`; write `config.py` + `scripts/check_env.py`; hand-run one fluidsynth render of any MIDI file.
*Done when:* `check_env.py` prints all-green with versions and a hand-rendered WAV plays in Windows Media Player. De-risks the only non-Python binaries before any code exists.

**M1 — Steel thread through both risky ends (1–2 days).** `ultimate_guitar.py` fetch of one hardcoded Wonderwall URL (js-store extraction; response saved to `tests/fixtures/`) → crude parse (chord symbols only, one per bar, fixed 87 BPM) → naive whole-note block chords via pretty_midi → `render.py` subprocess → minimal FastAPI page with one button and an `<audio>` tag. `scripts/smoke_render.py` (C–Am–F–G, no network) isolates render failures from scrape failures. Measure render time.
*Done when:* clicking Generate in a browser on the actual Windows 11 machine plays recognizable Wonderwall chords. Proves scraping, MIDI writing, FluidSynth-on-Windows, and file serving — every risk the project could die on.

**M2 — Model, parser, theory, transposition, search (2–3 days).** Full dataclasses + JSON persistence; section/`[tab]`/preamble-aware parser with bar heuristic; `chords.py` normalization + pychord parse + symbol transposition + enharmonic spelling; `tempo.py` chain; UG search endpoint with promo filtering; disk cache + rate limiter; manual-paste shim; `PATCH` editing; transpose parameter re-renders in a new key (still block chords). Offline fixture tests: `D/F#`, `A7sus4`, `C6/9`, `N.C.`, capo-absent, empty-tonality, pasted chart.
*Done when:* any of 5 varied test songs is found by name, parsed, and rendered correctly in 3 different keys; `pytest` green with network off.

**M3 — Guitar engine (2–3 days).** `voicings.py` + `patterns.py` + `guitar.py`: full strum spec (stagger, up-strum thinning, chucks, velocity shaping, humanize, slash basses, capo offset), applicature seeding, style selector wired.
*Done when:* pop_44 Wonderwall and boom-chick Let It Be are recognizably guitar-like in original key and transposed ±4; one by-ear tuning pass of velocities/stagger against GeneralUser GS completed (budget an evening — constants are starting points, not ground truth).

**M4 — Piano engine (1–2 days).** `piano.py`: pattern tables, nearest-inversion voice-leading, LH register clamps, CC64 pedaling; instrument checkboxes + steel/nylon toggle.
*Done when:* a piano-only ballad render has no adjacent chord-top leap greater than a 4th (assertable in a unit test) and the pedal audibly clears on chord changes.

**M5 — Full frontend (2–3 days).** Complete single page from §6: search flow, library, editable song panel, key/capo-mode/style/instrument controls, spinner, player, transposing chord-sheet display, download links, error-code → recovery-action wiring.
*Done when:* the musician covers an entire new song — search → tweak → transpose → play → download MIDI — without touching a terminal.

**M6 — Polish & resilience (ongoing, each item independent and skippable).** Drums track + checkbox; auto-capo scorer (then flip `capo_mode` default to `'auto'`); GetSongBPM autofill; ffmpeg MP3; CifraClub fallback + Brazilian normalization; count-in click; render pruning; section-repeat editor; README with full Windows setup + GetSongBPM backlink.
*Done when (resilience check):* blocking UG in the hosts file still gets from song name to audio via CifraClub or the paste box in ≤3 clicks.

---

## 8. Risks & Mitigations

| Risk | Likelihood / Impact | Mitigation |
|---|---|---|
| **UG changes `js-store` markup or tightens Cloudflare** (e-chords already challenge-walls identical requests) | Medium / High — kills primary source | All UG knowledge isolated in `ultimate_guitar.py` behind the `RawSheet` seam; watch kmille/freetar (breaks & gets fixed the same way); escalation ladder: curl_cffi TLS impersonation → CifraClub parser (M6) → **manual paste, built in M2, always works**. Permanent disk cache means already-fetched songs never break. |
| **UG ToS** — automation exceeds the personal-use carve-out (§6.2–6.4) | Low practical risk, single user | One on-demand fetch per song, 1 req/s throttle, permanent local cache, never republish sheets/lyrics, never distribute the app with UG scraping enabled. |
| **Chord-symbol edge cases** (unicode ♯/♭, `C6/9` vs slash, `N.C.`, stacked alterations `C7b9#11`, Brazilian `D4`/`H`) | Certain / Medium | Single `normalize()` chokepoint before pychord; unknown qualities pass through verbatim and voice as triads with an on-screen warning — **never an exception**; regression-test file of gnarly real symbols grows over time. |
| **FluidSynth on Windows** (no winget, Chocolatey stale at 2.4.7, pyFluidSynth DLL pain) | Medium / High if mishandled | M0 proves it by hand before any code; subprocess-only integration (no ctypes); absolute exe path in `config.py`; `/api/health` + `check_env.py` diagnose with fix instructions; cpp11→glib flavor fallback documented; pin ≥2.5.6 (security fixes in MIDI parsing). |
| **Song not found / wrong version / promo rows** | Medium / Low | Filter `type=='Chords'` + `/tab/` URLs, rank votes×rating, always show top 5 for human confirmation (never auto-pick); direct-URL field; paste box; `PATCH` lets the user fix bad key/bpm/capo/chords. |
| **Missing structural data** (BPM absent on many tabs; bar positions/time signatures never present; `capo` key absent; `tonality_name` empty) | Certain / Medium | Defensive `.get()` defaults everywhere; BPM chain UG → GetSongBPM (2 s, silent) → style default; one-chord-per-bar heuristic (how most campfire charts are played) with per-section user correction; 4/4 default with UI override. |
| **6/8 tempo half-speed bug** (MIDI tempo is per quarter; musicians count dotted quarters) | High if ignored / Medium | `Song.bpm` is *always* quarter-BPM; UI labels the field "dotted-quarter BPM" for 6/8 and converts ×1.5 at exactly one boundary — unit-tested. |
| **Transposed voicings unplayable/muddy** (core requirement at stake) | High if naive / High | Designed out: symbol-level transpose + full re-voicing per render (never MIDI-note shift); capo emulation from shapes; auto-capo scorer (M6) keeps open shapes; register clamps in both engines. |
| **Fast-render clipping / level drift** (FluidSynth issue #219) | Medium / Low | Explicit `-g 0.6`, gain exposed in `config.py`, peak spot-check in M1; drop reverb/chorus for previews if the measured render time disappoints. |
| **Library maintenance cliffs** (pretty_midi single maintainer, mido-free stack, pychord one maintainer) | Low / Low | Pin Python 3.12 and exact versions (`pretty_midi>=0.2.11` mandatory); tiny API surfaces behind the `arrange()`/`render()` seams make vendoring or swapping a contained change. |
| **GetSongBPM key suspension** (mandatory backlink) or missing songs | Low / Trivial | Best-effort only: 2 s timeout, silent fallback to defaults; backlink in README + About; feature is deletable. |
| **Pattern constants sound wrong with GeneralUser GS** | Certain (first pass) / Low | All musical constants are data in `patterns.py`; M3/M4 explicitly budget by-ear tuning passes — the developer is a musician; this is the fun part. |

**Deliberately cut** (revisit only on real need): user accounts, DB, job queues, Docker, websockets/progress streaming, in-browser MIDI playback (html-midi-player), ML arrangement, music21, bass track (trivial to add under `arrange/` later), sources beyond UG + CifraClub + paste, hosting for anyone but the one musician.

---

## 9. Open Questions for the User (taste, not engineering)

1. **Sheet display with capo:** when a chart uses a capo, do you want the sheet to show *shape* chords + "Capo 2" (play-along view) or *concert-pitch* chords (theory view)? Default plan: shape + capo badge, since you'll play along.
2. **Repertoire for tuning:** name ~5 songs you actually cover (ideally spanning a strummy pop tune, a ballad, and something in 3/4 or 6/8) — they become the M2/M3 acceptance fixtures and the by-ear tuning targets.
3. **Count-in:** do you want a 1–2 bar click/stick count-in before the track starts (helps live singing)? Cheap to add in M6 — on by default, off by default, or not at all?
4. **Default guitar color:** steel-string is the planned default; if most of your covers are fingerpicked/bossa/ballad material, nylon could be the default instead (both stay toggleable).