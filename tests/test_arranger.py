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


def test_piano_voices_both_chords_in_two_chord_bar():
    # One 4/4 bar: C on beats 1-2, G on beats 3-4. The piano must voice G in
    # the second half, not stay on C (or go silent).
    song = Song(id="_t", title="T", bpm=100.0, sections=[Section(name="A", chords=[
        ChordEvent("C", 0.0, 2.0), ChordEvent("G", 2.0, 2.0)])])
    pm = arrange(song, RenderOptions(guitar=False, drums=False, count_in=False))
    piano = [i for i in pm.instruments if i.name == "Piano"][0]
    sec_per_slot = 30.0 / 100.0
    second_half = [n for n in piano.notes if n.start >= 4 * sec_per_slot - 1e-6]
    assert second_half, "piano is silent in the second half of the bar"
    assert {n.pitch % 12 for n in second_half} & {7, 11, 2}  # some G-major tone


def test_guitar_sus_dim_use_real_tones_not_major_triad():
    from backtrack.chords import parse_symbol
    for sym, allowed in [("A7sus4", {9, 2, 4, 7}), ("Bdim", {11, 2, 5}),
                         ("Csus2", {0, 2, 7}), ("Caug", {0, 4, 8})]:
        p = parse_symbol(sym)
        pcs = {n % 12 for n in guitar_voicing(p.root_pc, p.quality, p.bass_pc)}
        assert pcs <= allowed, f"{sym}: {pcs} introduces tones outside {allowed}"


def test_fingerpick_is_sparser_single_notes():
    song = _song()
    strum = arrange(song, RenderOptions(guitar=True, piano=False, count_in=False,
                                        style="ballad", guitar_technique="strum"))
    pick = arrange(song, RenderOptions(guitar=True, piano=False, count_in=False,
                                       style="ballad", guitar_technique="fingerpick"))
    g_strum = [i for i in strum.instruments if i.name == "Guitar"][0]
    g_pick = [i for i in pick.instruments if i.name == "Guitar"][0]
    # fingerpicking plays one note at a time -> far fewer simultaneous onsets
    by_start = {}
    for n in g_pick.notes:
        by_start.setdefault(round(n.start, 2), 0)
        by_start[round(n.start, 2)] += 1
    assert max(by_start.values()) == 1               # never a chord, always single plucks
    assert len(g_pick.notes) < len(g_strum.notes)    # sparser than strumming


def test_resolve_capo_keeps_sounding_invariant():
    for capo in (0, 2, 5):
        for transpose in (-4, 0, 3, 12):
            shift, capo_out = resolve_capo(capo, transpose, "keep")
            assert shift + capo_out == capo + transpose
    assert resolve_capo(2, 3, "none") == (5, 0)
