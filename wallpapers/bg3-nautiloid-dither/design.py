"""The mind flayer nautiloid of Baldur's Gate 3, traced and shaded in 8x8 ordered dither, diving over banded haze with one breach burning on its hull."""

import math

import numpy as np
from numpy.typing import NDArray
from skimage.draw import polygon

from walldye import (
    ACCENT,
    ACCENT_4,
    BG,
    BG_ALT,
    BG_DEEP,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Vec,
    design,
    ladder,
    polar,
)
from walldye.field import cells, gauss, noise_grid
from walldye.pixel import dither, grid_runs

type Field = NDArray[np.float64]
type Mask = NDArray[np.bool_]
type Outline = list[list[list[int]]]  # polygons of (x, y) vertices in ship space

CELL = 4
# Ship space is the official render traced at 0.53 scale (data/outline.json); the silhouette
# and its two light bands come from the trace, the shell coil is procedural.
SHIP_MID = Vec(653, 409)  # centre of the ship's bounding box, 1246 by 734 units
ORIGIN_16X9 = Vec(350, 93)  # where ship-space (0, 0) sits on a 16:9 screen
PORTRAIT_SCALE = 0.72  # shrinks the ship to fit a portrait screen with a 90-unit margin
SHELL_C, SHELL_AX = (1045, 290), (134, 152)  # outer shell ellipse
UMB = (1112, 382)  # umbilicus: low and right of the shell centre
APERTURE = math.radians(163)  # mouth direction from the umbilicus (y down)
SEAM0, GROWTH = 0.8, 3.0  # seam leaves the mouth at 80% of the rim; the coil grows 3x per turn
STRAPS = (-2.75, -2.25, -1.75, -1.25, -0.75)  # strap directions from the umbilicus, radians
BREACH = (760, 395)
SMOKE = -38  # the smoke streams aft and up, in degrees
TAU = 2 * math.pi
# Dither levels 0-5 index the tone steps directly (level 1 is the ground and stays undrawn);
# 6-9 are the burning breach on the accent ladder, 10 the top-lit rim.
PALETTE = (BG_DEEP, None, BG_ALT, UI, UI_ALT, UI_HI, *ladder((BG, ACCENT_4, ACCENT), 5)[1:], MUTED)


def raster(polys: Outline, origin: Vec, scale: float, shape: tuple[int, int]) -> Mask:
    """Even-odd fill of ship-space polygons onto the cell grid, with ship (0, 0) at canvas
    point `origin` and ship units `scale` canvas units long."""
    m = np.zeros(shape, dtype=np.bool_)
    for p in polys:
        a = np.asarray(p, dtype=np.float64)
        ys = (a[:, 1] * scale + origin.y) / CELL - 0.5
        xs = (a[:, 0] * scale + origin.x) / CELL - 0.5
        rr, cc = polygon(ys, xs, shape)
        m[rr, cc] ^= True
    return m


def shell_field(x: Field, y: Field) -> tuple[Field, Field, Field]:
    """Involute coil fitted to the rim ellipse, at ship-space points (x, y): rho (distance from
    the umbilicus as a fraction of the way to the rim), the whorl coordinate w (negative on the
    outer whorl, whole turns inward) and the turn angle from the mouth."""
    cx, cy = SHELL_C
    ax, ay = SHELL_AX
    ux, uy = UMB
    dx, dy = x - ux, y - uy
    d = np.maximum(np.hypot(dx, dy), 1e-3)
    c, s = dx / d, dy / d
    qa = (c / ax) ** 2 + (s / ay) ** 2
    qb = 2 * ((ux - cx) * c / ax**2 + (uy - cy) * s / ay**2)
    qc = ((ux - cx) / ax) ** 2 + ((uy - cy) / ay) ** 2 - 1
    rim = (-qb + np.sqrt(qb * qb - 4 * qa * qc)) / (2 * qa)
    rho = d / rim
    ph = (np.arctan2(dy, dx) - APERTURE) % TAU
    w = np.log(SEAM0 / np.maximum(rho, 1e-4)) / math.log(GROWTH) - ph / TAU
    return rho, w, ph


