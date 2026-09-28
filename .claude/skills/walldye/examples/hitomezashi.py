"""Hitomezashi sashiko: two bit strings set every running stitch; union-find labels the enclosed regions and one is picked out as an appliqué patch."""

import math

from shapely import Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import ACCENT, ACCENT_6, UI, Canvas, P, Path, Rng, Vec, design

CELL = 30  # stitch length
GAP = 0.15  # fraction of each stitch left bare at both ends
INSET = 6  # appliqué inset of the patch


def bits(rng: Rng, n: int) -> list[int]:
    """`n` stitch offsets: mostly alternating bits draw long diagonal staircases, and a few
    looser bands break the period like a hand-set row."""
    loose = {i for c in rng.sample(range(2, n - 6), 2) for i in range(c, c + 5)}
    out = [rng.random() < 0.5]
    while len(out) < n:
        out.append(out[-1] if rng.random() < (0.4 if len(out) in loose else 0.12) else not out[-1])
    return [int(v) for v in out]


def regions(a: list[int], b: list[int], cols: int, rows: int) -> list[int]:
    """Label each cell (row-major) by the region it belongs to: neighbours join where no
    stitch separates them."""
    parent = list(range(cols * rows))

    def find(k: int) -> int:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for j in range(rows):
        for i in range(cols):
            if i + 1 < cols and (j + b[i + 1]) % 2:
                parent[find(j * cols + i)] = find(j * cols + i + 1)
            if j + 1 < rows and (i + a[j + 1]) % 2:
                parent[find(j * cols + i)] = find((j + 1) * cols + i)
    return [find(k) for k in range(cols * rows)]


def patch(cells: list[int] | set[int], cols: int) -> BaseGeometry:
    """The union of the given cells as one shapely geometry."""
    return unary_union(
        [
            box(k % cols * CELL, k // cols * CELL, (k % cols + 1) * CELL, (k // cols + 1) * CELL)
            for k in cells
        ]
    )


def pick(label: list[int], cols: int, s: Canvas) -> list[int]:
    """The cells of the ring-shaped region (one enclosing a hole) nearest the focal point,
    fully inside the frame."""
    # right third on landscape, centred on portrait, a little above the middle on both
    focus = s.pick(landscape=(0.66, 0.38), portrait=(0.5, 0.38))
    frame = s.inset(2 * CELL)
    groups: dict[int, list[int]] = {}
    for k, v in enumerate(label):
        groups.setdefault(v, []).append(k)
    best: list[int] = []
    best_d = math.inf
    for cells in groups.values():
        if not 24 <= len(cells) <= 80:
            continue
        shape = patch(cells, cols)
        x0, y0, x1, y1 = shape.bounds
        inside = frame.contains((x0, y0)) and frame.contains((x1, y1))
        if not isinstance(shape, Polygon) or len(shape.interiors) == 0 or not inside:
            continue
        d = abs(Vec(shape.centroid.x, shape.centroid.y) - focus)
        if d < best_d:
            best, best_d = cells, d
    return best


@design(aspects="any")
def draw(s: Canvas) -> None:
    cols, rows = math.ceil(s.w / CELL), math.ceil(s.h / CELL)
    rng = s.rng(11014)
    # the short-axis string is drawn first, so a portrait screen gets the landscape cloth turned
    # on its side
    short, long_ = bits(rng, min(rows, cols) + 1), bits(rng, max(rows, cols) + 1)
    a, b = (short, long_) if s.landscape else (long_, short)  # a: one bit per row, b: per column
    inside = set(pick(regions(a, b, cols, rows), cols, s))

    def seg(d: Path, p0: Vec, p1: Vec) -> None:
        d.M(p0 + (p1 - p0) * GAP).L(p1 + (p0 - p1) * GAP)

    # a stitch on the patch boundary (cells on either side differ in membership) is picked out
    plain, edge = P(), P()
    for j in range(1, rows):
        for i in range(cols):
            if (i + a[j]) % 2 == 0:
                hot = (j * cols + i in inside) != ((j - 1) * cols + i in inside)
                seg(edge if hot else plain, Vec(i, j) * CELL, Vec(i + 1, j) * CELL)
    for i in range(1, cols):
        for j in range(rows):
            if (j + b[i]) % 2 == 0:
                hot = (j * cols + i in inside) != (j * cols + i - 1 in inside)
                seg(edge if hot else plain, Vec(i, j) * CELL, Vec(i, j + 1) * CELL)

    # inset like an appliqué patch, so a background channel separates the cloth from the thread
    s.fill(P().shape(patch(inside, cols).buffer(-INSET, join_style="mitre")), ACCENT_6)
    s.stroke(plain, UI, 2.5, cap="round")
    s.stroke(edge, ACCENT, 2.5, cap="round")
