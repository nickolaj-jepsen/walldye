"""A lightning strike grown by dielectric breakdown on a square lattice: one return stroke reaches the ground among fading branch leaders."""

import numpy as np
from shapely.geometry import LineString

from walldye import (
    ACCENT,
    ACCENT_4,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    NpRng,
    P,
    Path,
    by_regime,
    design,
    mix,
)

type Cell = tuple[int, int]  # (row, col)
type Tree = dict[Cell, Cell | None]  # each cell's parent; the start cell has none

CELL = 12
SPAN = 160  # lattice columns on every landscape screen: the 16:9 width
DEPTH = 180  # ground band below the contact point on landscape screens
PORTRAIT_START = 0.45  # start column on portrait screens, as a fraction of the width
PORTRAIT_GROUND = 0.86  # ground line on portrait screens, as a fraction of the height
ETA = 1.2  # growth follows the potential to this power
SIDE = 0.55  # growth weight sideways; straight down is 1 and upward 0.02
SEED = 2
NBRS = tuple((dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx)
TONES = (UI_ALT, UI, BG_ALT)
GROUND = by_regime(BG_DEEP, mix(BG, BG_ALT, 0.5))  # a band a step darker than the sky
# Per branch order (1, 2, 3+), the (tone index, width) of its root 40 %, middle 35 % and tip:
# leaders thin out from the junction and fade one tone further at the tip.
TAPER = (
    ((0, 1.6), (0, 1.2), (1, 0.8)),
    ((1, 1.3), (1, 0.98), (2, 0.8)),
    ((2, 1.1), (2, 0.83), (2, 0.8)),
)


def breakdown(rng: NpRng, cols: int, rows: int, ground: int, start: Cell) -> tuple[Tree, Cell]:
    """Grow a dielectric-breakdown cluster from `start` on a `rows` x `cols` lattice, cell by cell,
    until it reaches row `ground` - 1. The potential is 0 on the cluster and the top row and 1
    from row `ground` down, relaxed by 25 Jacobi sweeps per step. Returns the parent map and the
    cell that touched down."""
    phi = np.tile(np.clip(np.arange(rows) / ground, 0, 1)[:, None], (1, cols))
    fixed = np.zeros((rows, cols), bool)
    fixed[0], fixed[ground:] = True, True
    cluster = np.zeros_like(fixed)
    parent: Tree = {start: None}
    cluster[start] = True
    phi[start] = 0
    while True:
        for _ in range(25):
            p = np.pad(phi, 1, mode="edge")
            avg = 0.25 * (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:])
            phi = np.where(fixed | cluster, phi, avg)
        c = np.pad(cluster, 1)
        grown = np.zeros_like(cluster)
        for dy, dx in NBRS:
            grown |= c[1 + dy : rows + 1 + dy, 1 + dx : cols + 1 + dx]
        cand = grown & ~cluster
        cand[:, [0, -1]] = False
        above = c[:-2, :-2] | c[:-2, 1:-1] | c[:-2, 2:]
        side = c[1:-1, :-2] | c[1:-1, 2:]
        bias = np.where(above, 1.0, np.where(side, SIDE, 0.02))
        ys, xs = np.nonzero(cand)
        w = np.clip(phi[ys, xs], 0, 1) ** ETA * bias[ys, xs]
        k = rng.choice(len(ys), p=w / w.sum())
        cell = (int(ys[k]), int(xs[k]))
        opts = [(cell[0] + dy, cell[1] + dx) for dy, dx in NBRS]
        opts = [o for o in opts if o in parent]
        opts = [o for o in opts if o[0] < cell[0]] or opts
        parent[cell] = opts[rng.integers(len(opts))]
        cluster[cell] = True
        phi[cell] = 0
        if cell[0] >= ground - 1:
            return parent, cell


