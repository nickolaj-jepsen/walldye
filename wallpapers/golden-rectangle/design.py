"""A 1:phi rectangle on a drafting sheet, cut into twelve squares with a quarter-arc spiral."""

from typing import NamedTuple

from walldye import ACCENT, BG, BG_ALT, UI, UI_ALT, Canvas, P, Params, Vec, design, knob, mix, ramp
from walldye.geom import Affine

PHI = (1 + 5**0.5) / 2
RW = 1080  # long side; the construction is drawn with the rectangle's top-left corner at (0, 0)
RH = RW / PHI
STEPS = 12
TINTS = ramp(BG, BG_ALT, STEPS + 1)[1:]  # squares tint up towards the eye, barely above the paper
FAINT = mix(BG_ALT, UI, 0.6)  # sheet furniture, a step quieter than the dimensions
DASHDOT = (18, 6, 3, 6)
DIM = 56  # offset of the dimension lines from the rectangle


class Cut(NamedTuple):
    """A square cut off what is left of the rectangle, and its quarter arc of the spiral."""

    corner: Vec  # top-left
    side: float
    start: Vec  # the arc runs clockwise from start to end around pivot
    end: Vec
    pivot: Vec


def cuts() -> tuple[Cut, ...]:
    """The STEPS squares cut off the rectangle in turn from its left, top, right and bottom."""
    x, y, w, h = 0.0, 0.0, float(RW), RH
    out: list[Cut] = []
    for k in range(STEPS):
        if k % 4 == 0:  # left
            a = h
            out.append(Cut(Vec(x, y), a, Vec(x, y + a), Vec(x + a, y), Vec(x + a, y + a)))
            x, w = x + a, w - a
        elif k % 4 == 1:  # top
            a = w
            out.append(Cut(Vec(x, y), a, Vec(x, y), Vec(x + a, y + a), Vec(x, y + a)))
            y, h = y + a, h - a
        elif k % 4 == 2:  # right
            a = h
            x0 = x + w - a
            out.append(Cut(Vec(x0, y), a, Vec(x + w, y), Vec(x0, y + a), Vec(x0, y)))
            w -= a
        else:  # bottom
            a = w
            y0 = y + h - a
            out.append(Cut(Vec(x, y0), a, Vec(x + w, y + h), Vec(x, y0), Vec(x + w, y0)))
            h -= a
    return tuple(out)


CUTS = cuts()


def sheet(s: Canvas) -> None:
    """Crop marks at the sheet corners and a blank title block in the bottom-right corner."""
    m, t = 60, 28
    marks = P()
    for cx, sx in ((m, 1), (s.w - m, -1)):
        for cy, sy in ((m, 1), (s.h - m, -1)):
            marks.M(cx + sx * t, cy).H(cx).V(cy + sy * t)
    bw, bh = 264, 74
    bx, by = s.w - m - bw, s.h - m - bh
    marks.rect(bx, by, bw, bh)
    marks.M(bx, by + bh * 0.45).H(bx + bw).M(bx + bw * 0.62, by).V(by + bh)
    marks.M(bx + bw * 0.62, by + bh * 0.72).H(bx + bw)
    s.stroke(marks, FAINT, 1.2)


def construction(s: Canvas, dimensions: bool) -> None:
    """The rectangle, its squares, construction lines, spiral and, when `dimensions`, its
    dimensions, in local units."""
    for tint, c in zip(TINTS, CUTS, strict=True):
        s.fill(P().rect(c.corner.x, c.corner.y, c.side, c.side), tint)
    grid = P()
    for c in CUTS[1:]:
        grid.rect(c.corner.x, c.corner.y, c.side, c.side)
    s.stroke(grid, UI, 1.5)
    s.stroke(P().rect(0, 0, RW, RH), UI_ALT, 1.8)

    # compass construction: swing the half-square diagonal down to find the long side
    foot, corner = Vec(RH / 2, RH), Vec(RH, 0)
    r = abs(corner - foot)
    s.stroke(
        P().M(corner).A(r, r, 0, 0, 1, RW, RH).M(foot).L(corner),
        mix(UI, UI_ALT, 0.5),
        1.3,
        dash=(6, 4),
    )

    # the eye sits where the diagonals of the rectangle and its first remainder cross
    s.stroke(P().M(0, 0).L(RW, RH).M(RH, RH).L(RW, 0), UI, 1.2, dash=DASHDOT)

    # compass pin holes: the construction's foot and the first six arc centers
    pins = P().dots([foot, *(c.pivot for c in CUTS[:6])], 4)
    s.path(pins, fill=BG, stroke=UI_ALT, stroke_width=1.4)

    if dimensions:
        # dimensions: 1 and 1/phi along the top, 1 down the left side
        dims, heads = P(), P()
        for x in (0, RH, RW):
            dims.M(x, -12).V(-DIM - 12)
        for xa, xb in ((0, RH), (RH, RW)):
            dims.M(xa, -DIM).H(xb)
            heads.arrowhead((xb, -DIM), 14, deg=0).arrowhead((xa, -DIM), 14, deg=180)
        for y in (0, RH):
            dims.M(-12, y).H(-DIM - 12)
        dims.M(-DIM, 0).V(RH)
        heads.arrowhead((-DIM, RH), 14, deg=90).arrowhead((-DIM, 0), 14, deg=-90)
        s.stroke(dims, UI, 1.3)
        s.fill(heads, UI_ALT)

    for i, c in enumerate(CUTS):
        w = round(4.2 - 2.4 * i / (STEPS - 1), 2)
        s.stroke(P().M(c.start).A(c.side, c.side, 0, 0, 1, c.end), ACCENT, w, cap="round")


class Drawing(Params):
    dimensions: bool = knob(default=True, doc="the dimensions of the rectangle")


@design(aspects="any", variants={"undimensioned": Drawing(dimensions=False)})
def draw(s: Canvas[Drawing]) -> None:
    sheet(s)
    # Landscape keeps the original's spot right of center. Portrait stands the rectangle upright
    # with a quarter turn anticlockwise: the first square at the bottom, dimensions left and below.
    c = s.pick(landscape=(37 / 64, 14 / 27), portrait=(0.53, 0.465))
    turn = 0 if s.landscape else -90
    with s.group(transform=Affine.frame(c, deg=turn) @ Affine.translate(-RW / 2, -RH / 2)):
        construction(s, s.params.dimensions)
