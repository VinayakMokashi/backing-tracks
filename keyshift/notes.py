"""Note-name / pitch-class helpers."""
from __future__ import annotations

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

NOTE_TO_PC = {
    "C": 0, "B#": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
    "Fb": 4, "F": 5, "E#": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10, "B": 11, "Cb": 11,
}
_FLAT_KEYS = {5, 10, 3, 8, 1}  # F Bb Eb Ab Db spelled with flats


def key_name(pitch_class: int, minor: bool = False) -> str:
    names = FLAT_NAMES if pitch_class % 12 in _FLAT_KEYS else SHARP_NAMES
    return f"{names[pitch_class % 12]}{'m' if minor else ''}"


def parse_note(name: str) -> tuple[int, bool]:
    """'G', 'F#', 'Bb', 'Em', 'C#m' -> (pitch_class, is_minor)."""
    s = name.strip().replace("♯", "#").replace("♭", "b")
    minor = s.lower().endswith("m") and not s.lower().endswith("maj")
    root = s[:-1] if minor and len(s) > 1 else s
    root = (root[0].upper() + root[1:]) if root else root
    if root not in NOTE_TO_PC:
        raise ValueError(f"Unrecognised key: {name!r}")
    return NOTE_TO_PC[root], minor
