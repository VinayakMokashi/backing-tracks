"""Core data model: Song / Section / ChordEvent / RenderOptions / ParsedChord.

Chords are stored as written symbols (shape chords when capo > 0); only root
and slash-bass pitch classes are ever transposed, so quality text survives
losslessly. Beats are in time-signature-denominator units. ``bpm`` is always
quarter-note BPM (MIDI set_tempo semantics) — the UI converts for 6/8.
``RenderOptions`` never mutates the saved Song.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field


@dataclass
class ChordEvent:
    symbol: str                 # verbatim chart symbol: 'Am7', 'D/F#', 'C69', 'N.C.'
    beat: float                 # onset from section start, in denominator beat units
    duration_beats: float


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
    artist: str = ""
    sections: list[Section] = field(default_factory=list)
    bpm: float = 100.0          # ALWAYS quarter-note BPM
    time_signature: tuple[int, int] = (4, 4)
    key: str = "C"              # SHAPE key as printed; sounding key = key + capo
    capo: int = 0               # semitones
    style: str = "pop"
    sheet_text: str = ""        # cleaned chord-over-lyric text for display
    applicature: dict | None = None   # UG per-chord voicings (MIDI note lists) when available
    source_url: str | None = None


@dataclass
class RenderOptions:            # per-render knobs, applied at arrange time only
    transpose: int = 0          # semitones vs. original SOUNDING key
    guitar: bool = True
    piano: bool = True
    drums: bool = False
    count_in: bool = True
    style: str | None = None    # override Song.style
    bpm: float | None = None    # override Song.bpm
    guitar_program: int = 25    # GM byte (0-indexed): 25 steel, 24 nylon
    capo_mode: str = "keep"     # 'keep' | 'auto' | 'none'


@dataclass
class ParsedChord:              # produced by chords.parse_symbol, consumed by arrangers
    root_pc: int                # 0-11
    quality: str                # opaque text: '', 'm', 'm7', 'sus4', 'm7b5', ...
    bass_pc: int | None = None  # slash bass
    is_rest: bool = False       # 'N.C.'


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "song"


def song_to_dict(song: Song) -> dict:
    d = asdict(song)
    d["time_signature"] = list(song.time_signature)
    return d


def song_from_dict(d: dict) -> Song:
    sections = [
        Section(
            name=s["name"],
            chords=[ChordEvent(**c) for c in s.get("chords", [])],
            bars=s.get("bars", 0),
            repeat=s.get("repeat", 1),
        )
        for s in d.get("sections", [])
    ]
    return Song(
        id=d["id"],
        title=d["title"],
        artist=d.get("artist", ""),
        sections=sections,
        bpm=d.get("bpm", 100.0),
        time_signature=tuple(d.get("time_signature", (4, 4))),
        key=d.get("key", "C"),
        capo=d.get("capo", 0),
        style=d.get("style", "pop"),
        sheet_text=d.get("sheet_text", ""),
        applicature=d.get("applicature"),
        source_url=d.get("source_url"),
    )


def options_hash(song: Song, opts: RenderOptions) -> str:
    """sha1 of (song content + resolved opts) -> render cache key.

    A hash hit skips arrange AND render — previously heard keys replay
    instantly.
    """
    resolved = asdict(opts)
    resolved["style"] = opts.style or song.style
    resolved["bpm"] = opts.bpm or song.bpm
    blob = json.dumps([song_to_dict(song), resolved], sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]
