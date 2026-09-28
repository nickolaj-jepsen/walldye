"""A Risk of Rain 2 teleporter charging on a night plain: ordered-dither ground and sky under a void-and-cluster dithered charge dome, with a pixel objective readout."""

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_5,
    ACCENT_6,
    ACCENT_8,
    BG,
    BG_ALT,
    BG_DEEP,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Rect,
    design,
)
from walldye.field import cells, gauss, noise_grid, runs
from walldye.geom import bezier_points
from walldye.pixel import Pixels, dither, glyphs, grid_runs, text_width

CELL, BAYER = 6, 8  # dither cell; Bayer matrix size, the period of the sky's dither in cells
SINK = 2 * CELL  # the teleporter stands this far below the horizon
# Charge dome radius, and its ground ellipse's ry / rx: the camera is ~12 deg above the plain.
RX, TILT = 560, 0.2
CHARGE = 0.73
MARGIN = 60  # objective panel to the right edge
# Distant hills: centre as a fraction of the width; then, in units, the offset from it where the
# hill stops (its sign picks the side), spread, height and noise wobble.
HILLS = ((260 / 1920, 500, 330, 80, 12), (1780 / 1920, -340, 260, 50, 10))

# Teleporter after the RoR2 model: a wide stepped disc, a cup pedestal at its centre and two
# crescent horns standing on the rim, bowing out and hooking inward with a gap between the tips.
SPRITE_W, SPRITE_H, OX, OY = 64, 44, 32, 40  # sprite size and its base centre, in cells
DISC = ((26, 5.4, -1), (24.5, 5.0, -2), (23, 4.7, -3))  # semi-axis x, semi-axis y, top-face row
HORN = ((19.5, -4.5), (28.5, -30), (13, -37))  # quadratic Bezier, cells from the base centre
# Sprite indices: shadowed side, top face, lit edge, highlight, then the hot and cooling sparks.
SPRITE = (None, UI, UI_ALT, UI_HI, MUTED, ACCENT, ACCENT_2)
SPARK, EMBER = 5, 6


