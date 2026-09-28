"""A roguelike ASCII overworld: noise fields pick terrain glyphs, and one least-cost road leads to a town."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from skimage.graph import route_through_array

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    BG_ALT,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    by_regime,
    design,
)
from walldye.field import noise_grid
from walldye.pixel import glyphs

FW, FH = 8, 16  # glyph cell
# Thin glyph strokes read fainter on a light ground, so light themes lift every role one step.
STEPS = (BG_ALT, UI, UI_ALT, UI_HI, MUTED)
SEA, LAND, HILL, PEAK = (by_regime(STEPS[k], STEPS[k + 1]) for k in range(4))
TONE: dict[str, Colour] = {
    ".": LAND,
    '"': LAND,
    "^": HILL,
    "▲": PEAK,
    "~": SEA,
    "shallows": LAND,
    "road": by_regime(ACCENT_3, ACCENT_1),
    "town": ACCENT,
}

type Grid = NDArray[np.float64]


def stroke(dx: float, dy: float) -> str:
    """The ASCII line character for a heading measured in cells, so 45° is one column per row."""
    a = math.degrees(math.atan2(-dy, dx)) % 180
    return "=" if a < 25 or a >= 155 else "/" if a < 70 else "|" if a < 110 else "\\"


@design(aspects="any")
def draw(s: Canvas) -> None:
    cols, rows = s.w // FW, s.h // FH

    def field(scale: int, key: int) -> Grid:
        """Isotropic fBm in [-1, 1] per cell: rows sampled twice as fine, then every other one
        kept, since cells are twice as tall as wide."""
        n = noise_grid(cols, 2 * rows, scale, s.np_rng(key), octaves=3)[::2]
        return n / np.abs(n).max()

    oy = (s.h - rows * FH) / 2
    x = (np.arange(cols) + 0.5) * FW
    y = (np.arange(rows)[:, None] + 0.5) * FH + oy
    # Map frame: `a` runs along the screen's long axis, `b` across it. Landscape puts the island
    # right of centre (windows open left); portrait turns the map 90° so the road climbs.
    mid = s.pick(landscape=(0.677, 0.5), portrait=(0.5, 0.58))
    if s.landscape:
        a, b, length = x - mid.x, y - mid.y, 510
    else:
        a, b, length = mid.y - y, x - mid.x, 640  # a phone has room for a longer island
    rng = s.np_rng(3)

    # a warped footprint: bays and capes
    r = np.hypot(a / length, b / 350) * (1 + 0.3 * field(24, 9))
    lab = ndimage.label(0.9 * field(24, 7) + 0.4 - 0.7 * r**3 > 0)[0]
    land = ndimage.binary_fill_holes(lab == np.argmax(np.bincount(lab.ravel())[1:]) + 1)
    inland = ndimage.distance_transform_edt(land, sampling=(2, 1))  # in cell widths
    offshore = ndimage.distance_transform_edt(~land, sampling=(2, 1))

    # Ranges along noise zero-lines, only where a broad uplift field allows, so a couple survive.
    uplift = np.clip(field(24, 30) * 2.5, 0, 1)
    ridge = (1 - np.abs(field(16, 12))) ** 5 * np.clip((inland - 2) / 8, 0, 1) * uplift
    forest = (field(12, 20) > 0.3) & (ridge < 0.25)
    u = rng.random((rows, cols))
    grid = np.full((rows, cols), " ", dtype="<U1")
    grid[land & (u < 0.22)] = "."
    grid[land & (inland < 2.5) & (u < 0.75)] = "."  # crisp shoreline
    grid[land & forest & (u < 0.85)] = '"'
    grid[land & (ridge > 0.3) & (u < 0.8)] = "^"
    grid[land & (ridge > 0.55)] = "▲"
    grid[~land & (u < 0.8 * np.exp(-((offshore / 5) ** 1.5)))] = "~"
    shallows = ~land & (offshore < 2.5)

    # Road: the cheapest path from the west coast to a town in the eastern foothills (map frame).
    coast = land & (inland < 1.5)
    start = np.unravel_index(
        np.argmin(np.where(coast, a + 1.5 * np.abs(b - 130), np.inf)), land.shape
    )
    foothill = land & (ridge > 0.12) & (ridge < 0.3) & (inland > 6)
    near = np.hypot(a - 320, b + 150) + np.where(foothill, 0, 1e5)  # fall back to any land
    goal = np.unravel_index(np.argmin(np.where(land, near, np.inf)), land.shape)
    cost = np.where(
        land, 3 + 3 * field(12, 40) + 80 * (ridge > 0.3) + 2 * forest + 8 * np.exp(-inland / 3), 1e4
    )
    route, _ = route_through_array(cost, start, goal, fully_connected=True, geometric=True)

    # Smooth the route hard (kills one-row jogs), then re-trace it cell by cell.
    cells: list[tuple[int, int]] = []
    smooth = ndimage.gaussian_filter1d(np.array(route, float), 7, axis=0, mode="nearest")
    for j, i in np.rint(smooth).astype(int).tolist():
        while cells and max(abs(j - cells[-1][0]), abs(i - cells[-1][1])) > 1:
            pj, pi = cells[-1]
            cells.append((pj + int(np.sign(j - pj)), pi + int(np.sign(i - pi))))
        if not cells or (j, i) != cells[-1]:
            cells.append((j, i))
    k = 1
    while k < len(cells) - 1:  # cut staircase corners so steps are single diagonal glyphs
        p, q = cells[k - 1], cells[k + 1]
        if abs(p[0] - q[0]) == 1 and abs(p[1] - q[1]) == 1:
            del cells[k]
        else:
            k += 1
    heading = np.gradient(
        ndimage.gaussian_filter1d(np.array(cells, float), 2, axis=0, mode="nearest"), axis=0
    )
    road = set(cells)
    for k, (c, (dy, dx)) in enumerate(zip(cells, heading.tolist(), strict=True)):
        ch, prev = stroke(dx, dy), cells[max(k - 1, 0)]
        if ch in "=|" and prev[0] != c[0] and prev[1] != c[1]:
            # a diagonal step inside a straight run
            ch = "/" if (c[0] - prev[0]) * (c[1] - prev[1]) < 0 else "\\"
        grid[c] = ch
    harbour, town = cells[0], cells[-1]
    grid[harbour], grid[town] = "o", "■"

    def tone(i: int, j: int, ch: str) -> Colour:
        if (j, i) == town:
            return TONE["town"]
        if (j, i) in road:
            return TONE["road"]
        return TONE["shallows" if shallows[j, i] else ch]

    glyphs(s, ["".join(row) for row in grid], tone, at=(0, oy), px=1)
