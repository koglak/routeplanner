import pytest

from museumdb.models import City
from museumdb.table import render_table


def lines_of(d):
    return render_table(City.from_dict(d)).splitlines()


def test_header_counts_confidence(rome_dict):
    assert lines_of(rome_dict)[0] == "Rome — 2 müze (1 yüksek, 1 orta, 0 düşük güven)"


def test_rows_show_duration_range_and_note(rome_dict):
    _, head, vatican, borghese = lines_of(rome_dict)
    assert head.split()[0] == "Müze"
    assert vatican.startswith("Vatican Museums")
    assert "3–4 sa" in vatican and "3 / 5 sa" in vatican
    assert vatican.endswith("Bilet önceden şiddetle önerilir")
    assert borghese.startswith("Borghese Gallery")
    assert "1–2 sa" in borghese and "1 / 2 sa" in borghese
    assert borghese == borghese.rstrip()


def test_columns_are_aligned(rome_dict):
    _, head, vatican, borghese = lines_of(rome_dict)
    assert head.index("Süre") == vatican.index("3–4 sa") == borghese.index("1–2 sa")
    assert head.index("Hızlı/Detaylı") == vatican.index("3 / 5 sa") == borghese.index("1 / 2 sa")


def test_missing_duration_shows_veri_yok(rome_dict):
    rome_dict["museums"][1]["duration"] = None
    lines = lines_of(rome_dict)
    assert lines[0] == "Rome — 2 müze (1 yüksek, 0 orta, 0 düşük güven, 1 veri yok)"
    assert "veri yok" in lines[3] and "—" in lines[3]


def test_unparsed_signals_count_as_veri_yok(rome_dict):
    rome_dict["museums"][1]["duration"] = {
        "signals": [{"source": "blog", "value": "half a day", "checked": "2026-10-01", "url": None}],
        "notes": [], "typical_min_h": None, "typical_max_h": None,
        "fast_h": None, "thorough_h": None, "confidence": None,
    }
    lines = lines_of(rome_dict)
    assert lines[0].endswith(", 1 veri yok)")
    assert "veri yok" in lines[3]


@pytest.mark.parametrize("lo, hi, text", [(3, None, "3+ sa"), (2, 2, "2 sa"), (1.5, 2.5, "1,5–2,5 sa")])
def test_duration_text_formats(rome_dict, lo, hi, text):
    d = rome_dict["museums"][0]["duration"]
    d["typical_min_h"], d["typical_max_h"] = lo, hi
    assert text in lines_of(rome_dict)[2]


def test_note_falls_back_to_first_duration_note(rome_dict):
    rome_dict["museums"][0]["planning"].pop("advance_ticket")
    assert lines_of(rome_dict)[2].endswith("Sesli rehberle +1 saat")
