"""Plain-text summary table of a city's museums (Turkish labels)."""
from __future__ import annotations

from museumdb.models import City, Museum

NO_DATA = "veri yok"
CONFIDENCE_LABELS = (("high", "yüksek"), ("medium", "orta"), ("low", "düşük"))
TICKET_NOTES = {
    "required": "Bilet önceden şart",
    "strongly_recommended": "Bilet önceden şiddetle önerilir",
    "recommended": "Bilet önceden önerilir",
}
HEADER = ("Müze", "Süre", "Hızlı/Detaylı", "Not")


def render_table(city: City) -> str:
    rows = [HEADER] + [(m.name, _duration_text(m), _range_text(m), _note_text(m)) for m in city.museums]
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    lines = [_summary_line(city)]
    for row in rows:
        aligned = "  ".join(cell.ljust(width) for cell, width in zip(row[:3], widths))
        lines.append(f"{aligned}  {row[3]}".rstrip())
    return "\n".join(lines)


def _summary_line(city: City) -> str:
    counts = {level: 0 for level, _ in CONFIDENCE_LABELS}
    no_data = 0
    for m in city.museums:
        level = m.duration.confidence if m.duration else None
        if level in counts:
            counts[level] += 1
        else:
            no_data += 1
    summary = ", ".join(f"{counts[level]} {label}" for level, label in CONFIDENCE_LABELS) + " güven"
    if no_data:
        summary += f", {no_data} {NO_DATA}"
    return f"{city.name} — {len(city.museums)} müze ({summary})"


def _hours(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def _duration_text(m: Museum) -> str:
    d = m.duration
    if d is None or d.typical_min_h is None:
        return NO_DATA
    if d.typical_max_h is None:
        return f"{_hours(d.typical_min_h)}+ sa"
    if d.typical_min_h == d.typical_max_h:
        return f"{_hours(d.typical_min_h)} sa"
    return f"{_hours(d.typical_min_h)}–{_hours(d.typical_max_h)} sa"


def _range_text(m: Museum) -> str:
    d = m.duration
    if d is None or d.fast_h is None:
        return "—"
    return f"{_hours(d.fast_h)} / {_hours(d.thorough_h)} sa"


def _note_text(m: Museum) -> str:
    ticket = m.planning.get("advance_ticket")
    if ticket is not None and ticket.value in TICKET_NOTES:
        return TICKET_NOTES[ticket.value]
    if m.duration is not None and m.duration.notes:
        return m.duration.notes[0]
    return ""
