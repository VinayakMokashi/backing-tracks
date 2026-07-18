"""RawSheet -> Song.

Bar-position heuristic (UG never gives durations): chords are grouped into bars
using barlines when present, otherwise one chord per bar (two chords on a
barless line share a bar). The parser is honest about guessing — durations,
time signature, and style stay user-editable via PATCH; the UI is the
correction mechanism.
"""
from __future__ import annotations

import re
from html import escape

from . import chords, tempo
from .model import ChordEvent, Section, Song, slugify
from .sources import RawSheet

SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
CHORD_TAG_RE = re.compile(r"\[ch\](.*?)\[/ch\]")
_MARK = "\x00"  # sentinel wrapping each chord so barline grouping survives cleaning


def _clean_line(line: str) -> str:
    line = line.replace("[tab]", "").replace("[/tab]", "")
    return CHORD_TAG_RE.sub(lambda m: m.group(1), line)


def wrap_bare_chords(text: str) -> str:
    """Add [ch] tags to a pasted chart that has none.

    A line becomes a chord line only if every non-barline token parses as a
    chord — so lyric lines survive untouched even when a stray word looks
    chord-ish. Barlines are preserved for the bar heuristic.
    """
    if "[ch]" in text:
        return text
    out: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if SECTION_RE.match(stripped):
            out.append(line)
            continue
        non_bar = [t for t in stripped.split() if t != "|"]
        chordish = [t for t in non_bar if chords.parse_symbol(t) is not None]
        if non_bar and len(chordish) == len(non_bar):
            out.append(re.sub(
                r"\S+",
                lambda m: (f"[ch]{m.group(0)}[/ch]"
                           if chords.parse_symbol(m.group(0)) is not None
                           else m.group(0)),
                line,
            ))
        else:
            out.append(line)
    return "\n".join(out)


def _bars_from_line(line: str) -> list[list[str]]:
    """Group a chord line's [ch] chords into bars.

    Uses [ch] tags as the authoritative chord list (a bare lyric word that
    looks like a chord is never counted), and real ``|`` barlines to divide
    bars. Without barlines, two chords share a bar and anything else is one
    chord per bar.
    """
    marked = CHORD_TAG_RE.sub(lambda m: f"{_MARK}{m.group(1).strip()}{_MARK}", line)
    segments = marked.split("|") if "|" in marked else [marked]
    bars: list[list[str]] = []
    for seg in segments:
        found = [c for c in re.findall(f"{_MARK}(.*?){_MARK}", seg) if c]
        if found:
            bars.append(found)
    if not bars:
        return []
    if "|" not in marked:
        group = bars[0]
        if len(group) == 2:
            return [group]            # two barless chords share one bar
        return [[c] for c in group]   # otherwise one chord per bar
    return bars


def to_html(sheet_text: str, transpose: int = 0, prefer_flats: bool = False) -> str:
    """Render a stored ([ch]-tagged) sheet to HTML, optionally transposing chords.

    The whole text is HTML-escaped first (chord symbols contain no HTML-special
    characters), then [ch] spans are substituted — so lyrics stay safe.
    """
    escaped = escape(sheet_text)

    def repl(m: re.Match) -> str:
        symbol = m.group(1)
        if transpose:
            symbol = chords.transpose_symbol(symbol, transpose, prefer_flats)
        return f'<span class="ch">{symbol}</span>'

    return CHORD_TAG_RE.sub(repl, escaped)


def parse(raw: RawSheet, title: str = "", artist: str = "") -> Song:
    title = title or raw.meta.get("title", "") or "Untitled"
    artist = artist or raw.meta.get("artist", "")
    numerator = 4  # 4/4 default; user-editable

    lines = (raw.content or "").replace("\r\n", "\n").split("\n")

    sections: list[Section] = []
    current: Section | None = None
    beat_cursor = 0.0
    sheet_lines: list[str] = []
    preamble_done = False
    has_headers = any(SECTION_RE.match(_clean_line(ln).strip()) for ln in lines)

    def start_section(name: str) -> None:
        nonlocal current, beat_cursor
        current = Section(name=name)
        sections.append(current)
        beat_cursor = 0.0

    for line in lines:
        cleaned = _clean_line(line)
        display = line.replace("[tab]", "").replace("[/tab]", "")  # keep [ch] tags
        header = SECTION_RE.match(cleaned.strip())
        if header and "[ch]" not in line:
            preamble_done = True
            start_section(header.group(1).strip())
            sheet_lines.append(display)
            continue
        if has_headers and not preamble_done and "[ch]" not in line:
            continue  # free-text notes before the first [Section] header
        sheet_lines.append(display)
        bars = _bars_from_line(line)
        if not bars:
            continue
        if current is None:
            start_section("Song")
        for bar_chords in bars:
            beats_each = numerator / len(bar_chords)
            for symbol in bar_chords:
                current.chords.append(
                    ChordEvent(symbol=symbol, beat=beat_cursor,
                               duration_beats=beats_each)
                )
                beat_cursor += beats_each

    for section in sections:
        total_beats = sum(ev.duration_beats for ev in section.chords)
        section.bars = round(total_beats / numerator)
    sections = [s for s in sections if s.chords]

    style = "pop"
    capo = int(raw.meta.get("capo", 0) or 0)
    bpm = tempo.resolve_bpm(raw.meta.get("bpm"), style, title, artist)

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
