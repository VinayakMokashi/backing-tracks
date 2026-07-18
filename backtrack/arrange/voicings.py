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
