import textwrap

import pytest

from walldye.tools import lint

HEAD = '"""A design."""\n\nfrom walldye import ACCENT, UI, Canvas, P, Params, design, mix\n'
DRAW = "\n\n@design()\ndef draw(s: Canvas) -> None:\n    s.fill(P().circle(s.center, 9), ACCENT)\n"


def errors(tmp_path, body: str = "", draw: str = DRAW, head: str = HEAD) -> list[str]:
    path = tmp_path / "design.py"
    path.write_text(head + textwrap.dedent(body) + draw)
    return lint.source.design(path)[0]


def test_a_plain_design_passes(tmp_path):
    assert errors(tmp_path) == []


@pytest.mark.parametrize(
    "line",
    [
        "import math, collections.abc",
        "import numpy as np",
        "from shapely.geometry import Polygon",
        "from walldye import geom, field, pixel",
    ],
)
def test_allowed_imports(tmp_path, line):
    assert errors(tmp_path, line + "\n") == []


@pytest.mark.parametrize(
    ("line", "name"),
    [
        ("import random", "random"),
        ("from numpy import random", "numpy.random"),
        ("from walldye import _color", "walldye._color"),
        ("from scipy.stats import qmc", "scipy.stats.qmc"),
    ],
)
def test_banned_imports(tmp_path, line, name):
    assert any(f"line 4: imports {name};" in e for e in errors(tmp_path, line + "\n"))


def test_relative_and_future_imports(tmp_path):
    assert errors(tmp_path, "from __future__ import annotations\n") == [
        "line 4: from __future__ imports change how annotations evaluate"
    ]
    assert errors(tmp_path, "from . import helper\n") == [
        "line 4: relative import; designs are single files"
    ]


@pytest.mark.parametrize(
    ("body", "draw_line", "message"),
    [
        ("import numpy as np\n", "    np.random.seed(3)", "uses numpy.random"),
        ("from walldye import field\n", "    field.Noise(3)", "calls Noise()"),
        (
            "import scipy.stats as st\n",
            "    st.uniform.rvs(size=3)",
            "calls rvs() without a stream",
        ),
        (
            "from scipy import stats\n",
            "    stats.bootstrap(([1],), sum, random_state=3)",
            "passes random_state=",
        ),
        (
            "from typing import cast\n",
            "    cast(float, 1)",
            "uses typing.cast; designs are type-checked",
        ),
        ("", "    s.fill(P(), UI)  # type: ignore", "line 9: `# type: ignore` silences Pyrefly"),
        (
            "from walldye import Color\n",
            "    Color((0, 1))",
            "calls Color(); the drawing API makes these",
        ),
        ("", "    hash('x')", "calls hash(), which depends on the process"),
        ("", "    global UI", "global statements change module state"),
        ("", "    s.fill(P().circle(s.center, 9), '#ff0000')", "raw color '#ff0000'"),
        ("", "    print(f'#{3:02x}{4:02x}{5:02x}')", "builds a hex color"),
        ("", "    print(f'{UI}')", "a color has no text form"),
    ],
)
def test_draw_rules(tmp_path, body, draw_line, message):
    found = errors(tmp_path, body, DRAW + draw_line + "\n")
    assert any(message in e for e in found), found


@pytest.mark.parametrize(
    "line",
    ["    s.rng(3).random()", "    print('#', 3)"],
)
def test_draw_rules_allow(tmp_path, line):
    assert errors(tmp_path, "import re\n", DRAW + line + "\n") == []


def test_library_samplers_take_a_stream(tmp_path):
    head = "from scipy import stats\nfrom skimage.util import random_noise\n"
    body = (
        "    stats.norm.rvs(size=3, random_state=s.np_rng(1))\n"
        "    random_noise([0.0], rng=s.np_rng('grain'))\n"
        "    s.rng(2).sample(range(9), 3)\n"
    )
    assert errors(tmp_path, head, DRAW + body) == []


@pytest.mark.parametrize(
    ("draw", "line"),
    [
        ("\n\ndef draw(s: Canvas) -> None:\n    pass\n", 6),
        (DRAW + "\n\n@design()\ndef draw(s: Canvas) -> None:\n    pass\n", 12),
    ],
)
def test_entry_point(tmp_path, draw, line):
    found = errors(tmp_path, draw=draw)
    assert (
        f"line {line}: a design has exactly one module-level @design(...) def draw(s: Canvas[...])"
        in found
    ), found


