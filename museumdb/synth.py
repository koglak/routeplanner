"""Turn raw duration signals into a summary range and confidence level (pure functions)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from museumdb.models import STRONG_SOURCES, Duration, Signal

MAX_HOURS = 12.0
_MINUTE_UNITS = {"min", "mins", "minute", "minutes", "dk", "dakika"}
# A number, optionally followed by a time unit; the unit must not run into further letters.
_TOKEN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(hours?|hrs?|h|saat|sa|minutes?|mins?|dakika|dk)?(?![^\W\d_])")
_OPEN = re.compile(r"more than|\bover\b|at least|not enough|\d\s*\+")
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_NUMBER_WORD = re.compile(
    r"\b(" + "|".join(_NUMBER_WORDS) + r")\b"
    r"(?=(?:\s*(?:to|or|-|–)\s*(?:\d+|" + "|".join(_NUMBER_WORDS) + r"))?\s+(?:hours?|hrs?|minutes?|mins?)\b)"
)
_AT_MOST = re.compile(r"less than|\bunder\b|up to|<")
_PLUS = re.compile(r"(\d)\s*\+")


@dataclass(frozen=True)
class Range:
    lo: float
    hi: float | None  # None = open-ended, e.g. "More than 3 hours"

    def overlaps(self, other: Range) -> bool:
        self_hi = math.inf if self.hi is None else self.hi
        other_hi = math.inf if other.hi is None else other.hi
        return self.lo <= other_hi and other.lo <= self_hi


def parse_duration(text: str) -> Range | None:
    """Parse "3–4 h", "More than 3 hours", "90 min", ... into hours; None if not understood."""
    t = text.lower()
    open_ended = bool(_OPEN.search(t))
    at_most = bool(_AT_MOST.search(t))
    t = _PLUS.sub(r"\1 ", t)
    t = _NUMBER_WORD.sub(lambda m: str(_NUMBER_WORDS[m.group(1)]), t)
    tokens = _join_hours_and_minutes(
        [(float(num.replace(",", ".")), unit) for num, unit in _TOKEN.findall(t)]
    )
    if not any(unit for _, unit in tokens):
        return None
    hours = [
        round(_to_hours(num, unit or _nearest_unit(tokens, i)), 2)
        for i, (num, unit) in enumerate(tokens[:2])
    ]
    if any(h <= 0 or h > MAX_HOURS for h in hours):
        return None
    if len(hours) == 2:
        lo, hi = sorted(hours)
        return Range(lo, hi)
    (x,) = hours
    if open_ended:
        return Range(x, None)
    if at_most:
        return Range(round(x / 2, 2), x)
    return Range(x, x)


def _join_hours_and_minutes(tokens: list[tuple[float, str]]) -> list[tuple[float, str]]:
    joined: list[tuple[float, str]] = []
    for num, unit in tokens:
        if joined and unit in _MINUTE_UNITS and num < 60:
            prev_num, prev_unit = joined[-1]
            if prev_unit and prev_unit not in _MINUTE_UNITS:
                joined[-1] = (prev_num + num / 60, prev_unit)
                continue
        joined.append((num, unit))
    return joined


def _nearest_unit(tokens: list[tuple[float, str]], i: int) -> str:
    """Unit for a bare number: the next explicit unit, else the previous one ("1-2 hours")."""
    for _, unit in tokens[i + 1:]:
        if unit:
            return unit
    for _, unit in reversed(tokens[:i]):
        if unit:
            return unit
    return "h"


def _to_hours(num: float, unit: str) -> float:
    return num / 60 if unit in _MINUTE_UNITS else num


def synthesize(signals: list[Signal], notes: list[str] | None = None) -> Duration | None:
    """Rebuild the duration summary from raw signals; None when there are no signals."""
    if not signals:
        return None
    duration = Duration(signals=list(signals), notes=list(notes or []))
    parsed = [(s.source, r) for s in signals if (r := parse_duration(s.value)) is not None]
    if not parsed:
        return duration
    ranges = [r for _, r in parsed]
    strong = [r for source, r in parsed if source in STRONG_SOURCES]
    duration.typical_min_h, duration.typical_max_h = _typical(strong or ranges)
    duration.fast_h = min(r.lo for r in ranges)
    duration.thorough_h = max(r.lo if r.hi is None else r.hi for r in ranges)
    duration.confidence = confidence(parsed)
    return duration


def _typical(ranges: list[Range]) -> tuple[float, float | None]:
    """Common intersection of the ranges, or their hull when they do not all overlap."""
    lo = max(r.lo for r in ranges)
    closed = [r.hi for r in ranges if r.hi is not None]
    hi = min(closed) if closed else None
    if hi is None or lo <= hi:
        return lo, hi
    hull_hi = max(closed) if len(closed) == len(ranges) else None
    return min(r.lo for r in ranges), hull_hi


def confidence(parsed: list[tuple[str, Range]]) -> str | None:
    """high: two different sources overlap (one of them strong); medium: any strong; low: weak only."""
    if not parsed:
        return None
    for i, (source_a, a) in enumerate(parsed):
        for source_b, b in parsed[i + 1:]:
            involves_strong = source_a in STRONG_SOURCES or source_b in STRONG_SOURCES
            if source_a != source_b and involves_strong and a.overlaps(b):
                return "high"
    if any(source in STRONG_SOURCES for source, _ in parsed):
        return "medium"
    return "low"
