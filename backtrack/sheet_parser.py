"""RawSheet -> Song.

Bar-position heuristic (UG never gives durations): each chord defaults to one
bar. The parser is honest about guessing — durations, time signature, and
style are user-editable via PATCH; the UI is the correction mechanism.
Two-chords-per-bar splitting and barline handling refine this in M2.
"""
from __future__ import annotations

import re

from . import chords
from .model import ChordEvent, Section, Song, slugify
from .sources import RawSheet

SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
CHORD_TAG_RE = re.compile(r"\[ch\](.*?)\[/ch\]")

_STYLE_DEFAULT_BPM = {"pop": 100.0, "folk": 104.0, "ballad": 72.0,
                      "muted_pop": 100.0, "waltz": 90.0, "six_eight": 90.0}


def _clean_line(line: str) -> str:
    line = line.replace("[tab]", "").replace("[/tab]", "")
    return CHORD_TAG_RE.sub(lambda m: m.group(1), line)


def parse(raw: RawSheet, title: str = "", artist: str = "") -> Song:
    title = title or raw.meta.get("title", "") or "Untitled"
    artist = artist or raw.meta.get("artist", "")
    numerator = 4  # 4/4 default; user-editable

    lines = (raw.content or "").replace("\r\n", "\n").split("\n")

    sections: list[Section] = []
    current: Section | None = None
    sheet_lines: list[str] = []
    preamble_done = False
    has_headers = any(SECTION_RE.match(_clean_line(ln).strip()) for ln in lines)

    for line in lines:
        cleaned = _clean_line(line)
        header = SECTION_RE.match(cleaned.strip())
        if header and "[ch]" not in line:
            preamble_done = True
            current = Section(name=header.group(1).strip())
            sections.append(current)
            sheet_lines.append(cleaned)
            continue
        if has_headers and not preamble_done and "[ch]" not in line:
            continue  # free-text notes before the first [Section] header
        sheet_lines.append(cleaned)
        symbols = CHORD_TAG_RE.findall(line)
        if not symbols:
            continue
        if current is None:
            current = Section(name="Song")
            sections.append(current)
        for symbol in symbols:
            bar = len(current.chords)
            current.chords.append(
                ChordEvent(symbol=symbol.strip(), beat=float(bar * numerator),
                           duration_beats=float(numerator))
            )

    for section in sections:
        section.bars = len(section.chords)
    sections = [s for s in sections if s.chords]

    style = "pop"
    bpm = raw.meta.get("bpm") or _STYLE_DEFAULT_BPM[style]
    capo = int(raw.meta.get("capo", 0) or 0)

    tonality = raw.meta.get("tonality") or ""
    key = tonality if chords.parse_symbol(tonality) else ""
    if key and capo:
        # UG's tonality_name is the SOUNDING key; the model stores the SHAPE
        # key (sounding = shape + capo), so shift the capo back out.
        parsed = chords.parse_symbol(key)
        flats = chords.prefer_flats_for(parsed.root_pc - capo, chords.key_is_minor(key))
        key = chords.transpose_symbol(key, -capo, flats)
    if not key:
        key = "C"
        for ev in (sections[0].chords if sections else []):
            first = chords.parse_symbol(ev.symbol)
            if first is not None and not first.is_rest:
                key = ev.symbol
                break

    return Song(
        id=slugify(f"{artist} {title}"),
        title=title,
        artist=artist,
        sections=sections,
        bpm=float(bpm),
        time_signature=(numerator, 4),
        key=key,
        capo=capo,
        style=style,
        sheet_text="\n".join(sheet_lines).strip(),
        applicature=raw.applicature,
        source_url=raw.url,
    )
