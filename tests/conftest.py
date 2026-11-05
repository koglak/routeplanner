import copy

import pytest

# Summary fields are consistent with what synth.synthesize computes from the signals,
# so this dict survives a save/get round trip unchanged.
ROME = {
    "schema_version": 1,
    "city": {"slug": "rome", "name": "Rome", "country": "IT", "wikidata_id": "Q220", "queried_at": "2026-10-01"},
    "museums": [
        {
            "id": "Q182955",
            "name": "Vatican Museums",
            "name_local": "Musei Vaticani",
            "category": ["art", "history"],
            "popularity_rank": 1,
            "address": "Viale Vaticano, 00165 Roma",
            "coords": [41.9065, 12.4536],
            "website": "https://www.museivaticani.va",
            "user_notes": [],
            "duration": {
                "signals": [
                    {"source": "google", "value": "3–4 h", "checked": "2026-10-01", "url": None},
                    {"source": "tripadvisor", "value": "More than 3 hours", "checked": "2026-10-01", "url": None},
                    {"source": "reddit", "value": "~5 h with audio guide", "checked": "2026-10-01",
                     "url": "https://reddit.com/r/rome/x"},
                ],
                "notes": ["Sesli rehberle +1 saat"],
                "typical_min_h": 3, "typical_max_h": 4, "fast_h": 3, "thorough_h": 5, "confidence": "high",
            },
            "planning": {
                "busiest": {"value": "Sa–Ça 10:00–13:00", "source": "google", "checked": "2026-10-01"},
                "queue_min": {"value": "60–120", "source": "reddit", "checked": "2026-10-01"},
                "advance_ticket": {"value": "strongly_recommended", "source": "official", "checked": "2026-10-01"},
            },
            "volatile": {
                "price": {"value": "€20 adult", "source": "official", "checked": "2026-10-01"},
                "hours": {"value": "Mo–Sa 08:00–19:00", "source": "official", "checked": "2026-10-01"},
            },
        },
        {
            "id": "Q999001",
            "name": "Borghese Gallery",
            "name_local": "Galleria Borghese",
            "category": ["art"],
            "popularity_rank": 2,
            "address": None,
            "coords": None,
            "website": None,
            "user_notes": [],
            "duration": {
                "signals": [{"source": "tripadvisor", "value": "1-2 hours", "checked": "2026-10-01", "url": None}],
                "notes": [],
                "typical_min_h": 1, "typical_max_h": 2, "fast_h": 1, "thorough_h": 2, "confidence": "medium",
            },
            "planning": {},
            "volatile": {},
        },
    ],
}


@pytest.fixture
def rome_dict():
    return copy.deepcopy(ROME)
