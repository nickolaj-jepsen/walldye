"""A carbon brake disc and caliper in three-quarter view on a pixel grid, heat in ordered dither."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_4,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    Vec,
    by_regime,
    design,
)
from walldye.field import cells
from walldye.pixel import dither, grid_runs

type F64 = NDArray[np.float64]
type Mask = NDArray[np.bool_]

CELL = 2
R = 560.0  # outer radius
DIA, THK = 278.0, 32.0  # mm
ROWS, PER_ROW = 7, 210  # 1,470 holes
HOLE, ROW_PITCH = 2.5, 4.0  # mm
TABS = 30
BORE = (0.66, 0.72)  # drive tab tips and roots, share of the outer radius
TILT = math.radians(40)  # the disc's axis away from the line of sight
CAL = (math.radians(102), math.radians(162))  # caliper arc from its trailing end
CAL_R = (0.84, 1.12)  # caliper's radial extent, share of the outer radius
CAL_H = 1.6  # caliper's half-width, share of the disc's half-thickness
DECAY = (0.32, 0.55)  # heat's fall-off along the rim, radians: the core and the tail

# surfaces, in label order
SKY, FACE, RIM, TIP, ROOT, SIDE, C_FRONT, C_OUTER, C_END = range(9)
# palette indices
P_FACE, P_WALL, P_HOLE, P_LINE, P_CLINE, G1, G2, G3 = range(1, 9)
# holes are recesses: sunk below the ground on dark themes, inked on paper
HOLE_INK = by_regime(BG_DEEP, UI)
PALETTE = [None, BG_ALT, BG, HOLE_INK, UI, UI_ALT, ACCENT_4, ACCENT_2, ACCENT]
# the faces and the outer curved walls take the face's tone; the bore's walls take the ground's,
# so the bore reads as one opening
FILL = np.array([0, P_FACE, P_FACE, P_WALL, P_WALL, P_WALL, P_FACE, P_FACE, P_FACE])
# outline groups: the bore walls as one, and the caliper's end face, a sliver seen almost edge
# on, with its outer wall
PART = np.array([0, 1, 2, 3, 3, 3, 4, 5, 5])
GLOW = np.array([0, G1, G2, G3])
DASH = (26, 6, 3, 5)  # a center line's dash, gap, dot and gap


def dashed(d: NDArray[np.float64]) -> NDArray[np.bool_]:
    """Whether distance d along a center line falls on a dash or a dot."""
    m = np.abs(d) % sum(DASH)
    return (m < DASH[0]) | ((m >= sum(DASH[:2])) & (m < sum(DASH[:3])))


@design(aspects="any")
def draw(s: Canvas) -> None:
    k = R / (DIA / 2)  # units per mm
    T = THK * k
    ct, st = math.cos(TILT), math.sin(TILT)
    turn = math.radians(35 if s.landscape else 60)
    cp, sp = math.cos(turn), math.sin(turn)
    a0, a1 = CAL

    def to_screen(lx: F64 | float, ly: F64 | float) -> tuple[F64, F64]:
        return np.asarray(lx * cp - ly * sp), np.asarray(lx * sp + ly * cp)

    # placed by the caliper's trailing end, where the glow starts: the disc bleeds off the
    # top right corner of a landscape screen, and off the right edge of a portrait one
    ex, ey = (float(v) for v in to_screen(R * math.cos(a0), R * math.sin(a0) * ct))
    if s.landscape:
        c = Vec(s.w - 260, 0.6 * s.h - ey - 50)
    else:
        c = Vec(0.45 * s.w - ex, 0.6 * s.h - ey)

    xs, ys = cells(s.inset(0), CELL)
    dx, dy = xs - c.x, ys - c.y
    # the disc's frame: x in its plane across the line of sight, the near rim toward +y
    x, y = dx * cp + dy * sp, -dx * sp + dy * cp

    def depth(r: F64 | float, a: F64 | float, hh: F64 | float) -> F64:
        return np.asarray(r * np.sin(a) * st + hh * ct)

    def plane(hh: float) -> tuple[F64, F64]:
        """Radius and angle of each cell on the plane at height hh."""
        v = (y + hh * st) / ct
        return np.hypot(x, v), np.arctan2(v, x)

    def cylinder(r: float, near: bool) -> tuple[F64, F64]:
        """Angle and height of each cell on the near or far half of the cylinder r."""
        a = np.arccos(np.clip(x / r, -1, 1))
        a = a if near else -a
        return a, (r * np.sin(a) * ct - y) / st

    def wall(a: float, r0: float, r1: float, hh: float) -> F64:
        """Depth of each cell on the radial wall at angle a, -inf off it."""
        if abs(math.cos(a)) < 1e-3:
            return np.full(x.shape, -np.inf)  # seen edge on
        r = x / math.cos(a)
        h = (r * math.sin(a) * ct - y) / st
        return np.where((r >= r0) & (r <= r1) & (np.abs(h) <= hh), depth(r, a, h), -np.inf)

    def on_tab(a: F64) -> Mask:
        return (a / (2 * math.pi) * TABS) % 1 < 0.5

    # z-buffer of every surface facing the viewer
    z = np.full((9, *x.shape), -np.inf)
    rt, rr = BORE[0] * R, BORE[1] * R
    rho, phi_f = plane(T / 2)
    inner = np.where(on_tab(phi_f), rt, rr)
    z[FACE] = np.where((rho <= R) & (rho >= inner), depth(rho, phi_f, T / 2), -np.inf)
    phi, h = cylinder(R, near=True)
    z[RIM] = np.where((np.abs(x) <= R) & (np.abs(h) <= T / 2), depth(R, phi, h), -np.inf)
    ta, th = cylinder(rt, near=False)
    seen = (np.abs(x) <= rt) & (np.abs(th) <= T / 2) & on_tab(ta)
    z[TIP] = np.where(seen, depth(rt, ta, th), -np.inf)
    ra, rh = cylinder(rr, near=False)
    seen = (np.abs(x) <= rr) & (np.abs(rh) <= T / 2) & ~on_tab(ra)
    z[ROOT] = np.where(seen, depth(rr, ra, rh), -np.inf)
    z[SIDE] = np.maximum.reduce([wall(math.pi * m / TABS, rt, rr, T / 2) for m in range(60)])

    r0, r1 = CAL_R[0] * R, CAL_R[1] * R
    hc = CAL_H * T / 2
    cr, ca = plane(hc)
    seen = (cr >= r0) & (cr <= r1) & (ca >= a0) & (ca <= a1)
    z[C_FRONT] = np.where(seen, depth(cr, ca, hc), -np.inf)
    oa, oh = cylinder(r1, near=True)
    seen = (np.abs(x) <= r1) & (np.abs(oh) <= hc) & (oa >= a0) & (oa <= a1)
    z[C_OUTER] = np.where(seen, depth(r1, oa, oh), -np.inf)
    z[C_END] = np.maximum(wall(a0, r0, r1, hc), wall(a1, r0, r1, hc))

    label = np.argmax(z, axis=0)
    label[np.isinf(z).all(axis=0)] = SKY
    zt = z.max(axis=0)
    grid = FILL[label]

    # holes: circles on the rim, alternate rows offset by half a pitch, each centered on a
    # whole cell so that holes of one size all rasterize to the same shape
    pitch = ROW_PITCH * k
    row = np.clip(np.round(h / pitch), -(ROWS // 2), ROWS // 2)
    step = 2 * math.pi / PER_ROW
    off = (row % 2) * step / 2
    ha = off + np.round((phi - off) / step) * step
    hx, hy = to_screen(R * np.cos(ha), R * np.sin(ha) * ct - row * pitch * st)
    ox = (np.floor((c.x + hx) / CELL) + 0.5) * CELL - xs
    oy = (np.floor((c.y + hy) / CELL) + 0.5) * CELL - ys
    lx, ly = ox * cp + oy * sp, -ox * sp + oy * cp
    sa = np.sin(ha)
    u = -lx / np.maximum(sa, 0.45)  # along the rim
    v = (u * np.cos(ha) * ct - ly) / st  # across it
    # near the limb the holes would squash into a fine hatch, so the rim stays plain there
    hole = (label == RIM) & (sa > 0.45) & (u**2 + v**2 < (HOLE * k / 2) ** 2)
    grid[hole] = P_HOLE

    # outlines: a cell whose neighbor shows another part lying behind it; the bore walls
    # take none, so the tabs seen through the bore make no second toothed ring
    part = PART[label]
    # near the limb the face's edge and the rim's silhouette would run as a tramline, so only
    # the silhouette is drawn there
    limb = np.sin(phi) < 0.3
    pp, pz = np.pad(part, 1, mode="edge"), np.pad(zt, 1, mode="edge")
    edge = np.zeros(label.shape, bool)
    for j, i in ((0, 1), (2, 1), (1, 0), (1, 2)):
        nb, nz = (
            pp[j : j + part.shape[0], i : i + part.shape[1]],
            pz[j : j + part.shape[0], i : i + part.shape[1]],
        )
        fold = ((part == 1) & (nb == 2)) | ((part == 2) & (nb == 1))
        edge |= (part != 0) & (part != 3) & (nb != part) & ((nb == 0) | (nz < zt)) & ~(fold & limb)
    caliper = label >= C_FRONT
    grid[edge & ~caliper] = P_LINE
    grid[edge & caliper] = P_CLINE

    # center lines on the face's plane, dash and dot, running just past the disc and hidden by
    # the rim
    across = (y + T / 2 * st) / ct
    reach = 1.06 * R
    center = (np.abs(across) * ct < CELL * 0.75) & (np.abs(x) < reach) & dashed(x)
    center |= (np.abs(x) < CELL * 0.75) & (np.abs(across) < reach) & dashed(across * ct)
    center &= np.isin(label, (SKY, FACE, TIP, ROOT, SIDE)) & ~edge
    grid[center] = P_LINE

    # heat: hottest where the rim leaves the caliper, cooling as the disc turns on
    face = label == FACE
    age = a0 - np.where(face, phi_f, phi)
    heat = np.where(age > 0, 0.5 * np.exp(-age / DECAY[0]) + 0.5 * np.exp(-age / DECAY[1]), 0)
    # the face glows only in a strip along the rim, next to the core
    strip = np.clip((rho - 0.9 * R) / (0.1 * R), 0, 1) * np.clip((heat - 0.35) / 0.65, 0, 1)
    # the rim's outline takes the rim's heat on both sides of the fold, so it steps down once
    line_heat = np.where(face & (rho < 0.97 * R), strip, heat)
    heat = np.where(face, strip, heat)
    heat *= (face | (label == RIM)) & ~hole
    # the fill ends where the outline stops glowing, so the rim runs cold before the frame
    level = dither(np.clip((heat - 0.1) / 0.9, 0, 1), 4, method="bayer", matrix=4)
    # outlines change step with the heat but stay unbroken
    step_up = np.where(line_heat > 0.1, np.ceil(3 * np.minimum(line_heat, 1)), 0)
    level = np.where(edge & (face | (label == RIM)), step_up, level).astype(int)
    grid[level > 0] = GLOW[level[level > 0]]

    grid_runs(s, grid, PALETTE, CELL)
