"""The Erdtree over Limgrave in void-and-cluster dither: a dome of filaments on a twisted trunk, with Stormveil on its cliff, a ruined aqueduct and a crowned tower."""

import itertools
import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    NpRng,
    Point,
    by_regime,
    design,
    polar,
    smoothstep,
)
from walldye.field import gauss, noise_grid
from walldye.geom import bezier_points
from walldye.pixel import dither, grid_runs

type Field = NDArray[np.float64]
type Grid = NDArray[np.int64]

CELL = 4
COLS, ROWS = 1920 // CELL, 1080 // CELL  # the scene is laid out in cells
# Index 0 is the background and stays undrawn; the neutral steps come next, then the accent
# ramp from faintest to full, so `g >= A7` means "lit by the tree" and `A7 + k` steps up it.
# The ground is a step below the sky and its grain a step above; on paper BG_DEEP turns paler
# than the sky, so there the ground takes BG_ALT and its grain BG.
PAL = (
    None,
    BG_DEEP,
    BG_ALT,
    UI,
    UI_ALT,
    by_regime(BG_DEEP, BG_ALT),
    by_regime(BG_ALT, BG),
    ACCENT_7,
    ACCENT_6,
    ACCENT_5,
    ACCENT_3,
    ACCENT_1,
    ACCENT,
)
DEEP, ALT, STONE, CASTLE, GROUND, GRAIN, A7, A6, A5, A3, A1, A0 = range(1, 13)

TX = 334  # trunk centre (cells)
FORK = 80  # row where the trunk parts into limbs
HZ = 198  # Limgrave horizon
CX, CY, RX, RY = 352, -40, 214, 128  # crown dome, centre above the frame
# Main boughs, as in the loading screen: two long limbs west, the rest splaying up and east.
MAINS = (
    (150, 86),
    (178, 58),
    (236, 24),
    (292, 0),
    (372, -4),
    (430, 20),
    (476, 56),
    (482, 90),
    (206, 92),
)
STRANDS = 180  # boughs plus the fine web
# God rays: x where they leave the canopy, lean, width.
RAYS = ((236, -0.22, 3), (282, -0.08, 2.5), (388, 0.12, 3), (430, 0.22, 2.5))
# Stormveil (cells): rim spikes (x, half-width, height), wall blocks (x0, x1, height) and towers
# (x, width, top row, crown: d drum, c small crown, s needle spire, p pointed roof).
SPIKES = ((124, 3, 10), (130, 4, 16), (136, 3, 9), (141, 2, 6), (117, 2, 5))
WALLS = ((44, 55, 8), (55, 66, 13), (66, 98, 17), (98, 108, 12), (108, 116, 7))
TOWERS = (
    (47, 4, 110, "c"),
    (53, 8, 98, "d"),
    (62, 4, 104, "p"),
    (67, 9, 86, "d"),
    (78, 3, 76, "s"),
    (83, 8, 92, "d"),
    (93, 4, 100, "c"),
    (99, 7, 106, "d"),
    (109, 3, 112, "p"),
)
CASTLE_BASE = 126


def bn(s: Canvas, field: ArrayLike, key: int, levels: int = 2) -> Grid:
    """Void-and-cluster dither of a (ROWS, COLS) tone field into indices 0 .. levels - 1."""
    return dither(field, levels, method="bluenoise", rng=s.np_rng(key))


def plot(g: Grid, a: Point, b: Point, val: int, w: int = 1) -> None:
    """Raise the cells along segment a-b, `w` cells wide, to at least `val`."""
    n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) * 2 + 1
    t = np.linspace(0, 1, n)
    i = np.round(a[0] + (b[0] - a[0]) * t).astype(int)
    j = np.round(a[1] + (b[1] - a[1]) * t).astype(int)
    for dx in range(w):
        ii = i + dx - w // 2
        ok = (ii >= 0) & (ii < COLS) & (j >= 0) & (j < ROWS)
        np.maximum.at(g, (j[ok], ii[ok]), val)


def crown_d(xs: Field, ys: Field) -> Field:
    """Elliptic distance from the crown's centre, 1 on the dome's rim."""
    return np.hypot((xs - CX) / RX, (ys - CY) / RY)


