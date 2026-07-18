from backtrack import chords


def test_normalize_variants():
    assert chords.normalize("C♯m7") == "C#m7"
    assert chords.normalize("Bb") == "Bb"
    assert chords.normalize("C6/9") == "C69"
    assert chords.normalize("C(add9)") == "Cadd9"
    assert chords.normalize("H7") == "B7"
    assert chords.normalize("  Am 7 ") == "Am7"


def test_parse_common_symbols():
    assert chords.parse_symbol("C").root_pc == 0
    assert chords.parse_symbol("Am7").quality == "m7"
    dfs = chords.parse_symbol("D/F#")
    assert dfs.root_pc == 2 and dfs.bass_pc == 6
    assert chords.parse_symbol("A7sus4").quality == "7sus4"
    assert chords.parse_symbol("C69").quality == "69"
    assert chords.parse_symbol("Bbm7b5").root_pc == 10


def test_parse_rest_and_garbage():
    nc = chords.parse_symbol("N.C.")
    assert nc is not None and nc.is_rest
    assert chords.parse_symbol("No Chord").is_rest
    assert chords.parse_symbol("lyrics here") is None
    assert chords.parse_symbol("") is None


def test_transpose_symbol():
    assert chords.transpose_symbol("C", 2) == "D"
    assert chords.transpose_symbol("Am", 3) == "Cm"
    assert chords.transpose_symbol("D/F#", 2) == "E/G#"
    assert chords.transpose_symbol("B", 1) == "C"        # wrap
    assert chords.transpose_symbol("N.C.", 5) == "N.C."  # rest unchanged


def test_transpose_prefers_flats_in_flat_keys():
    # transposing into Eb should spell with flats, not D#
    assert chords.transpose_symbol("C", 3, prefer_flats=True) == "Eb"
    assert chords.prefer_flats_for(chords.NOTE_TO_PC["Eb"], minor=False)
    assert not chords.prefer_flats_for(chords.NOTE_TO_PC["E"], minor=False)


def test_key_is_minor():
    assert chords.key_is_minor("Am")
    assert chords.key_is_minor("F#m")
    assert not chords.key_is_minor("C")
    assert not chords.key_is_minor("Cmaj7")
