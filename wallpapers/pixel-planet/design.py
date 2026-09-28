"""A ringed planet lit from behind in flat pixel shading: a thin crescent, a banded night side, a tilted ring."""

import math

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    ACCENT_8,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Rect,
    Vec,
    by_regime,
    design,
    mix,
)
from walldye.field import cells
from walldye.geom import scatter
from walldye.pixel import grid_runs

CELL = 8
R = 23 * CELL  # planet radius
SHEAR = 0.25  # ring tilt as an exact 1:4 slope, so its long edges step in even runs
RING_IN, RING_OUT, SQUASH = 1.4, 2.0, 0.24  # ring radii in planet radii, and its foreshortening
LIGHT = np.array([-0.62, -0.5, -0.35])  # upper left, slightly behind the planet
STAR_DENSITY = 36 / (240 * 135)  # stars per cell: 36 on a 16:9 screen

# Grid indices into PALETTE; 0 is empty sky.
DISC = (1, 2, 3, 4, 5)  # lit levels, night side to crescent
RING_OUTER, RING_INNER, LIP, SHADE, GLINT = 6, 7, 8, 9, 10
# Shade steps away from the lit side: into the sky on a dark screen, ink on a light one.
SHADE_TONE = by_regime(BG_DEEP, mix(UI, ACCENT_6, 0.5))
PALETTE = (
    None,
    ACCENT_8,
    ACCENT_7,
    ACCENT_5,
    ACCENT_3,
    ACCENT,
    BG_ALT,
    UI,
    UI_ALT,
    SHADE_TONE,
    UI_HI,
)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of centre and a little high on a landscape screen; below the clock on a portrait one
    c = s.pick(landscape=(0.62, 0.4), portrait=(0.54, 0.36), snap=CELL)
    xs, ys = cells(Rect(0, 0, s.w, s.h), CELL)
    rows, cols = xs.shape
    dx, dy = (xs - c.x) / R, (ys - c.y) / R
    d2 = dx * dx + dy * dy
    disc = d2 < 1
    nz = np.sqrt(np.clip(1 - d2, 0, 1))
    u, v = dx, dy - SHEAR * dx  # ring frame

    # Lighting from behind leaves a crescent; clean thresholds, no dither.
    sun = LIGHT / np.linalg.norm(LIGHT)
    lam = dx * sun[0] + dy * sun[1] + nz * sun[2]
    level = np.digitize(lam, [-0.08, 0.2, 0.42, 0.62])

    # Latitude bands parallel to the ring plane darken one step; the crescent stays whole.
    lat = np.arcsin(np.clip(-math.sqrt(1 - SQUASH**2) * v + SQUASH * nz, -1, 1))
    band = (np.floor(lat * 3.6 + 0.35) % 2 == 1) & (np.abs(lat) < 1.1)
    level = np.where(band & (level < 4), np.maximum(level - 1, 0), level)
    grid = np.where(disc, np.array(DISC)[level], 0)
    grid[disc & band & (level == 0)] = SHADE

    # The ring's back half hides behind the disc; the front half casts a strip of shadow on it.
    def ring_at(vv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        e = np.sqrt(u * u + (vv / SQUASH) ** 2)
        return (e > RING_IN) & (e < RING_OUT), e

    ring, e = ring_at(v)
    front = v > 0
    shadow, _ = ring_at(v + 2 * CELL / R)
    grid[disc & shadow & front & ~ring] = SHADE
    visible = ring & (front | ~disc)
    grid = np.where(visible, np.where(e < 1.72, RING_INNER, RING_OUTER), grid)
    grid[visible & front & ~np.roll(visible, -1, 0) & (u < -0.35)] = LIP

    # Stars keep clear of the planet and its ring and reuse the ring's tones; two are small crosses.
    cx, cy = c.x / CELL, c.y / CELL

    def clear(p: Vec) -> bool:
        return (
            math.hypot((p.x - cx) / 2.4, p.y - cy) >= 1.35 * R / CELL
            and not grid[int(p.y), int(p.x)]
        )

    n = round(STAR_DENSITY * cols * rows)
    stars = scatter(n, Rect(3, 3, cols - 6, rows - 6), s.rng(11), min_dist=12, accept=clear)
    for k, (x, y) in enumerate(stars.astype(int)):
        if k < 2:
            grid[y, x - 1 : x + 2] = RING_INNER
            grid[y - 1 : y + 2, x] = RING_INNER
            grid[y, x] = GLINT
        else:
            grid[y, x] = LIP if k % 3 else RING_INNER

    grid_runs(s, grid, PALETTE, CELL)