def test_entry_point_missing_and_design_elsewhere(tmp_path):
    assert errors(tmp_path, draw="") == [
        "a design has exactly one module-level @design(...) def draw(s: Canvas[...])"
    ]
    found = errors(tmp_path, "D = design\n")
    assert "line 4: design is only used as the @design(...) decorator on draw" in found


MODULE_OK = """\
import math
from dataclasses import dataclass

import numpy as np
from walldye import Rect, Vec, by_regime, clamp, ladder, lerp, polar, ramp, smoothstep

type Pair = tuple[float, float]
TILT = math.radians(6)
X0, BAYS, BAY = 10, 3, 40.0
X1 = X0 + BAYS * BAY
SPOKES = np.array([(math.cos(a), math.sin(a)) for a in np.radians(range(0, 360, 30))])
TONES = (*ladder((UI, ACCENT), 5), *ramp(UI, ACCENT, 3)[1:])
STRUCT = by_regime(UI, mix(UI, ACCENT, 0.5))
BOX = Rect(0, 0, 10, 10)
AT = polar(Vec(1, 2), 3, deg=4)
T = lerp(0, 1, clamp(smoothstep(0, 1, 0.5)))
NAMES = "a b c".split()
LABEL = "-".join(NAMES).upper()
TABLE = {k: v for k, v in zip(NAMES, range(3), strict=True) if v > 0}
KEY = lambda p: math.hypot(*p)  # noqa: E731
COUNT: int = len(NAMES)
COUNT += 1
assert COUNT > 0
NORM = np.linalg.norm(SPOKES[0])


def helper(n: int) -> int:
    return n * 2


DOUBLE = helper(COUNT)


@dataclass(frozen=True)
class Knot:
    x: float


class Knobs(Params):
    n: int = 3


class More(Knobs):
    m: int = 2


V = {"x": Knobs(n=4), "y": More(m=1)}
"""


def test_module_level_constants_pass(tmp_path):
    assert errors(tmp_path, MODULE_OK) == []


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("RING = P().circle((0, 0), 40)\n", "line 4: calls P().circle() at module level"),
        (
            "TABLE = []\nfor k in range(3):\n    TABLE.append(k)\n",
            "line 5: a module-level for statement",
        ),
        ("X = LATER + 1\nLATER = 2\n", "line 4: LATER is not bound before this module-level line"),
        ("X = [1]\nX[0] = 2\n", "line 5: module-level assignments bind names"),
        (
            "import functools\n\n\n@functools.cache\ndef f() -> int:\n    return 1\n",
            "line 8: module-level functions are undecorated",
        ),
    ],
)
def test_module_level_failures(tmp_path, body, message):
    found = errors(tmp_path, body)
    assert any(e.startswith(message) for e in found), found


@pytest.mark.parametrize(
    ("body", "draw_body", "flagged"),
    [
        ("TABLE: list[int] = []\n", "    TABLE.append(1)", True),
        ("TABLE = [1]\n", "    TABLE[0] = 2", True),
        ("class K:\n    n = 1\n", "    K.n = 2", True),
        ("TABLE = [1]\n", "    def inner() -> None:\n        TABLE.pop()\n\n    inner()", True),
        ("TABLE: list[int] = []\n", "    TABLE = []\n    TABLE.append(1)", False),
        ("TABLE = [1]\n", "    rows = list(TABLE)\n    rows.append(2)", False),
    ],
)
def test_mutation(tmp_path, body, draw_body, flagged):
    found = errors(tmp_path, body, DRAW + draw_body + "\n")
    assert any("changes module-level" in e for e in found) is flagged, found


def test_errors_name_their_lines_in_order(tmp_path):
    found = errors(tmp_path, "import random\nX = P()\n", DRAW + "    hash(1)\n")
    assert [e.split(":")[0] for e in found] == ["line 4", "line 5", "line 11"]


def test_color_words_warn(tmp_path):
    path = tmp_path / "design.py"
    path.write_text('"""A terracotta sun."""\n\n# ACCENT rim, a warm orange glow\n')
    assert lint.source.design(path)[1] == [
        "color words in docstrings or comments: orange, terracotta (name tokens or roles, never hues)"
    ]


def test_color_words_match_plurals_but_not_tokens():
    text = "Greys and whites under the ambers; GREYS, BLUES, reddish, Blueprint, crimsons"
    assert lint.words.color_words(text) == {"greys", "whites", "ambers", "crimsons"}


