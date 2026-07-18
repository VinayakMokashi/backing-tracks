"""Guitar strum engine: turns a strum pattern + chord timeline into MIDI.

Down/up strums are staggered note-ons across the voicing (down = low->high,
up = top strings high->low); muted chucks are short gated notes; boom-chick
patterns pick the bass root/fifth. Voicings come from voicings.guitar_voicing
(built from written shapes) and every guitar note is offset by the capo.
"""
from __future__ import annotations

import random

import pretty_midi

from ..model import ParsedChord
from .voicings import guitar_voicing

_STAGGER = 0.015   # seconds between successive strings in a strum
_JITTER = 0.004    # +/- timing humanize per note
_CHUCK_LEN = 0.06  # muted-hit note length


def _clamp_vel(v: float) -> int:
    return max(1, min(127, int(round(v))))


def _strum(inst, notes, base_vel, start, end, rng, *, high_to_low=False):
    ordered = sorted(notes, reverse=high_to_low)
    for i, pitch in enumerate(ordered):
        onset = start + i * _STAGGER + rng.uniform(-_JITTER, _JITTER)
        vel = _clamp_vel(base_vel - i * 2 + rng.randint(-5, 5))
        note_end = max(end, onset + 0.05)
        inst.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch,
                                           start=max(0.0, onset), end=note_end))


def _bass_note(voicing: list[int], fifth: bool) -> int:
    root = voicing[0]
    if not fifth:
        return root
    candidate = root + 7
    return candidate - 12 if candidate > 55 else candidate


def emit(inst, event: str, base_vel: int, voicing: list[int],
         start: float, dur: float, rng: random.Random) -> None:
    end = start + dur
    if event == "D":
        _strum(inst, voicing, base_vel, start, end, rng)
    elif event == "U":
        top = sorted(voicing)[-4:]
        _strum(inst, top, base_vel, start, end, rng, high_to_low=True)
    elif event == "X":
        for pitch in voicing:
            onset = start + rng.uniform(0, _JITTER)
            inst.notes.append(pretty_midi.Note(
                velocity=_clamp_vel(base_vel - 8), pitch=pitch,
                start=max(0.0, onset), end=onset + _CHUCK_LEN))
    elif event in ("BR", "B5"):
        pitch = _bass_note(voicing, fifth=event == "B5")
        inst.notes.append(pretty_midi.Note(velocity=_clamp_vel(base_vel),
                                           pitch=pitch, start=start, end=end))


def build_track(program: int, pattern, chord_at, slots_per_bar: int,
                total_bars: int, sec_per_slot: float, t0: float,
                capo_out: int, rng: random.Random) -> pretty_midi.Instrument:
    inst = pretty_midi.Instrument(program=program, name="Guitar")
    for bar in range(total_bars):
        bar_start = bar * slots_per_bar
        for slot, event, vel, dur in pattern:
            if slot >= slots_per_bar:
                continue
            chord: ParsedChord | None = chord_at(bar_start + slot)
            if chord is None or chord.is_rest:
                continue
            voicing = [n + capo_out for n in
                       guitar_voicing(chord.root_pc, chord.quality, chord.bass_pc)]
            start = t0 + (bar_start + slot) * sec_per_slot
            emit(inst, event, vel, voicing, start, dur * sec_per_slot, rng)
    return inst
