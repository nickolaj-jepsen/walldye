import dataclasses
import json

import pytest

from walldye._document import MotifInfo
from walldye.tools import motif, paths

SPEC = json.loads((paths.ROOT / "src/lib/__fixtures__/motif.json").read_text())


def info(d: dict) -> MotifInfo:
    return MotifInfo(
        tuple(d["at"]),
        (0, 0, 1, 1),
        tuple(d["extent"]),
        tuple(d["handle"]),
        d["overscan"],
        d["cell"],
        tuple(d["scale"]),
    )


BOX = [-279, -279, 558, 558]
CELL_3 = info({"at": [1305, 498], "extent": BOX, "handle": BOX, "overscan": False, "cell": 3,
               "scale": [0.5, 2]})  # fmt: skip


@pytest.mark.parametrize("case", SPEC["transform"])
def test_transform(case):
    assert motif.transform(case["x"], case["y"], case["k"]) == case["out"]


@pytest.mark.parametrize("case", SPEC["place"])
def test_place(case):
    assert motif.place(case["svg"], case["x"], case["y"], case["k"]) == case["out"]


@pytest.mark.parametrize("case", SPEC["ground"])
def test_ground(case):
    assert motif.ground(case["svg"]) == case["out"]


@pytest.mark.parametrize("case", SPEC["alone"])
def test_alone(case):
    assert motif.alone(case["svg"], tuple(case["box"])) == case["out"]


@pytest.mark.parametrize("case", SPEC["placements"])
def test_placements(case):
    w, h = case["canvas"]
    assert (motif.problems(info(case["motif"]), w, h, tuple(case["place"])) == []) == case["ok"]


def test_a_template_without_a_motif_cannot_be_placed():
    svg = next(c["svg"] for c in SPEC["ground"] if "data-motif" not in c["svg"])
    with pytest.raises(ValueError, match="no motif"):
        motif.place(svg, 0, 0, 1)
    with pytest.raises(ValueError, match="no motif"):
        motif.alone(svg, (0, 0, 1, 1))
    assert motif.unplaced(svg) == svg


def test_unplaced_forgets_the_placement():
    a, b = (motif.place(SPEC["place"][0]["svg"], x, 300, 1) for x in (10, 20))
    assert a != b and motif.unplaced(a) == motif.unplaced(b)


@pytest.mark.parametrize("text", ["1,2", "1,2,3,4", "a,2,3", "1,nan,2", "1,2,inf", ""])
def test_parse_refuses(text):
    with pytest.raises(ValueError, match="X,Y,K"):
        motif.parse(text)


def test_parse():
    assert motif.parse("200,300.5,1.25") == (200, 300.5, 1.25)


def test_problems_say_why():
    m = CELL_3
    assert motif.problems(m, 1920, 1080, (-1, 0, 3)) == [
        "the anchor (-1, 0) is off the 1920x1080 canvas",
        "the size 3 is outside 0.5..2",
    ]
    assert motif.problems(m, 1920, 1080, (0, 0, 1.1)) == [
        "the size 1.1 makes the 3-unit cell fractional"
    ]


def test_size_range_keeps_whole_cells():
    m = CELL_3
    assert motif.size_range(m) == (0.6667, 2.0)
    assert motif.size_range(dataclasses.replace(m, cell=None)) == (0.5, 2.0)
    assert all(motif.problems(m, 1920, 1080, (0, 0, k)) == [] for k in motif.size_range(m))


def test_problems_take_any_size_the_site_offers_a_large_cell():
    m = dataclasses.replace(CELL_3, cell=32.0)
    # The site writes 17/32 as 0.5313, which puts 32 * k 0.0016 off whole.
    assert all(motif.problems(m, 1920, 1080, (0, 0, round(n / 32, 4))) == [] for n in range(16, 65))
    assert motif.problems(m, 1920, 1080, (0, 0, 0.532)) != []
