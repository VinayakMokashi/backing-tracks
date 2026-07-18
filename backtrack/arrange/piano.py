"""Piano comping engine: voice-led right hand, root/fifth left hand, pedal.

The right hand picks the inversion in C4-C6 whose top note moves least from the
previous chord; the left hand plays the bass root (and fifth/octave per
pattern); the sustain pedal (CC64) is held per chord and lifted just before
each change — the single biggest realism win.
"""
from __future__ import annotations

import pretty_midi

from ..model import ParsedChord
from .voicings import quality_to_intervals

_RH_LO, _RH_HI = 60, 84   # C4..C6
_LH_LO = 36               # bass register floor
_SUSTAIN = 64


def _voice_lead(root_pc: int, quality: str, prev_top: int | None) -> list[int]:
    tones = sorted({(root_pc + i) % 12 for i in quality_to_intervals(quality)[:4]})
    base = sorted(_RH_LO + ((pc - _RH_LO) % 12) for pc in tones)
    best: tuple[int, list[int]] | None = None
    cur = base
    for _ in range(len(cur)):
        if cur[-1] <= _RH_HI:
            top = cur[-1]
            cost = abs(top - (prev_top if prev_top is not None else 67))
            if best is None or cost < best[0]:
                best = (cost, sorted(cur))
        cur = sorted(cur[1:] + [cur[0] + 12])
    return best[1] if best else [_RH_LO + root_pc % 12]


def _lh_root(chord: ParsedChord) -> int:
    pc = chord.bass_pc if chord.bass_pc is not None else chord.root_pc
    return _LH_LO + (pc % 12)          # 36..47


def _token_pitch(token: str, lh_root: int, third: int, fifth: int) -> int:
    if token == "R2":
        return lh_root
    if token == "R2+7":
        return lh_root + 7
    if token == "R2+12":
        return lh_root + 12
    if token == "T3":
        return third
    if token == "T5":
        return fifth
    return lh_root


def _spans_with_voicing(spans):
    """Precompute LH root + voice-led RH notes for each sounding chord span."""
    voiced = []
    prev_top: int | None = None
    for start, end, chord in spans:
        if chord is None or chord.is_rest:
            voiced.append(None)
            continue
        rh = _voice_lead(chord.root_pc, chord.quality, prev_top)
        prev_top = rh[-1]
        intervals = quality_to_intervals(chord.quality)
        third_pc = (chord.root_pc + (intervals[1] if len(intervals) > 1 else 4)) % 12
        fifth_pc = (chord.root_pc + (intervals[2] if len(intervals) > 2 else 7)) % 12
        third = 60 + third_pc
        fifth = 60 + fifth_pc
        voiced.append({"start": start, "end": end, "lh_root": _lh_root(chord),
                       "rh": rh, "third": third, "fifth": fifth})
    return voiced


def _active(voiced, slot):
    for v in voiced:
        if v is not None and v["start"] <= slot < v["end"]:
            return v
    return None


def build_track(program: int, pattern, spans, slots_per_bar: int, total_bars: int,
                sec_per_slot: float, t0: float) -> pretty_midi.Instrument:
    inst = pretty_midi.Instrument(program=program, name="Piano")
    voiced = _spans_with_voicing(spans)

    # Sustain pedal: down at each chord onset, up 20 ms before this chord's own
    # span ends — so a following rest (N.C.) actually silences the piano.
    for v in (v for v in voiced if v is not None):
        down_t = t0 + v["start"] * sec_per_slot
        up_t = t0 + v["end"] * sec_per_slot - 0.02
        inst.control_changes.append(
            pretty_midi.ControlChange(_SUSTAIN, 127, max(0.0, down_t)))
        inst.control_changes.append(
            pretty_midi.ControlChange(_SUSTAIN, 0, max(down_t + 0.05, up_t)))

    # Drive each bar by chord ONSETS so a chord that begins mid-bar is voiced
    # (mirrors the guitar engine, which looks up the chord per slot).
    for bar in range(total_bars):
        bar_start = bar * slots_per_bar
        bar_end = bar_start + slots_per_bar
        onsets = sorted({int(v["start"]) for v in voiced if v is not None
                         and bar_start <= v["start"] < bar_end} | {bar_start})
        for idx, onset in enumerate(onsets):
            seg_end = onsets[idx + 1] if idx + 1 < len(onsets) else bar_end
            for row in pattern:
                slot, kind = row[0], row[1]
                if onset + slot >= seg_end:
                    continue
                v = _active(voiced, onset + slot)
                if v is None:
                    continue
                if kind == "ARP":
                    _emit_arp(inst, row, voiced, onset, seg_end - onset,
                              sec_per_slot, t0)
                else:
                    _emit_slot(inst, row, v, onset, sec_per_slot, t0)
    return inst


def _emit_slot(inst, row, v, bar_start, sec_per_slot, t0):
    slot, kind, spec, vel, dur = row
    start = t0 + (bar_start + slot) * sec_per_slot
    end = start + max(dur * sec_per_slot - 0.02, 0.05)
    if kind == "LH":
        for token in spec:
            pitch = _token_pitch(token, v["lh_root"], v["third"], v["fifth"])
            inst.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch,
                                               start=start, end=end))
    elif kind == "RH":  # spec == 'triad'
        for pitch in v["rh"]:
            inst.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch,
                                               start=start, end=end))


def _emit_arp(inst, row, voiced, seg_start, seg_slots, sec_per_slot, t0):
    _slot, _kind, tokens, vel, _dur = row
    for i in range(seg_slots):
        v = _active(voiced, seg_start + i)   # re-resolve per slot: mid-bar changes
        if v is None:
            continue
        token = tokens[i % len(tokens)]
        pitch = _token_pitch(token, v["lh_root"], v["third"], v["fifth"])
        accent = 8 if i in (0, seg_slots // 2) else 0
        start = t0 + (seg_start + i) * sec_per_slot
        end = start + sec_per_slot * 1.1  # legato overlap into the next slot
        inst.notes.append(pretty_midi.Note(velocity=min(127, vel + accent),
                                           pitch=pitch, start=start, end=end))
