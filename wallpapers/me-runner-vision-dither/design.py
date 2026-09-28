"""Mirror's Edge runner vision: a concrete rooftop in one-point perspective where only the route is picked out, shaded with 4x4 ordered-dither pattern fills."""

import math
from collections.abc import Iterable, Sequence
from typing import Literal

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_3,
    ACCENT_5,
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
    Path,
    Point,
    Ref,
    Vec,
    by_regime,
    design,
    mix,
    polar,
)
from walldye.pixel import bayer

# Camera: one-point perspective, metres in world space, heights relative to our roof.
VX, VY, F, EYE = 1060, 420, 1000, 1.7
EDGE = 8.0  # depth of our parapet's inner face
LIP = 0.3  # parapet height
WING_X, WING_H = -5.5, 3.2  # stair block on our roof; its wall faces the camera side
FOOT = 640  # screen y of every building's foot, hidden behind our parapet
CELL = 4  # dither cell; a pattern tile is 4x4 cells
TILE = 4 * CELL
HAZE = mix(BG_ALT, UI, 0.35)
# Dither ramps by role: (under, over). Level k lights k of 16 cells in `over`; with no `under`
# the unlit cells show whatever is already drawn. On paper our roof (SLAB) steps down a tone,
# so the floor stays a quiet ground instead of the heaviest mass on screen.
RAMPS: tuple[tuple[Colour | None, Colour], ...] = (
    (BG, BG_ALT),
    (None, HAZE),
    (UI, UI_ALT),
    (by_regime(UI_HI, UI_ALT), by_regime(UI_ALT, UI)),
)
JOINT = by_regime(UI, mix(UI_ALT, UI_HI, 0.5))  # expansion joints, a step off the roof
SKY, VEIL, CONCRETE, SLAB = 0, 1, 2, 3
# Distant towers (x0, x1, top); mid towers (x0, x1, top, top_r, curve, side depth); near towers.
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
    (410, 540, 50, 180, -30, 30),  # the sail-topped skyscraper
    (600, 700, 330, 330, 0, 24),
    (1140, 1248, 205, 205, 0, 24),  # the twin-mast tower
    (1330, 1460, 262, 262, 0, 26),
    (1600, 1730, 226, 226, 0, 26),
)
NEAR = ((740, 880, 372), (1500, 1650, 352), (1760, 1920, 300))


def pr(x: float, y: float, z: float) -> Vec:
    """Screen position of the world point x metres right of the view axis, y up from our roof
    and z deep."""
    return Vec(VX + F * x / z, VY - F * (y - EYE) / z)


def box(a: Point, b: Point) -> Path:
    """The screen rectangle from top-left corner `a` to bottom-right corner `b`."""
    return P().rect(a[0], a[1], b[0] - a[0], b[1] - a[1])


def segments(segs: Iterable[tuple[Point, Point]]) -> Path:
    """One path of straight segments."""
    d = P()
    for a, b in segs:
        d.M(a).L(b)
    return d


def quad(s: Canvas, pts: Sequence[tuple[float, float]], paint: Colour) -> None:
    s.fill(P().poly(pts, closed=True), paint)


