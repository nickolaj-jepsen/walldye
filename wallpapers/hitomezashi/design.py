"""Hitomezashi sashiko from two strings of stitch offsets, with one enclosed region flood-filled."""

import math

from shapely import box
from shapely.ops import unary_union

from walldye import ACCENT, ACCENT_6, UI, Canvas, P, Path, Rng, Vec, design

CELL = 30  # stitch length
GAP = 0.15  # fraction of each stitch left bare at both ends
INSET = 6  # appliqué inset of the patch
COLS, ROWS = 64, 36  # the tuned piece of cloth, one 16:9 screen of cells
PANELS = 2  # more pieces of cloth on every side of it, enough for any screen shape
# ANCHOR is a cell of the hand-picked region for this seed: a diamond ring with a stem and one side lobe
SEED, ANCHOR = 11014, (42, 8)


def bits(rng: Rng, n: int) -> list[int]:
    """`n` stitch offsets: mostly alternating bits draw long diagonal staircases, and a few
    looser bands break the period like a hand-set row."""
    loose = {i for c in rng.sample(range(2, n - 6), 2) for i in range(c, c + 5)}
    out = [rng.random() < 0.5]
    while len(out) < n:
        out.append(out[-1] if rng.random() < (0.4 if len(out) in loose else 0.12) else not out[-1])
    return [int(v) for v in out]


def widen(core: list[int], rng: Rng) -> dict[int, int]:
    """Offsets by line index: `core` at 0 .. len(core) - 1, with PANELS more runs of its length,
    drawn like it, before and after."""
    n = len(core)
    out = dict(enumerate(core))
    for k in range(1, PANELS + 1):
        out |= {i - k * n: v for i, v in enumerate(bits(rng, n))}
        out |= {i + k * n: v for i, v in enumerate(bits(rng, n))}
    return out


def region(a: dict[int, int], b: dict[int, int], start: tuple[int, int]) -> set[tuple[int, int]]:
    """The cells (column, row) reachable from `start` without crossing a stitch. Row line j
    carries a stitch below cell column i when i + a[j] is even; column line i one beside cell
    row j when j + b[i] is even. Raises KeyError if the region runs off the cloth."""
    seen = {start}
    todo = [start]
    while todo:
        i, j = todo.pop()
        steps = (
            ((i + 1, j), j + b[i + 1]),
            ((i - 1, j), j + b[i]),
            ((i, j + 1), i + a[j + 1]),
            ((i, j - 1), i + a[j]),
        )
        for cell, parity in steps:
            if parity % 2 and cell not in seen:
                seen.add(cell)
                todo.append(cell)
    return seen


@design(aspects="any")
def draw(s: Canvas) -> None:
    r = s.rng(SEED)
    core_a, core_b = bits(r, ROWS + 1), bits(r, COLS + 1)
    more = s.rng("cloth")
    a, b = widen(core_a, more), widen(core_b, more)  # a: one offset per row line, b: per column
    inside = region(a, b, ANCHOR)

    # the screen is a window onto the cloth, shifted by whole cells so the patch sits on the focus
    focus = s.pick(landscape=(0.7, 0.375), portrait=(0.5, 0.38))
    xs, ys = [i for i, _ in inside], [j for _, j in inside]
    mid = Vec(min(xs) + max(xs) + 1, min(ys) + max(ys) + 1) / 2
    x0, y0 = round(mid.x - focus.x / CELL), round(mid.y - focus.y / CELL)
    o = Vec(-x0, -y0) * CELL
    cols = range(x0, x0 + math.ceil(s.w / CELL))
    rows = range(y0, y0 + math.ceil(s.h / CELL))

    def seg(d: Path, p0: Vec, p1: Vec) -> None:
        d.M(p0 + (p1 - p0) * GAP).L(p1 + (p0 - p1) * GAP)

    # a stitch on the patch boundary (cells on either side differ in membership) is picked out
    plain, edge = P(), P()
    for j in rows[1:]:
        for i in cols:
            if (i + a[j]) % 2 == 0:
                hot = ((i, j) in inside) != ((i, j - 1) in inside)
                seg(edge if hot else plain, o + Vec(i, j) * CELL, o + Vec(i + 1, j) * CELL)
    for i in cols[1:]:
        for j in rows:
            if (j + b[i]) % 2 == 0:
                hot = ((i, j) in inside) != ((i - 1, j) in inside)
                seg(edge if hot else plain, o + Vec(i, j) * CELL, o + Vec(i, j + 1) * CELL)

    # inset like an appliqué patch, so a background channel separates the cloth from the thread
    cells = []
    for i, j in sorted(inside):
        x, y = o + Vec(i, j) * CELL
        cells.append(box(x, y, x + CELL, y + CELL))
    s.fill(P().shape(unary_union(cells).buffer(-INSET, join_style="mitre")), ACCENT_6)
    s.stroke(plain, UI, 2.5, cap="round")
    s.stroke(edge, ACCENT, 2.5, cap="round")