def branches(g: Grid, rng: NpRng) -> None:
    """Filament web: strands rise from the fork and sweep out to every part of the dome,
    fraying into drooping tips."""

    def twig(p: Point, ang: float, length: float, lvl: int) -> None:
        if lvl > 3 or length < 2 or math.hypot((p[0] - CX) / RX, (p[1] - CY) / RY) > 1.05:
            return
        q = polar(p, length, rad=ang)
        plot(g, p, q, A7 if lvl else A6)
        for _ in range(2):
            na = ang + rng.uniform(-0.6, 0.6)
            # droop: pull the angle part of the way toward straight down
            na += 0.3 * ((np.pi / 2 - na + np.pi) % (2 * np.pi) - np.pi) * rng.uniform(0.3, 1)
            twig(q, na, length * 0.7, lvl + 1)

    for k in range(STRANDS):
        main = k < len(MAINS)  # a few bright boughs read through the fine web
        if main:
            tx, ty = MAINS[k]
        else:
            # a target on the dome, biased toward its rim so the crown reads wide and full
            th = rng.uniform(np.pi * 0.04, np.pi * 0.96)
            r = rng.uniform(0.55, 0.98)
            tx, ty = CX + RX * r * math.cos(th), max(CY + RY * r * math.sin(th), -6.0)
        sx = TX + rng.uniform(-14, 14)
        # arc up from the fork, then droop to the rim
        ctrl = (
            (sx, FORK + 4),
            (sx + 0.55 * (tx - sx), min(ty, FORK) - rng.uniform(30, 60)),
            (tx, ty),
        )
        pts = bezier_points(ctrl, 27) + rng.normal(0, 0.7, (28, 2))
        for i, (a, b) in enumerate(itertools.pairwise(pts)):
            t = i / len(pts)
            if main:
                plot(g, (a[0], a[1]), (b[0], b[1]), A3 if t < 0.5 else A5, 2 if t < 0.35 else 1)
            else:
                plot(g, (a[0], a[1]), (b[0], b[1]), A5 if t < 0.2 else (A6 if t < 0.7 else A7))
        end = pts[-1] - pts[-3]
        twig((tx, ty), math.atan2(end[1], end[0]), rng.uniform(5, 9), 0)


def trunk_field(s: Canvas, xs: Field, ys: Field) -> Field:
    """Brightness of the trunk: a tall column of twisted root-strands, near vertical, lost in
    the mist at its foot."""
    t = np.clip((ys - FORK) / (HZ - FORK), 0, 1)
    # slight root flare, small fork flare
    half = 18 + 3 * t + 10 * np.clip((FORK + 14 - ys) / 16, 0, 1) ** 2
    u = (xs - TX - 1.5 * np.sin(ys / 30)) / half
    inside = (np.abs(u) < 1) & (ys >= FORK + 6 * np.clip(1 - 2.5 * np.abs(u), 0, 1))
    wob = noise_grid(COLS, ROWS, 10, s.np_rng(41), octaves=2)
    streak = np.zeros_like(xs)
    for k, c0 in enumerate(np.linspace(-0.85, 0.85, 9)):
        # strands twist round the column
        c = c0 + 0.16 * np.sin(ys * 0.06 + k * 1.3) + 0.08 * wob
        streak = np.maximum(streak, np.clip(1 - np.abs(u - c) * 10, 0, 1))
    core = 1 - np.abs(u) ** 2
    v = 0.18 + 0.3 * core + 0.4 * streak * (0.4 + 0.6 * core)
    fade = 1 - 0.75 * smoothstep(150, HZ, ys)
    return np.where(inside, v * fade, 0)


def mesa(s: Canvas, g: Grid, xs: Field, ys: Field) -> None:
    """Rock outcrop east of the tree: sloping west shoulder, flat top, lost in mist below."""
    n = noise_grid(COLS, ROWS, 6, s.np_rng(33))
    top = 116 + 0.12 * (446 - xs) + 4 * np.clip(404 - xs, 0, None)
    top += 3 * np.clip(xs - 448, 0, None) + 1.2 * n
    keep = bn(s, 0.1 + 0.9 * smoothstep(172, 122, ys), 37) == 1
    g[(ys >= top) & keep & (g < A5)] = ALT