def strands(parent: Tree, contact: Cell) -> list[tuple[int, list[Cell]]]:
    """The tree cut into polylines as (order, cells): order 0 is the channel from the start to
    `contact`, and each branch is one order above the strand it leaves. A strand follows its
    largest subtree; side subtrees of fewer than 3 cells are dropped."""
    kids: dict[Cell, list[Cell]] = {}
    for c, p in parent.items():
        if p is not None:
            kids.setdefault(p, []).append(c)
    # parents come before their children in `parent`, so one backward pass sums subtree sizes
    size = dict.fromkeys(parent, 1)
    for c in reversed(parent):
        p = parent[c]
        if p is not None:
            size[p] += size[c]
    main = set[Cell]()
    step: Cell | None = contact
    while step is not None:
        main.add(step)
        step = parent[step]
    root = next(iter(parent))
    out: list[tuple[int, list[Cell]]] = []
    stack: list[tuple[Cell, int, Cell | None]] = [(root, 0, None)]
    while stack:
        c, order, prev = stack.pop()
        line = [prev, c] if prev else [c]
        while kids.get(c):
            ks = sorted(kids[c], key=lambda k: (k in main, size[k]), reverse=True)
            for k in ks[1:]:
                if size[k] >= 3:
                    stack.append((k, order + 1 if order or k not in main else 0, c))
            c = ks[0]
            line.append(c)
        out.append((order, line))
    return out


def simplify(pts: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """Douglas-Peucker simplification of a polyline with more than two points."""
    if len(pts) <= 2:
        return pts
    return [(x, y) for x, y, *_ in LineString(pts).simplify(tol).coords]


@design(aspects="any")
def draw(s: Canvas) -> None:
    if s.landscape:
        # one strike for every landscape shape, grown on the 16:9 lattice and shifted so that
        # it starts at the same fraction of the width
        cols, start = SPAN, 43
        dx = (s.w / (SPAN * CELL) - 1) * (start + 0.5) * CELL
        ground = (s.h - DEPTH) // CELL
    else:
        cols, dx = s.w // CELL, 0.0
        start = round(cols * PORTRAIT_START)
        ground = round(s.h * PORTRAIT_GROUND / CELL)
    gy = ground * CELL
    rng = s.np_rng(SEED)
    parent, contact = breakdown(rng, cols, s.h // CELL + 1, ground, (0, start))
    jit = {c: rng.uniform(-0.35, 0.35, 2) for c in parent}

    def xy(c: Cell) -> tuple[float, float]:
        return (c[1] + 0.5 + jit[c][1]) * CELL + dx, (c[0] + jit[c][0]) * CELL

    s.fill(P().rect(0, gy, s.w, s.h - gy), GROUND)
    glow = s.radial_gradient([(0, ACCENT_4, 0.8), (1, BG, 0)], (0.5, 0.5), 0.5, units="bbox")
    s.fill(P().ellipse((xy(contact)[0], gy - 7), 150, 16), glow)
    s.stroke(P().M(0, gy).H(s.w), UI, 1.5)

    legs: dict[tuple[int, float], Path] = {}
    channel: list[tuple[float, float]] = []
    for order, line in strands(parent, contact):
        pts = [xy(c) for c in line]
        if order == 0:
            # the entry is a lattice scribble; straighten it harder than the rest
            k = next(i for i, p in enumerate(pts) if p[1] > 110)
            channel = simplify(pts[: k + 1], 7)[:-1] + simplify(pts[k:], 3.5) + [(pts[-1][0], gy)]
            continue
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        if y1 - y0 < 0.6 * abs(x1 - x0):
            continue  # mostly sideways leaders read as noise
        pts = simplify(pts, 2.5)
        n = len(pts)
        for key, (lo, hi) in zip(TAPER[min(order, 3) - 1], ((0, 0.4), (0.4, 0.75), (0.75, 1))):
            seg = pts[int(lo * (n - 1)) : int(hi * (n - 1)) + 1]
            if len(seg) > 1:
                legs.setdefault(key, P()).poly(seg)
    with s.group(stroke_linecap="round", stroke_linejoin="round"):
        # faintest leaders first, the return stroke on top, thinning in six steps to the ground
        for (t, w), d in sorted(legs.items(), key=lambda kv: -kv[0][0]):
            s.stroke(d, TONES[t], w)
        n = len(channel)
        for k in range(6):
            seg = channel[k * n // 6 : (k + 1) * n // 6 + 1]
            s.stroke(P().poly(seg), ACCENT, 4.2 - 2.4 * k / 5)
