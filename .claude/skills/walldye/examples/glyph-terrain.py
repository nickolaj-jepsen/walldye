"""A roguelike ASCII overworld: noise fields pick terrain glyphs, one A*-routed road leads to an accent town."""

import math

import numpy as np
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
    H,
    W,
    glyphs,
    is_light,
    noise_grid,
)

ASPECTS = ["any"]

U = min(W, H) / 1080  # glyph pixel size; the map keeps its scale on every screen shape
FW, FH = 8 * U, 16 * U
COLS, ROWS = int(W // FW), int(H // FH)
# Thin glyph strokes read fainter on a light ground, so the light regime lifts every role one token.
LIFT = int(is_light())
LADDER = [BG_ALT, UI, UI_ALT, UI_HI, MUTED][LIFT:]
ROAD = ACCENT_1 if LIFT else ACCENT_3
# Roles, not colours, name the glyph paths: two roles may share a hex under some theme.
TONE = {
    ".": LADDER[1],
    '"': LADDER[1],
    "^": LADDER[2],
    "▲": LADDER[3],
    "~": LADDER[0],
    "shallows": LADDER[1],
    "road": ROAD,
    "town": ACCENT,
}


def field(scale, seed):
    """Isotropic fBm in [-1, 1] per cell: rows sampled 2x then halved, since cells are twice as tall as wide."""
    c, r = (
        -(-COLS // scale) * scale,
        -(-2 * ROWS // scale) * scale,
    )  # pad so every octave's lattice divides
    n = noise_grid(c, r, scale, seed=seed, octaves=3)[::2][:ROWS, :COLS]
    return n / np.abs(n).max()


def stroke(dx, dy):
    """ASCII line character for a heading measured in cells, so 45° means one column per row."""
    a = math.degrees(math.atan2(-dy, dx)) % 180
    return "=" if a < 25 or a >= 155 else "/" if a < 70 else "|" if a < 110 else "\\"


def draw(s):
    oy = (H - ROWS * FH) / 2
    x = (np.arange(COLS) + 0.5) * FW
    y = (np.arange(ROWS)[:, None] + 0.5) * FH + oy
    # Map frame: `a` runs along the screen's long axis, `b` across it. Landscape puts the island right
    # of centre (windows open left); portrait turns the map 90° so the road climbs toward the top.
    if W >= H:
        a, b, length = x - 0.677 * W, y - 0.5 * H, 510 * U
    else:
        a, b, length = 0.58 * H - y, x - 0.5 * W, 640 * U  # a phone has room for a longer island
    rng = np.random.default_rng(3)

    r = np.hypot(a / length, b / (350 * U)) * (
        1 + 0.3 * field(24, 9)
    )  # warped footprint: bays and capes
    lab = ndimage.label(0.9 * field(24, 7) + 0.4 - 0.7 * r**3 > 0)[0]
    land = ndimage.binary_fill_holes(lab == np.argmax(np.bincount(lab.ravel())[1:]) + 1)
    inland = ndimage.distance_transform_edt(land, sampling=(2, 1))  # in cell widths
    offshore = ndimage.distance_transform_edt(~land, sampling=(2, 1))

    # Ranges along noise zero-lines, only where a broad 'uplift' field allows, so a couple of ranges survive.
    uplift = np.clip(field(24, 30) * 2.5, 0, 1)
    ridge = (1 - np.abs(field(16, 12))) ** 5 * np.clip((inland - 2) / 8, 0, 1) * uplift
    forest = (field(12, 20) > 0.3) & (ridge < 0.25)
    u = rng.random((ROWS, COLS))
    grid = np.full((ROWS, COLS), " ", dtype="<U1")
    grid[land & (u < 0.22)] = "."
    grid[land & (inland < 2.5) & (u < 0.75)] = "."  # crisp shoreline
    grid[land & forest & (u < 0.85)] = '"'
    grid[land & (ridge > 0.3) & (u < 0.8)] = "^"
    grid[land & (ridge > 0.55)] = "▲"
    grid[~land & (u < 0.8 * np.exp(-((offshore / 5) ** 1.5)))] = "~"
    shallows = ~land & (offshore < 2.5)

    # Road: cheapest path from the 'west' coast to a town in the 'eastern' foothills (in map frame).
    coast = land & (inland < 1.5)
    start = np.unravel_index(
        np.argmin(np.where(coast, a + 1.5 * np.abs(b - 130 * U), np.inf)), land.shape
    )
    foothill = land & (ridge > 0.12) & (ridge < 0.3) & (inland > 6)
    near = np.hypot(a - 320 * U, b + 150 * U) + np.where(foothill, 0, 1e5)  # fall back to any land
    town = np.unravel_index(np.argmin(np.where(land, near, np.inf)), land.shape)
    cost = np.where(
        land, 3 + 3 * field(12, 40) + 80 * (ridge > 0.3) + 2 * forest + 8 * np.exp(-inland / 3), 1e4
    )
    path, _ = route_through_array(cost, start, town, fully_connected=True, geometric=True)

    # Smooth the A* path hard (kills one-row jogs), then re-trace it cell by cell.
    cells = []
    for c in np.rint(
        ndimage.gaussian_filter1d(np.array(path, float), 7, axis=0, mode="nearest")
    ).astype(int):
        while cells and max(abs(c[0] - cells[-1][0]), abs(c[1] - cells[-1][1])) > 1:
            cells.append(
                (
                    cells[-1][0] + np.sign(c[0] - cells[-1][0]),
                    cells[-1][1] + np.sign(c[1] - cells[-1][1]),
                )
            )
        if not cells or tuple(c) != cells[-1]:
            cells.append(tuple(c))
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
    for k, (c, (dy, dx)) in enumerate(zip(cells, heading)):
        ch, prev = stroke(dx, dy), cells[max(k - 1, 0)]
        if ch in "=|" and prev[0] != c[0] and prev[1] != c[1]:
            ch = (
                "/" if (c[0] - prev[0]) * (c[1] - prev[1]) < 0 else "\\"
            )  # a diagonal step inside a straight run
        grid[c] = ch
    harbour, town = cells[0], cells[-1]
    grid[harbour], grid[town] = "o", "■"

    def role(i, j, ch):
        if (j, i) == town:
            return "town"
        if (j, i) in road:
            return "road"
        return "shallows" if shallows[j, i] else ch

    glyphs(
        s,
        ["".join(row) for row in grid],
        lambda i, j, ch: TONE[role(i, j, ch)],
        key=role,
        font="8x16",
        px=U,
        y=oy,
    )
