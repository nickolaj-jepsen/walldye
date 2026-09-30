"""A still frame of the pipes.sh screensaver: random-walk pipes of box-drawing glyphs."""

import math
from collections import Counter
from itertools import pairwise

from walldye import ACCENT, ACCENT_3, BG_ALT, UI, UI_ALT, Canvas, Color, P, Rng, design
from walldye.pixel import glyphs

type Cell = tuple[int, int]

PX, CW, CH = 2, 16, 32  # 8x16 font at px 2: one glyph cell in canvas units
BLEED = 8  # at least this much of the edge rows runs off-screen, so exiting pipes leave cleanly
DIRS: dict[str, Cell] = {"R": (1, 0), "L": (-1, 0), "D": (0, 1), "U": (0, -1)}
OPP = {"R": "L", "L": "R", "U": "D", "D": "U"}
GLYPH = {"LR": "━", "DU": "┃", "DR": "┏", "DL": "┓", "RU": "┗", "LU": "┛"}
LOOK, RUN = 8, 6  # turn look-ahead, min straight cells between turns
REGION = (20, 8)  # cells per density-scoring region
QUIET = (46 / 120, 13 / 34)  # the top-left corner no pipe enters, as fractions of the grid
# Oldest first, so later pipes overdraw earlier ones: (entry edge, position along it as a
# fraction of the 120x34-cell 16:9 grid, tone, most cells before it must have left).
PIPES: list[tuple[str, float, Color, int]] = [
    ("D", 16 / 120, UI, 150),
    ("R", 29 / 34, UI, 140),
    ("U", 64 / 120, UI_ALT, 90),
    ("D", 102 / 120, BG_ALT, 110),
    ("L", 20 / 34, BG_ALT, 110),
    ("U", 112 / 120, BG_ALT, 90),
    ("D", 58 / 120, BG_ALT, 90),
    ("R", 2 / 34, BG_ALT, 120),
]
# The newest pipe, traced back from its head: cells per run, alternately right and up, before
# the last run to the right edge. The first two runs are the part still being drawn.
STAIR = {True: (8, 9, 16, 8), False: (6, 14, 10, 12)}


def step(p: Cell, k: str) -> Cell:
    return p[0] + DIRS[k][0], p[1] + DIRS[k][1]


def walk(
    rng: Rng,
    size: Cell,
    edge: str,
    pos: int,
    grid: dict[Cell, tuple[str, Color]],
    block: set[Cell],
    quiet: Cell,
    tone: Color,
    n: int,
) -> bool:
    """Add one pipe entering at `edge` to `grid`; True if it leaves the screen again within `n`
    cells. It never enters `block`, the `quiet` corner or its own trail, and crosses an older
    pipe only through a perpendicular straight."""
    cols, rows = size
    p, d = {
        "R": ((cols - 1, pos), "L"),
        "L": ((0, pos), "R"),
        "D": ((pos, rows - 1), "U"),
        "U": ((pos, 0), "D"),
    }[edge]
    came, run, own = edge, 0, set[Cell]()

    def out(p: Cell) -> bool:
        return not (0 <= p[0] < cols and 0 <= p[1] < rows)

    def ok(p: Cell, k: str) -> bool:
        if out(p):
            return True
        if p in block or p in own or (p[0] < quiet[0] and p[1] < quiet[1]):
            return False
        # an older pipe's perpendicular straight may be crossed, like pipes.sh overdraw
        return p not in grid or grid[p][0] == ("┃" if k in "LR" else "━")

    def clear(p: Cell, k: str) -> bool:  # look ahead so a turn never curls back into the trail
        for _ in range(LOOK):
            p = step(p, k)
            if out(p):
                return True
            if p in own or p in block:
                return False
        return True

    if not ok(p, d):
        return False
    for _ in range(n):
        turns = [k for k in rng.sample([k for k in DIRS if k not in (d, OPP[d])], 2) if clear(p, k)]
        opts = ([d] if run < RUN or rng.random() < 0.9 else []) + (turns if run >= RUN else [])
        k = next((k for k in opts if ok(step(p, k), k)), None)
        if k is None:
            return False
        grid[p] = (GLYPH["".join(sorted(came + k))], tone)
        own.add(p)
        run = run + 1 if k == d else 0
        came, d, p = OPP[k], k, step(p, k)
        if out(p):
            return True
        if p in grid:  # crossing: the newer pipe's straight simply overwrites the cell
            grid[p] = ("━" if k in "LR" else "┃", tone)
            own.add(p)
            p = step(p, k)
            if out(p):
                return True
            if not ok(p, k):
                return False
            run += 1
    return False


