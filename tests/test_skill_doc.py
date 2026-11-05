import json
import re
from pathlib import Path

from museumdb.validation import parse_city

SKILL = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "muze" / "SKILL.md"


def test_skill_frontmatter_names_the_command():
    assert SKILL.read_text(encoding="utf-8").startswith("---\nname: muze\n")


def test_skill_draft_example_is_a_valid_document():
    text = SKILL.read_text(encoding="utf-8")
    match = re.search(r"## Taslak örneği.*?```json\n(.*?)```", text, re.S)
    assert match, "SKILL.md needs a ```json block under '## Taslak örneği'"
    city = parse_city(json.loads(match.group(1)))
    assert city.museums, "example should contain at least one museum"
