import re

import pytest
import yaml

from walldye.tools import common

SKILL = common.ROOT / ".claude/skills/walldye/SKILL.md"


def examples() -> list[str]:
    section = SKILL.read_text().split("\n## Examples\n", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"^\| `([a-z0-9-]+)` \|", section, re.MULTILINE)


def test_the_skill_lists_examples():
    assert len(examples()) >= 5


# The skill points builders at these pieces, so a dropped or hidden one would teach nothing.
@pytest.mark.parametrize("slug", examples())
def test_each_skill_example_is_a_published_design(slug):
    folder = common.piece_dir(slug)
    assert (folder / "design.py").is_file()
    meta = yaml.safe_load((folder / "meta.yaml").read_text())
    assert meta.get("draft") is not True
