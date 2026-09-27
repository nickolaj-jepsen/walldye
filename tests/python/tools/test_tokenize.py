import json

import pytest
from fixtures import regen

from walldye.tools import tokenize

SPEC = json.loads((regen.SHARED / "tokenize.json").read_text())


@pytest.mark.parametrize("case", SPEC["cases"], ids=lambda c: c["name"])
def test_spec(case):
    text = case["input"]
    assert text.isascii()  # offsets must mean the same in JS
    assert [list(o) for o in tokenize.find_colours(text)] == case["occurrences"]
    assert tokenize.normalise(text) == case["normalised"]
    assert tokenize.skeleton(text) == case["skeleton"]
    assert tokenize.normalise(case["normalised"]) == case["normalised"]
    assert tokenize.skeleton(case["normalised"]) == case["skeleton"]


def test_spec_tables():
    assert SPEC["named"] == tokenize.NAMED and len(tokenize.NAMED) == 148
    assert SPEC["skeleton_mark"] == tokenize.SKELETON_MARK


def test_substitute():
    svg = '<rect fill="#fff" stroke=" red "/><path fill="none"/>'
    assert (
        tokenize.substitute(svg, ["#000000", "#111111"])
        == '<rect fill="#000000" stroke=" #111111 "/><path fill="none"/>'
    )
    with pytest.raises(ValueError):
        tokenize.substitute(svg, ["#000000"])
