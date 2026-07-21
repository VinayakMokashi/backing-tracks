"""Rhythmic pattern data — the musician-developer's tuning surface.

Pure data + the STYLES registry. Engines read these tables and never hardcode
musical constants. A "slot" is one eighth note; a bar has
``numerator * 8 // denominator`` slots (8 for 4/4, 6 for 3/4 and 6/8).

Strum events:  (slot, event, velocity, duration_slots)
  event: 'D' downstrum, 'U' upstrum, 'X' muted chuck,
         'BR' bass root string, 'B5' bass fifth string
Piano events:  (slot, hand, spec, velocity, duration_slots)
  hand 'LH' spec is a list of tokens ('R2', 'R2+7', 'R2+12'); 'RH' spec is
  'triad' (the voice-led right-hand inversion). 'ARP' rows are expanded by the
  piano engine.
Drum events:   {'kick'|'snare'|'stick'|'hat': [(slot, gm_note, velocity), ...]}
  'hat' may be the string 'eighths' / 'quarters' — expanded by the drum engine.
"""
from __future__ import annotations

STRUM_PATTERNS: dict[str, list[tuple[float, str, int, float]]] = {
    # D DU UDU — the universal pop/folk strum
    "pop_44": [(0, "D", 105, 2), (2, "D", 88, 1), (3, "U", 76, 1),
               (5, "U", 76, 1), (6, "D", 96, 1), (7, "U", 78, 1)],
    "folk_boomchick_44": [(0, "BR", 100, 2), (2, "D", 85, 1), (3, "U", 72, 1),
                          (4, "B5", 95, 2), (6, "D", 85, 1), (7, "U", 72, 1)],
    "ballad_44": [(0, "D", 98, 4), (4, "D", 88, 3), (7, "U", 70, 1)],
    "muted_pop_44": [(0, "D", 100, 2), (2, "X", 82, 0.25), (3, "U", 74, 1),
                     (4, "X", 90, 0.25), (5, "U", 74, 1), (6, "D", 88, 1),
                     (7, "U", 76, 1)],
    "waltz_34": [(0, "BR", 100, 2), (2, "D", 82, 2), (4, "D", 76, 1),
                 (5, "U", 66, 1)],
    "six_eight_68": [(0, "D", 102, 2), (2, "U", 72, 1), (3, "D", 88, 2),
                     (5, "U", 72, 1)],
}

# 'ARP' expands to one note per slot from the token list, cycling.
PIANO_PATTERNS: dict[str, list[tuple]] = {
    "block_44": [(0, "LH", ["R2", "R2+12"], 92, 4), (0, "RH", "triad", 88, 2),
                 (2, "RH", "triad", 78, 2)],
    "broken8ths_44": [(0, "ARP",
                       ["R2", "R2+7", "R2+12", "T3", "T5", "T3", "R2+12", "R2+7"],
                       78, 1)],
    "ballad_44": [(0, "LH", ["R2"], 90, 2), (2, "LH", ["R2+7"], 84, 2),
                  (1, "RH", "triad", 76, 1), (3, "RH", "triad", 74, 1)],
    "waltz_34": [(0, "LH", ["R2"], 92, 1), (1, "RH", "triad", 76, 1),
                 (2, "RH", "triad", 70, 1)],
    "arp_68": [(0, "ARP", ["R2", "R2+7", "R2+12", "T3", "R2+12", "R2+7"], 74, 1)],
}

# Fingerpick events: (slot, selector, velocity, duration_slots)
# selector picks one note from the chord voicing (sorted low->high):
#   'b'  = bass (lowest)        'b2' = second-lowest (alternating thumb)
#   't0' = highest string       't1' = 2nd from top     't2' = 3rd from top
# Notes ring longer than a slot (legato) — that sustain is what reads as
# fingerpicking rather than a plucked stab.
FINGERPICK_PATTERNS: dict[str, list[tuple[float, str, int, float]]] = {
    # flowing bass -> ascending treble arpeggio, twice per bar (ballad staple)
    "ballad_44": [(0, "b", 102, 3), (1, "t2", 80, 3), (2, "t1", 84, 3),
                  (3, "t0", 78, 3), (4, "b2", 94, 3), (5, "t2", 80, 3),
                  (6, "t1", 84, 3), (7, "t0", 78, 3)],
    "six_eight_68": [(0, "b", 102, 3), (1, "t2", 78, 2), (2, "t1", 82, 2),
                     (3, "b2", 92, 3), (4, "t2", 78, 2), (5, "t0", 80, 2)],
    "waltz_34": [(0, "b", 102, 3), (2, "t1", 82, 2), (4, "t0", 80, 2)],
}


def fingerpick_pattern(style: str) -> list[tuple[float, str, int, float]]:
    _, _, _, _, ts = STYLES.get(style, STYLES[DEFAULT_STYLE])
    if ts == (6, 8):
        return FINGERPICK_PATTERNS["six_eight_68"]
    if ts == (3, 4):
        return FINGERPICK_PATTERNS["waltz_34"]
    return FINGERPICK_PATTERNS["ballad_44"]


DRUM_PATTERNS: dict[str, dict] = {
    "pop_44": {"kick": [(0, 36, 100), (4, 36, 96)],
               "snare": [(2, 38, 98), (6, 38, 98)], "hat": "eighths"},
    "ballad_44": {"kick": [(0, 36, 92)], "stick": [(2, 37, 72), (6, 37, 72)],
                  "hat": "quarters"},
    "waltz_34": {"kick": [(0, 36, 95)], "stick": [(2, 37, 68), (4, 37, 64)]},
    "six_eight_68": {"kick": [(0, 36, 98)], "snare": [(3, 38, 92)],
                     "hat": "eighths"},
}

# style -> (strum, piano, drums, default_bpm, time_signature)
STYLES: dict[str, tuple[str, str, str, float, tuple[int, int]]] = {
    "pop": ("pop_44", "block_44", "pop_44", 100.0, (4, 4)),
    "folk": ("folk_boomchick_44", "broken8ths_44", "pop_44", 104.0, (4, 4)),
    "ballad": ("ballad_44", "ballad_44", "ballad_44", 72.0, (4, 4)),
    "muted_pop": ("muted_pop_44", "block_44", "pop_44", 100.0, (4, 4)),
    "waltz": ("waltz_34", "waltz_34", "waltz_34", 90.0, (3, 4)),
    "six_eight": ("six_eight_68", "arp_68", "six_eight_68", 90.0, (6, 8)),
}

DEFAULT_STYLE = "pop"


def style_patterns(style: str) -> tuple[str, str, str]:
    strum, piano, drums, _, _ = STYLES.get(style, STYLES[DEFAULT_STYLE])
    return strum, piano, drums
