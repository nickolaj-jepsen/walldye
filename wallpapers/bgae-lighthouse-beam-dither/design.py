"""Jade's lighthouse on its rock off Hillys at night in Bayer-dithered cells, tapered rays radiating from the lamp."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    ACCENT_HI,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    design,
)
from walldye.field import cells, falloff, gauss, noise_grid
from walldye.pixel import dither, grid_runs

CELL = 6
# Index palette: the six dithered scene tones, the ray ramp from faint to strong, the lamp.
PALETTE = (
    *(BG_DEEP, BG, BG_ALT, UI, UI_ALT, UI_HI),
    *(ACCENT_6, ACCENT_5, ACCENT_3, ACCENT_2),
    *(ACCENT, ACCENT_HI),
)
SCENE = 6  # dither levels of the scene: tone 0 is BG_DEEP, 5 is UI_HI
POST, POST_HI = 4, 5  # the far beacons
RAY0 = 5  # ray dither level k maps to RAY0 + k
GLOW_DIM, GLOW, GLOW_HI = 6, 7, 8  # lamp surround and reflection
LAMP, LAMP_HI = 10, 11

# Rock profile against the tower axis: column offsets and heights above the horizon, a knob
# under the tower, then a block rising to a flat top with a sheer seaward face.
ROCK_X = (-16, -15, -13, -10, -6, 7, 11, 14, 20, 32, 46, 58, 70, 74, 75, 76)
ROCK_H = (0, 8, 15, 18, 23, 23, 19, 17, 21, 27, 32, 34, 35, 33, 26, 0)
ROCK_TOP, ROCK_L, ROCK_R = 40, -16, 77  # the window the rock's texture fields cover
DOCKS = ((50, 6, 5), (63, 3.5, 3))  # waterline openings in the bluff: offset, half-width, height
HILL_L, HILL_R = -54, 86  # the mainland's extent around its peak

type Field = NDArray[np.float64]


@design(aspects="any")
def draw(s: Canvas) -> None:
    cols, rows = s.w // CELL, s.h // CELL
    # The tower axis and the horizon: right of centre on a landscape screen, left of centre and
    # below the middle on a portrait one, where the rock takes most of the width.
    anchor = s.pick(landscape=(0.6125, 0.65), portrait=(0.42, 0.6), snap=CELL)
    tc, hr = round(anchor.x / CELL), round(anchor.y / CELL)
    # The far beacons frame the scene near both edges and stay clear of the rock's face.
    left_post = 22 if s.landscape else 14
    right_post = max(cols - 30, tc + 90)
    # The mainland peak sits a fifth of the way in, at least 116 columns left of the tower on a
    # landscape screen; on a portrait one it passes behind the rock.
    peak = min(round(0.2 * cols), tc - 116) if s.landscape else round(0.2 * cols)

    J, I = np.indices((rows, cols))
    xs, ys = cells(s.inset(0), CELL)
    off = I - tc  # column offset from the tower axis, which runs between off -1 and 0
    rel = off + 0.5
    v = J - hr  # rows below the horizon, negative above it
    col = np.arange(cols)

    # Tone in scene levels (0 = BG_DEEP .. 5 = UI_HI): a sky brightening down to the horizon.
    tone = 0.15 + 1.15 * np.clip(J / hr, 0, 1) ** 2.4 + 0.2 * np.clip((v + 5) / 5, 0, 1)
    # Sea: swell bands that widen with depth, broken into streaks.
    sea = v >= 0
    swell = noise_grid(cols, rows, 40, s.np_rng(7), octaves=2)
    swell = np.repeat(swell[::6, :], 6, axis=0)[:rows]
    depth = np.clip(v / (rows - hr), 0, 1)
    bands = 0.5 + 0.5 * np.sin((ys - hr * CELL) / (14 + 40 * depth) * 2 * math.pi + swell * 3)
    streak = np.clip(bands**6 * (0.6 + 0.8 * noise_grid(cols, rows, 60, s.np_rng(9))), 0, 1)
    tone = np.where(sea, 0.3 + 1.3 * streak * (1 - 0.75 * depth) - 0.25 * depth, tone)
    tone = np.where(v == 0, 1.9, tone)

    # Hillys mainland on the horizon: one peaked mountain with a lower shoulder.
    hx = col - peak
    snow = noise_grid(HILL_R - HILL_L, 1, 6, s.np_rng(33), octaves=2)[0]
    mtn = np.maximum(24 - np.abs(hx) * np.where(hx < 0, 0.62, 0.48), 0)
    mtn += np.maximum(7 - np.abs(hx - 48) * 0.2, 0)
    mtn = np.maximum(mtn, 2.0 * gauss(hx + 34, 30))
    mtn += 0.9 * snow[np.clip(hx - HILL_L, 0, HILL_R - HILL_L - 1)] * (mtn > 0.5)
    mh = np.round(np.where((hx > HILL_L) & (hx < HILL_R), mtn, 0))[None, :]
    far = (v < 0) & (v >= -mh) & (mh >= 1)
    tone = np.where(far, 1.25 + 0.35 * np.clip((v + 16) / 16, 0, 1) + 0.25 * (hx < -2), tone)

    # A low flat landmass on the far right horizon, beyond the right beacon.
    land = (v < 0) & (I >= right_post + 8) & (I < right_post + 30)
    land &= v >= -np.where(I < right_post + 11, 2, 4)
    tone = np.where(land, 1.9 + 0.3 * (v == -4), tone)

    # Rock, lit from the left. Its texture fields cover only the rock's own window, so it looks
    # the same on every screen.
    struct = np.zeros((rows, cols), bool)
    win = np.s_[hr - ROCK_TOP : hr + 3, tc + ROCK_L : tc + ROCK_R]
    wr, wc = ROCK_TOP + 3, ROCK_R - ROCK_L
    rn = noise_grid(wc, 1, 4, s.np_rng(21), octaves=3)[0]
    rtop = hr - np.interp(col - tc, ROCK_X, ROCK_H, left=-9, right=-9)
    rtop += 1.2 * rn[np.clip(col - tc - ROCK_L, 0, wc - 1)] * ((col > tc - 15) & (col < tc + 72))
    rock = (J >= np.round(rtop)[None, :]) & (v <= 2)
    lit = np.clip((40 - off) / 60, 0, 1) * np.clip(0.4 + (off + 20) / 30, 0, 1)
    crag = np.zeros((rows, cols))
    crag[win] = noise_grid(wc, wr, 3, s.np_rng(5), octaves=3)
    fiss = np.zeros((rows, cols), bool)
    fiss[win] = np.abs(noise_grid(wc * 3, wr, 12, s.np_rng(8))[:, ::3]) < 0.05  # vertical cracks
    face = off >= 72  # sheer right face in shadow
    rim = (J - rtop[None, :]) < 2
    tone = np.where(
        rock, 1.65 + 0.9 * lit + 0.55 * crag + 0.8 * rim - 0.9 * fiss - 0.5 * face, tone
    )
    struct |= rock

    for dx, rw, rh in DOCKS:
        dock = (v <= 0) & (((rel - dx) / rw) ** 2 + ((v - 0.5) / rh) ** 2 <= 1)
        tone = np.where(dock, 0.1, tone)
    tone = np.where((v == 0) & (off >= 42) & (off <= 49), 2.6, tone)  # jetty

    # Pillared plinth: frame beam, corner posts, pale curved wall between them; its foot sunk
    # into the knob.
    drum = (v >= -33) & (v <= -22) & (np.abs(rel) <= 11.5)
    du = np.clip((rel + 11.5) / 23, 0, 1)
    tone = np.where(drum, 2.3 + 2.1 * (1 - du) ** 1.2, tone)
    tone = np.where(drum & (v <= -32), 2.9 + 1.9 * (1 - du), tone)
    posts = drum & (v > -32) & np.isin(off, (-12, -6, 5, 11))
    tone = np.where(posts, 1.2 + 0.8 * (1 - du), tone)
    tone = np.where((rel + 8.5) ** 2 + (v + 27) ** 2 <= 1.6, 0.8, tone)  # porthole
    struct |= drum

    # Strongly tapered cone: narrow under the gallery, wide at the plinth; portholes down the
    # lit side.
    hw = 5 + 4.5 * (v + 63) / 29
    tower = (v >= -63) & (v <= -34) & (np.abs(rel) <= hw)
    u = np.clip((rel + hw) / (2 * hw), 0, 1)
    tone = np.where(tower, 2.4 + 2.3 * (1 - u) ** 1.2, tone)
    for pv in (-59, -50, -41):
        pc = round(-0.35 * (5 + 4.5 * (pv + 63) / 29))
        tone = np.where((v == pv) & (off == pc), 0.8, tone)
    struct |= tower

    # Flared saucer gallery with a thin lip.
    su = np.clip((rel + 14) / 28, 0, 1)
    sau = ((v == -65) & (np.abs(rel) <= 15.5)) | ((v == -64) & (np.abs(rel) <= 10))
    tone = np.where(sau, 2.7 + 2.3 * (1 - su) + 0.3 * (v == -65), tone)
    tone = np.where(sau & (v == -65) & (np.abs(rel) > 13.5), 1.8 + 1.5 * (1 - su), tone)
    struct |= sau

    # Glazed lantern under a smaller top disc; the lamp cells are painted after dithering.
    lant = (v >= -68) & (v <= -66) & (np.abs(rel) <= 4.5)
    mull = lant & np.isin(off, (-5, -2, 1, 4))
    tone = np.where(lant, 0.3, tone)
    tone = np.where(mull, 3.4 + 0.8 * (1 - su), tone)
    disc = (v == -69) & (np.abs(rel) <= 7)
    tone = np.where(disc, 3.0 + 1.8 * (1 - su), tone)
    struct |= lant | disc

    # Tall thin mast up to the umbrella, which is painted after dithering.
    mast = (v >= -85) & (v <= -70) & (off == -1)
    tone = np.where(mast, 3.3, tone)
    struct |= mast

    grid = dither(np.clip(tone / 5, 0, 1), SCENE, method="bayer", matrix=8)

    # Rays: tapered wedges radiating from the lamp, widening outward.
    lamp = (tc * CELL, (hr - 66.5) * CELL)
    dx, dy = xs - lamp[0], ys - lamp[1]
    rr = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)
    rg = s.np_rng(4)
    rays: Field = np.zeros_like(rr)
    n = 14
    for a in np.linspace(0, 2 * math.pi, n, endpoint=False) + rg.uniform(-0.1, 0.1, n) + 0.15:
        reach = rg.uniform(220, 400)
        da = np.abs((ang - a + math.pi) % (2 * math.pi) - math.pi)
        wa = 0.045 + 0.02 * rg.random()  # angular half-width
        rays = np.maximum(rays, falloff(da, wa, 0.7) * falloff(rr, reach, 1.3) * 0.62)
    rays = np.maximum(rays, 0.95 * gauss(rr, 30))
    rays = np.where(rays < 0.1, 0, rays)  # cut the sparse dither tail
    rays = np.where(struct | sea | ((v > -89) & (v < -69) & (np.abs(rel) <= 5.5)), 0, rays)
    rgrid = dither(rays, 5, method="bayer", matrix=8)
    grid = np.where(rgrid > 0, RAY0 + rgrid, grid)

    glass = lant & ~mull
    grid[glass] = np.where((v == -67) | (np.abs(rel) < 3), LAMP, GLOW)[glass]
    grid[hr - 67, tc - 1 : tc + 1] = LAMP_HI

    # Broad shallow umbrella cap atop the mast, lit on its left; a finial above.
    for j, half in ((hr - 89, 1), (hr - 88, 3), (hr - 87, 4.5), (hr - 86, 6)):
        for i in range(tc - math.ceil(half), tc + int(half)):
            grid[j, i] = GLOW if j == hr - 86 else LAMP if i < tc - 1 else GLOW_HI
    grid[hr - 92 : hr - 89, tc - 1] = POST_HI

    # Far beacon shafts standing in the sea: dotted at the top, solid and brightest at the base.
    for bc, top in ((left_post, hr - 55), (right_post, hr - 51)):
        for j in range(top, hr + 1):
            k = (j - top) / (hr - top)
            if k > 0.45 or (j + bc) % max(1, int(4 - 4 * k)) == 0:
                grid[j, bc] = POST_HI if k > 0.55 else POST
        grid[hr - 1 : hr + 1, bc - 1 : bc + 2] = POST
        grid[hr - 3 : hr, bc] = POST_HI
        for j in range(hr + 2, hr + 18, 2):
            if (j * 3 + bc) % 4:
                grid[j, bc - (j % 3 == 0)] = POST

    # Broken reflection column from the waterline under the lamp.
    r = s.np_rng(11)
    j0 = hr + 5
    for j in range(j0, rows, 2):
        k = (j - j0) / (rows - j0)
        top = j < j0 + 10
        if not top and r.random() < 0.35 + 0.55 * k:
            continue
        w = 1 + int(r.integers(0, 3)) + int(3 * (1 - k) ** 2 if top else 2 * (1 - k))
        c = tc + int(r.integers(-2, 2)) - w // 2
        grid[j, c : c + w] = GLOW if k < 0.3 else GLOW_DIM

    grid_runs(s, grid, PALETTE, CELL, skip=1)
