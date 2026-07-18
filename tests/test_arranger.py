from backtrack.arrange import arrange, resolve_capo
from backtrack.arrange.piano import _voice_lead
from backtrack.arrange.voicings import guitar_voicing
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


def _notes(pm):
    return [n for inst in pm.instruments for n in inst.notes]


def test_arrange_basic_invariants():
    pm = arrange(_song(), RenderOptions(drums=True))
    notes = _notes(pm)
    assert notes
    for n in notes:
        assert 0 <= n.velocity <= 127
        assert 0 <= n.pitch <= 127
        assert n.start >= 0 and n.end > n.start


def test_instrument_toggles():
    guitar_only = arrange(_song(), RenderOptions(guitar=True, piano=False,
                                                 count_in=False))
    names = {i.name for i in guitar_only.instruments}
    assert "Guitar" in names and "Piano" not in names
    both = arrange(_song(), RenderOptions(guitar=True, piano=True, count_in=False))
    assert {"Guitar", "Piano"} <= {i.name for i in both.instruments}


def test_count_in_offsets_music_start():
    with_ci = arrange(_song(), RenderOptions(count_in=True, piano=False))
    without = arrange(_song(), RenderOptions(count_in=False, piano=False))
    gwith = [i for i in with_ci.instruments if i.name == "Guitar"][0]
    gwithout = [i for i in without.instruments if i.name == "Guitar"][0]
    assert min(n.start for n in gwith.notes) > min(n.start for n in gwithout.notes)


def test_transpose_shifts_everything_up():
    base = arrange(_song(), RenderOptions(count_in=False))
    up = arrange(_song(), RenderOptions(count_in=False, transpose=2))
    assert min(n.pitch for n in _notes(up)) == min(n.pitch for n in _notes(base)) + 2


def test_piano_voice_leading_small_leaps():
    # C -> Am -> F -> G tops should never jump more than a fourth (5 semitones)
    prev = None
    tops = []
    for sym, quality in [(0, ""), (9, "m"), (5, ""), (7, "")]:
        rh = _voice_lead(sym, quality, prev)
        prev = rh[-1]
        tops.append(rh[-1])
    for a, b in zip(tops, tops[1:]):
        assert abs(a - b) <= 5


def test_guitar_voicing_is_guitar_shaped():
    # open C uses the dictionary voicing; a barre chord (F) spans >= an octave
    assert guitar_voicing(0, "") == sorted([48, 52, 55, 60, 64])
    f = guitar_voicing(5, "")
    assert max(f) - min(f) >= 12 and len(f) >= 5


def test_resolve_capo_keeps_sounding_invariant():
    for capo in (0, 2, 5):
        for transpose in (-4, 0, 3, 12):
            shift, capo_out = resolve_capo(capo, transpose, "keep")
            assert shift + capo_out == capo + transpose
    assert resolve_capo(2, 3, "none") == (5, 0)