def aqueduct(s: Canvas, g: Grid) -> None:
    """Ruined aqueduct: one continuous arcade at a steady height with broken gaps and uneven
    piers."""
    deck, x0, x1, pitch = 168, 150, 312, 10
    gaps = ((186, 204), (240, 252))  # collapsed spans: deck gone, piers left at odd heights
    rng = s.np_rng(21)
    stub: dict[int, int] = {}
    for i in range(x0, x1):
        k = (i - x0) // pitch
        local = ((i - x0) % pitch) / pitch
        top = deck + (1 if k % 3 == 1 else 0) + (-1 if k % 4 == 3 else 0)
        if any(a <= i < b for a, b in gaps):
            if local < 0.3:
                h = int(rng.integers(2, 12))  # drawn every column, kept per pier
                h = stub.setdefault(k, h)
                g[top + h : HZ + 2, i] = STONE
                g[top + h - 1, i] = STONE if i % 2 else 0
            continue
        g[top : top + 3, i] = STONE  # deck and parapet
        if i % 2 == 0:
            g[top - 1, i] = STONE
        if local < 0.3:
            g[top : HZ + 2, i] = STONE  # pier
        else:
            c = abs((local - 0.65) / 0.35)
            g[top : top + 3 + round(7 * (1 - math.sqrt(max(0.0, 1 - c)))), i] = STONE  # arch
    # The deck breaks off in a ragged step at each gap.
    for a, b in gaps:
        g[deck - 1 : deck + 1, a] = STONE
        for k in range(3):
            g[deck - 1 : deck + 2 - k, b - 1 - k] = 0
    # Two slender ruined towers rise from the arcade.
    for x, t in ((206, 150), (270, 146)):
        g[t : HZ + 2, x : x + 4] = STONE
        g[t - 1, x : x + 4 : 2] = STONE
        g[t - 3 : t - 1, x + 1] = STONE


def tower(g: Grid) -> None:
    """The tall crowned tower before the trunk, a little west of its centre."""
    x0, w, top = TX - 18, 11, 130
    g[top : HZ + 2, x0 : x0 + w] = STONE
    # stepped crown: a corbelled gallery, a narrower upper stage, crenellations
    g[top - 3 : top, x0 - 2 : x0 + w + 2] = STONE
    g[top - 4, x0 - 2 : x0 + w + 2 : 2] = STONE
    g[top - 11 : top - 3, x0 + 2 : x0 + w - 2] = STONE
    g[top - 13 : top - 11, x0 + 1 : x0 + w - 1] = STONE
    g[top - 14, x0 + 1 : x0 + w - 1 : 2] = STONE
    g[top - 9 : top - 5, x0 + 5] = ALT
    for j in range(top + 8, HZ - 20, 14):
        g[j : j + 3, x0 + 5] = ALT


