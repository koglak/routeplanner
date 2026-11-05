from museumdb.models import City, Duration, FieldValue, Museum, Signal


def test_city_round_trips_through_dict(rome_dict):
    assert City.from_dict(rome_dict).to_dict() == rome_dict


def test_from_dict_builds_nested_types(rome_dict):
    city = City.from_dict(rome_dict)
    vatican = city.museums[0]
    assert city.slug == "rome"
    assert isinstance(vatican.duration, Duration)
    assert vatican.duration.signals[2] == Signal(
        "reddit", "~5 h with audio guide", "2026-10-01", "https://reddit.com/r/rome/x"
    )
    assert vatican.volatile["price"] == FieldValue("€20 adult", "official", "2026-10-01")
    assert city.museums[1].duration.signals[0].url is None


def test_minimal_museum_gets_defaults():
    m = Museum.from_dict({"id": "Q1", "name": "X"})
    assert m.duration is None
    assert m.planning == {} and m.volatile == {}
    assert m.user_notes == [] and m.category == []
    assert m.coords is None