class Dither:
    """4x4 Bayer pattern fills for the ramps in RAMPS, one pattern per (ramp, level), made on
    first use."""

    def __init__(self, s: Canvas) -> None:
        self.s = s
        self.order = bayer(4)
        self.tiles: dict[tuple[int, int], Ref] = {}

    def paint(self, ramp: int, k: int) -> Colour | Ref | None:
        """The paint for level `k` (0 to 16) of `ramp`; None when there is nothing to draw."""
        under, over = RAMPS[ramp]
        if k <= 0:
            return under
        if k >= 16 and under is not None:
            return over
        if (ramp, k) not in self.tiles:
            lit = P()
            for j in range(4):
                for i in range(4):
                    if self.order[j, i] < k / 16:
                        lit.rect(i * CELL, j * CELL, CELL, CELL)
            with self.s.pattern(TILE, TILE) as tile:
                if under is not None:
                    tile.fill(P().rect(0, 0, TILE, TILE), under)
                tile.fill(lit, over)
            self.tiles[ramp, k] = tile.ref
        return self.tiles[ramp, k]

    def grad(
        self,
        poly: Sequence[tuple[float, float]],
        axis: Literal["x", "y"],
        a0: float,
        a1: float,
        ramp: int,
        lo: float = 0.0,
        hi: float = 1.0,
    ) -> None:
        """Fill `poly` with `ramp`'s levels from lo * 16 to hi * 16 in bands stepping along the
        screen `axis` from a0 to a1; the first and last bands run on to the polygon's edges.
        Band edges snap to the cell grid so the patterns tile without seams."""
        xs, ys = [float(p[0]) for p in poly], [float(p[1]) for p in poly]
        x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1
        e0, e1 = (x0, x1) if axis == "x" else (y0, y1)
        ks = range(round(lo * 16), round(hi * 16) + 1)
        span = (a1 - a0) / max(1, len(ks) - 1)
        bands: list[tuple[int, int, Colour | Ref]] = []
        for idx, k in enumerate(ks):
            b0 = a0 + (idx - 0.5) * span if idx else e0 - 1
            b1 = a0 + (idx + 0.5) * span if idx < len(ks) - 1 else e1 + 1
            b0, b1 = round(min(b0, b1) / CELL) * CELL, round(max(b0, b1) / CELL) * CELL
            if b1 <= b0:
                continue
            paint = self.paint(ramp, k)
            if paint is not None:
                bands.append((b0, b1, paint))
        with self.s.clip() as region:
            region.add(P().poly(poly, closed=True))
        with self.s.group(clip_path=region.ref):
            for b0, b1, paint in bands:
                if axis == "x":
                    self.s.fill(P().rect(b0, y0, b1 - b0, y1 - y0), paint)
                else:
                    self.s.fill(P().rect(x0, b0, x1 - x0, b1 - b0), paint)


def tower(
    s: Canvas,
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
    curve: float = 0.0,
    floor: float = 4.0,
) -> None:
    """Office tower facing the camera, x0..x1 on screen at depth z, with a window band per
    `floor` metres; `top_r` and `curve` slope and bow its crown, and `side` shades the face
    that recedes `depth` metres toward the vanishing point."""
    top_r = top if top_r is None else top_r
    fh = F * floor / z
    if side is not None and depth:
        sx, sy = (x1, top_r) if x1 < VX else (x0, top)
        k = z / (z + depth)
        far = VX + (sx - VX) * k
        quad(s, [(sx, sy), (far, VY + (sy - VY) * k), (far, FOOT), (sx, FOOT)], side)
    crown = P().M(x0, FOOT).L(x0, top)
    if curve:
        crown.Q((x0 + x1) / 2, (top + top_r) / 2 + curve, x1, top_r)
    else:
        crown.L(x1, top_r)
    s.fill(crown.L(x1, FOOT).Z(), face)
    # The bands start below the crown's lower corner, so a sloped crown needs no clip.
    bands = P()
    y = max(top, top_r) + fh * 0.6
    while y < FOOT:
        bands.rect(x0, y, x1 - x0, fh * 0.42)
        y += fh
    s.fill(bands, band)


def crane(
    s: Canvas,
    x: float,
    z: float,
    jib_y: float,
    jib_len: float,
    cj_len: float,
    col: Colour,
    dark: Colour,
) -> None:
    """Hammerhead tower crane at world x, depth z: lattice mast, jib and counter-jib at height
    jib_y, counterweight, cab, tower head, trolley and hook."""
    mw = 2.4
    (a0, jy), (a1, _) = pr(x - mw / 2, jib_y, z), pr(x + mw / 2, jib_y, z)
    ms = a1 - a0
    lat = P().M(a0, jy).V(FOOT).M(a1, jy).V(FOOT)
    y, flip = jy, False
    while y < FOOT:
        lat.M(a0 if flip else a1, y).L(a1 if flip else a0, y + ms)
        y += ms
        flip = not flip
    jd = F * 1.8 / z
    tip, cje = pr(x - jib_len, 0, z).x, pr(x + cj_len, 0, z).x
    lat.M(tip, jy).H(a0).M(tip, jy - jd).H(a0)
    lat.M(a1, jy).H(cje).M(a1, jy - jd).H(cje)
    step = jd * 1.1
    xx, up = a0, True
    while xx - step > tip:
        lat.M(xx, jy if up else jy - jd).L(xx - step, jy - jd if up else jy)
        xx -= step
        up = not up
    lat.M(tip, jy).V(jy - jd)
    xx, up = a1, True
    while xx + step < cje:
        lat.M(xx, jy if up else jy - jd).L(xx + step, jy - jd if up else jy)
        xx += step
        up = not up
    hx, hy = (a0 + a1) / 2, pr(0, jib_y + 8, z).y
    lat.M(a0, jy - jd).L(hx, hy).L(a1, jy - jd)
    lat.M(hx, hy).L(tip + (a0 - tip) * 0.35, jy - jd).M(hx, hy).L(cje - 6, jy - jd)
    s.stroke(lat, col, 1.5, join="round")
    cw = F * 5 / z
    s.fill(P().rect(cje - cw, jy, cw, F * 2.6 / z), dark)
    cab = F * 2.4 / z
    tx = tip + (a0 - tip) * 0.55
    hook = jy + F * 16 / z
    s.stroke(P().M(tx, jy).V(hook), col, 1)
    s.fill(P().rect(a0 - cab, jy, cab, cab).rect(tx - 5, jy, 10, 4).rect(tx - 4, hook, 8, 7), col)