def stormveil(s: Canvas, g: Grid, xs: Field, ys: Field) -> None:
    """Stormveil: crowned spires crowded on a sheer, jagged cliff that overhangs east, its
    underside eaten by mist."""
    ny = noise_grid(COLS, ROWS, 10, s.np_rng(29), octaves=3)
    # cliff outline: top edge near row 124, west face tapering in, east brow overhanging
    top = 124 + 2 * noise_grid(COLS, 1, 4, s.np_rng(3), octaves=2)
    west = 40 + 0.15 * (ys - 124) + 6 * ny
    east = 146 - 0.6 * np.clip(ys - 136, 0, None) + 6 * ny + 5 * smoothstep(134, 124, ys)
    under = HZ + 2 - 16 * smoothstep(90, 140, xs) + 6 * noise_grid(COLS, ROWS, 7, s.np_rng(17))
    rock = (ys >= top) & (xs >= west) & (xs <= east) & (ys < under)
    for x, w, h in SPIKES:  # rock spikes along the east rim, up to the castle's height
        rock |= (np.abs(xs - x) <= w * (1 - (124 - ys) / h)) & (ys >= 124 - h) & (ys < 126)
    # a detached rock pillar to the west, as seen from the First Step
    pil = 24 + 2 * ny
    rock |= (
        (ys >= 140 + 2 * np.abs(np.sin(xs * 1.3)))
        & (np.abs(xs - pil) < 5 - (ys - 140) * 0.02)
        & (ys < 196)
    )
    # Face texture: long vertical fractures and lit ledges from noise squashed sideways.
    strata = noise_grid(COLS * 3, ROWS, 9, s.np_rng(7), octaves=3)[:, ::3]
    face = np.where(strata > 0.05, STONE, np.where(strata < -0.4, DEEP, ALT))
    face = np.where((ys - top) < 2, STONE, face)
    keep = bn(s, smoothstep(under, under - 22, ys), 23) == 1
    g[:] = np.where(rock & keep, face, g)

    # The castle: an uneven cluster of drum towers with flared, spiked crowns.
    base = CASTLE_BASE
    for xa, xb, h in WALLS:
        g[base - h : base, xa:xb] = CASTLE
        g[base - h - 1, xa:xb:2] = CASTLE
    for x, w, t, kind in TOWERS:
        g[t:base, x : x + w] = CASTLE
        if kind == "s":
            g[t - 9 : t, x + 1] = CASTLE
            g[t : t + 2, x - 1 : x + w + 1] = CASTLE
        elif kind == "p":
            for k in range(w // 2 + 2):
                g[t - k, x + k // 2 : x + w - k // 2] = CASTLE
        else:
            out = 2 if kind == "d" else 1
            g[t - 3 : t, x - out : x + w + out] = CASTLE  # corbelled rim wider than the shaft
            g[t - 1, x - out] = g[t - 1, x + w + out - 1] = 0
            for i in range(x - out, x + w + out, 2):  # ring of spiky pinnacles
                g[t - 5 if (i - x) % 4 == 0 else t - 4 : t - 3, i] = CASTLE
        g[t + 5 : base - 14 : 5, x + w // 2] = STONE  # slit windows


@design()
def draw(s: Canvas) -> None:
    ys, xs = np.indices((ROWS, COLS), dtype=float)
    g: Grid = np.zeros((ROWS, COLS), dtype=np.int64)

    # Sky haze thickening into the mist band.
    hn = noise_grid(COLS, ROWS, 40, s.np_rng(2), octaves=3)
    haze = 0.18 * smoothstep(120, HZ, ys) * (0.6 + 0.4 * hn)
    g[bn(s, haze, 3) == 1] = ALT

    # God rays slanting down out of the canopy, staying under its span.
    for x_top, lean, wdt in RAYS:
        ray = gauss(xs - x_top - lean * (ys - 70), wdt)
        ray *= smoothstep(50, 95, ys) * smoothstep(190, 120, ys)
        g[bn(s, 0.3 * ray, 7 + x_top) == 1] = A6

    # Canopy: a dense dome of filaments, brightest near the top and fraying at the rim.
    d = crown_d(xs, ys) + 0.1 * noise_grid(COLS, ROWS, 14, s.np_rng(31), octaves=3)
    glow = smoothstep(1.0, 0.6, d) * (0.45 + 0.55 * smoothstep(95, 0, ys))
    lvl = bn(s, 0.85 * glow, 17, levels=4)  # 1..3: A7, A6, A5
    g = np.where(lvl > 0, A7 + lvl - 1, g)
    web = np.zeros_like(g)
    branches(web, s.np_rng(9))
    g = np.maximum(g, web)

    # Trunk: the only place the full accent appears.
    td = bn(s, trunk_field(s, xs, ys), 5, levels=6)  # 1..5: A6, A5, A3, A1, ACCENT
    g = np.where(td > 0, A6 + td - 1, g)

    # Mist swallowing the tree's foot.
    mist = smoothstep(165, HZ, ys) * (0.4 + 0.25 * hn)
    g[(bn(s, mist, 13) == 1) & (g >= A7)] = ALT

    mesa(s, g, xs, ys)
    aqueduct(s, g)
    tower(g)
    stormveil(s, g, xs, ys)

    # Limgrave: an uneven horizon, then a gentle foreground rise.
    x = xs[0]
    hz = HZ + 7 * noise_grid(COLS, 1, 60, s.np_rng(9), octaves=3)[0] + 3 * np.sin(x / 29)
    hz -= 7 * smoothstep(380, 475, x) + 4 * smoothstep(40, 0, x)
    ridge = 240 - 22 * smoothstep(230, 20, x) - 10 * smoothstep(380, 475, x)
    ridge += 4 * noise_grid(COLS, 1, 20, s.np_rng(8))[0]
    gv = 0.12 + 0.2 * noise_grid(COLS, ROWS, 24, s.np_rng(5), octaves=3)
    gv = gv * smoothstep(HZ + 40, HZ, ys) + 0.08
    far = np.where(bn(s, gv, 11) == 1, GRAIN, GROUND)
    near = np.where(bn(s, 0.35 * smoothstep(ridge + 6, ridge, ys), 19) == 1, GRAIN, GROUND)
    g = np.where(ys >= ridge, near, np.where(ys >= hz, far, g))

    grid_runs(s, g, PAL, CELL)