@design(aspects="any")
def draw(s: Canvas) -> None:
    cols, rows = math.ceil(s.w / CW), math.ceil((s.h + BLEED) / CH)
    # center the grid on the canvas, its origin on the font-pixel grid
    x0, y0 = -((cols * CW - s.w) // (2 * PX)) * PX, -((rows * CH - s.h) // (2 * PX)) * PX
    quiet = (round(QUIET[0] * cols), round(QUIET[1] * rows))

    # The newest pipe enters from the right edge and steps down towards its head.
    head = s.pick(landscape=(82 / 120, 23 / 34), portrait=(0.6, 0.62))
    hc, hr = round((head.x - x0) / CW), round((head.y - y0) / CH)
    a, b, c, e = STAIR[s.landscape]
    way = [
        (cols - 1, hr - b - e),
        (hc + 1 + a + c, hr - b - e),
        (hc + 1 + a + c, hr - b),
        (hc + 1 + a, hr - b),
        (hc + 1 + a, hr),
        (hc + 1, hr),
    ]
    accent: list[tuple[Cell, str]] = []
    came = "R"
    for (c0, r0), (c1, r1) in pairwise(way):
        k = "L" if c1 < c0 else "R" if c1 > c0 else "D" if r1 > r0 else "U"
        p = (c0, r0)
        while p != (c1, r1):
            if accent and accent[-1][0] == p:
                accent.pop()
            accent.append((p, GLYPH["".join(sorted(came + k))]))
            p, came = step(p, k), OPP[k]
    accent.append((way[-1], "━"))
    hot = [p for p, _ in accent].index(way[-3])  # the last two runs are the hot, newest part

    # a moat so the newest pipe, and its head most of all, reads on its own
    block: set[Cell] = set()
    for (c0, r0), _ in accent:
        m = 6 if abs(c0 - hc) + abs(r0 - hr) < 6 else 2
        block |= {(c0 + i, r0 + j) for i in range(-m, m + 1) for j in range(-m // 2, m // 2 + 1)}

    grid: dict[Cell, tuple[str, Color]] = {}
    grow = max(1.0, (cols + rows) / 154)  # a bigger grid needs longer walks to cross it
    # A bigger grid gets more pipes for the same density: the first few again, entering half
    # an edge further along, each right after its original.
    extra = max(0, round(len(PIPES) * cols * rows / (120 * 34)) - len(PIPES))
    pipes = [
        q
        for i, (edge, f, tone, n) in enumerate(PIPES)
        for q in [(edge, f, tone, n)] + ([(edge, (f + 0.5) % 1, tone, n)] if i < extra else [])
    ]
    for edge, f, tone, n in pipes:
        pos = round(f * (cols if edge in "DU" else rows))
        # of the seeded walks that cross the screen, keep the longest that fills the emptiest regions
        best: tuple[float, dict[Cell, tuple[str, Color]]] | None = None
        for seed in range(40):
            g = dict(grid)
            if not walk(
                s.rng(seed), (cols, rows), edge, pos, g, block, quiet, tone, round(n * grow)
            ):
                continue
            dens = Counter((c0 // REGION[0], r0 // REGION[1]) for c0, r0 in g)
            score = len(g) - 0.02 * sum(v * v for v in dens.values())
            if best is None or score > best[0]:
                best = (score, g)
        grid = best[1] if best else grid

    for i, (p, ch) in enumerate(accent):
        grid[p] = (ch, ACCENT if i >= hot else ACCENT_3)
    lines = [[" "] * cols for _ in range(rows)]
    for (c0, r0), (ch, _) in grid.items():
        lines[r0][c0] = ch
    glyphs(s, ["".join(r) for r in lines], lambda c, r, ch: grid[c, r][1], at=(x0, y0), px=PX)
    # the block cursor, one cell past the pipe and 4 units clear of it
    s.fill(P().rect(x0 + hc * CW - 4, y0 + hr * CH, CW, CH), ACCENT)
