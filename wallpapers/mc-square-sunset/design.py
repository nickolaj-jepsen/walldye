"""A square sun setting behind stepped voxel hills under a flat cloud layer, in a coarse ordered-dither sky."""

from typing import Literal

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    ACCENT_8,
    ACCENT_HI,
    BG,
    BG_ALT,
    BG_DEEP,
    BLACK,
    MUTED,
    UI,
    UI_ALT,
    Canvas,
    Colour,
    P,
    Params,
    Rect,
    by_regime,
    design,
    knob,
    ladder,
    mix,
    smoothstep,
)
from walldye.field import cells
from walldye.pixel import dither, grid_runs, sprite


class Hour(Params):
    moment: Literal["sunset", "moonrise"] = knob(
        default="sunset", doc="the sun setting, or the moon risen over the same hills at night"
    )


VARIANTS = {"moonrise": Hour(moment="moonrise")}

CELL, BLOCK, TEXEL = 8, 24, 12  # sky dither cell, terrain block, sun texel
SUN = 8 * TEXEL  # sun.png's opaque 8x8 core
SINK = 0.55  # share of the core still above the horizon
LAND = 1080 - (736 + SINK * SUN)  # horizon to the bottom edge at 16:9
# Terrain layers from the back: noise key, base depth below the horizon at 16:9, amplitude,
# noise step per column.
RIDGES = ((11, 99.2, 150, 0.09), (4, 171.2, 120, 0.11), (21, 243.2, 72, 0.14), (8, LAND, 60, 0.2))
TREE_COL = -7  # oak column, in blocks from the sun's left edge
CLOUD_T, CLOUD_U = 32, 8  # slab thickness and its lit underside
CLOUD_UP = 381  # slab top above the horizon
# Slab x-extents from the sun's left edge, repeating every CLOUD_PERIOD.
CLOUDS = ((-1200, -840), (-600, -240), (-72, 96), (264, 528))
CLOUD_PERIOD = 1920
EDGE = 96  # a slab ending closer than this to a side runs off it instead
STARS = 260 / (1920 * (1080 - LAND - 120))  # star attempts per unit of starry sky
OAK = """
.###.
.###.
#####
#####
..#..
..#..
..#..
"""
# moon_phases.png's full moon: an 8x8 face with darker maria.
MOON = """
aaaaaaaa
aabbaaaa
abbbaaba
aabaaaaa
aaaaabba
aaaaabba
aabaaaaa
aaaaaaaa
"""
MOON_UP = 2.75 * SUN  # the moon's top above the horizon
# Terrain from far to near. The dark regime lifts the far ridge into the haze and sinks the
# near ones into shadow; on paper every layer is a step darker than the one behind it.
TERRAIN = (
    by_regime(mix(BG_ALT, UI, 0.3), BG_ALT),
    by_regime(mix(BG_ALT, BG_DEEP, 0.6), UI),
    by_regime(BG_DEEP, mix(UI, UI_ALT, 0.5)),
    by_regime(BLACK, UI_ALT),
)
CORE = by_regime(ACCENT_HI, ACCENT_2)  # the sun's pale centre and the moon's face
WARM = 5  # cloud tint steps by distance from the sun
TOPS = ladder((BG_ALT, mix(BG_ALT, ACCENT_7, 0.5)), WARM)
UNDERS = ladder((UI, mix(UI, ACCENT_6, 0.6)), WARM)


