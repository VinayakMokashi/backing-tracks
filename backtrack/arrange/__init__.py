"""Arranger: arrange(song, opts) -> pretty_midi.PrettyMIDI — the one seam.

Flattens sections (honoring repeat) into an absolute eighth-note-slot timeline,
resolves transpose + capo into shape/sounding chord spans, and hands each
enabled track to its engine (guitar strum, piano comping, optional drums), with
a leading count-in click.
"""
from __future__ import annotations

import math
import random

import pretty_midi

from .. import chords
from ..model import ParsedChord, RenderOptions, Song
from . import drums, guitar, piano, patterns

_STICK = 37  # GM side stick, used for the count-in
_SEED = 1337  # fixed so a given (song, options) always renders identically


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


def _shift(parsed: ParsedChord | None, n: int) -> ParsedChord | None:
    if parsed is None:
        return None
    if parsed.is_rest:
        return parsed
    return ParsedChord(
        root_pc=(parsed.root_pc + n) % 12,
        quality=parsed.quality,
        bass_pc=(parsed.bass_pc + n) % 12 if parsed.bass_pc is not None else None,
    )


def _timeline(song: Song, slots_per_beat: float):
    """Return (spans, total_bars, section_start_bars).

    spans: list of (start_slot, end_slot, ParsedChord|None) in absolute slots.
    """
    numerator = song.time_signature[0]
    slots_per_bar = numerator * slots_per_beat
    spans: list[tuple[float, float, ParsedChord | None]] = []
    section_start_bars: set[int] = set()
    cursor_beats = 0.0
    for section in song.sections:
        section_beats = max(
            (ev.beat + ev.duration_beats for ev in section.chords),
            default=float(section.bars * numerator),
        )
        for _ in range(max(1, section.repeat)):
            section_start_bars.add(int(round(cursor_beats / numerator)))
            for ev in section.chords:
                start_slot = (cursor_beats + ev.beat) * slots_per_beat
                end_slot = start_slot + ev.duration_beats * slots_per_beat
                spans.append((start_slot, end_slot, chords.parse_symbol(ev.symbol)))
            cursor_beats += section_beats
    max_end = max((e for _, e, _ in spans), default=0.0)
    total_bars = max(1, math.ceil(max_end / slots_per_bar - 1e-9))
    return spans, total_bars, section_start_bars


def _chord_at(spans):
    def lookup(slot):
        for start, end, chord in spans:
            if start <= slot < end:
                return chord
        return None
    return lookup


def arrange(song: Song, opts: RenderOptions) -> pretty_midi.PrettyMIDI:
    style = opts.style or song.style
    strum_name, piano_name, drum_name = patterns.style_patterns(style)
    bpm = opts.bpm or song.bpm
    numerator, denominator = song.time_signature
    sec_per_beat = (60.0 / bpm) * (4.0 / denominator)
    sec_per_slot = 30.0 / bpm            # one eighth-note slot
    slots_per_beat = 8 / denominator
    slots_per_bar = int(round(numerator * slots_per_beat))
    rng = random.Random(_SEED)

    symbol_shift, capo_out = resolve_capo(song.capo, opts.transpose, opts.capo_mode)

    spans, total_bars, section_start_bars = _timeline(song, slots_per_beat)
    shape_spans = [(s, e, _shift(c, symbol_shift)) for s, e, c in spans]
    sounding_spans = [(s, e, _shift(c, symbol_shift + capo_out)) for s, e, c in spans]

    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    pm.time_signature_changes.append(
        pretty_midi.TimeSignature(numerator, denominator, 0.0))

    t0 = 0.0
    if opts.count_in:
        clicks = pretty_midi.Instrument(program=0, is_drum=True, name="Count-in")
        for beat in range(numerator):
            start = beat * sec_per_beat
            clicks.notes.append(pretty_midi.Note(
                velocity=100 if beat == 0 else 78, pitch=_STICK,
                start=start, end=start + 0.1))
        pm.instruments.append(clicks)
        t0 = numerator * sec_per_beat

    if opts.guitar:
        pm.instruments.append(guitar.build_track(
            opts.guitar_program, patterns.STRUM_PATTERNS[strum_name],
            _chord_at(shape_spans), slots_per_bar, total_bars, sec_per_slot,
            t0, capo_out, rng))
    if opts.piano:
        pm.instruments.append(piano.build_track(
            0, patterns.PIANO_PATTERNS[piano_name], sounding_spans,
            slots_per_bar, total_bars, sec_per_slot, t0))
    if opts.drums:
        pm.instruments.append(drums.build_track(
            patterns.DRUM_PATTERNS[drum_name], slots_per_bar, total_bars,
            sec_per_slot, t0, section_start_bars, rng))

    return pm
