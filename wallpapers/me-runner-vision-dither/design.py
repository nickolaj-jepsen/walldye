"""Mirror's Edge runner vision: a concrete rooftop in one-point perspective where only the route is picked out, every surface set on one grid of cells shaded with 4x4 ordered dither."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from skimage.draw import line, polygon

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    BG,
    BG_ALT,
    BG_DEEP,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    P,
    Point,
    Ref,
    Vec,
    by_regime,
    design,
    mix,
)
from walldye.pixel import bayer, grid_runs

type Mask = NDArray[np.bool_]
type Levels = NDArray[np.int64]
type Stack = tuple[Colour | None, tuple[tuple[Colour, int], ...]]

# Camera: one-point perspective, metres in world space, heights relative to our roof.
VX, VY, F, EYE = 1060, 420, 1000, 1.7
EDGE = 8.0  # depth of our parapet's inner face
LIP = 0.3  # parapet height
WING_X, WING_H = -5.5, 3.2  # stair block on our roof; its wall faces the camera side
FOOT = 640  # screen y of every building's foot, hidden behind our parapet
CELL = 4  # every surface sits on this grid of cells; a dither tile is 4x4 cells
TILE = 4 * CELL
HAZE = mix(BG_ALT, UI, 0.35)
# Dither ramps by role: (under, over). Level k lights k of 16 cells in `over`. On paper our roof
# (SLAB) steps down a tone, so the floor stays a quiet ground instead of the heaviest mass.
SKY = (BG, BG_ALT)
CONCRETE = (UI, UI_ALT)
SLAB = (by_regime(UI_HI, UI_ALT), by_regime(UI_ALT, UI))
ROUTE = (ACCENT_3, ACCENT)  # route fronts and sides: accent dithered over a darker rung
JOINT = by_regime(UI, mix(UI_ALT, UI_HI, 0.5))  # expansion joints, a step off the roof
# Distant towers (x0, x1, top); mid towers (x0, x1, top, top_r, setbacks, side depth); near towers.
FAR = (
    (560, 640, 262),
    (690, 750, 300),
    (1170, 1250, 276),
    (1290, 1340, 330),
    (1410, 1500, 296),
    (1545, 1610, 318),
    (1650, 1740, 286),
    (1790, 1880, 312),
)
MID = (
    (410, 540, 50, 180, 4, 30),  # the stepped skyscraper
    (600, 700, 330, 330, 1, 24),
    (1140, 1248, 205, 205, 1, 24),  # the twin-mast tower
    (1330, 1460, 262, 262, 1, 26),
    (1600, 1730, 226, 226, 1, 26),
)
NEAR = ((740, 880, 372), (1500, 1650, 352), (1760, 1920, 300))


def pr(x: float, y: float, z: float) -> Vec:
    """Screen position of the world point x metres right of the view axis, y up from our roof
    and z deep."""
    return Vec(VX + F * x / z, VY - F * (y - EYE) / z)


def snap(v: float) -> float:
    """`v` rounded to the nearest cell edge."""
    return round(v / CELL) * CELL


def bands(
    at: NDArray[np.float64], a0: float, a1: float, lo: float = 0.0, hi: float = 1.0
) -> Levels:
    """Dither levels from lo * 16 at `a0` to hi * 16 at `a1` for the cell centres `at`, in
    even steps that hold on past both ends."""
    k0, k1 = round(lo * 16), round(hi * 16)
    span = (a1 - a0) / max(1, k1 - k0)
    return k0 + np.clip(np.round((at - a0) / span), 0, k1 - k0).astype(np.int64)


class Cells:
    """The picture as a (rows, cols) grid of indices into stacks on the CELL grid, painted back
    to front. A stack is a base colour (None: nothing) and dither layers over it, each a colour
    lighting k of every 16 cells."""

    def __init__(self, s: Canvas) -> None:
        self.s = s
        self.rows, self.cols = round(s.h / CELL), round(s.w / CELL)
        self.grid: Levels = np.zeros((self.rows, self.cols), dtype=np.int64)
        ys, xs = np.mgrid[0 : self.rows, 0 : self.cols]
        self.cx, self.cy = (xs + 0.5) * CELL, (ys + 0.5) * CELL
        self.stacks: list[Stack] = [(None, ())]
        self.index: dict[Stack, int] = {self.stacks[0]: 0}

    def empty(self) -> Mask:
        return np.zeros(self.grid.shape, dtype=np.bool_)

    def poly(self, pts: Sequence[Point]) -> Mask:
        """The cells whose centres fall inside the screen polygon `pts`."""
        a = np.asarray(pts, dtype=np.float64) / CELL - 0.5
        m = self.empty()
        rr, cc = polygon(a[:, 1], a[:, 0], m.shape)
        m[rr, cc] = True
        return m

    def box(self, a: Point, b: Point) -> Mask:
        """The cells of the screen rectangle from top-left `a` to bottom-right `b`, its edges
        rounded to the grid."""
        m = self.empty()
        r0, r1 = (max(0, round(v / CELL)) for v in (a[1], b[1]))
        c0, c1 = (max(0, round(v / CELL)) for v in (a[0], b[0]))
        m[r0:r1, c0:c1] = True
        return m

    def segs(self, segs: Sequence[tuple[Point, Point]], width: int = 1) -> Mask:
        """Stepped lines of cells between the cells holding each pair of screen points,
        `width` cells thick (grown right and down)."""
        m = self.empty()
        for a, b in segs:
            ends = (int(a[1] // CELL), int(a[0] // CELL), int(b[1] // CELL), int(b[0] // CELL))
            rr, cc = line(*ends)
            for dy in range(width):
                for dx in range(width):
                    r, c = rr + dy, cc + dx
                    ok = (r >= 0) & (r < self.rows) & (c >= 0) & (c < self.cols)
                    m[r[ok], c[ok]] = True
        return m

    def stairs(self, a: Point, b: Point, n: int = 0) -> Levels:
        """Per column, the row edge of a staircase from `a` toward `b` in runs of n whole cells
        (0: the nearest whole ratio of its run to its rise, or level when it rises under half a
        cell), anchored at the cell corner nearest `a` and carried on past both ends."""
        c0, r0 = round(a[0] / CELL), round(a[1] / CELL)
        dc, dr = (b[0] - a[0]) / CELL, (b[1] - a[1]) / CELL
        c = np.arange(self.cols)
        if abs(dr) < 0.5:
            return np.full(self.cols, r0, dtype=np.int64)
        n = n or max(1, round(abs(dc) / abs(dr)))
        along = c - c0 if dc > 0 else c0 - 1 - c
        return r0 + (1 if dr > 0 else -1) * (along // n)

    def plane(self, top: tuple[Point, Point], foot: tuple[Point, Point], n: int = 0) -> Mask:
        """A face on an upright plane: the columns between the two ends of its `top` edge,
        from the staircase along `top` down to the one along `foot` (`n` sets the run of the
        top staircase)."""
        ca, cb = sorted(round(p[0] / CELL) for p in top)
        c = np.arange(self.cols)[None, :]
        r = np.arange(self.rows)[:, None]
        return (c >= ca) & (c < cb) & (r >= self.stairs(*top, n)) & (r < self.stairs(*foot))

    def _at(self, stack: Stack) -> int:
        if stack not in self.index:
            self.index[stack] = len(self.stacks)
            self.stacks.append(stack)
        return self.index[stack]

    def solid(self, m: Mask, c: Colour) -> None:
        """Cover the cells in `m` with `c`."""
        self.grid[m] = self._at((c, ()))

    def lift(self, m: Mask, c: Colour, k: Levels) -> None:
        """Light k (per cell, 0 to 16) of every 16 cells in `m` with `c`, in 4x4 ordered-dither
        order; the other cells keep what is under them."""
        kk = np.clip(k, 0, 16)
        sel = m & (kk > 0)
        pairs = np.unique(np.stack([self.grid[sel], kk[sel]], axis=1), axis=0).tolist()
        moves: list[tuple[Mask, int]] = []
        for i, v in pairs:
            base, layers = self.stacks[i]
            if v == 16:
                stack: Stack = (c, ())
            elif layers and layers[-1][0] == c:
                stack = (base, (*layers[:-1], (c, max(v, layers[-1][1]))))
            else:
                stack = (base, (*layers, (c, v)))
            moves.append((sel & (self.grid == i) & (kk == v), self._at(stack)))
        for where, j in moves:
            self.grid[where] = j

    def paint(self, m: Mask, ramp: tuple[Colour, Colour], k: Levels) -> None:
        """Cover the cells in `m` with `ramp`'s first colour, lifted to level `k` by its second."""
        self.solid(m, ramp[0])
        self.lift(m, ramp[1], k)

    def _tile(self, stack: Stack) -> Ref:
        base, layers = stack
        with self.s.pattern(TILE, TILE) as tile:
            if base is not None:
                tile.fill(P().rect(0, 0, TILE, TILE), base)
            for c, k in layers:
                lit = P()
                for j, i in zip(*np.nonzero(bayer(4) < k / 16), strict=True):
                    lit.rect(int(i) * CELL, int(j) * CELL, CELL, CELL)
                tile.fill(lit, c)
        return tile.ref

    def draw(self) -> None:
        """Draw the grid, one pixel path per stack left in it: a flat colour, or a 4x4 tile."""
        used = set(np.unique(self.grid).tolist())
        paints: list[Colour | Ref | None] = [
            None if n not in used else st[0] if not st[1] else self._tile(st)
            for n, st in enumerate(self.stacks)
        ]
        grid_runs(self.s, self.grid, paints, CELL)


