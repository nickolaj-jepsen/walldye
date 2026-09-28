"""A vector-arcade horizon: midpoint-displaced ranges, a wireframe volcano throwing embers and a crescent moon."""

import itertools
import math

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import LineString

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Rng,
    Vec,
    design,
    mix,
    polar,
)

VH, CRATER, BASE = 220, 30, 170  # volcano height, crater half-width, left base half-width
# Volcano outline as offsets from the foot of its axis on the horizon.
CONE = (
    (-BASE, 0),
    (-128, -50),
    (-112, -60),
    (-80, -118),
    (-58, -160),
    (-CRATER, -VH),
    (CRATER, -VH),
    (50, -176),
    (104, -84),
    (BASE + 16, 0),
)
# Ranges as (seed, x0, x1, rise), x measured from the left edge, the volcano axis or the right edge.
LEFT_FAR, LEFT_NEAR = (29, -60, 700, 120), (22, -40, 520, 150)
VOLCANO_FAR, VOLCANO_NEAR = (25, -800, 140, 90), (22, 120, 490, 110)
RIGHT_FAR = (0, -240, 220, 85)
GAP = 150  # bare horizon wider than this, between anchored ranges, gets filler ranges
FILLERS = ((9, 95), (36, 80), (12, 105), (41, 85), (30, 100), (59, 90))  # (seed, rise), in turn
PHASES = (0.08, 0.13, 0.2, 0.34, 0.5, 0.7, 0.92, 1.2)  # ember flight, as fractions of the climb
G = 0.3  # ember gravity


def ridge(r: Rng, x0: float, x1: float, hy: float, rise: float) -> NDArray[np.float64]:
    """Midpoint-displaced ridge from (x0, hy) to (x1, hy) peaking `rise` above it under a sine
    envelope, simplified to chunky vertices; draws 63 values from `r`."""
    ys = [0.0, 0.0]
    amp = 1.0
    for _ in range(6):
        nxt: list[float] = []
        for a, b in itertools.pairwise(ys):
            nxt += [a, (a + b) / 2 + r.uniform(-0.4, 1) * amp]
        ys = nxt + [ys[-1]]
        amp *= 0.6
    n = len(ys) - 1
    env = [math.sin(math.pi * i / n) ** 0.5 for i in range(n + 1)]
    top = max(max(0, y) * e for y, e in zip(ys, env, strict=True))
    pts = [
        (x0 + (x1 - x0) * i / n, hy - rise * max(0, y) * e / top)
        for i, (y, e) in enumerate(zip(ys, env, strict=True))
    ]
    return np.asarray(LineString(pts).simplify(7).coords)


def gaps(spans: list[tuple[float, float]], lo: float, hi: float) -> list[tuple[float, float]]:
    """The stretches of [lo, hi] wider than GAP that no span covers, left to right."""
    out: list[tuple[float, float]] = []
    x = lo
    for a, b in sorted(spans):
        if a - x > GAP:
            out.append((x, a))
        x = max(x, b)
    if hi - x > GAP:
        out.append((x, hi))
    return out


@design(aspects="any")
def draw(s: Canvas) -> None:
    hy = s.h * 2 / 3
    vx = s.pick(landscape=(17 / 24, 0), portrait=(0.6, 0)).x
    r = s.rng(1980)

    far_specs = [
        LEFT_FAR,
        (VOLCANO_FAR[0], vx + VOLCANO_FAR[1], vx + VOLCANO_FAR[2], VOLCANO_FAR[3]),
        (RIGHT_FAR[0], s.w + RIGHT_FAR[1], s.w + RIGHT_FAR[2], RIGHT_FAR[3]),
    ]
    near_specs = [
        LEFT_NEAR,
        (VOLCANO_NEAR[0], vx + VOLCANO_NEAR[1], vx + VOLCANO_NEAR[2], VOLCANO_NEAR[3]),
    ]

    far = P()
    for seed, x0, x1, rise in far_specs:
        far.poly(ridge(s.rng(seed), x0, x1, hy, rise))
    # On wide screens the anchored ranges drift apart; fill the bare horizon between them.
    fillers = itertools.cycle(FILLERS)
    for a, b in gaps([(x0, x1) for _, x0, x1, _ in far_specs + near_specs], 0, s.w):
        k = max(1, round((b - a) / 620))
        step = (b - a) / k
        for j in range(k):
            seed, rise = next(fillers)
            x0 = a + j * step - 140
            far.poly(ridge(s.rng(seed), x0, x0 + step + 280, hy, rise))
    s.path(far, fill=BG, stroke=mix(BG_ALT, UI, 0.4), stroke_width=1.6, stroke_linejoin="round")

    foot = Vec(vx, hy)
    cone = P().poly([foot + d for d in CONE])
    s.path(cone, fill=BG, stroke=UI_HI, stroke_width=2, stroke_linejoin="round")

    near = P()
    for seed, x0, x1, rise in near_specs:
        near.poly(ridge(s.rng(seed), x0, x1, hy, rise))
    s.path(near, fill=BG, stroke=UI_ALT, stroke_width=2, stroke_linejoin="round")

    s.stroke(P().M(0, hy).H(s.w), UI, 1.2)

    # Ground: rows of dashes whose depth, spacing and weight shrink toward the horizon, far to
    # near, as many as fit before two rows sit closer than 14 units.
    depth = s.h - hy - 60
    rows = 1
    while depth / (1 + (rows - 1) * 0.9) - depth / (1 + rows * 0.9) >= 14:
        rows += 1
    for j in reversed(range(rows)):
        z = 1 + j * 0.9
        y, step, ln = hy + depth / z, 90 / z, 2 + 6 / z
        dashes = P()
        x = ((5 - j) * 37) % step
        while x < s.w:
            dashes.M(x - ln / 2, y).H(x + ln / 2)
            x += step
        s.stroke(dashes, UI, 1.2 + 0.4 / z)

    # Embers frozen along parabolic arcs out of the crater, some still rising, some falling.
    crater = Vec(vx, hy - VH - 6)
    phases = list(PHASES)
    r.shuffle(phases)  # so the embers still close to the crater aren't all on one side of the fan
    with s.buckets((ACCENT, ACCENT_1), "stroke", stroke_width=3, stroke_linecap="round") as embers:
        for i, ph in enumerate(phases):
            a = -90 + (i - 3.5) * 5 + r.uniform(-1.5, 1.5)
            vel = polar((0, 0), r.uniform(9, 11), deg=a)
            t = -vel.y / G * ph
            p = crater + vel * t + (0, 0.5 * G * t * t)
            heading = (vel + (0, G * t)).unit()
            embers[1 if i % 3 == 1 else 0].M(p).L(p - heading * r.uniform(14, 22))

    # Crescent moon: outer arc and an offset inner arc sharing the horns.
    mc, mr = s.pick(landscape=(7 / 32, 13 / 54), portrait=(0.27, 0.3)), 50
    h1, h2 = polar(mc, mr, deg=-120), polar(mc, mr, deg=120)
    moon = P().M(h1).A(mr, mr, 0, 1, 0, h2).A(mr * 0.8, mr * 0.8, 0, 0, 1, h1).Z()
    s.stroke(moon, ACCENT_3, 1.6, join="round")
