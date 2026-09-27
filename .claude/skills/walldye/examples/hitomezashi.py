"""Hitomezashi sashiko: two bit strings set every running stitch; union-find labels the enclosed regions and one is picked out in accent."""

import random

from shapely.geometry import box
from shapely.ops import unary_union

from walldye import ACCENT, ACCENT_6, UI, H, P, W

ASPECTS = ["any"]

CELL = 30  # stitch length; canvas units are screen-independent (short side is always 1080)
COLS, ROWS = -(-W // CELL), -(-H // CELL)
GAP = 0.15  # fraction of each stitch left bare at both ends
INSET = 6  # appliqué inset of the accent patch
SEED = 11014


def bits(r, n):
    # mostly alternating bits draw long diagonal staircases; a few looser bands break the period like a hand-set row
    loose = {i for c in r.sample(range(2, n - 6), 2) for i in range(c, c + 5)}
    out = [r.random() < 0.5]
    while len(out) < n:
        out.append(out[-1] if r.random() < (0.4 if len(out) in loose else 0.12) else not out[-1])
    return [int(v) for v in out]


def regions(a, b):
    """Label each cell (row-major) by the region it belongs to: neighbours join where no stitch separates them."""
    parent = list(range(COLS * ROWS))

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for j in range(ROWS):
        for i in range(COLS):
            if i + 1 < COLS and (j + b[i + 1]) % 2:
                parent[find(j * COLS + i)] = find(j * COLS + i + 1)
            if j + 1 < ROWS and (i + a[j + 1]) % 2:
                parent[find(j * COLS + i)] = find((j + 1) * COLS + i)
    return [find(k) for k in range(COLS * ROWS)]


def patch(cells):
    return unary_union(
        [
            box(k % COLS * CELL, k // COLS * CELL, (k % COLS + 1) * CELL, (k // COLS + 1) * CELL)
            for k in cells
        ]
    )


def pick(label):
    """Cells of the ring-shaped region (it encloses a hole) nearest the focal point, fully inside the frame."""
    # focal point: right third on landscape, centred on portrait, a little above the middle on both
    fx, fy = (0.66 * W if W > H else 0.5 * W), 0.38 * H
    groups = {}
    for k, v in enumerate(label):
        groups.setdefault(v, []).append(k)
    best, best_d = [], float("inf")
    for cells in groups.values():
        if not 24 <= len(cells) <= 80:
            continue
        shape = patch(cells)
        x0, y0, x1, y1 = shape.bounds
        if (
            shape.geom_type != "Polygon"
            or not shape.interiors
            or x0 < 2 * CELL
            or y0 < 2 * CELL
            or x1 > W - 2 * CELL
            or y1 > H - 2 * CELL
        ):
            continue
        d = (shape.centroid.x - fx) ** 2 + (shape.centroid.y - fy) ** 2
        if d < best_d:
            best, best_d = cells, d
    return best


def draw(s):
    r = random.Random(SEED)
    # the short-axis string is drawn first, so a portrait screen gets the landscape cloth turned on its side
    short, long_ = bits(r, min(ROWS, COLS) + 1), bits(r, max(ROWS, COLS) + 1)
    a, b = (short, long_) if W >= H else (long_, short)  # a: one bit per row, b: one per column
    inside = set(pick(regions(a, b)))

    def seg(d, x0, y0, x1, y1):
        d.M(x0 + (x1 - x0) * GAP, y0 + (y1 - y0) * GAP).L(
            x0 + (x1 - x0) * (1 - GAP), y0 + (y1 - y0) * (1 - GAP)
        )

    # a stitch on the patch boundary (cells on either side differ in membership) is sewn in accent
    plain, hot = P(), P()
    for j in range(1, ROWS):
        for i in range(COLS):
            if (i + a[j]) % 2 == 0:
                edge = (j * COLS + i in inside) != ((j - 1) * COLS + i in inside)
                seg(hot if edge else plain, i * CELL, j * CELL, (i + 1) * CELL, j * CELL)
    for i in range(1, COLS):
        for j in range(ROWS):
            if (j + b[i]) % 2 == 0:
                edge = (j * COLS + i in inside) != (j * COLS + i - 1 in inside)
                seg(hot if edge else plain, i * CELL, j * CELL, i * CELL, (j + 1) * CELL)

    # inset like an appliqué patch so a background channel separates the cloth from the thread
    shape = patch(inside).buffer(-INSET, join_style=2)
    fill = P()
    for poly in getattr(shape, "geoms", [shape]):
        for ring in [poly.exterior, *poly.interiors]:
            fill.poly(ring.coords, closed=True)
    s.path(fill, fill=ACCENT_6, fill_rule="evenodd")
    s.path(plain, fill="none", stroke=UI, stroke_width=2.5, stroke_linecap="round")
    s.path(hot, fill="none", stroke=ACCENT, stroke_width=2.5, stroke_linecap="round")
