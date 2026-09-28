"""A hung weaving after Anni Albers: half-square triangles in chevron bands, crossed by a zigzag road of triangles lit more strongly as it climbs."""

from shapely.geometry import Polygon
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_6,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    Colour,
    P,
    Vec,
    design,
    ladder,
    ramp,
)

COLS, ROWS, CELL = 12, 20, 40
SIZE = Vec(COLS * CELL, ROWS * CELL)
# (column step per row climbed, rows): corner to corner, bottom-left to top-right
RUNS = ((1, 8), (-1, 4), (1, 7))
THREAD = 20  # fringe pitch; threads hang 44 to 56 below the weave

type Tri = list[Vec]


def tris(o: Vec, i: int, j: int, flip: bool) -> tuple[Tri, Tri]:
    """Cell (i, j)'s two triangles (upper, lower) on a weave with its top-left corner at `o`;
    `flip` cuts the cell along / instead of \\."""
    tl = o + (i * CELL, j * CELL)
    tr, br, bl = tl + (CELL, 0), tl + (CELL, CELL), tl + (0, CELL)
    return ([tl, tr, bl], [tr, br, bl]) if flip else ([tl, tr, br], [tl, br, bl])


def road() -> dict[tuple[int, int], tuple[int, bool]]:
    """{cell: (step index, flip)} along the zigzag, from the bottom row upward."""
    i, j, out = 0, ROWS - 1, {}
    for di, n in RUNS:
        for _ in range(n):
            out[(i, j)] = (len(out), di > 0)
            i, j = i + di, j - 1
    out[(i, j)] = (len(out), RUNS[-1][0] > 0)
    return out


def area(s: Canvas, pieces: list[Tri], paint: Colour) -> None:
    """Fill the union of `pieces` as one shape, so no internal edge can seam."""
    s.fill(P().shape(unary_union([Polygon(t) for t in pieces])), paint)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: right of centre, weave and fringe centred on the height; portrait: mid-screen
    o = s.pick(landscape=(1400 / 1920, 512 / 1080), portrait=(0.5, 0.5), snap=1) - SIZE / 2
    r = s.rng(24)
    path = road()
    n = len(path)
    light = ladder((ACCENT_3, ACCENT_1, ACCENT), n)
    dark = ramp(ACCENT_6, ACCENT_3, n)
    ui: list[Tri] = []
    hi: list[Tri] = []
    for j in range(ROWS):
        for i in range(COLS):
            if (i, j) in path:
                continue
            odd = r.random() < 0.1
            upper, lower = tris(o, i, j, (j % 2 == 1) ^ odd)
            # the plain weave: warp-lit upper halves in bands of two columns
            if odd:
                hi.append(upper)
            elif (i // 2 + j) % 2 == 0:
                ui.append(upper)
            else:
                ui.append(lower)
    # painted in layers so every edge blends into the colour beneath, not the wall
    s.fill(P().rect(o.x, o.y, SIZE.x, SIZE.y), BG_ALT)
    area(s, ui, UI)
    area(s, hi, UI_ALT)
    for (i, j), (k, flip) in path.items():
        s.fill(P().rect(o.x + i * CELL, o.y + j * CELL, CELL, CELL), dark[k])
        s.fill(P().poly(tris(o, i, j, flip)[0], closed=True), light[k])
    fringe = P()
    bottom = o.y + SIZE.y
    for k in range(int(SIZE.x) // THREAD):
        fringe.M(o.x + THREAD / 2 + k * THREAD, bottom - 1).V(bottom + r.uniform(44, 56))
    s.stroke(fringe, UI, 1.5)