def tower(
    px: Cells,
    x0: float,
    x1: float,
    top: float,
    z: float,
    face: Colour,
    band: Colour,
    *,
    side: Colour | None = None,
    depth: float = 0.0,
    top_r: float | None = None,
    setbacks: int = 1,
    floor: float = 4.0,
) -> None:
    """Office tower facing the camera, x0..x1 on screen at depth z, with a window band per
    `floor` metres; its crown drops from `top` to `top_r` in `setbacks` flat steps, and `side`
    shades the face that recedes `depth` metres toward the vanishing point."""
    x0, x1 = snap(x0), snap(x1)
    top_r = top if top_r is None else top_r
    if side is not None and depth:
        sx, sy = (x1, top_r) if x1 < VX else (x0, top)
        k = z / (z + depth)
        far = VX + (sx - VX) * k
        px.solid(px.plane(((sx, sy), (far, VY + (sy - VY) * k)), ((sx, FOOT), (far, FOOT))), side)
    body = px.empty()
    for i in range(setbacks):
        xa, xb = (snap(x0 + (x1 - x0) * j / setbacks) for j in (i, i + 1))
        y = top + (top_r - top) * (i / max(1, setbacks - 1)) ** 1.5  # deeper steps to the right
        body |= px.box((xa, y), (xb, FOOT))
    px.solid(body, face)
    # Floors in whole cells, starting below the crown's lowest step.
    pitch = max(2, round(F * floor / z / CELL))
    r0 = round((max(top, top_r) + F * floor / z * 0.6) / CELL)
    rows = np.arange(px.rows)[:, None]
    px.solid(body & (rows >= r0) & ((rows - r0) % pitch < round(pitch * 0.42)), band)


