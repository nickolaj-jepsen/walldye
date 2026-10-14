"""A ringed planet lit from behind in flat pixel shading."""

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
WIN = 2 * R // CELL + 3  # half-width in cells of the window that holds the planet and its ring

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


def planet() -> np.ndarray:
    """The planet and its ring as grid indices, on a square window of cells centered on the
    planet with a cell corner at its center."""
    xs, ys = cells(Rect(-WIN * CELL, -WIN * CELL, 2 * WIN * CELL, 2 * WIN * CELL), CELL)
    dx, dy = xs / R, ys / R
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
    return grid


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of center and a little high on a landscape screen; below the clock on a portrait one
    home = (0.62, 0.4) if s.landscape else (0.54, 0.36)
    c = s.pick(landscape=(0.62, 0.4), portrait=(0.54, 0.36), snap=CELL)
    # The sky is laid out once around the planet's own place, in screen cells, and moves with it.
    cx, cy = round(home[0] * s.w / CELL), round(home[1] * s.h / CELL)
    rows, cols = cells(Rect(0, 0, s.w, s.h), CELL)[0].shape
    body = planet()

    def at(x: int, y: int) -> int:
        """The planet's grid index at screen cell (x, y), 0 off its window."""
        i, j = x - cx + WIN, y - cy + WIN
        return int(body[j, i]) if 0 <= i < 2 * WIN and 0 <= j < 2 * WIN else 0

    # Stars keep clear of the planet and its ring and reuse the ring's tones; two are small crosses.
    def clear(p: Vec) -> bool:
        apart = math.hypot((p.x - cx) / 2.4, p.y - cy) >= 1.35 * R / CELL
        return apart and not at(math.floor(p.x), math.floor(p.y))

    n = round(STAR_DENSITY * cols * rows)
    stars = scatter(n, Rect(3, 3, cols - 6, rows - 6), s.rng(11), min_dist=12, accept=clear)
    handle = Rect(-RING_OUT * R - CELL, -R - CELL, 2 * RING_OUT * R + 2 * CELL, 2 * R + 2 * CELL)

    with s.motif(c, "cover", handle=handle, cell=CELL) as m:
        # the sky past the screen's edges, wherever the planet goes, kept a star's spacing
        # clear of the screen's own stars
        x0, y0 = math.floor(m.cover.x / CELL) + cx, math.floor(m.cover.y / CELL) + cy
        w, h = math.ceil(m.cover.x1 / CELL) + cx - x0, math.ceil(m.cover.y1 / CELL) + cy - y0

        def beyond(p: Vec) -> bool:
            return not (-9 <= p.x < cols + 9 and -9 <= p.y < rows + 9) and clear(p)

        more = round(STAR_DENSITY * (w * h - cols * rows))
        far = scatter(more, Rect(x0, y0, w, h), s.rng(12), min_dist=12, accept=beyond)

        grid = np.zeros((h, w), np.int64)
        grid[cy - WIN - y0 : cy + WIN - y0, cx - WIN - x0 : cx + WIN - x0] = body
        for k, (x, y) in enumerate(stars.astype(int) - (x0, y0)):
            if k < 2:
                grid[y, x - 1 : x + 2] = RING_INNER
                grid[y - 1 : y + 2, x] = RING_INNER
                grid[y, x] = GLINT
            else:
                grid[y, x] = LIP if k % 3 else RING_INNER
        for k, (x, y) in enumerate(np.floor(far).astype(int) - (x0, y0), start=n):
            grid[y, x] = LIP if k % 3 else RING_INNER
        grid_runs(s, grid, PALETTE, CELL, ((x0 - cx) * CELL, (y0 - cy) * CELL))
