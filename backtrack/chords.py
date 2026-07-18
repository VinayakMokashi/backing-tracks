"""Chord-symbol math: normalization, parsing, transposition, spelling.

The single chord regex lives here. Quality text is treated as opaque —
it maps to intervals only at voicing time (see arrange/voicings.py), which
is what makes symbol-level transposition lossless.
"""
from __future__ import annotations

import re

from .model import ParsedChord

CHORD_RE = re.compile(r"^([A-G][#b]?)([^/]*)(?:/([A-G][#b]?))?$")

NOTE_TO_PC = {
    "C": 0, "B#": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "Fb": 4, "F": 5, "E#": 5, "F#": 6, "Gb": 6, "G": 7,
    "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11, "Cb": 11,
}
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

_REST_SYMBOLS = {"N.C.", "N.C", "NC", "NOCHORD"}  # checked after space-stripping

# Major keys spelled with flats: F Bb Eb Ab Db Gb; their relative minors: d g c f bb eb.
_FLAT_MAJOR_PCS = {5, 10, 3, 8, 1, 6}
_FLAT_MINOR_PCS = {2, 7, 0, 5, 10, 3}


def normalize(symbol: str) -> str:
    s = symbol.strip().replace(" ", "")
    s = s.replace("♯", "#").replace("♭", "b").replace("♮", "")
    s = s.replace("(", "").replace(")", "")  # 'C(add9)' -> 'Cadd9'
    if s[:1] == "H":  # German notation
        s = "B" + s[1:]
    s = s.replace("6/9", "69")  # slash-form 6/9 is a quality, not a slash chord
    return s


def parse_symbol(symbol: str) -> ParsedChord | None:
    """Parse a chord symbol; None if the text is not a chord at all.

    Unknown qualities still parse (quality is opaque here) — the voicing
    layer decides how to sound them.
    """
    s = normalize(symbol)
    if s.upper() in _REST_SYMBOLS:
        return ParsedChord(root_pc=0, quality="", is_rest=True)
    m = CHORD_RE.match(s)
    if not m:
        return None
    root, quality, bass = m.group(1), m.group(2) or "", m.group(3)
    if bass is not None and bass not in NOTE_TO_PC:
        return None
    return ParsedChord(
        root_pc=NOTE_TO_PC[root],
        quality=quality,
        bass_pc=NOTE_TO_PC[bass] if bass else None,
    )


def pc_name(pc: int, prefer_flats: bool) -> str:
    return (FLAT_NAMES if prefer_flats else SHARP_NAMES)[pc % 12]


def transpose_symbol(symbol: str, semitones: int, prefer_flats: bool = False) -> str:
    parsed = parse_symbol(symbol)
    if parsed is None or parsed.is_rest:
        return symbol
    out = pc_name(parsed.root_pc + semitones, prefer_flats) + parsed.quality
    if parsed.bass_pc is not None:
        out += "/" + pc_name(parsed.bass_pc + semitones, prefer_flats)
    return out


def prefer_flats_for(sounding_key_pc: int, minor: bool) -> bool:
    pcs = _FLAT_MINOR_PCS if minor else _FLAT_MAJOR_PCS
    return sounding_key_pc % 12 in pcs


def key_is_minor(key_symbol: str) -> bool:
    q = (parse_symbol(key_symbol) or ParsedChord(0, "")).quality
    return q.startswith("m") and not q.startswith("maj")
