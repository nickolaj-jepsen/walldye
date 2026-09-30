"""Glass cracked by one impact: random-walk cracks, rings and cut shards."""

import itertools
import math
from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.prepared import prep

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_4,
    BG_ALT,
    UI,
    Canvas,
    NpRng,
    P,
    Path,
    Rect,
    Vec,
    clamp,
    design,
    ladder,
    polar,
)
from walldye.geom import parts

type Line = list[Vec]

N_RADIAL = 14
TONES = ladder((UI, BG_ALT), 4)  # crack tone, stepping down with distance from the impact
SHARDS = (ACCENT, ACCENT_1, ACCENT_4)  # bright, deep, and the dim snapped-off tips


def walk(
    rng: NpRng,
    p: Vec,
    a: float,
    sigma: float,
    bounds: Rect,
    step: float = 12,
    stop: Callable[[Vec, Vec], bool] | None = None,
    max_len: float = 4000,
) -> Line:
    """A crack from `p` heading `a` radians, turning by N(0, sigma) each `step`, until it leaves
    `bounds`, `stop(last, new)` holds, or it has run `max_len`; the last point is included."""
    pts = [p]
    for _ in range(int(max_len / step)):
        a += rng.normal(0, sigma)
        p = polar(p, step, rad=a)
        pts.append(p)
        if not bounds.contains(p) or (stop and stop(pts[-2], p)):
            break
    return pts


def at_radius(line: Line, c: Vec, r: float) -> Vec | None:
    """First point along `line` at distance `r` from `c`, or None."""
    for p0, p1 in itertools.pairwise(line):
        d0, d1 = abs(p0 - c), abs(p1 - c)
        if d0 <= r < d1:
            return p0 + (p1 - p0) * ((r - d0) / (d1 - d0))
    return None


def jagged(rng: NpRng, a: Vec, b: Vec, bow: float, n: int = 8) -> Line:
    """Slightly bowed, slightly wobbly crack from `a` to `b`; `bow` is a fraction of its length."""
    normal = (b - a).perp()
    return [
        a
        + (b - a) * t
        + normal * (bow * 4 * t * (1 - t) + (rng.normal(0, 0.005) if 0 < t < 1 else 0))
        for t in np.linspace(0, 1, n)
    ]


def tone(d: float) -> int:
    """TONES index for a crack `d` from the impact: UI out to 350, BG_ALT from 1050."""
    return round(clamp((d - 350) / 700) * 3)


def taper(s: Canvas, c: Vec, lines: list[Line], width: Callable[[float], float]) -> None:
    """Stroke polylines with width and tone falling off with distance from the impact `c`."""
    paths: dict[tuple[int, int], Path] = {}  # (width in fifths of a unit, tone index)
    for line in lines:
        prev = None
        for a, b in itertools.pairwise(line):
            d = abs((a + b) / 2 - c)
            k = round(width(d) * 5), tone(d)
            if k != prev:
                paths.setdefault(k, P()).M(a)
            paths[k].L(b)
            prev = k
    # thinnest first; within a width the faintest first, so brighter cracks cross on top
    for (w, t), d in sorted(paths.items(), key=lambda kv: (kv[0][0], -kv[0][1])):
        s.stroke(d, TONES[t], w / 5, cap="round", join="round")


