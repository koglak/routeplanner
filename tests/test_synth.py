from museumdb.models import Signal
from museumdb.synth import Range, confidence, synthesize


def sig(source, value):
    return Signal(source, value, "2026-10-01")


def summary(d):
    return (d.typical_min_h, d.typical_max_h, d.fast_h, d.thorough_h, d.confidence)


def test_no_signals_gives_none():
    assert synthesize([]) is None


def test_overlapping_strong_sources_are_high():
    d = synthesize([sig("google", "3–4 h"), sig("tripadvisor", "More than 3 hours"),
                    sig("reddit", "~5 h with audio guide")])
    assert summary(d) == (3, 4, 3, 5, "high")


def test_single_strong_source_is_medium():
    assert summary(synthesize([sig("tripadvisor", "1-2 hours")])) == (1, 2, 1, 2, "medium")


def test_non_overlapping_strong_sources_are_medium_with_hull_range():
    d = synthesize([sig("google", "1-2 h"), sig("tripadvisor", "3-4 hours")])
    assert summary(d) == (1, 4, 1, 4, "medium")


def test_hull_with_open_range_stays_open():
    d = synthesize([sig("google", "1-2 h"), sig("tripadvisor", "More than 3 hours")])
    assert summary(d) == (1, None, 1, 3, "medium")


def test_strong_and_weak_overlap_is_high_but_typical_uses_strong_only():
    d = synthesize([sig("tripadvisor", "2-3 hours"), sig("reddit", "3 hours")])
    assert summary(d) == (2, 3, 2, 3, "high")


def test_only_weak_sources_are_low_even_when_overlapping():
    d = synthesize([sig("reddit", "2-3 hours"), sig("blog", "about 2 hours")])
    assert summary(d) == (2, 2, 2, 3, "low")


def test_same_source_twice_is_not_high():
    d = synthesize([sig("google", "2-3 h"), sig("google", "2 h")])
    assert d.confidence == "medium"


def test_unparseable_signals_are_kept_but_not_summarised():
    signals = [sig("blog", "half a day"), sig("reddit", "2h30")]
    d = synthesize(signals)
    assert d.signals == signals
    assert summary(d) == (None, None, None, None, None)


def test_unparseable_signal_is_ignored_next_to_parseable_one():
    d = synthesize([sig("google", "3-4 h"), sig("blog", "half a day")])
    assert summary(d) == (3, 4, 3, 4, "medium")
    assert len(d.signals) == 2


def test_notes_are_carried_over():
    assert synthesize([sig("google", "1 h")], ["Sesli rehberle +1 saat"]).notes == ["Sesli rehberle +1 saat"]


def test_confidence_of_nothing_is_none():
    assert confidence([]) is None
    assert confidence([("osm", Range(1, 2))]) == "low"
