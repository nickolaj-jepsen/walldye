"""Shared by the helper-module tests: a canvas to draw on, the pixel paths it drew, the v1 pins
and a parser from path data to the rectangles it draws."""

import json
import re
from pathlib import Path

from walldye import Canvas, Colour, MaskColour, Params
from walldye._document import Builder

HERE = Path(__file__).parent
PINS = json.loads((HERE.parent / "fixtures" / "v1_pins" / "helpers.json").read_text())

type Rects = list[tuple[float, float, float, float]]

_ABS = re.compile(r"M(-?[\d.]+) (-?[\d.]+)H(-?[\d.]+)V(-?[\d.]+)H(-?[\d.]+)Z")
_REL = re.compile(r"M(-?[\d.]+) (-?[\d.]+)h(-?[\d.]+)v(-?[\d.]+)h(-?[\d.]+)z")


def canvas(w: int = 1920, h: int = 1080) -> tuple[Canvas, Builder]:
    """A live dark canvas and the builder it draws into."""
    doc = Builder(w, h, "dark")
    return Canvas(Params(), w=w, h=h, light=False, doc=doc, source=HERE / "design.py"), doc


def drawn(doc: Builder) -> list[tuple[Colour | MaskColour, str, str]]:
    """(fill, d, the element's text with the fill cut out) of each drawn path, in order;
    each path must carry exactly one colour."""
    document = doc.finish()
    lines = [ln for ln in document.skeleton().splitlines() if ln.startswith("<path")]
    colours = document.colours()
    assert len(colours) == len(lines)
    out = []
    for colour, line in zip(colours, lines, strict=True):
        d = line.split(' d="')[1].split('"')[0]
        out.append((colour, d, line))
    return out


def rects(d: str) -> Rects:
    """The rectangles of path data made only of pixel cells, absolute (v2) or relative (v1)."""
    out: Rects = []
    if d.startswith("M") and "h" in d:
        for x, y, w, h, back in _REL.findall(d):
            assert float(back) == -float(w)
            out.append((float(x), float(y), float(w), float(h)))
        assert "".join(m.group(0) for m in _REL.finditer(d)) == d
    else:
        for x0, y0, x1, y1, x2 in _ABS.findall(d):
            assert x2 == x0
            w, h = round(float(x1) - float(x0), 6), round(float(y1) - float(y0), 6)
            out.append((float(x0), float(y0), w, h))
        assert "".join(m.group(0) for m in _ABS.finditer(d)) == d
    return out
