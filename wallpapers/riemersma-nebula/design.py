"""An emission nebula cut by dust lanes beside open starfield, quantized to square cells by Riemersma dithering along a Hilbert curve."""

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import map_coordinates, zoom

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_5,
    ACCENT_7,
    MUTED,
    UI,
    UI_HI,
    Canvas,
    NpRng,
    Rect,
    Vec,
    design,
)
from walldye.field import cells, falloff, gauss
from walldye.geom import scatter
from walldye.pixel import Pixels, dither

type Field = NDArray[np.float64]

CELL = 3
# The nebula is computed on a fixed window of cells, the same in every aspect; the dithered
# field has faded to nothing well inside its edges, so the window never shows as a cut.
COLS, ROWS = 426, 360
CORE_AT = (660, 440)  # the core's offset inside the window
TILT = -0.35  # the nebula's long axis, radians
LANE_AT = (-400, 460)  # a point on the dust lane, from the core
SIDE = 400  # the nebula's side of the sky starts this far left of the core
# Index 0 is empty sky; 1-4 the dithered gas, faintest first; 5-7 the stars.
PALETTE = (None, ACCENT_7, ACCENT_5, ACCENT_3, ACCENT, UI, UI_HI, MUTED)
STAR_UI, STAR_UI_HI, STAR_MUTED = 5, 6, 7
STAR_DENSITY = 32 / (860 * 1000)  # candidates per square unit of open sky
THIN_STARS = 9  # over the nebula's side of a whole window


def value_noise(rng: NpRng, cols: int, rows: int, feature: int) -> Field:
    """Smooth cubic value noise in about [-1, 1], (rows, cols), with features about `feature`
    cells wide."""
    g = rng.uniform(-1, 1, (rows // feature + 4, cols // feature + 4))
    return zoom(g, feature, order=3)[:rows, :cols]


def fbm(s: Canvas, key: int, feature: int, octaves: int = 4) -> Field:
    """Unit-variance fBm over the window; octave o comes from stream key + o."""
    f = np.zeros((ROWS, COLS))
    for o in range(octaves):
        f += 0.55**o * value_noise(s.np_rng(key + o), COLS, ROWS, max(2, feature >> o))
    return f / f.std()


def field(s: Canvas, dx: Field, dy: Field) -> Field:
    """Gas density in [0, 1] at offsets (dx, dy) from the core, one value per window cell."""
    wx, wy = fbm(s, 1, 60), fbm(s, 2, 60)
    jj, ii = np.mgrid[0:ROWS, 0:COLS].astype(float)

    def warp(f: Field) -> Field:
        return map_coordinates(f, [jj + wy * 22, ii + wx * 22], mode="nearest")

    gas = warp(fbm(s, 3, 110, 3))
    dust = np.abs(warp(fbm(s, 4, 150, 3)))  # ridged: dark lanes along zero crossings
    grain = fbm(s, 5, 7, 2)  # keeps every region off a quantization plateau
    ca, sa = np.cos(TILT), np.sin(TILT)

    def radius(ax: float, ay: float, wobble: float) -> Field:
        u, v = dx / ax, dy / ay
        return np.hypot(u * ca - v * sa, u * sa + v * ca) + wobble * gas

    veil = falloff(radius(540, 380, 0.3), 1, 1.3)  # wide thin gas: mostly the faintest step
    body = falloff(radius(300, 220, 0.25), 1, 1.5)  # the dense part, kept small
    hot = gauss(np.hypot(dx, dy), 70 * np.sqrt(2))
    v = veil * (0.42 + 0.1 * gas) + 0.28 * body + 0.24 * hot
    # one straight dust lane, tilted and passing well below-right of the core
    lane_dy = LANE_AT[1] - (dx - LANE_AT[0]) * 0.62 + wy * 45
    lane = gauss((dy - lane_dy) / (55 + 20 * gas), 1)
    # the core itself stays whole: no dust ridges splitting it into two pockets
    dust_k = 1 - 0.6 * hot
    v *= (1 - dust_k * 0.4 * (1 - np.clip(dust / 0.5, 0, 1))) * (1 - 0.8 * lane)
    v += 0.08 * grain * np.clip(v * 6, 0, 1) * (1 - 0.8 * hot)
    return np.clip(v, 0, 1)


def overlap(a: Rect, b: Rect) -> Rect | None:
    """The intersection of two rects, or None when they do not overlap."""
    x0, y0 = max(a.x, b.x), max(a.y, b.y)
    x1, y1 = min(a.x1, b.x1), min(a.y1, b.y1)
    return Rect(x0, y0, x1 - x0, y1 - y0) if x1 > x0 and y1 > y0 else None


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the core on the right third of a landscape screen, the left kept as open sky; high on a
    # portrait one, bleeding off the right edge. The window origin is snapped to whole cells.
    o = s.pick(landscape=(0.677, 0.407), portrait=(0.62, 0.36)) - CORE_AT
    ox, oy = round(o.x / CELL) * CELL, round(o.y / CELL) * CELL
    core = Vec(ox, oy) + CORE_AT
    win = Rect(ox, oy, COLS * CELL, ROWS * CELL)
    xs, ys = cells(win, CELL)
    v = field(s, xs - core.x, ys - core.y)
    gas = dither(v, 5, method="riemersma")

    # one grid for the whole canvas, so stars and gas share the cell lattice
    px = Pixels(s.w // CELL, s.h // CELL, PALETTE)
    i0, j0 = ox // CELL, oy // CELL
    a0, b0 = max(i0, 0), max(j0, 0)
    a1, b1 = min(i0 + COLS, px.cols), min(j0 + ROWS, px.rows)
    px.grid[b0:b1, a0:a1] = gas[b0 - j0 : b1 - j0, a0 - i0 : a1 - i0]

    def plot(p: NDArray[np.float64], index: int) -> None:
        px.grid[int(p[1] // CELL), int(p[0] // CELL)] = index

    r = s.rng(9)
    # stars in the open sky: everywhere but the nebula's side of its window
    sky = s.inset(40)
    side = Rect(core.x - SIDE, oy, win.x1 - core.x + SIDE, win.h)
    n = round(STAR_DENSITY * sky.w * sky.h)
    for p in scatter(n, sky, r, accept=lambda q: not side.contains(q), tries=1):
        plot(p, STAR_MUTED if r.random() < 0.2 else STAR_UI_HI)

    # fainter stars over the nebula's side, only where the gas is thin (the faintest step at most)
    def thin(q: Vec) -> bool:
        i, j = int((q.x - ox) // CELL), int((q.y - oy) // CELL)
        return bool(gas[j, i] <= 1 and v[j, i] < 0.3)

    thin_rect = Rect(ox + 60, oy + 30, win.w - 88, win.h - 60)
    near = overlap(thin_rect, s.inset(30))
    if near is not None:
        n = round(THIN_STARS * near.w * near.h / (thin_rect.w * thin_rect.h))
        for p in scatter(n, near, r, accept=thin):
            plot(p, STAR_UI_HI if r.random() < 0.3 else STAR_UI)

    px.draw(s, CELL)
