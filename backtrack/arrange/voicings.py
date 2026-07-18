"""Voicing data: quality -> interval sets. Pure data + tiny helpers.

Guitar open-chord dictionary and barre formulas land in M3. Quality maps to
intervals only here — never inside the engines.
"""
from __future__ import annotations

import functools
import logging

from ..chords import NOTE_TO_PC

logger = logging.getLogger(__name__)

QUALITY_INTERVALS = {
    "": [0, 4, 7],
    "m": [0, 3, 7],
    "7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "M7": [0, 4, 7, 11],
    "m7": [0, 3, 7, 10],
    "sus4": [0, 5, 7],
    "sus2": [0, 2, 7],
    "dim": [0, 3, 6],
    "dim7": [0, 3, 6, 9],
    "aug": [0, 4, 8],
    "add9": [0, 4, 7, 14],
    "madd9": [0, 3, 7, 14],
    "6": [0, 4, 7, 9],
    "69": [0, 4, 7, 9, 14],
    "m7b5": [0, 3, 6, 10],
    "7sus4": [0, 5, 7, 10],
    "m6": [0, 3, 7, 9],
    "5": [0, 7],
    "9": [0, 4, 7, 10, 14],
    "m9": [0, 3, 7, 10, 14],
    "maj9": [0, 4, 7, 11, 14],
}


# Open-position voicings (MIDI notes low->high; standard tuning
# E2=40 A2=45 D3=50 G3=55 B3=59 E4=64). Keyed by name; resolved to
# (root_pc, quality) at import.
OPEN_CHORDS: dict[str, list[int]] = {
    "E": [40, 47, 52, 56, 59, 64], "Em": [40, 47, 52, 55, 59, 64],
    "E7": [40, 47, 50, 56, 59, 64], "Em7": [40, 47, 52, 55, 62, 64],
    "A": [45, 52, 57, 61, 64], "Am": [45, 52, 57, 60, 64],
    "A7": [45, 52, 55, 61, 64], "Am7": [45, 52, 55, 60, 64],
    "Asus4": [45, 52, 57, 62, 64],
    "D": [50, 57, 62, 66], "Dm": [50, 57, 62, 65],
    "D7": [50, 57, 60, 66], "Dm7": [50, 57, 60, 65], "Dsus4": [50, 57, 62, 67],
    "G": [43, 47, 50, 55, 59, 67], "G7": [43, 47, 50, 55, 59, 65],
    "C": [48, 52, 55, 60, 64], "C7": [48, 52, 58, 60, 64],
    "Cmaj7": [48, 52, 55, 59, 64], "B7": [47, 51, 57, 59, 66],
}

_OPEN_STRING_PCS = (4, 9, 2, 7, 11, 4)  # E A D G B E


def _build_open_by_key() -> dict[tuple[int, str], list[int]]:
    from ..chords import parse_symbol
    table: dict[tuple[int, str], list[int]] = {}
    for name, notes in OPEN_CHORDS.items():
        parsed = parse_symbol(name)
        if parsed is not None:
            table[(parsed.root_pc, parsed.quality)] = sorted(notes)
    return table


OPEN_BY_KEY = _build_open_by_key()

# Barre-shape interval stacks above the root note on the barre string.
_E_SHAPE = {
    "maj": [0, 7, 12, 16, 19, 24], "min": [0, 7, 12, 15, 19, 24],
    "dom7": [0, 7, 10, 16, 19], "min7": [0, 7, 10, 15, 19],
}
_A_SHAPE = {
    "maj": [0, 7, 12, 16, 19], "min": [0, 7, 12, 15, 19],
    "dom7": [0, 7, 10, 16], "min7": [0, 7, 10, 15],
}


def _shape_family(quality: str) -> str:
    minor = quality.startswith("m") and not quality.startswith("maj")
    seventh = "7" in quality and "maj7" not in quality and "M7" not in quality
    if minor and seventh:
        return "min7"
    if minor:
        return "min"
    if seventh:
        return "dom7"
    return "maj"


