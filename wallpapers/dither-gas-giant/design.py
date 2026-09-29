"""A gas giant rising from the corner, its belts, turbulence and one storm oval quantized by serpentine Stucki error diffusion."""

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import map_coordinates, zoom

from walldye import (
    ACCENT,
    ACCENT_6,
    ACCENT_7,
    BG_ALT,
    UI,
    Canvas,
    NpRng,
    Rect,
    design,
)
from walldye.field import cells
from walldye.pixel import dither, grid_runs

type Field = NDArray[np.float64]

CELL = 3
R = 900  # planet radius
# planet center: this far in from the right edge and below the bottom one; portrait screens
# lift it, so the storm clears the bottom edge
CORNER = (70, 170)
CORNER_PORTRAIT = (40, 50)
TILT = 0.22  # band tilt, radians
STORM = (-0.42, -0.36)  # (longitude-ish x', latitude) in planet units
ACCENT_BELT = -3  # the belt just north of the storm; every other belt keeps the UI steps
LEVELS = 5  # steps of 0.25; the field peaks near 0.55, so only levels 0-2 occur
# Dither level to palette index: BG_ALT and UI on plain cloud, ACCENT_7 and ACCENT_6 on the
# picked-out belt and the storm, full ACCENT only for the grain in the storm's eye.
PALETTE = (None, BG_ALT, UI, ACCENT_7, ACCENT_6, ACCENT)
PLAIN = np.array([0, 1, 2, 2, 2])
PICKED = np.array([0, 3, 4, 4, 4])
SPARK = 5


def value_noise(rng: NpRng, shape: tuple[int, int], feature: tuple[int, int]) -> Field:
    """Cubic-interpolated value noise of `shape`, with features `feature` cells (rows, cols)."""
    g = rng.uniform(-1, 1, (shape[0] // feature[0] + 4, shape[1] // feature[1] + 4))
    return zoom(g, feature, order=3)[: shape[0], : shape[1]]


@design(aspects=("16:9", "32:9", "9:19.5", "10:16"))
def draw(s: Canvas) -> None:
    dx, dy = CORNER if s.landscape else CORNER_PORTRAIT
    cx, cy = s.w - dx, s.h + dy
    # the grid covers only the planet's box, snapped so every cell edge stays on the grid
    x0 = max(0, (cx - R - 20) // CELL * CELL)
    y0 = max(0, (cy - R - 20) // CELL * CELL)
    xs, ys = cells(Rect(x0, y0, s.w - x0, s.h - y0), CELL)

    # Planet coordinates: x' along the bands, latitude across them, mu the limb darkening term.
    u, v = (xs - cx) / R, (ys - cy) / R
    c, sn = np.cos(TILT), np.sin(TILT)
    xp, lat = u * c + v * sn, -u * sn + v * c
    rho = np.hypot(xp, lat)
    inside = rho < 1
    mu = np.sqrt(np.clip(1 - rho * rho, 0, 1))
    lon = np.arcsin(np.clip(xp / np.maximum(np.sqrt(np.clip(1 - lat * lat, 0, 1)), 1e-3), -1, 1))

    # storm: swirl the sampling coordinates inside an ellipse
    sx, sy = (lon - STORM[0]) / 0.16, (lat - STORM[1]) / 0.07
    sr = np.hypot(sx, sy)
    swirl = 2.4 * np.exp(-sr * sr * 1.5)
    ca, sa = np.cos(swirl), np.sin(swirl)
    lon_s = STORM[0] + (sx * ca - sy * sa) * 0.16
    lat_s = STORM[1] + (sx * sa + sy * ca) * 0.07

    # anisotropic turbulence: long along the bands, short across them
    shape = (600, 900)
    turb = (
        value_noise(s.np_rng(3), shape, (6, 60))
        + 0.5 * value_noise(s.np_rng(4), shape, (3, 24))
        + 0.25 * value_noise(s.np_rng(5), shape, (2, 10))
    )

    def ti(la: Field, lo: Field) -> Field:
        return map_coordinates(turb, [(la + 1) * 290, (lo + 1.6) * 270], mode="nearest")

    lat_w = lat_s + 0.028 * ti(lat_s, lon_s)
    phase = lat_w * 26 + 0.8
    band = np.sin(phase)  # >0 zones, <0 belts
    edge = 1 - np.abs(band)  # turbulence lives at the band edges; the band cores stay laminar
    belt = (np.floor((phase - np.pi) / (2 * np.pi)) == ACCENT_BELT) & (band < 0)
    val = 0.4 + 0.2 * band + 0.24 * belt + (0.03 + 0.1 * edge) * ti(lat_s * 1.7, lon_s * 1.3)

    oval = np.exp(-((sr / 0.9) ** 6))
    ring = np.exp(-(((sr - 1.05) / 0.22) ** 2))
    swirl_tex = ti(lat_s * 4, lon_s * 4)
    val = val * (1 - 0.65 * ring) * (1 - oval) + oval * (
        0.5 + 0.2 * swirl_tex + 0.25 * np.exp(-sr * sr * 3)
    )
    val = np.where(inside, val * 0.78 * mu**0.6, 0)
    # sparse full-accent grain in the storm's inner third: ~18% at the eye, 0 at the collar
    hot = np.where(inside, 0.2 * np.clip(1 - sr / 0.85, 0, 1) ** 1.5, 0)
    tinted = (belt | (oval > 0.3)) & inside

    q = dither(val, LEVELS, method="stucki", serpentine=True)
    grid = np.where(tinted, PICKED[q], PLAIN[q])
    grid[dither(hot, 2, method="stucki", serpentine=True) == 1] = SPARK
    grid_runs(s, grid, PALETTE, CELL, (x0, y0))