def ridge(s: Canvas, key: int, base: int, amp: float, step: float, c0: int) -> list[int]:
    """Stepped skyline tops, one per block column across the canvas: an fBm height quantised
    down to whole blocks above `base`. Column c samples the noise at c + c0."""
    cols = s.w // BLOCK
    h = (s.noise(key).fbm((np.arange(cols) + c0) * step, 0.37, octaves=3) + 0.5) * amp
    return [base - int(max(0.0, v) // BLOCK) * BLOCK for v in h.tolist()]


def skyline(s: Canvas, tops: list[int], fill: Colour) -> None:
    pts: list[tuple[float, float]] = [(0, s.h)]
    for c, y in enumerate(tops):
        pts += [(c * BLOCK, y), ((c + 1) * BLOCK, y)]
    pts.append((s.w, s.h))
    s.fill(P().poly(pts, closed=True), fill)


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Hour]) -> None:
    night = s.params.moment == "moonrise"
    # right of centre and low on a landscape screen; lower right on a portrait one
    p = s.pick(landscape=(0.675, 0.6815), portrait=(0.58, 0.68), snap=CELL)
    sx, sy = round(p.x / BLOCK) * BLOCK, p.y
    cx, cy = sx + SUN / 2, sy + SUN / 2
    hz = sy + SINK * SUN
    if night:
        # the moon has risen opposite, low over the left of the same hills, in a clear sky
        mx = round(s.frac(0.3, 0).x / TEXEL) * TEXEL - SUN // 2
        my = round((hz - MOON_UP) / TEXEL) * TEXEL
        cx, cy = mx + SUN / 2, my + SUN / 2
        sprite(s, MOON, {"a": CORE, "b": ACCENT}, TEXEL, (mx, my))
    else:
        # Sunset fog strongest toward the sun, fading to the sides and up the sky, plus
        # sun.png's soft square glow several times the core's size.
        xs, ys = cells(Rect(0, 0, s.w, int(hz + 80) // CELL * CELL), CELL)
        band = (1 - smoothstep(0, 820, np.abs(xs - cx))) ** 1.6 * (
            1 - smoothstep(0, 400, hz - ys)
        ) ** 1.4
        cheb = np.maximum(np.abs(xs - cx), np.abs(ys - cy))
        halo = (1 - smoothstep(0.5 * SUN, 3.6 * SUN, cheb)) ** 1.5
        glow = np.minimum(1.0, band * 0.62 + halo * 0.5)
        grid = dither(glow, 5, method="bayer", matrix=4)
        grid_runs(s, grid, [None, ACCENT_8, ACCENT_7, ACCENT_6, ACCENT_5], CELL)
        # sun.png core: a 1-texel rim around a 6x6 pale centre.
        s.fill(P().rect(sx, sy, SUN, SUN), ACCENT)
        s.fill(P().rect(sx + TEXEL, sy + TEXEL, SUN - 2 * TEXEL, SUN - 2 * TEXEL), CORE)

    # Stars: sparse and random, thinning toward the horizon, gone where the sunset fog lights
    # the sky or around the moon.
    rng = s.rng(3)
    stars = P()
    for _ in range(round(STARS * s.w * (hz - 120))):
        x, y = rng.uniform(0, s.w), rng.uniform(0, hz - 120)
        if night:
            fade = smoothstep(hz - 360, hz - 160, y) + (
                1 - smoothstep(1.5 * SUN, 3 * SUN, max(abs(x - cx), abs(y - cy)))
            )
        else:
            fade = smoothstep(hz - 460, hz - 160, y) + (
                1 - smoothstep(300, 900, abs(x - cx))
            ) * smoothstep(hz - 709, hz - 289, y)
        if rng.random() < 0.35 * (1 - min(1, fade)):
            z = rng.choice((3, 3, 4))
            stars.rect(round(x), round(y), z, z)
    s.fill(stars, mix(BG, MUTED, 0.4))

    # Cloud layer edge-on: flat slabs of one thickness with a lit underside, tinted by
    # their distance from the sun.
    cloud_y = round(hz) - CLOUD_UP
    with s.buckets(TOPS, "fill") as tops, s.buckets(UNDERS, "fill") as unders:
        k0 = -((sx + CLOUDS[-1][1]) // CLOUD_PERIOD) - 1
        for k in range(k0, k0 + s.w // CLOUD_PERIOD + 3):
            for a, b in CLOUDS:
                x0 = max(0, sx + a + k * CLOUD_PERIOD)
                x1 = min(s.w, sx + b + k * CLOUD_PERIOD)
                if x1 - x0 < EDGE:
                    continue
                x0 = 0 if x0 < EDGE else x0
                x1 = s.w if s.w - x1 < EDGE else x1
                warm = 0 if night else 1 - smoothstep(150, 700, abs((x0 + x1) / 2 - cx))
                i = round(warm * (WARM - 1))
                tops[i].rect(x0, cloud_y, x1 - x0, CLOUD_T - CLOUD_U)
                unders[i].rect(x0, cloud_y + CLOUD_T - CLOUD_U, x1 - x0, CLOUD_U)

    c0 = 54 - sx // BLOCK  # the hills around the sun are the same on every screen
    # A portrait screen has more ground below the horizon: the two near layers take it, with
    # taller hills, and the far ones keep their 16:9 depths.
    extra = s.h - hz - LAND
    grow = (0, 0, 0.5, 1)  # share of the extra ground each layer's base moves down by
    lift = (1, 1, 1 + extra / LAND, 1 + extra / LAND)  # amplitude factor
    base = [
        s.h - round((s.h - hz - d - g * extra) / BLOCK) * BLOCK
        for (_, d, _, _), g in zip(RIDGES, grow, strict=True)
    ]
    far, mid, near, nearest = (
        ridge(s, key, b, amp * f, step, c0)
        for (key, _, amp, step), b, f in zip(RIDGES, base, lift, strict=True)
    )
    # Level the far ridge under the sun so it sinks behind one clean block edge.
    for c in range((sx - 2 * BLOCK) // BLOCK, (sx + SUN + 2 * BLOCK) // BLOCK + 1):
        far[c] = round(hz)
    skyline(s, far, TERRAIN[0])

    # A 5-block plateau for the oak, with the hill stepping down one block per column off it.
    tc = sx // BLOCK + TREE_COL
    top = base[1] - round((base[1] - hz - 27.2) / BLOCK) * BLOCK
    for c in range(len(mid)):
        mid[c] = min(mid[c], top + max(0, abs(c - tc) - 2) * BLOCK)
    skyline(s, mid, TERRAIN[1])
    # Oak side-on: three logs, two 5-wide leaf layers, two 3-wide ones.
    sprite(s, OAK, {"#": TERRAIN[1]}, BLOCK, ((tc - 2) * BLOCK, top - 7 * BLOCK))

    skyline(s, near, TERRAIN[2])
    skyline(s, nearest, TERRAIN[3])
