"""A woven runner of half-square triangles in chevron bands, crossed by a zigzag road of triangles."""

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
    Color,
    P,
    Vec,
    design,
    ladder,
    ramp,
)

COLS, ROWS, CELL = 24, 10, 40  # along and across the runner
# (row step per column, columns): a W from the lower left corner, rising first
RUNS = ((-1, 7), (1, 6), (-1, 6), (1, 4))
THREAD = 20  # fringe pitch; threads hang 44 to 56 beyond each end

type Tri = list[Vec]


def tris(i: int, j: int, flip: bool) -> tuple[Tri, Tri]:
    """Cell (i, j)'s two triangles (upper, lower) in runner space, top-left corner at the origin;
    `flip` cuts the cell along / instead of \\."""
    tl = Vec(i * CELL, j * CELL)
    tr, br, bl = tl + (CELL, 0), tl + (CELL, CELL), tl + (0, CELL)
    return ([tl, tr, bl], [tr, br, bl]) if flip else ([tl, tr, br], [tl, br, bl])


def road() -> dict[tuple[int, int], tuple[int, bool]]:
    """{cell: (step index, flip)} along the zigzag, left to right."""
    i, j, out = 0, ROWS - 1, {}
    for dj, n in RUNS:
        for _ in range(n):
            out[(i, j)] = (len(out), dj < 0)
            i, j = i + 1, j + dj
    out[(i, j)] = (len(out), RUNS[-1][0] < 0)
    return out


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: the runner lies across, a little below center; portrait: it hangs, mirrored
    # across its diagonal so the road zigzags down the screen
    size = Vec(COLS * CELL, ROWS * CELL)
    wide = s.landscape
    zoom = 1.0 if wide else 1.25  # a hanging runner is drawn larger to fill the tall screen
    shown = (size if wide else Vec(size.y, size.x)) * zoom
    o = s.pick(landscape=(0.5, 0.54), portrait=(0.5, 0.5), snap=1) - shown / 2

    def at(p: Vec) -> Vec:
        return o + (p if wide else Vec(p.y, p.x)) * zoom

    def tri(t: Tri) -> Tri:
        return [at(p) for p in t]

    def area(pieces: list[Tri], paint: Color) -> None:
        """Fill the union of `pieces` as one shape, so no internal edge can seam."""
        s.fill(P().shape(unary_union([Polygon(tri(t)) for t in pieces])), paint)

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
            upper, lower = tris(i, j, (i % 2 == 1) ^ odd)
            # the plain weave: lit upper halves in bands of two rows
            if odd:
                hi.append(upper)
            elif (j // 2 + i) % 2 == 0:
                ui.append(upper)
            else:
                ui.append(lower)
    # painted in layers so every edge blends into the color beneath, not the wall
    s.fill(P().poly(tri([Vec(0, 0), Vec(size.x, 0), size, Vec(0, size.y)]), closed=True), BG_ALT)
    area(ui, UI)
    area(hi, UI_ALT)
    for (i, j), (k, flip) in path.items():
        cell = [
            Vec(i, j) * CELL,
            Vec(i + 1, j) * CELL,
            Vec(i + 1, j + 1) * CELL,
            Vec(i, j + 1) * CELL,
        ]
        s.fill(P().poly(tri(cell), closed=True), dark[k])
        s.fill(P().poly(tri(tris(i, j, flip)[0]), closed=True), light[k])
    fringe = P()
    for k in range(int(size.y) // THREAD):
        y = THREAD / 2 + k * THREAD
        for x0, sign in ((0.0, -1), (size.x, 1)):
            fringe.M(at(Vec(x0 - sign, y))).L(at(Vec(x0 + sign * r.uniform(44, 56), y)))
    s.stroke(fringe, UI, 1.5 * zoom)