def crane(
    px: Cells,
    x: float,
    z: float,
    jib_y: float,
    jib_len: float,
    cj_len: float,
    col: Colour,
    dark: Colour,
) -> None:
    """Hammerhead tower crane at world x, depth z: lattice mast, jib and counter-jib at height
    jib_y, counterweight, cab, tower head, trolley and hook, one cell thick."""
    mw = 2.4
    (a0, jy), (a1, _) = pr(x - mw / 2, jib_y, z), pr(x + mw / 2, jib_y, z)
    ms = a1 - a0
    lat: list[tuple[Point, Point]] = [((a0, jy), (a0, FOOT)), ((a1, jy), (a1, FOOT))]
    y, flip = jy, False
    while y < FOOT:
        lat.append(((a0 if flip else a1, y), (a1 if flip else a0, y + ms)))
        y += ms
        flip = not flip
    jd = F * 1.8 / z
    tip, cje = pr(x - jib_len, 0, z).x, pr(x + cj_len, 0, z).x
    lat += [((tip, jy), (a0, jy)), ((tip, jy - jd), (a0, jy - jd)), ((tip, jy), (tip, jy - jd))]
    lat += [((a1, jy), (cje, jy)), ((a1, jy - jd), (cje, jy - jd))]
    step = jd * 1.1
    for start, end, sign in ((a0, tip, -1), (a1, cje, 1)):
        xx, up = start, True
        while (end - (xx + sign * step)) * sign > 0:
            lat.append(((xx, jy if up else jy - jd), (xx + sign * step, jy - jd if up else jy)))
            xx += sign * step
            up = not up
    hx, hy = (a0 + a1) / 2, pr(0, jib_y + 8, z).y
    lat += [((a0, jy - jd), (hx, hy)), ((hx, hy), (a1, jy - jd))]
    lat += [((hx, hy), (tip + (a0 - tip) * 0.35, jy - jd)), ((hx, hy), (cje - 6, jy - jd))]
    tx = tip + (a0 - tip) * 0.55
    hook = jy + F * 16 / z
    lat.append(((tx, jy), (tx, hook)))
    px.solid(px.segs(lat), col)
    cw, cab = F * 5 / z, F * 2.4 / z
    px.solid(px.box((cje - cw, jy), (cje, jy + F * 2.6 / z)), dark)
    parts = px.box((a0 - cab, jy), (a0, jy + cab)) | px.box((tx - 4, jy), (tx + 8, jy + 4))
    px.solid(parts | px.box((tx - 4, hook), (tx + 4, hook + 8)), col)