def _stack_intervals(root_pc: int, quality: str) -> list[int]:
    """Fallback voicing straight from the chord's real interval set — used when
    no barre triad/7 shape is a subset of the chord (dim/aug/sus/7sus4/5/...)."""
    e_fret = (root_pc - _OPEN_STRING_PCS[0]) % 12
    root = 40 + e_fret if 1 <= e_fret <= 6 else 45 + ((root_pc - _OPEN_STRING_PCS[1]) % 12)
    return [root + i for i in quality_to_intervals(quality)]


def _barre_voicing(root_pc: int, quality: str) -> list[int]:
    family = _shape_family(quality)
    chord_pcs = {i % 12 for i in quality_to_intervals(quality)}
    family_pcs = {i % 12 for i in _E_SHAPE[family]}
    if not family_pcs <= chord_pcs:
        # A maj/dom7 barre would inject a 3rd/5th/7th the chord lacks and clash
        # with the piano — voice the actual chord tones instead.
        return _stack_intervals(root_pc, quality)
    e_fret = (root_pc - _OPEN_STRING_PCS[0]) % 12
    if 1 <= e_fret <= 6:
        root = 40 + e_fret
        stack = _E_SHAPE[family]
    else:
        a_fret = (root_pc - _OPEN_STRING_PCS[1]) % 12
        root = 45 + a_fret
        stack = _A_SHAPE[family]
    return [root + i for i in stack]


def _apply_slash_bass(notes: list[int], bass_pc: int) -> list[int]:
    upper = notes[1:] if len(notes) > 1 else notes
    bass = 40 + ((bass_pc - _OPEN_STRING_PCS[0]) % 12)  # 40..51
    while upper and bass >= min(upper):
        bass -= 12
    if bass < 28:
        bass += 12
    return sorted([bass, *upper])


def guitar_voicing(root_pc: int, quality: str,
                   bass_pc: int | None = None) -> list[int]:
    """MIDI notes (low->high) for a chord's SHAPE, before any capo offset.

    Open-chord dictionary first, then E/A barre shapes; slash basses replace
    the lowest string. Extensions unsupported by a barre fall back to the
    triad/7 shape (the piano carries the colour tones).
    """
    notes = OPEN_BY_KEY.get((root_pc % 12, quality))
    if notes is None:
        notes = _barre_voicing(root_pc % 12, quality)
    notes = sorted(notes)
    if bass_pc is not None and bass_pc % 12 != root_pc % 12:
        notes = _apply_slash_bass(notes, bass_pc)
    return notes


@functools.lru_cache(maxsize=512)
def _pychord_intervals(quality: str) -> tuple[int, ...] | None:
    """Ask pychord for the interval set of a quality we don't hand-table.

    Returns pitch classes relative to the root (folded into one octave), or
    None if pychord can't parse it.
    """
    try:
        from pychord import Chord
    except ImportError:
        return None
    try:
        components = Chord("C" + quality).components()
    except Exception:
        return None
    intervals: list[int] = []
    for name in components:
        pc = NOTE_TO_PC.get(name)
        if pc is None:
            return None
        if pc not in intervals:
            intervals.append(pc)
    return tuple(intervals) if intervals else None


def quality_to_intervals(quality: str) -> list[int]:
    """Map a chord quality to semitone intervals above the root.

    Explicit table first, then pychord for exotic symbols, and only then a
    plain triad with a logged warning — never a crash on user input.
    """
    if quality in QUALITY_INTERVALS:
        return QUALITY_INTERVALS[quality]
    from_pychord = _pychord_intervals(quality)
    if from_pychord is not None:
        return list(from_pychord)
    logger.warning("Unknown chord quality %r — voicing as plain triad", quality)
    if quality.startswith("m") and not quality.startswith("maj"):
        return QUALITY_INTERVALS["m"]
    return QUALITY_INTERVALS[""]
