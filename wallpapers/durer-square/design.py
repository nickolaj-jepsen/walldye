"""The Melencolia magic square counted out in pips, one per unit, and joined from 1 to 16 by a single line over a few close retracings."""

from walldye import ACCENT, ACCENT_3, BG, UI, UI_ALT, Canvas, P, Rng, Vec, design

S = 480  # side of the square; each cell is S / 4
SQUARE = ((16, 3, 2, 13), (5, 10, 11, 8), (9, 6, 7, 12), (4, 15, 14, 1))
CELL = {v: (c, r) for r, row in enumerate(SQUARE) for c, v in enumerate(row)}
RING = 10  # radius of the open ring on 16
RETRACINGS = 6
PIP, PITCH = 5, 22  # pip radius; pips sit on a 4 x 4 grid inside each cell
YEAR = (15, 14)  # the bottom row's middle pair, the year the square was engraved


def jitter(rng: Rng, k: float, i: int) -> float:
    """An offset in cells for column or row `i` of the square, drawn from [-k, k] but limited to
    k / 3 on the side facing out of the square in the edge columns and rows."""
    lo = -k / 3 if i == 0 else -k
    hi = k / 3 if i == 3 else k
    return rng.uniform(lo, hi)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of center on a landscape screen, the upper part of a portrait one; whole units keep
    # the corner ticks on the pixel grid
    corner = s.pick(landscape=(0.71875, 0.5), portrait=(0.5, 0.38), snap=1) - (S / 2, S / 2)
    cs = S / 4

    def at(v: int, dx: float = 0.0, dy: float = 0.0) -> Vec:
        col, row = CELL[v]
        return corner + ((col + 0.5 + dx) * cs, (row + 0.5 + dy) * cs)

    # ticks on the inner grid crossings and the four outer corners, none on the edge midpoints
    ticks = P()
    for i in range(5):
        for j in range(5):
            if 0 < i < 4 and 0 < j < 4 or i in (0, 4) and j in (0, 4):
                x, y = corner + (i * cs, j * cs)
                ticks.M(x - 6, y).H(x + 6).M(x, y - 6).V(y + 6)
    s.stroke(ticks, UI, 1.5)

    # Each number as that many pips, filling its cell's grid in reading order.
    pips, year = P(), P()
    for v in range(1, 17):
        for n in range(v):
            p = at(v) + ((n % 4 - 1.5) * PITCH, (n // 4 - 1.5) * PITCH)
            (year if v in YEAR else pips).circle(p, PIP)
    s.fill(pips, UI_ALT)
    s.fill(year, ACCENT_3)

    rng = s.rng(1948)
    # A few close retracings, one path each so their overlaps compound.
    with s.group(stroke_opacity=0.4):
        for _ in range(RETRACINGS):
            k = rng.uniform(0.06, 0.16)
            pts = [
                at(v, jitter(rng, k, CELL[v][0]), jitter(rng, k, CELL[v][1])) for v in range(1, 17)
            ]
            s.stroke(P().poly(pts), UI, 1.2, join="round")

    true = [at(v) for v in range(1, 17)]
    # The last leg stops at the open ring's outer edge so the ring reads as a clean terminal.
    a, b = true[-2], true[-1]
    line = [*true[:-1], b - (b - a).unit() * (RING + 3.5)]
    # A halo lifts the line off the pips and retracings it crosses.
    s.stroke(P().poly(line), BG, 6, join="round", cap="round")
    s.stroke(P().poly(line), ACCENT, 2.4, join="round", cap="round")
    s.fill(P().circle(true[0], 7), ACCENT)
    s.stroke(P().circle(b, RING), ACCENT, 2.5)