def test_data_rules(wallpapers):
    d = wallpapers / "piece" / "data"
    d.mkdir(parents=True)
    for name in ("points.json", "names.txt", "grid.npy", ".hidden.json", "x.csv", "late.json\n"):
        (d / name).write_text("")
    (d / "nested").mkdir()
    assert lint.piece.data("piece") == [
        "data/.hidden.json: data files are .json, .txt or .npy with a plain name",
        "data/late.json\n: data files are .json, .txt or .npy with a plain name",
        "data/nested/: data/ holds files only, no subdirectories",
        "data/x.csv: data files are .json, .txt or .npy with a plain name",
    ]
    assert lint.piece.data("other") == []


def test_svg_limits():
    head = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    assert lint.templates.svg(head + "</svg>") == ([], [])
    assert lint.templates.svg(head + '<image href="x.png"/></svg>')[0] == [
        "<image> is not allowed: templates are self-contained vectors"
    ]
    errors_, warnings = lint.templates.svg(head + "<g/>" * 16_000 + "</svg>")
    assert errors_ == [] and warnings == [
        "16001 elements is heavy (over 15,000); merge shapes into one <path> per color"
    ]
    assert lint.templates.svg(head + "<g/>" * 20_000 + "</svg>")[0] == [
        "20001 elements is over the limit of 20,000; merge shapes into one <path> per color"
    ]
    errors_, warnings = lint.templates.svg(head + f'<path d="{"M0 0" * 160_000}"/></svg>')
    assert errors_ == [] and warnings[0].startswith("640,")
    assert lint.templates.svg(head + f'<path d="{"M0 0" * 260_000}"/></svg>')[0][0].startswith(
        "1,040,"
    )
    assert lint.templates.svg("<svg>")[0][0].startswith("invalid XML")


TAXONOMY = {"technique": {"drafting", "dither"}, "subject": {"space"}}
GOOD = {"title": "T", "description": "A disc.", "model": "claude-opus-5-5", "technique": ["dither"]}
HUMAN = {"title": "T", "description": "A disc.", "author": "A. Person", "technique": ["dither"]}
FAN = {"franchise": {"title": "Outer Wilds", "owner": "Mobius Digital"}}
WORK = {"kind": "recreation", "title": "Schotter"}
NAMES = ("default", "late")
LABELS = {"default": {"label": "Early"}, "late": {"label": "Late in the turn", "draft": True}}


