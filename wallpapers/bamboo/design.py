"""A bamboo grove in flat shapes after sumi-e ink painting."""

import math
from typing import NamedTuple

import numpy as np
from shapely import LineString

from walldye import (
    ACCENT,
    ACCENT_2,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    P,
    Path,
    Rng,
    Vec,
    design,
    mix,
    polar,
)
from walldye.geom import ribbon


class Culm(NamedTuple):
    x: float  # centerline at the bottom edge
    width: float
    lean: float  # how far the top drifts sideways over a 1080-unit height
    depth: int  # 0 back .. 2 front


# (x, width, lean, depth) of each Culm
CULMS = (
    (95, 18, 30, 0),
    (300, 20, -24, 0),
    (575, 22, 40, 0),
    (710, 17, 18, 0),
    (205, 30, -36, 1),
    (430, 30, 34, 1),
    (650, 27, -20, 1),
    (55, 44, 26, 2),
    (590, 46, 14, 2),
)
TONES = ((BG_ALT, BG_DEEP), (UI, BG_ALT), (mix(UI, UI_ALT, 0.5), UI))  # (body, node) per depth
LIT = 5  # the lit culm
CROSS, CROSS_Y = 8, 250  # the front culm whose leaves reach over the lit one, and from which node


class Grove(NamedTuple):
    """Where the culms stand on this canvas: x positions scaled by `sx`, leans by `sl`."""

    h: float
    sx: float
    sl: float

    def center(self, c: Culm, y: float) -> float:
        """Culm centerline x at height `y`: a gentle bow leaning from bottom to top."""
        t = 1 - y / self.h
        lean = c.lean * self.sl
        return c.x * self.sx + lean * t + 0.35 * lean * math.sin(math.pi * t)


def culm(
    rnd: Rng, g: Grove, c: Culm, anchor: float | None
) -> tuple[np.ndarray, np.ndarray, list[float]]:
    """Outline and shaded right flank of culm `c`, swelling slightly at each node, and the node
    heights; one node is shifted onto `anchor` if given."""
    nodes, y = [], rnd.uniform(-120, 40)
    while y < g.h + 60:
        nodes.append(y)
        y += rnd.uniform(150, 230)
    if anchor is not None:
        shift = anchor - min(nodes, key=lambda n: abs(n - anchor))
        nodes = [n + shift for n in nodes]
    ys = np.linspace(-20, g.h + 20, round(280 * (g.h + 40) / 1120))
    bulge = sum(np.exp(-(((ys - n) / 7) ** 2)) for n in nodes)
    half = c.width / 2 * (1 + 0.1 * bulge)
    cx = np.array([g.center(c, y) for y in ys])
    outline = ribbon(np.column_stack([cx, ys]), 2 * half)
    # the right flank, from 55% of the way across to the edge
    shade = ribbon(np.column_stack([cx + 0.775 * half, ys]), 0.45 * half)
    # straight runs need few points: this halves the file and keeps the swellings
    return slim(outline), slim(shade), nodes


def slim(pts: np.ndarray) -> np.ndarray:
    """`pts` without the points that lie within 0.05 units of the line through the rest."""
    return np.asarray(LineString(pts).simplify(0.05).coords)


def blade(d: Path, root: Vec, deg: float, length: float, width: float, curl: float) -> None:
    """A bamboo leaf on a pinched stalk, widest about 30% out, tapering to a sharp tip and
    bowing sideways by `curl` of its length."""
    along = polar((0, 0), 1, deg=deg)
    t = np.linspace(0, 1, 28)
    grow = np.sin(np.pi / 2 * np.clip((t - 0.07) / 0.23, 0, 1)) ** 0.9
    taper = np.where(t > 0.3, ((1 - t) / 0.7) ** 0.85, 1)
    half = np.maximum(0.5, width / 2 * grow * taper)
    spine = root + np.outer(length * t, along) + np.outer(curl * length * t * t, along.perp())
    d.spline(ribbon(spine, 2 * half), closed=True)


def sprig(
    leaves: Path,
    twigs: Path,
    rnd: Rng,
    root: Vec,
    n: int,
    side: int = 1,
    hang: tuple[float, float] | None = None,
) -> None:
    """A short bowed twig out of a node with `n` leaves hung at staggered points along it.

    `side` is +1 for a twig to the right of the culm, -1 to the left; `hang` = (deg, length)
    forces the first leaf. Leaf angles are measured below the horizontal, away from the culm.
    """
    reach, rise = rnd.uniform(25, 45), rnd.uniform(30, 70)
    heading = -rise if side > 0 else 180 + rise

    def tip(u: float) -> Vec:
        return polar(root, reach * u, deg=heading) + (0, 6 * u * u)

    twigs.spline([tip(u) for u in np.linspace(0, 1, 6)])
    u, used = 1.0, []
    base = rnd.uniform(35, 65)
    for k in range(n):
        # take the candidate angle farthest from the sprig's other leaves so they never stack
        a = max(
            (base + rnd.uniform(-25, 25) for _ in range(12)),
            key=lambda a: min([abs(a - b) for b in used] + [math.degrees(1)]),
        )
        length = rnd.uniform(90, 180)
        if hang and k == 0:
            a, length = hang
        elif rnd.random() < 0.22:
            a = rnd.uniform(78, 88)  # a steep, nearly vertical hanger
        used.append(a)
        width = rnd.uniform(13, 18)
        curl = side * rnd.uniform(0.02, 0.07)
        blade(leaves, tip(u), a if side > 0 else 180 - a, length, width, curl)
        u -= rnd.uniform(8, 20) / reach


@design(aspects="any")
def draw(s: Canvas) -> None:
    # portrait: the grove narrows to keep the right side open and leans a little more
    g = Grove(s.h, 1, 1) if s.landscape else Grove(s.h, 0.74, math.sqrt(s.h / 1080))
    rnd = s.rng(23)
    grove = [Culm(*row) for row in CULMS]
    for i in sorted(range(len(grove)), key=lambda i: (grove[i].depth, i == LIT)):
        c = grove[i]
        body, node = (ACCENT, ACCENT_2) if i == LIT else TONES[c.depth]
        outline, shade, nodes = culm(rnd, g, c, CROSS_Y if i == CROSS else None)
        s.fill(P().poly(outline, closed=True), body)
        s.fill(P().poly(shade, closed=True), mix(body, node, 0.35))
        rings = P()
        for y in nodes:
            cx, hw = g.center(c, y), c.width / 2 * 1.12
            rings.M(cx - hw, y - 1).Q(cx, y + 4, cx + hw, y - 1)  # a slightly smiling ring
        s.stroke(rings, node, 2 + c.depth * 0.4, cap="round")
        if i == LIT:
            continue
        leaves, twigs = P(), P()
        spots = [n for n in nodes if 120 < n < s.h - 220]
        count = round((1 + (c.depth == 2)) * s.h / 1080)  # more sprigs up a taller screen
        for y in rnd.sample(spots, min(len(spots), count)):
            n = rnd.choices([1, 2, 3], [1, 2, 3])[0]
            sprig(leaves, twigs, rnd, Vec(g.center(c, y) + c.width / 2, y), n)
        if i == CROSS:
            # one fan reaching left across the lit culm ties it into the grove
            root = Vec(g.center(c, CROSS_Y) - c.width / 2, CROSS_Y)
            sprig(leaves, twigs, rnd, root, 2, side=-1, hang=(18, 175))
        s.stroke(twigs, body, 1.6, cap="round")
        s.fill(leaves, body)
