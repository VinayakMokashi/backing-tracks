import json
from pathlib import Path

from backtrack import chords, sheet_parser
from backtrack.sources import RawSheet

FIXTURE = Path(__file__).parent / "fixtures" / "wonderwall-ug-rawsheet.json"


def _wonderwall() -> RawSheet:
    return RawSheet(**json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_parses_wonderwall_fixture():
    song = sheet_parser.parse(_wonderwall())
    assert song.title.lower() == "wonderwall"
    assert song.artist == "Oasis"
    assert song.capo == 2
    assert abs(song.bpm - 87.0) < 0.01
    assert song.key == "Em"            # sounding F#m minus capo 2
    assert len(song.sections) >= 5
    # every parsed chord symbol is a real chord (never crashes the arranger)
    for section in song.sections:
        for ev in section.chords:
            assert chords.parse_symbol(ev.symbol) is not None
    assert "[ch]" in song.sheet_text   # tags retained for the sheet view


def test_content_none_does_not_crash():
    raw = RawSheet(content=None, meta={"title": "x"}, applicature=None,
                   source="paste", url=None)
    song = sheet_parser.parse(raw)
    assert song.sections == []


def test_barline_bar_grouping():
    raw = RawSheet(
        content="[Verse]\n[ch]C[/ch] [ch]G[/ch] | [ch]Am[/ch] | [ch]F[/ch]\n",
        meta={}, applicature=None, source="paste", url=None,
    )
    song = sheet_parser.parse(raw)
    bar1 = [ev for ev in song.sections[0].chords]
    # first bar has two chords (half each), next two bars one chord each
    assert bar1[0].symbol == "C" and bar1[0].duration_beats == 2.0
    assert bar1[1].symbol == "G" and bar1[1].duration_beats == 2.0
    assert bar1[2].symbol == "Am" and bar1[2].duration_beats == 4.0


def test_paste_wraps_bare_chords_and_keeps_lyrics():
    chart = "[Verse]\nC        G       Am      F\nToday is gonna be the day\n"
    wrapped = sheet_parser.wrap_bare_chords(chart)
    assert "[ch]C[/ch]" in wrapped
    assert "Today is gonna be the day" in wrapped
    assert "[ch]day[/ch]" not in wrapped  # lyric line untouched
    song = sheet_parser.parse(RawSheet(content=wrapped, meta={}, applicature=None,
                                       source="paste", url=None))
    symbols = [ev.symbol for ev in song.sections[0].chords]
    assert symbols == ["C", "G", "Am", "F"]