@design(aspects="any")
def draw(s: Canvas) -> None:
    # upper right on a landscape screen, upper third on a portrait one
    c = s.pick(landscape=(1400 / 1920, 380 / 1080), portrait=(0.62, 0.3))
    bounds = s.inset(-20)
    rng = s.np_rng(11)

    base = rng.uniform(0, 2 * math.pi)
    angles = [base + (k + rng.uniform(-0.3, 0.3)) * 2 * math.pi / N_RADIAL for k in range(N_RADIAL)]
    # one fewer ray into the top edge, where the bar and window titles sit
    angles = [a for a in angles if not 245 < math.degrees(a) % 360 < 262]
    n = len(angles)
    reach = 58 * rng.uniform(0.6, 1.4, n)
    splinters = set(rng.choice(n, 3, replace=False).tolist())
    reach[list(splinters)] *= 1.6
    radials = [
        walk(rng, polar(c, r, rad=a), a, math.radians(1.2), bounds) for a, r in zip(angles, reach)
    ]

    rings: list[Line] = []
    r = 110
    while r < 900:
        for i in range(n):
            a = at_radius(radials[i], c, r * rng.uniform(0.94, 1.06))
            b = at_radius(radials[(i + 1) % n], c, r * rng.uniform(0.94, 1.06))
            if a is None or b is None or rng.random() > 0.75 - r / 1100:
                continue
            if r > 600 and abs(b - a) > 350:
                continue
            # concentric glass cracks sag slightly toward the impact
            sag = rng.uniform(0.005, 0.015)
            rings.append(jagged(rng, a, b, sag if (b - a).perp().dot(c - a) > 0 else -sag))
        r *= rng.uniform(1.35, 1.55)

    net = prep(MultiLineString(radials + rings))
    branches: list[Line] = []
    while len(branches) < 8:
        line = radials[rng.integers(n)]
        j = int(rng.integers(len(line) // 10, len(line) // 2))
        p0, p1 = line[j], line[j + 1]
        a = math.atan2(p1.y - p0.y, p1.x - p0.x) + rng.choice([-1, 1]) * rng.uniform(0.4, 0.8)
        pts = walk(
            rng,
            polar(p0, 4, rad=a),
            a,
            math.radians(3),
            bounds,
            8,
            lambda p, q: net.intersects(LineString([p, q])),
            500,
        )
        if len(pts) > 8:
            branches.append([p0, *pts])

    taper(s, c, radials, lambda d: max(0.8, 1.6 - d / 1000))
    rings = [q for q in rings if q[0].y + q[-1].y > 300]  # keep the strip under the top bar clear
    taper(s, c, rings + branches, lambda d: max(0.6, 1.3 - d / 700))

    shards(s, rng, c, angles, reach, splinters)


def shards(
    s: Canvas,
    rng: NpRng,
    c: Vec,
    angles: list[float],
    reach: NDArray[np.float64],
    splinters: set[int],
) -> None:
    """Burst of glass at `c`: a crushed core, a ring of fragments, wedges out to an irregular rim."""
    tau = 2 * math.pi
    rays = sorted(
        [(a % tau, r, i in splinters) for i, (a, r) in enumerate(zip(angles, reach))]
        + [(rng.uniform(0, tau), 58 * rng.uniform(0.6, 1.4), False) for _ in range(8)]
    )
    eff = [r / 1.6 if sp else r for _, r, sp in rays]  # body radius, splinters excluded
    nxt = [*range(1, len(rays)), 0]

    def pt(r: float, a: float) -> Vec:
        return polar(c, r, rad=a)

    def gap(line: BaseGeometry) -> BaseGeometry:  # every crack gets its own width
        return line.buffer(rng.uniform(0.8, 1.6) / 2, cap_style="flat")

    def cut(p: Vec, q: Vec) -> BaseGeometry:
        return gap(LineString([p, q]))

    rim: list[Vec] = []
    cuts: list[BaseGeometry] = []
    for i, j in enumerate(nxt):
        (a0, r0, sp), a1 = rays[i], rays[j][0] + (tau if j == 0 else 0)
        if sp:  # a long thin splinter running out along the crack, snapped off at its base
            b = eff[i]
            rim += [pt(b * 0.95, a0 - 0.07), pt(r0, a0), pt(b * 0.95, a0 + 0.07)]
            cuts += [
                cut(pt(12, a0), pt(b * 0.9, a0)),
                cut(pt(b * 0.9, a0 - 0.09), pt(b * 0.9, a0 + 0.09)),
            ]
        else:
            rim.append(pt(r0, a0))
            cuts.append(cut(pt(12, a0), pt(r0 + 8, a0)))
        lo = min(eff[i], eff[j])
        rim.append(pt(lo * rng.uniform(0.55, 1.05), (a0 + a1) / 2))
        sector = Polygon([pt(0, a0), pt(300, a0), pt(300, a1)])
        # zero to two cross cracks through this wedge
        for rc in rng.uniform(24, max(26, 0.8 * lo), rng.choice([0, 1, 1, 2])):
            chord = LineString(
                [pt(rc * rng.uniform(0.9, 1.1), a0 - 0.3), pt(rc * rng.uniform(0.9, 1.1), a1 + 0.3)]
            )
            cuts.append(gap(chord.intersection(sector)))
    burst = Polygon(rim).buffer(0)

    ca = np.sort(rng.uniform(0, tau, 13))
    core = Polygon([pt(8 * rng.uniform(0.7, 1.3), a) for a in ca])
    ring = Polygon([pt(15 * rng.uniform(0.7, 1.3), a) for a in ca])
    cuts += [core, gap(ring.exterior)]
    m = rng.integers(6, 11)
    cuts += [
        cut(pt(0, a), pt(25, a)).intersection(ring)
        for a in (np.arange(m) + rng.uniform(-0.3, 0.3, m)) * tau / m
    ]
    pieces = burst.difference(unary_union(cuts))

    center = Point(c)
    cells = sorted((g for g in parts(pieces) if g.area > 3), key=lambda g: -g.distance(center))
    dim = 0
    with s.buckets(SHARDS, "fill") as fill:
        for g in cells:
            if g.within(ring):
                if rng.random() < 0.2:  # crushed: some fragments are gone
                    continue
                k = rng.choice(2, p=[0.8, 0.2])
            elif rng.random() < 0.06:
                continue
            elif (
                g.distance(center) > 22
                and g.area < 200
                and dim < 0.2 * len(cells)
                and rng.random() < 0.5
            ):
                k, dim = 2, dim + 1  # only snapped-off outer tips go dim
            else:
                k = rng.choice(2, p=[0.55, 0.45] if g.distance(center) < 22 else [0.25, 0.75])
            fill[k].shape(g)