def ac_unit(px: Cells, x0: float, x1: float, z0: float, z1: float, h: float) -> None:
    """Rooftop condenser: lit lid, front face with two square fan guards, louvred side toward
    the vanishing point."""
    if x0 > 0:
        side = px.plane((pr(x0, h, z0), pr(x0, h, z1)), (pr(x0, 0, z0), pr(x0, 0, z1)))
        px.solid(side, UI)
        zs = [z0 + (z1 - z0) * i / 7 for i in range(1, 7)]
        louvres = px.segs([(pr(x0, h * 0.85, z), pr(x0, h * 0.2, z)) for z in zs])
        px.solid(louvres & side, BG_ALT)
    px.solid(px.poly([pr(x0, h, z0), pr(x1, h, z0), pr(x1, h, z1), pr(x0, h, z1)]), UI_HI)
    (fl, ft), (fr, fb) = pr(x0, h, z0), pr(x1, 0, z0)
    px.paint(px.box((fl, ft), (fr, fb)), CONCRETE, bands(px.cy, fb, ft, 0.25, 1.0))
    # Each guard is 3m + 1 cells a side, so its mesh of one-cell bars every third cell closes
    # evenly on the rim, with a four-cell motor block at the centre.
    c0, c1, r0, r1 = (round(v / CELL) for v in (fl, fr, ft, fb))
    size = 28
    gap, top = (c1 - c0 - 2 * size) // 3, r0 + (r1 - r0 - size) // 2
    rows, cols = np.arange(px.rows)[:, None] - top, np.arange(px.cols)[None, :]
    rims, wells, mesh, hubs = px.empty(), px.empty(), px.empty(), px.empty()
    for left in (c0 + gap, c1 - gap - size):
        u = cols - left
        rims |= (u >= 0) & (u < size) & (rows >= 0) & (rows < size)
        well = (u >= 1) & (u < size - 1) & (rows >= 1) & (rows < size - 1)
        wells |= well
        mesh |= well & ((u % 3 == 0) | (rows % 3 == 0))
        hubs |= (abs(2 * u - size + 1) < 4) & (abs(2 * rows - size + 1) < 4)
    px.solid(rims, UI_HI)
    px.solid(wells, BG_DEEP)
    px.solid(mesh, UI)
    px.solid(hubs, UI_ALT)
    px.solid(px.box((fl, fb), (fr, fb + CELL)), BG_ALT)