@pytest.mark.parametrize(
    ("slug", "meta", "names", "error"),
    [
        ("ok", GOOD, (), None),
        ("ok", {**GOOD, "title": ""}, (), "needs a title"),
        ("about", GOOD, (), "reserved"),
        ("ok", {**GOOD, "sources": [WORK]}, (), "recreation source needs an explicit license"),
        ("ok", {**GOOD, "sources": [WORK], "license": "CC0-1.0"}, (), None),
        ("ok", {**GOOD, "sources": [{"kind": "homage", "title": "X"}]}, (), "source kind"),
        ("ok", {**GOOD, "sources": [{"kind": "reference", "topic": "Dither"}]}, (), None),
        (
            "ok",
            {**GOOD, "sources": [{"kind": "reference", "title": "A", "topic": "B"}]},
            (),
            "a title names a work and a topic anything else; not both",
        ),
        ("ok", {**GOOD, "sources": [{"kind": "reference"}]}, (), "needs a title, a topic or"),
        ("ok", HUMAN, (), "human-made pieces need an explicit license"),
        ("ok", {**HUMAN, "license": "CC0-1.0"}, (), None),
        ("ok", {**HUMAN, "model": "claude-opus-5-5"}, (), "author: is for human-made pieces"),
        ("ok", {**GOOD, "model": ""}, (), "needs model: (the model id that made it)"),
        ("ok", {**GOOD, "model": "gpt-x"}, (), "'gpt-x' needs a credit name in MODEL_NAMES"),
        ("ok", {**GOOD, "license": "LicenseRef-fan-work"}, (), "marked by franchise"),
        ("ok", {**GOOD, **FAN}, (), None),
        ("ok", {**GOOD, **FAN, "sources": [WORK]}, (), None),
        ("ok", {**GOOD, **FAN, "license": "CC0-1.0"}, (), "drop license:"),
        ("ok", {**GOOD, "franchise": {"title": "X"}}, (), "franchise needs a title and an owner"),
        ("ok", {**GOOD, "technique": ["weaving"]}, (), "'weaving' is not in taxonomy.yaml"),
        ("ok", {**GOOD, "technique": "dither"}, (), "technique must be a list"),
        ("ok", {**GOOD, "proposed_facets": {"technique": ["weaving"]}}, (), "proposed_facets"),
        ("ok", {**GOOD, "proposed_facets": {"technique": ["weaving"]}, "draft": True}, (), None),
        ("ok", {**GOOD, "draft": "false"}, (), "draft must be true or false, not 'false'"),
        ("ok", {**GOOD, "license": "CC0"}, (), "license 'CC0' has no LICENSES/CC0.txt"),
        (
            "ok",
            {**GOOD, "variants": LABELS},
            (),
            "variants: is only for designs that declare named variants",
        ),
        ("ok", {**GOOD, "variants": LABELS}, NAMES, None),
        ("ok", GOOD, NAMES, "meta.yaml needs variants: with a label for each of default, late"),
        (
            "ok",
            {**GOOD, "variants": {"default": {"label": "Early"}}},
            NAMES,
            "variants: missing late",
        ),
        (
            "ok",
            {**GOOD, "variants": {**LABELS, "open": {"label": "Open"}}},
            NAMES,
            "variants: open not declared",
        ),
        (
            "ok",
            {**GOOD, "variants": {**LABELS, "late": {"label": "a b c d e"}}},
            NAMES,
            "one to four plain words",
        ),
        (
            "ok",
            {**GOOD, "variants": {**LABELS, "late": {"label": "Late variant"}}},
            NAMES,
            "the label says variant",
        ),
        (
            "ok",
            {**GOOD, "variants": {**LABELS, "late": {"label": "early"}}},
            NAMES,
            "late and default share the label 'early'",
        ),
        (
            "ok",
            {
                **GOOD,
                "variants": {"default": {"label": "E", "draft": True}, "late": {"label": "L"}},
            },
            NAMES,
            "variants: default: draft not allowed",
        ),
        (
            "ok",
            {**GOOD, "variants": {**LABELS, "late": {"label": "L", "note": "x"}}},
            NAMES,
            "late: note not allowed",
        ),
    ],
)
def test_meta_rules(slug, meta, names, error, tmp_path, monkeypatch):
    monkeypatch.setattr(lint.piece, "LICENSES", tmp_path)
    for name in ("CC0-1.0", "LicenseRef-fan-work"):
        (tmp_path / f"{name}.txt").write_text("license text\n")
    found, _ = lint.piece.meta(slug, meta, TAXONOMY, names or ("default",))
    if error is None:
        assert found == []
    else:
        assert any(error in e for e in found), found


def test_meta_wants_a_source_for_data(wallpapers):
    (wallpapers / "ok/data").mkdir(parents=True)
    assert "data/ needs a kind: data source" in " ".join(lint.piece.meta("ok", GOOD, TAXONOMY)[0])
    for source in ({"kind": "data", "topic": "Star positions"}, WORK):
        found, _ = lint.piece.meta("ok", {**GOOD, **FAN, "sources": [source]}, TAXONOMY)
        assert found == []


def test_license_of():
    assert lint.piece.license_of(GOOD) == "CC0-1.0"
    assert lint.piece.license_of({**GOOD, **FAN}) == "LicenseRef-fan-work"
    assert lint.piece.license_of({**GOOD, "sources": [WORK]}) is None
    assert lint.piece.license_of(HUMAN) is None
    assert lint.piece.license_of({**HUMAN, "license": "CC-BY-4.0"}) == "CC-BY-4.0"


def test_meta_warnings():
    meta = {**GOOD, "description": "A terracotta disc on a Black ground."}
    meta["variants"] = {
        "default": {"label": "Early"},
        "late": {"label": "Red dusk", "description": "A blue sea."},
    }
    _, warnings = lint.piece.meta("ok", meta, None, NAMES)
    assert any("black, terracotta" in w for w in warnings)
    assert any("taxonomy.yaml not found" in w for w in warnings)
    assert (
        "color words in variants: late: blue, red (describe the shape, without naming colors)"
        in warnings
    )


def test_fan_work_license_text_is_committed():
    text = (lint.piece.LICENSES / "LicenseRef-fan-work.txt").read_text()
    for phrase in (
        "No license is granted",
        "unofficial fan tribute",
        "trademarks",
        "non-commercial",
        "takedown@walldye.com",
    ):
        assert phrase in text


def test_pixel_origins():
    assert lint.templates.pixel_origins([(3, 0, 6), (3, 0.5, 6), (2, 1, 1.25), (3, 0.5, 6)]) == [
        "pixel grid origin (0.5, 6) is not a whole unit; snap it to the 3-unit cell grid",
        "pixel grid origin (1, 1.25) is not a whole unit; snap it to the 2-unit cell grid",
    ]
