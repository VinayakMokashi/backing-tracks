import os
import time

import config
from backtrack import store
from backtrack.arrange import choose_auto_capo, plan_capo
from backtrack.arrange.voicings import OPEN_BY_KEY
from backtrack.chords import parse_symbol
from backtrack.model import ChordEvent, Section, Song
from backtrack.sources.cifraclub import _normalize_br


def _song(symbols, capo=0):
    return Song(id="_t", title="T", capo=capo, sections=[Section(
        name="A", chords=[ChordEvent(s, i * 4.0, 4.0) for i, s in enumerate(symbols)])])


def test_auto_capo_finds_open_shapes():
    # Bb / Eb / F are all barre chords; some capo turns every one into an
    # open shape (e.g. capo 1 -> A D E, or capo 3 -> G C D).
    song = _song(["Bb", "Eb", "F"])
    capo = choose_auto_capo(song, 0)
    for sym in ("Bb", "Eb", "F"):
        p = parse_symbol(sym)
        assert ((p.root_pc - capo) % 12, p.quality) in OPEN_BY_KEY
    shift, capo_out = plan_capo(song, 0, "auto")
    assert shift + capo_out == 0  # sounding invariant


def test_auto_capo_sounding_invariant_under_transpose():
    song = _song(["C", "G", "Am", "F"], capo=0)
    for t in (-3, 0, 5):
        shift, capo_out = plan_capo(song, t, "auto")
        assert shift + capo_out == t


def test_normalize_brazilian_notation():
    assert _normalize_br("D4") == "Dsus4"
    assert _normalize_br("A7(4)") == "A7sus4"
    assert _normalize_br("G9") == "Gadd9"
    assert _normalize_br("Am7") == "Am7"  # unchanged


def test_prune_renders_keeps_newest():
    song_id = "_prunetest"
    render_dir = config.RENDERS_DIR / song_id
    render_dir.mkdir(parents=True, exist_ok=True)
    try:
        now = time.time()
        for i in range(25):
            wav = render_dir / f"h{i:02d}.wav"
            wav.write_bytes(b"x")
            (render_dir / f"h{i:02d}.mid").write_bytes(b"x")
            os.utime(wav, (now + i, now + i))  # newer index = newer mtime
        store.prune_renders(song_id, keep=20)
        remaining = sorted(p.stem for p in render_dir.glob("*.wav"))
        assert len(remaining) == 20
        assert "h24" in remaining and "h00" not in remaining
        assert not (render_dir / "h00.mid").exists()
    finally:
        for p in render_dir.glob("*"):
            p.unlink()
        render_dir.rmdir()