def teleporter() -> Pixels:
    """The teleporter as an index grid over SPRITE, its base centre at column OX, row OY."""
    px = Pixels(SPRITE_W, SPRITE_H, SPRITE)
    g = px.grid
    u, v = cells(Rect(-OX, -OY, SPRITE_W, SPRITE_H), 1)
    for a, b, top in DISC:
        g[(np.hypot(u / a, (v - top) / b) <= 1) | (np.hypot(u / a, (v - top - 1) / b) <= 1)] = 1
        face = np.hypot(u / a, (v - top) / b)
        g[face <= 1] = 2
        g[(face <= 1) & (face > 1 - 1.1 / b) & (v < top)] = 3  # lit far lip
    # Cup pedestal: short stem, flared bowl.
    g[(np.abs(u) < 1.2) & (v > -9) & (v < -2.5)] = 4
    g[np.hypot(u / 1.8, (v + 3) / 0.8) <= 1] = 4
    g[np.hypot(u / 4, (v + 11) / 1.7) <= 1] = 4
    g[(np.abs(u) < 4 - 1.4 * np.clip(v + 11, 0, 2.2)) & (v > -11) & (v < -7.5)] = 3
    g[np.hypot(u / 3, (v + 11.3) / 0.9) <= 1] = 1  # hollow of the cup
    t = np.linspace(0, 1, 400)
    radius = 2.3 * (1 - t) ** 0.7 + 0.35
    for side in (1, -1):
        spine = bezier_points([(side * x, y) for x, y in HORN], 399)
        for (hx, hy), r in zip(spine, radius, strict=True):
            horn = np.hypot(u - hx, v - hy) <= r
            g[horn] = 3
            g[horn & (side * (u - hx) > r - 1.1)] = 4  # outer edge catches the light
    return px


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Teleporter base: right of centre on a landscape screen, centred low on a portrait one.
    base = s.pick(landscape=(1182 / 1920, 792 / 1080), portrait=(0.5, 0.66), snap=CELL)
    hz = base.y - SINK
    rx = min(RX, 0.4 * s.w)  # the whole dome stays on a portrait screen
    ry = rx * TILT
    xs, ys = cells(Rect(0, 0, s.w, s.h), CELL)
    top = ys - CELL / 2  # each cell's top edge

    n = noise_grid(s.w // CELL, s.h // CELL, 50, s.np_rng(7), octaves=3)
    ridge = np.full(xs.shape, hz + 20)
    for k, (fc, reach, spread, height, wobble) in enumerate(HILLS):
        c = fc * s.w
        near = xs < c + reach if reach > 0 else xs > c + reach
        crest = hz - height * gauss(xs - c, spread) + wobble * n[k]
        ridge = np.minimum(ridge, np.where(near, crest, hz + 20))

    sky = 1 / 3 + 0.16 * (top / hz) ** 3
    # Ground: dark near the horizon, two soft Bayer bands lifting toward the foreground.
    gt = np.clip((top - hz) / (s.h - hz), 0, 1)
    ground = 0.12 + 0.18 * gauss(gt - 0.5, 0.08) + 0.24 * gauss(gt - 0.92, 0.1) + 0.04 * n
    above = ys < hz
    hill = (top >= ridge) & above
    g = dither(np.where(hill, 0.2 + 0.04 * n, ground), 4, method="bayer", matrix=BAYER)
    g[above & ~hill] = 1

    # The sky's dither varies only by row, so it repeats every 8 columns: one strip of it, tiled.
    sky_rows = int(hz // CELL)
    strip = dither(sky[:sky_rows, :BAYER], 4, method="bayer", matrix=BAYER)
    tile = P()
    for j in range(sky_rows):
        for a, b in runs(strip[j] == 2):
            tile.rect(a * CELL, j * CELL, (b - a) * CELL, CELL)
    with s.pattern(BAYER * CELL, hz) as dots:
        dots.fill(tile, BG_ALT)
    grid_runs(s, (above & ~hill).astype(np.int64), [None, dots.ref], CELL)

    # A few stars in the upper sky, none behind the objective panel.
    cols = s.w // CELL
    panel_y = 48 if s.landscape else 144
    rnd = s.rng(11)
    for _ in range(round(26 * cols * (sky_rows // 2 - 4) / (320 * 61))):
        j, i = rnd.randrange(4, sky_rows // 2), rnd.randrange(0, cols)
        if not (i > cols - 80 and j < (panel_y + 72) // CELL):
            g[j, i] = 3
    grid_runs(s, g, [BG_DEEP, BG, BG_ALT, UI], CELL, skip=1)

    # Charge zone as a translucent dome in void-and-cluster dither: the ground ellipse plus the
    # hemisphere's silhouette (orthographic, so a circle of radius rx), both with a fresnel rim.
    cx, cy = xs - base.x, ys - base.y
    d = np.hypot(cx / rx, cy / ry)
    grad = np.hypot(cx / rx**2, cy / ry**2) / np.maximum(d, 1e-6)
    pd = (d - 1) / np.maximum(grad, 1e-9)  # signed distance to the ground ellipse, in units
    halo = np.where(pd < 0, 0.3 * gauss(pd, 14), 0.26 * gauss(pd, 12))
    floor = np.where(d < 1, 0.05 + 0.03 * np.clip(1 - d, 0, 1), 0)
    rd = np.hypot(cx, cy) - rx
    up = cy < 0
    lift = np.clip(-cy / rx, 0, 1)  # the dome shell thins toward its crown, as a fresnel rim would
    shell = np.where(up & (rd < 0), (0.2 - 0.08 * lift) * gauss(rd, 22) + 0.035, 0)
    glow = np.maximum.reduce([halo, floor, shell])
    gl = dither(glow, 5, method="bluenoise", rng=s.np_rng(3))
    # Crisp one-cell rims over the dither: bright front edge, dimmer far edge and dome silhouette.
    gl = np.where(up & (np.abs(rd) < CELL * 0.55), 3, gl)
    gl = np.where(np.abs(pd) < CELL * 0.6, np.where(up, 3, 4), gl)
    grid_runs(s, gl, [None, ACCENT_8, ACCENT_6, ACCENT_5, ACCENT_2], CELL)

    # Sparks drifting up out of the cup, the lowest three still hot.
    tp = teleporter()
    rp = s.rng(4)
    for k in range(7):
        di = rp.randint(-2 - k // 2, 1 + k // 2)
        tp.grid[OY - 14 - 3 * k - rp.randint(0, 2), OX + di] = SPARK if k < 3 else EMBER
    tp.draw(s, CELL, base - (OX * CELL, OY * CELL))

    # Objective panel, top right as in the RoR2 HUD: header, then a checkbox beside each objective.
    line = f"Charge the Teleporter ({round(CHARGE * 100)}%)"
    x = s.w - MARGIN - text_width(line, font="5x8", px=2)
    glyphs(s, "OBJECTIVE", UI_HI, at=(x - 26, panel_y), font="5x8", px=2)
    s.stroke(P().rect(x - 25, panel_y + 25, 13, 13), UI_HI, 2)
    glyphs(s, line, MUTED, at=(x, panel_y + 24), font="5x8", px=2)
