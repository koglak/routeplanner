import pytest

from museumdb.synth import Range, parse_duration


@pytest.mark.parametrize(
    "text, expected",
    [
        ("3–4 h", Range(3, 4)),
        ("More than 3 hours", Range(3, None)),
        ("1-2 hours", Range(1, 2)),
        ("~5 h", Range(5, 5)),
        ("~5 h with audio guide", Range(5, 5)),
        ("90 min", Range(1.5, 1.5)),
        ("<1 hour", Range(0.5, 1)),
        ("Less than 1 hour", Range(0.5, 1)),
        ("3+ hours", Range(3, None)),
        ("2 to 3 hrs", Range(2, 3)),
        ("about 2 hours", Range(2, 2)),
        ("30 min - 1 hour", Range(0.5, 1)),
        ("4-2 hours", Range(2, 4)),
        ("1,5 saat", Range(1.5, 1.5)),
        ("2-3 saat", Range(2, 3)),
        ("45 dk", Range(0.75, 0.75)),
        ("People typically spend 1.5 hours here", Range(1.5, 1.5)),
        ("1 hour 30 minutes", Range(1.5, 1.5)),
        ("Plan on spending 1 hour 30 minutes to 2 hours to explore", Range(1.5, 2)),
        ("2 hours 15 min - 3 hours", Range(2.25, 3)),
        ("We spent almost three hours there", Range(3, 3)),
        ("Friends spent less than two hours there", Range(1, 2)),
        ("well worth five minutes if you're passing", Range(0.08, 0.08)),
        ("Two to three hours", Range(2, 3)),
        ("one hour it's not enough at all", Range(1, None)),
    ],
)
def test_parses_known_formats(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "half a day",
        "3 people",          # numbers but no time unit
        "Mo–Sa 08:00–19:00",  # opening hours, not a duration
        "15 hours",          # beyond MAX_HOURS: not a museum visit
        "2h30",              # must never become a 2–30 h range
        "0 h",
        "one of the best museums",
    ],
)
def test_returns_none_for_unusable_text(text):
    assert parse_duration(text) is None


def test_overlap_includes_touching_and_open_ranges():
    assert Range(3, 4).overlaps(Range(3, None))
    assert Range(2, 3).overlaps(Range(3, 4))
    assert not Range(1, 2).overlaps(Range(3, None))
    assert not Range(5, 5).overlaps(Range(3, 4))