@design(aspects=("16:9", "32:9", "9:19.5", "10:16"))
def draw(s: Canvas) -> None:
    # Landscape keeps the ship full size, a little right of centre so the bow has room ahead
    # of it; portrait shrinks it into the upper middle, above the haze.
    k = 1.0 if s.landscape else PORTRAIT_SCALE
    home = ORIGIN_16X9 + SHIP_MID  # the ship centre on a 16:9 screen
    at = s.pick(landscape=(home.x / 1920, home.y / 1080), portrait=(0.5, 0.42), snap=1)
    origin = at - SHIP_MID * k
    X, Y = cells(s.inset(0), CELL)
    shape = (X.shape[0], X.shape[1])
    x, y = (X - origin.x) / k, (Y - origin.y) / k  # ship space

    def ng(scale: float, key: int, octaves: int) -> Field:
        return noise_grid(shape[1], shape[0], scale, s.np_rng(key), octaves=octaves)

    # Avernus haze: calm strata thickening toward a low horizon. It is quiet ahead of the bow
    # and, on screens wider than 16:9, fades out again behind the stern.
    horizon = s.pick(landscape=(0, 900 / 1080), portrait=(0, 0.74)).y
    haze = ng(90, 7, 4)
    band = gauss(Y - horizon - 40 * ng(220, 8, 2), 170)
    strata = np.clip(np.sin(Y / 11 + 5 * ng(260, 9, 2)), 0, 1) ** 6
    xr = x + ORIGIN_16X9.x  # where the cell would sit across a 16:9 screen
    quiet = np.clip(xr / 1920 * 1.3 + 0.1, 0, 1) * gauss(np.maximum(xr - 1920, 0), 400)
    # the haze only ever lifts the ground: sinking it scattered specks too faint to see
    val = 0.2 + np.maximum(0.05 * haze + 0.12 * band + 0.07 * band * strata, 0) * quiet

    outline: dict[str, Outline] = s.data("outline.json")
    sil, mid, hi = (raster(outline[n], origin, k, shape) for n in ("silhouette", "mid", "high"))
    ex, ey = (x - SHELL_C[0]) / SHELL_AX[0], (y - SHELL_C[1]) / SHELL_AX[1]
    r2 = ex * ex + ey * ey
    shell = sil & (r2 <= 1)
    above = np.zeros_like(sil)
    above[2:] = sil[:-2]
    edge_up = sil & ~above  # the top two cells of every part, lit from above

    # Hull, horns, prow tentacles and legs: three tones traced from the render's lighting.
    tone = np.where(hi, 0.96, np.where(mid, 0.72, 0.48))
    val = np.where(sil & ~shell, np.where(edge_up, np.maximum(tone, 0.7), tone), val)

    # Shell: outer whorl with growth ribs and bony straps; the seam winds into a ribbed eye.
    rho, w, ph = shell_field(x, y)
    shade = np.clip(-0.45 * ex - 0.6 * ey + 0.65 * np.sqrt(np.clip(1 - r2, 0, 1)), 0, 1)
    body = 0.5 + 0.45 * shade - 0.12 * (np.cos(ph * 30 + 4 * rho) ** 2 > 0.85)
    du = np.hypot(x - UMB[0], y - UMB[1])
    cage = (np.abs(rho - 0.9) < 0.025) | (np.abs(rho - 0.72) < 0.02) & (w < 0)
    straps = cage & (ey - 0.4 * ex < 0.2)  # the crest cage under the horns
    for a in STRAPS:  # straps from the horn bases toward the eye
        da = np.arctan2(y - UMB[1], x - UMB[0]) - a - 0.6 * (1 - rho)
        straps |= (np.abs((da + math.pi) % TAU - math.pi) * du < 3.5) & (rho > 0.5)
    body = np.where(straps, 0.24, body)
    f = w % 1
    tube = np.sin(math.pi * f)
    ribs = np.cos((ph + TAU * np.floor(w)) * 22) ** 2 > 0.8
    coil = (0.46 + 0.3 * tube * shade + 0.18 * tube - 0.18 * ribs) * np.clip(
        1 - 0.1 * np.floor(w), 0.5, 1
    )
    coil = np.where(f > 0.9, 0.2, np.where(f < 0.12, 0.86, coil))  # groove shadow, lit lip
    sv = np.where(w < 0, body, coil) + 0.1 * ng(3, 31, 2)  # bony grain
    sv = np.where(rho < 0.05, 0.18, sv)
    rim = (r2 > 0.86) & (ey - 0.6 * ex < -0.2)
    sv = np.where(rim, 0.9, sv)
    val = np.where(shell, sv, val)

    grid = dither(val, 6, method="bayer", matrix=8)

    # The breach: a ragged burning core on the upper hull, its smoke streaming aft and up. The
    # trail follows the ship's scale; the core keeps its size so the event stays legible.
    bx, by = x - BREACH[0], y - BREACH[1]
    heading = polar((0, 0), 1, deg=SMOKE)
    along = bx * heading.x + by * heading.y
    warp = ng(40, 21, 3)
    across = (by * heading.x - bx * heading.y) + 24 * warp * np.clip(along / 240, 0, 1) ** 1.2
    width = 4 + np.clip(along, 0, None) * 0.07
    dens = 0.3 + 0.6 * np.exp(-np.clip(along, 0, None) / 80)
    trail = (
        np.exp(-((across / width) ** 2))
        * dens
        * np.clip(1 - along / 260, 0, 1)
        * np.clip(along / 10, 0, 1)
    )
    trail *= 0.75 + 0.5 * ng(14, 23, 2)
    rad = np.hypot(bx, by) * k / (9 * (1 + 0.6 * ng(3, 22, 2)))
    core = 0.88 * gauss(rad, 1) + 0.4 * gauss(rad, 2.6)
    ember = dither(np.maximum(core, trail), 5, method="bluenoise", rng=s.np_rng(3))
    grid = np.where(ember > 0, 5 + ember, grid)

    grid = np.where((edge_up & hi) | (shell & rim & edge_up), 10, grid)  # crisp top-lit rim
    grid_runs(s, grid, PALETTE, CELL, skip=None)
