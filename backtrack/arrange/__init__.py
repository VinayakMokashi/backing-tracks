"""Arranger: arrange(song, opts) -> pretty_midi.PrettyMIDI — the one seam.

M1 scope: piano block chords + optional count-in, proving timing, transposition
and rendering end-to-end. The guitar strum engine (M3) and piano comping engine
(M4) replace the track builders behind this same seam.
"""
from __future__ import annotations

import pretty_midi

from .. import chords
from ..model import ChordEvent, RenderOptions, Song
from .voicings import quality_to_intervals

_STICK = 37  # GM side stick, used for the count-in


def resolve_capo(capo: int, transpose: int, capo_mode: str) -> tuple[int, int]:
    """Split a transpose request into (symbol_shift, capo_out).

    symbol_shift is applied to the written SHAPE chords; capo_out is the capo
    fret the guitar plays with. Their sum is always capo + transpose, so the
    SOUNDING pitch is invariant across modes — only the fingering/display
    change. 'keep' preserves the written shapes whenever the resulting capo
    lands in a playable 0-11 range. 'auto' behaves like 'keep' until the M6
    open-shape scorer ships.
    """
    total = capo + transpose
    if capo_mode == "none":
        return total, 0
    if 0 <= total <= 11:
        return 0, total          # keep written shapes, move the capo
    return total, 0              # capo out of range -> transpose the shapes


def _flatten(song: Song) -> list[tuple[float, ChordEvent]]:
    """Sections (honoring repeat) -> [(absolute_beat, event)] timeline."""
    numerator = song.time_signature[0]
    timeline: list[tuple[float, ChordEvent]] = []
    cursor = 0.0
    for section in song.sections:
        section_beats = max(
            (ev.beat + ev.duration_beats for ev in section.chords),
            default=float(section.bars * numerator),
        )
        for _ in range(max(1, section.repeat)):
            for ev in section.chords:
                timeline.append((cursor + ev.beat, ev))
            cursor += section_beats
    return timeline


def arrange(song: Song, opts: RenderOptions) -> pretty_midi.PrettyMIDI:
    bpm = opts.bpm or song.bpm
    numerator, denominator = song.time_signature
    sec_per_beat = (60.0 / bpm) * (4.0 / denominator)

    # M1: piano plays SOUNDING chords — shape symbols shifted by capo + transpose.
    total_shift = song.capo + opts.transpose

    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    pm.time_signature_changes.append(
        pretty_midi.TimeSignature(numerator, denominator, 0.0)
    )

    t0 = 0.0
    if opts.count_in:
        clicks = pretty_midi.Instrument(program=0, is_drum=True, name="Count-in")
        for beat in range(numerator):
            start = beat * sec_per_beat
            velocity = 100 if beat == 0 else 78
            clicks.notes.append(
                pretty_midi.Note(velocity=velocity, pitch=_STICK,
                                 start=start, end=start + 0.1)
            )
        pm.instruments.append(clicks)
        t0 = numerator * sec_per_beat

    piano = pretty_midi.Instrument(program=0, name="Piano")
    for abs_beat, ev in _flatten(song):
        parsed = chords.parse_symbol(ev.symbol)
        if parsed is None or parsed.is_rest:
            continue
        root_pc = (parsed.root_pc + total_shift) % 12
        bass_pc = (
            (parsed.bass_pc + total_shift) % 12 if parsed.bass_pc is not None else root_pc
        )
        start = t0 + abs_beat * sec_per_beat
        end = start + max(ev.duration_beats * sec_per_beat - 0.02, 0.05)

        # Left hand: bass note in 36-47 plus its octave above.
        lh_root = 36 + bass_pc
        lh_pitches = (lh_root, lh_root + 12)
        for pitch in lh_pitches:
            piano.notes.append(
                pretty_midi.Note(velocity=88, pitch=pitch, start=start, end=end)
            )
        # Right hand: chord tones centred around middle C.
        rh_root = 60 + root_pc
        if rh_root > 67:
            rh_root -= 12
        for interval in quality_to_intervals(parsed.quality):
            pitch = rh_root + interval
            if pitch in lh_pitches:
                continue  # root already sounded by the LH octave — avoid unison stacking
            piano.notes.append(
                pretty_midi.Note(velocity=80, pitch=pitch, start=start, end=end)
            )
    pm.instruments.append(piano)
    return pm
