from backtrack.arrange import arrange, resolve_capo
from backtrack.model import ChordEvent, RenderOptions, Section, Song


def _song(bpm: float = 100.0) -> Song:
    return Song(
        id="_t", title="T",
        sections=[Section(name="A", chords=[
            ChordEvent("C", 0.0, 4.0), ChordEvent("Am", 4.0, 4.0),
            ChordEvent("F", 8.0, 4.0), ChordEvent("G", 12.0, 4.0),
        ], bars=4)],
        bpm=bpm,
    )


def test_arrange_basic_invariants():
    pm = arrange(_song(), RenderOptions())
    notes = [n for inst in pm.instruments for n in inst.notes]
    assert notes
    for n in notes:
        assert 0 <= n.velocity <= 127
        assert 0 <= n.pitch <= 127
        assert n.start >= 0 and n.end > n.start


def test_count_in_adds_drum_track_and_offsets_start():
    with_count = arrange(_song(), RenderOptions(count_in=True))
    without = arrange(_song(), RenderOptions(count_in=False))
    assert any(inst.is_drum for inst in with_count.instruments)
    assert not any(inst.is_drum for inst in without.instruments)
    piano_with = [i for i in with_count.instruments if not i.is_drum][0]
    piano_without = [i for i in without.instruments if not i.is_drum][0]
    first_with = min(n.start for n in piano_with.notes)
    first_without = min(n.start for n in piano_without.notes)
    assert first_with > first_without  # count-in pushes the music later


def test_am_has_no_unison_duplicate():
    pm = arrange(_song(), RenderOptions(count_in=False))
    piano = [i for i in pm.instruments if not i.is_drum][0]
    am = sorted(n.pitch for n in piano.notes if abs(n.start - 4.0 * 0.6) < 0.2)
    assert len(am) == len(set(am))  # no two notes at the same pitch


def test_transpose_shifts_pitches_up():
    base = arrange(_song(), RenderOptions(count_in=False))
    up = arrange(_song(), RenderOptions(count_in=False, transpose=2))
    base_first = [i for i in base.instruments if not i.is_drum][0].notes[0].pitch
    up_first = [i for i in up.instruments if not i.is_drum][0].notes[0].pitch
    assert up_first == base_first + 2


def test_resolve_capo_keeps_sounding_invariant():
    for capo in (0, 2, 5):
        for transpose in (-4, 0, 3, 12):
            shift, capo_out = resolve_capo(capo, transpose, "keep")
            assert shift + capo_out == capo + transpose
    # 'none' never uses a capo
    assert resolve_capo(2, 3, "none") == (5, 0)
