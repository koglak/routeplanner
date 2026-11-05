"""Schema validation and slug checks for city documents."""
from __future__ import annotations

import json
import re
from functools import cache
from importlib.resources import files

from jsonschema import Draft202012Validator

from museumdb.models import City

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_REPORTED_ERRORS = 10


class ValidationError(ValueError):
    """A city document or slug failed validation."""


@cache
def _validator() -> Draft202012Validator:
    schema = json.loads(files("museumdb").joinpath("schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def check_slug(slug: str) -> None:
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        raise ValidationError(
            f"invalid slug {slug!r}: use lowercase English letters, digits and single hyphens (e.g. 'new-york')"
        )


def validate_city_dict(data: dict) -> None:
    errors = sorted(_validator().iter_errors(data), key=lambda e: str(list(e.absolute_path)))
    if errors:
        messages = [
            f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
            for e in errors[:MAX_REPORTED_ERRORS]
        ]
        raise ValidationError("; ".join(messages))
    ids = [m["id"] for m in data["museums"]]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValidationError(f"duplicate museum ids: {', '.join(duplicates)}")


def parse_city(data: dict) -> City:
    validate_city_dict(data)
    return City.from_dict(data)