@design()
def draw(s: Canvas) -> None:
    px = Cells(s)
    par, ry = pr(0, LIP, EDGE).y, pr(0, 0, EDGE).y  # our parapet's top and foot

    # Sky: an ordered-dither lift from the ground tone toward the glare at the horizon.
    px.paint(px.box((0, 0), (s.w, par + 4)), SKY, bands(px.cy, 120, 560))

    # Far city: banded towers, faded into the haze.
    for x0, x1, top in FAR:
        tower(px, x0, x1, top, 420, BG_ALT, BG)
    px.lift(px.box((0, 240), (s.w, FOOT)), HAZE, bands(px.cy, 260, 480, 0.0, 0.25))

    # Mid city: the stepped skyscraper, a twin-mast tower, plain slabs; side faces toward
    # the vanishing point. The crane stands among them in dimmed accent steps.
    px.solid(px.segs([((1182, 205), (1182, 120)), ((1206, 205), (1206, 104))]), UI)
    for x0, x1, top, top_r, steps, depth in MID:
        tower(
            px, x0, x1, top, 220, UI, BG_ALT, side=BG_ALT, depth=depth, top_r=top_r, setbacks=steps
        )
    crane(px, 40, 150, 44, 50, 18, ACCENT_5, ACCENT_6)
    for x0, x1, top in NEAR:
        tower(px, x0, x1, top, 140, UI_ALT, UI, side=UI, depth=18)
    px.lift(px.box((0, 380), (s.w, FOOT)), HAZE, bands(px.cy, 420, 600, 0.0, 0.5))

    # Landing roof across the gap: its ledge and the stairwell door beyond are the route.
    lx0, lx1, lz, lz1 = -2.6, 4.2, 13.0, 34.0
    fl, lt = pr(lx0, LIP, lz)
    fr, lroof = pr(lx1, 0, lz)
    deck = [pr(lx0, 0, lz), pr(lx1, 0, lz), pr(lx1, 0, lz1), pr(lx0, 0, lz1)]
    px.paint(px.poly(deck), CONCRETE, bands(px.cy, deck[2].y, deck[0].y))
    px.solid(px.box((fl, lroof), (fr, par + 2)), UI)  # its facade, down behind our parapet
    hx0, hx1, hz, hh = -1.4, 1.4, 22.0, 2.7
    a, b = pr(hx0, hh, hz), pr(hx1, 0, hz)
    px.paint(px.box(a, b), (UI_ALT, UI_HI), bands(px.cy, b.y, a.y, 0.5, 1.0))
    px.solid(px.box((a.x - CELL, a.y - CELL), (b.x + CELL, a.y)), MUTED)
    # Route faces: lit tops in solid accent, fronts and sides dithered over a darker rung.
    d0, d1 = pr(-0.45, 2.05, hz), pr(0.45, 0, hz)
    px.solid(px.box(d0, d1), ACCENT)
    panel = px.box((d0.x + CELL, d0.y + CELL), (d1.x - CELL, d1.y))  # inside a one-cell frame
    px.paint(panel, ROUTE, bands(px.cy, d1.y, d0.y, 0.5, 0.75))
    px.solid(px.box((fl, lt - CELL), (fr, lt)), ACCENT)
    px.paint(px.box((fl, lt), (fr, lroof)), ROUTE, bands(px.cy, lroof, lt, 0.5, 0.75))
    px.solid(px.box((fl, lroof), (fr, lroof + CELL)), BG_ALT)

    # Our roof: a concrete slab dithered from glare at the parapet to shade, with expansion
    # joints running to the vanishing point and across.
    slab = px.box((0, ry), (s.w, s.h))
    px.paint(slab, SLAB, bands(px.cy, ry + 20, s.h - 40, 0.0, 0.75))
    # Joints at x = EYE times 2, 1 and 3 run from the vanishing point in even 1:2, 1:1 and 1:3
    # staircases.
    rows, cols = np.arange(px.rows)[:, None], np.arange(px.cols)
    joints = px.empty()
    for x in (-2 * EYE, EYE, 3 * EYE):
        joints |= rows == px.stairs((VX, VY), pr(x, 0, EDGE))[cols]
    for z in (4.6, 2.6):
        joints |= rows == round(pr(0, 0, z).y / CELL)
    px.solid(joints & slab, JOINT)
    wx = pr(WING_X, 0, EDGE).x
    px.solid(px.box((wx, par), (s.w, ry)), UI)
    px.solid(px.box((wx, pr(0, LIP, EDGE + 0.3).y), (s.w, par)), MUTED)

    # Springboard box at the parapet: the route's first cue, lined up with the ledge. Its side
    # face is under two cells wide, so it keeps to the one column past the front.
    bx0, bx1, bz0, bz1, bh = -1.6, -0.3, 6.4, 7.2, 0.45
    a, c = pr(bx0, bh, bz0), pr(bx1, 0, bz0)
    cols, edge = np.arange(px.cols)[None, :], round(c.x / CELL)
    side = px.poly([pr(bx1, bh, bz0), pr(bx1, bh, bz1), pr(bx1, 0, bz1), pr(bx1, 0, bz0)])
    px.paint(side & (cols == edge), ROUTE, np.full(px.grid.shape, 4))
    top = px.poly([pr(bx0, bh, bz0), pr(bx1, bh, bz0), pr(bx1, bh, bz1), pr(bx0, bh, bz1)])
    px.solid(top & (cols <= edge), ACCENT)
    px.paint(px.box(a, c), ROUTE, bands(px.cy, c.y, a.y, 0.375, 0.75))
    px.solid(px.box((a.x, c.y), (c.x, c.y + CELL)), BG_ALT)

    ac_unit(px, 2.6, 4.2, 5.4, 6.6, 1.0)

    # Stair block wall on the left: dithered from shade (near) to glare (far), with its
    # coping, corner and one window. Its receding edges are even 1:n staircases.
    near, far = 1.2, EDGE
    top = (pr(WING_X, WING_H, far), pr(WING_X, WING_H, near))
    face = px.plane(top, (pr(WING_X, 0, far), pr(WING_X, 0, near)))
    px.paint(face, CONCRETE, bands(px.cx, 0, top[0].x))
    cope = WING_H - 0.2
    # Runs of five under the coping against four along its top, so it widens toward us.
    under = px.stairs(pr(WING_X, cope, far), pr(WING_X, cope, near), 5)
    px.solid(face & (np.arange(px.rows)[:, None] < under), MUTED)
    px.solid(face & ~np.roll(face, -1, axis=1), UI_HI)  # the corner: the wall's last column
    za, zb, yt, yb = 5.8, 6.9, 2.5, 1.1
    glass = px.plane(
        (pr(WING_X, yt, zb), pr(WING_X, yt, za)), (pr(WING_X, yb, zb), pr(WING_X, yb, za))
    )
    px.paint(glass, (BG_DEEP, UI), bands(px.cy, pr(0, yb, zb).y, pr(0, yt, zb).y, 0.0, 0.25))
    sill = glass & ~np.roll(glass, -1, axis=0)
    cols, rows = np.arange(px.cols)[None, :], np.arange(px.rows)[:, None]
    mullion = cols == round(pr(WING_X, 0, (za + zb) / 2).x / CELL)
    transom = rows == round(pr(WING_X, (yt + yb) / 2, zb).y / CELL)
    px.solid(glass & (mullion | transom) | np.roll(sill, 1, axis=0), MUTED)

    px.draw()
