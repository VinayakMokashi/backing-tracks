"""RawSheet -> Song.

Timing model (UG never gives explicit durations): each chord's length is read
from the horizontal COLUMN SPACING the chart uses to place it over the lyric —
a chord held over many syllables spans more columns and gets more beats than a
chord that changes quickly. Chord-only lines (intros) default to one bar each,
and explicit ``|`` barlines are honoured when present. Durations remain
user-editable via PATCH; the UI is the correction mechanism.
"""
from __future__ import annotations

import math
import re
from html import escape

import config

from . import chords, tempo
from .model import ChordEvent, Section, Song, slugify
from .sources import RawSheet

SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
CHORD_TAG_RE = re.compile(r"\[ch\](.*?)\[/ch\]")
_MARK = "\x00"  # sentinel wrapping each chord so barline grouping survives cleaning


def _clean_line(line: str) -> str:
    line = line.replace("[tab]", "").replace("[/tab]", "")
    return CHORD_TAG_RE.sub(lambda m: m.group(1), line)


def _is_tab_line(cleaned: str) -> bool:
    """True for guitar-tablature lines (e|--2--0--, etc.) — not lyrics."""
    s = cleaned.strip()
    if len(s) < 4:
        return False
    dashes = s.count("-")
    return dashes >= 5 and (dashes + s.count("|")) / len(s) > 0.5


def _is_legend_line(cleaned: str) -> bool:
    """True for capo/transpose reference tables ('C = D', 'Em = F#m') that
    trail many charts — chord-shaped but never played."""
    return "=" in cleaned


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


def _chord_columns(line: str) -> tuple[str, list[tuple[int, str]]]:
    """Return (cleaned_line, [(column, symbol), ...]).

    The column is where the chord visually sits once [ch] tags are removed —
    i.e. where it lands over the lyric beneath it.
    """
    s = line.replace("[tab]", "").replace("[/tab]", "")
    parts: list[str] = []
    cols: list[tuple[int, str]] = []
    pos = col = 0
    for m in CHORD_TAG_RE.finditer(s):
        before = s[pos:m.start()]
        col += len(before)
        parts.append(before)
        symbol = m.group(1).strip()
        cols.append((col, symbol))
        parts.append(symbol)
        col += len(symbol)
        pos = m.end()
    parts.append(s[pos:])
    return "".join(parts), cols


def _distribute(widths: list[int], total_beats: int) -> list[int]:
    """Split total_beats among chords proportional to their column widths,
    quantized to whole beats, each at least 1, summing exactly to total_beats."""
    n = len(widths)
    total = max(total_beats, n)          # guarantee >= 1 beat per chord
    span = sum(widths) or n
    exact = [w / span * total for w in widths]
    beats = [max(1, round(x)) for x in exact]
    while sum(beats) > total:            # trim the currently-largest
        i = max(range(n), key=lambda k: beats[k])
        if beats[i] <= 1:
            break
        beats[i] -= 1
    while sum(beats) < total:            # grow the most under-allocated
        i = max(range(n), key=lambda k: exact[k] - beats[k])
        beats[i] += 1
    return beats


def _lyric_durations(cols, cleaned_chord: str, lyric: str,
                     numerator: int) -> list[tuple[str, float]]:
    """Durations from column spacing over the paired lyric line."""
    width = max(len(cleaned_chord.rstrip()), len(lyric.rstrip()))
    positions = [c for c, _ in cols]
    symbols = [s for _, s in cols]
    n = len(symbols)
    widths = [max(1, (positions[i + 1] if i + 1 < n else max(width, positions[i] + 1))
                  - positions[i]) for i in range(n)]
    bars = max(1, round(width / config.CHARS_PER_BAR), math.ceil(n / numerator))
    beats = _distribute(widths, bars * numerator)
    return list(zip(symbols, (float(b) for b in beats)))


def _barline_durations(line: str, numerator: int) -> list[tuple[str, float]]:
    """One bar per ``|``-delimited group, split evenly among its chords."""
    out: list[tuple[str, float]] = []
    for bar_chords in _bars_from_line(line):
        each = numerator / len(bar_chords)
        out.extend((sym, each) for sym in bar_chords)
    return out


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

    i = 0
    while i < len(lines):
        line = lines[i]
        cleaned = _clean_line(line)
        display = line.replace("[tab]", "").replace("[/tab]", "")  # keep [ch] tags
        header = SECTION_RE.match(cleaned.strip())
        if header and "[ch]" not in line:
            preamble_done = True
            start_section(header.group(1).strip())
            sheet_lines.append(display)
            i += 1
            continue
        if "[ch]" not in line:
            if not (has_headers and not preamble_done) and not _is_tab_line(cleaned):
                sheet_lines.append(display)  # lyric / blank line (skip preamble & tab)
            i += 1
            continue

        cleaned_chord, cols = _chord_columns(line)
        if _is_legend_line(cleaned_chord):
            i += 1  # capo/transpose legend table — not song chords
            continue
        sheet_lines.append(display)

        # A following non-chord, non-header, non-blank, non-tab line is this
        # line's lyric (its length/columns tell us how long each chord is held).
        lyric = None
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            nxt_clean = _clean_line(nxt)
            if (nxt.strip() and "[ch]" not in nxt
                    and not SECTION_RE.match(nxt_clean.strip())
                    and not _is_tab_line(nxt_clean)):
                lyric = nxt_clean

        if "|" in cleaned_chord:
            events = _barline_durations(line, numerator)
        elif lyric is not None:
            events = _lyric_durations(cols, cleaned_chord, lyric, numerator)
        else:
            events = [(sym, float(numerator)) for _, sym in cols]  # one bar each

        if events:
            if current is None:
                start_section("Song")
            for symbol, dur in events:
                current.chords.append(
                    ChordEvent(symbol=symbol, beat=beat_cursor, duration_beats=dur))
                beat_cursor += dur

        if lyric is not None:
            sheet_lines.append(lyric)
            i += 2  # consume the lyric line too
        else:
            i += 1

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
