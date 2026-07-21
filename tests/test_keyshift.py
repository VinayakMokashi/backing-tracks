import pytest

from keyshift.notes import key_name, parse_note
from keyshift.pitch import shortest_shift


def test_parse_note():
    assert parse_note("G") == (7, False)
    assert parse_note("F#") == (6, False)
    assert parse_note("Bb") == (10, False)
    assert parse_note("Em") == (4, True)
    assert parse_note("C#m") == (1, True)
    with pytest.raises(ValueError):
        parse_note("H7")


def test_key_name_spelling():
    assert key_name(2, False) == "D"
    assert key_name(4, True) == "Em"
    assert key_name(10, False) == "Bb"     # flat key spelled with a flat
    assert key_name(6, False) == "F#"


def test_shortest_shift_is_within_a_tritone():
    assert shortest_shift(4, 7) == 3       # E -> G up
    assert shortest_shift(2, 7) == 5       # D -> G up
    assert shortest_shift(0, 11) == -1     # C -> B down (shorter than +11)
    assert shortest_shift(7, 2) == -5      # G -> D down
    for a in range(12):
        for b in range(12):
            assert -6 <= shortest_shift(a, b) <= 6