def ac_unit(s: Canvas, x0: float, x1: float, z0: float, z1: float, h: float) -> None:
    """Rooftop condenser: lit lid, front face with two round fan grilles, louvred side toward
    the vanishing point."""
    if x0 > 0:
        quad(s, [pr(x0, h, z0), pr(x0, h, z1), pr(x0, 0, z1), pr(x0, 0, z0)], UI)
        zs = [z0 + (z1 - z0) * i / 7 for i in range(1, 7)]
        s.stroke(segments((pr(x0, h * 0.85, z), pr(x0, h * 0.2, z)) for z in zs), BG_ALT, 2)
    quad(s, [pr(x0, h, z0), pr(x1, h, z0), pr(x1, h, z1), pr(x0, h, z1)], UI_HI)
    (fl, ft), (fr, fb) = pr(x0, h, z0), pr(x1, 0, z0)
    s.fill(box((fl, ft), (fr, fb)), UI_ALT)
    # Centres and radii on the 0.1 grid P() writes, so each circle's two half arcs meet cleanly.
    r = round(min((fr - fl) / 4 - 8, (fb - ft) / 2 - 10), 1)
    fans, blades, hubs = P(), P(), P()
    for i in range(2):
        c = Vec(round(fl + (fr - fl) * (i * 2 + 1) / 4, 1), round((ft + fb) / 2, 1))
        fans.circle(c, r)
        hubs.circle(c, round(r * 0.14, 1))
        for a in range(3):
            blades.M(c).L(polar(c, r * 0.8, rad=a * 2 * math.pi / 3 + 0.4))
    s.path(fans, fill=BG_DEEP, stroke=UI_HI, stroke_width=2)
    s.stroke(blades, UI, r * 0.28, cap="round")
    s.fill(hubs, UI_ALT)
    s.fill(P().rect(fl, fb, fr - fl, 4), BG_ALT)


