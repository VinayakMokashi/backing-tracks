"""Optional drum engine: GM kit on channel index 9 (is_drum=True).

Kick 36, snare 38, side-stick 37, closed hat 42, crash 49. Patterns are the
per-style tables in patterns.py; a crash lands on beat 1 of each new section.
"""
from __future__ import annotations

import random

import pretty_midi

_HAT, _CRASH = 42, 49


def _hat_slots(spec: str, slots_per_bar: int):
    if spec == "eighths":
        return [(s, 78 if s % 2 == 0 else 62) for s in range(slots_per_bar)]
    if spec == "quarters":
        return [(s, 55) for s in range(0, slots_per_bar, 2)]
    return []


def build_track(pattern: dict, slots_per_bar: int, total_bars: int,
                sec_per_slot: float, t0: float, section_start_bars: set[int],
                rng: random.Random) -> pretty_midi.Instrument:
    inst = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

    def hit(slot, note, vel):
        start = t0 + slot * sec_per_slot
        inst.notes.append(pretty_midi.Note(
            velocity=max(1, min(127, vel + rng.randint(-4, 4))),
            pitch=note, start=start, end=start + 0.08))

    for bar in range(total_bars):
        base = bar * slots_per_bar
        for voice in ("kick", "snare", "stick"):
            for slot, note, vel in pattern.get(voice, []):
                if slot < slots_per_bar:
                    hit(base + slot, note, vel)
        for slot, vel in _hat_slots(pattern.get("hat", ""), slots_per_bar):
            hit(base + slot, _HAT, vel)
        if bar in section_start_bars:
            hit(base, _CRASH, 105)
    return inst