@design()
def draw(s: Canvas) -> None:
    dz = Dither(s)
    par, ry = pr(0, LIP, EDGE).y, pr(0, 0, EDGE).y  # our parapet's top and foot

    # Sky: an ordered-dither lift from the ground tone toward the glare at the horizon.
    dz.grad([(0, 0), (s.w, 0), (s.w, par + 4), (0, par + 4)], "y", 120, 560, SKY)

    # Far city: banded towers, faded into the haze with a dither veil.
    for x0, x1, top in FAR:
        tower(s, x0, x1, top, 420, BG_ALT, BG)
    dz.grad([(0, 240), (s.w, 240), (s.w, FOOT), (0, FOOT)], "y", 260, 480, VEIL, 0.0, 0.25)

    # Mid city: the sail-topped skyscraper, a twin-mast tower, plain slabs; side faces toward
    # the vanishing point. The crane stands among them in dimmed accent steps.
    s.stroke(P().M(1182, 205).V(120).M(1206, 205).V(104), UI, 3)
    for x0, x1, top, top_r, curve, depth in MID:
        tower(s, x0, x1, top, 220, UI, BG_ALT, side=BG_ALT, depth=depth, top_r=top_r, curve=curve)
    crane(s, 40, 150, 44, 50, 18, ACCENT_3, ACCENT_5)
    for x0, x1, top in NEAR:
        tower(s, x0, x1, top, 140, UI_ALT, UI, side=UI, depth=18)
    dz.grad([(0, 380), (s.w, 380), (s.w, FOOT), (0, FOOT)], "y", 420, 600, VEIL, 0.0, 0.5)

    # Landing roof across the gap: its ledge and the stairwell door beyond are the route.
    lx0, lx1, lz, lz1 = -2.6, 4.2, 13.0, 34.0
    fl, lt = pr(lx0, LIP, lz)
    fr, lroof = pr(lx1, 0, lz)
    deck = [pr(lx0, 0, lz), pr(lx1, 0, lz), pr(lx1, 0, lz1), pr(lx0, 0, lz1)]
    dz.grad(deck, "y", deck[2].y, deck[0].y, CONCRETE)
    s.fill(box((fl, lroof), (fr, par + 2)), UI)  # its facade, down behind our parapet
    hx0, hx1, hz, hh = -1.4, 1.4, 22.0, 2.7
    a, b = pr(hx0, hh, hz), pr(hx1, 0, hz)
    s.fill(box(a, b), UI_HI)
    s.fill(P().rect(a.x - 2, a.y - 3, b.x - a.x + 4, 4), MUTED)
    d0, d1 = pr(-0.45, 2.05, hz), pr(0.45, 0, hz)
    s.fill(box(d0, d1), ACCENT)
    s.fill(P().rect(d0.x + 2, d0.y + 2, d1.x - d0.x - 4, 2), ACCENT_1)
    s.fill(P().rect(d1.x - 5, (d0.y + d1.y) / 2, 3, 2), ACCENT_3)
    s.fill(box((fl, lt), (fr, lroof)), ACCENT)
    quad(s, [(fl, lt), (fr, lt), pr(lx1, LIP, lz + 0.3), pr(lx0, LIP, lz + 0.3)], ACCENT_1)
    s.fill(P().rect(fl, lroof, fr - fl, 4), BG_ALT)

    # Our roof: a concrete slab dithered from glare at the parapet to shade, with expansion
    # joints running to the vanishing point and across.
    dz.grad([(0, ry), (s.w, ry), (s.w, s.h), (0, s.h)], "y", ry + 20, s.h - 40, SLAB, 0.0, 0.75)
    zn = F * EYE / (s.h - VY)  # depth of the roof at the bottom edge
    joints = [(pr(x, 0, zn * 0.98), pr(x, 0, EDGE)) for x in (-2.8, 1.6, 6.0)]
    joints += [((0, pr(0, 0, z).y), (s.w, pr(0, 0, z).y)) for z in (4.6, 2.6)]
    s.stroke(segments(joints), JOINT, 2)
    wx = pr(WING_X, 0, EDGE).x
    s.fill(P().rect(wx, par, s.w - wx, ry - par), UI)
    pt = pr(0, LIP, EDGE + 0.3).y
    s.fill(P().rect(wx, pt, s.w - wx, par - pt + 1), MUTED)

    # Springboard box at the parapet: the route's first cue, lined up with the ledge.
    bx0, bx1, bz0, bz1, bh = -1.6, -0.3, 6.4, 7.2, 0.45
    quad(s, [pr(bx1, bh, bz0), pr(bx1, bh, bz1), pr(bx1, 0, bz1), pr(bx1, 0, bz0)], ACCENT_2)
    quad(s, [pr(bx0, bh, bz0), pr(bx1, bh, bz0), pr(bx1, bh, bz1), pr(bx0, bh, bz1)], ACCENT_1)
    a, c = pr(bx0, bh, bz0), pr(bx1, 0, bz0)
    s.fill(box(a, c), ACCENT)
    s.fill(P().rect(a.x, c.y, c.x - a.x, 5), BG_ALT)

    ac_unit(s, 2.6, 4.2, 5.4, 6.6, 1.0)

    # Stair block wall on the left: dithered from shade (near) to glare (far), with its
    # coping, corner and one window.
    wall = [
        pr(WING_X, WING_H, 1.2),
        pr(WING_X, WING_H, EDGE),
        pr(WING_X, 0, EDGE),
        pr(WING_X, 0, 1.2),
    ]
    dz.grad(wall, "x", 0, wall[1].x, CONCRETE)
    cope = WING_H - 0.2
    quad(s, [wall[0], wall[1], pr(WING_X, cope, EDGE), pr(WING_X, cope, 1.2)], MUTED)
    s.stroke(segments([(wall[1], wall[2])]), UI_HI, 2)
    za, zb, yt, yb = 5.8, 6.9, 2.5, 1.1
    zm, ym = (za + zb) / 2, (yt + yb) / 2
    pane = [pr(WING_X, yt, za), pr(WING_X, yt, zb), pr(WING_X, yb, zb), pr(WING_X, yb, za)]
    quad(s, pane, BG_DEEP)
    frame = [
        (pr(WING_X, yt, zm), pr(WING_X, yb, zm)),
        (pr(WING_X, ym, za), pr(WING_X, ym, zb)),
        (pane[3], pane[2]),
    ]
    s.stroke(segments(frame), MUTED, 3)
