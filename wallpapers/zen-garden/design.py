"""A dry garden from above: straight rake lines stopping at rings around three stones."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from shapely.affinity import scale, translate
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_HI,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    NpRng,
    P,
    Vec,
    by_regime,
    design,
)
from walldye.geom import Polyline, parts

GAP = 16  # rake pitch, for the rings and the straight lines alike
# How far the first passing line rises over a ring group, which is also how deep the first
# stopping line cuts into it: shallower cuts leave slivers, higher lifts squeeze the lines above.
LIFT = 12
SQUEEZE = 0.85  # line pitch over a ring group, as a share of GAP, until the lift runs out
EASE = 10  # smoothing where a bowed line rejoins the straight
STEP = 2  # sampling along a bowed line
FAR = 1e6
# (group, offset from the group's anchor, radius, rings, fill, shade): rings follow stone size.
# The shade stays a step darker than the fill in both regimes.
STONES = (
    (0, Vec(0, 0), 75, 6, UI, by_regime(BG_ALT, UI_ALT)),
    (0, Vec(96, 236), 42, 4, UI_ALT, by_regime(UI, UI_HI)),
    (1, Vec(0, 0), 55, 5, ACCENT, by_regime(ACCENT_2, ACCENT_HI)),
)
GROUPS = sorted({st[0] for st in STONES})
NMAX = max(st[3] for st in STONES)
BRIDGE = 110  # closing radius of the outermost ring's waist between grouped stones


def stone_outline(rng: NpRng, c: Vec, r: float) -> NDArray[np.float64]:
    """A rounded, slightly lopsided outline of radius about `r` around `c`, 360 points."""
    a = (rng.uniform(0.04, 0.06), rng.uniform(0.02, 0.035), 0.012)
    p = rng.uniform(0, 2 * np.pi, 3)
    th = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    rr = r * (
        1
        + a[0] * np.cos(2 * th + p[0])
        + a[1] * np.cos(3 * th + p[1])
        + a[2] * np.cos(5 * th + p[2])
    )
    return np.column_stack([c.x + rr * np.cos(th), c.y + rr * np.sin(th)])


def rings(bodies: Sequence[Polygon], group: int, level: int) -> BaseGeometry:
    """The ground within `level` rings of any of `group`'s stones, a pitch per ring, each
    stone's count of rings ending at level NMAX."""
    return unary_union(
        [
            b.buffer((level - NMAX + st[3]) * GAP, 32)
            for b, st in zip(bodies, STONES)
            if st[0] == group and level - NMAX + st[3] > 0
        ]
    )


def outline(bodies: Sequence[Polygon], group: int) -> BaseGeometry:
    """The outermost ring of `group`, with the waist between its stones filled in."""
    return rings(bodies, group, NMAX).buffer(BRIDGE, 32).buffer(-BRIDGE, 32)


def even(outline: Polygon) -> NDArray[np.float64]:
    """Points about 6 apart, evenly spaced round the exterior of `outline`: buffers leave
    uneven vertices that a Catmull-Rom spline turns into wobbles."""
    line = Polyline(np.asarray(outline.exterior.coords), closed=True)
    return line.at(np.linspace(0, line.length, int(line.length // 6), endpoint=False))


def loop(pts: NDArray[np.float64]) -> NDArray[np.float64]:
    """`pts` with the first point repeated at the end."""
    return np.vstack([pts, pts[:1]])


def nudge(v: float, target: float) -> float:
    """The shift, under half a pitch either way, that brings `v` to `target` modulo GAP."""
    return (target - v + GAP / 2) % GAP - GAP / 2


def lattice(v: float) -> float:
    """The line position nearest `v`: the lines sit half a pitch off multiples of GAP."""
    return (round(v / GAP - 0.5) + 0.5) * GAP


def fitted(bodies: Sequence[Polygon], group: int) -> list[Polygon]:
    """`bodies` with `group`'s lowest-reaching stone stretched and the group moved, each by
    under half a pitch, so its outermost ring's top and bottom sit LIFT inside the lines."""
    out = list(bodies)
    ks = [k for k, st in enumerate(STONES) if st[0] == group]
    top, _, bottom = extent(out, group)
    low = max(ks, key=lambda k: out[k].bounds[3] + STONES[k][3] * GAP)
    x0, y0, _, y1 = out[low].bounds
    out[low] = scale(out[low], 1, 1 + nudge(bottom - top, 2 * LIFT) / (y1 - y0), origin=(x0, y0))
    dy = nudge(extent(out, group)[0], GAP / 2 - LIFT)
    for k in ks:
        out[k] = translate(out[k], 0, dy)
    return out


def extent(bodies: Sequence[Polygon], group: int) -> tuple[float, NDArray[np.float64], float]:
    """The top of `group`'s outermost ring, points about 1 apart along it, and its bottom."""
    zone = outline(bodies, group)
    edge = np.vstack(
        [
            (line := Polyline(np.asarray(p.exterior.coords), closed=True)).at(
                np.arange(0, line.length, 1.0)
            )
            for p in parts(zone)
            if isinstance(p, Polygon)
        ]
    )
    return float(zone.bounds[1]), edge, float(zone.bounds[3])


def envelope(
    edge: NDArray[np.float64], xs: NDArray[np.float64], d: float, side: int
) -> NDArray[np.float64]:
    """Along `xs`, the top (`side` -1) or bottom (1) of the ground within `d` of `edge`, and FAR
    past the line on that side where nothing is in reach."""
    dx = xs[:, None] - edge[None, :, 0]
    rise = np.sqrt(np.clip(d * d - dx * dx, 0, None))
    ys = np.where(np.abs(dx) <= d, edge[None, :, 1] + side * rise, -side * FAR)
    out: NDArray[np.float64] = ys.min(axis=1) if side < 0 else ys.max(axis=1)
    return out


def smin(a: NDArray[np.float64], b: NDArray[np.float64], k: float) -> NDArray[np.float64]:
    """The smaller of `a` and `b`, rounded off within `k` of where they meet; monotonic in
    both, so lines bent with it keep their order."""
    h = np.clip(1 - np.abs(a - b) / k, 0, 1)
    out: NDArray[np.float64] = np.minimum(a, b) - k * h * h / 4
    return out


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the pair high on the right and the single stone low on the left, a diagonal on any screen
    anchors = (
        s.pick(landscape=(1360 / 1920, 420 / 1080), portrait=(0.56, 0.3)),
        s.pick(landscape=(480 / 1920, 770 / 1080), portrait=(0.3, 0.7)),
    )
    bodies = [
        Polygon(stone_outline(s.np_rng(40 + k), anchors[g] + off, r))
        for k, (g, off, r, *_) in enumerate(STONES)
    ]
    for g in GROUPS:
        bodies = fitted(bodies, g)

    # Each stone's rings run a pitch apart, and the outermost wraps the pair as one, bridging
    # the waist between them. Inside that bridge, lines follow it a pitch apart and stop
    # against the stones' own rings, so the waist is raked as evenly as the rest.
    rake = P()
    for g in GROUPS:
        outer = outline(bodies, g)
        for ground in [*(rings(bodies, g, level) for level in range(1, NMAX)), outer]:
            for p in parts(ground):
                if isinstance(p, Polygon):
                    rake.spline(even(p), closed=True)
        own = rings(bodies, g, NMAX - 1).buffer(1, 32)
        inner = outer.buffer(-GAP, 32)
        while bridges := [
            part
            for p in parts(inner)
            if isinstance(p, Polygon)
            for part in parts(LineString(loop(even(p))).difference(own))
            if isinstance(part, LineString) and part.length > GAP
        ]:
            for part in bridges:
                rake.spline(np.asarray(part.coords))
            inner = inner.buffer(-GAP, 32)

    # Straight lines at the rake pitch stop on the outermost ring. The ones that would only
    # graze a group bow over it (or under) along offsets of that ring, the first a pitch out
    # and the rest SQUEEZE closer until the lift runs out, then ease back to straight.
    zone = unary_union([outline(bodies, g) for g in GROUPS])
    groups = [extent(bodies, g) for g in GROUPS]
    xs = np.arange(-GAP, s.w + GAP + STEP, STEP, dtype=np.float64)
    for c in np.arange(GAP / 2, s.h, GAP):
        y = np.full_like(xs, c)
        for top, edge, bottom in groups:
            # k: how far this line's straight run lies beyond the group's first passing line
            for side, k in (
                (-1, lattice(top + LIFT - GAP) - c),
                (1, c - lattice(bottom - LIFT + GAP)),
            ):
                d = GAP + k * SQUEEZE
                if k < 0 or LIFT - k * (1 - SQUEEZE) < -EASE:
                    continue
                reach = (xs > edge[:, 0].min() - d) & (xs < edge[:, 0].max() + d)
                bend = np.full_like(xs, -side * FAR)
                bend[reach] = envelope(edge, xs[reach], d, side)
                y = side * -smin(-side * y, -side * bend, EASE)
        line = LineString(np.column_stack([xs, y])).simplify(0.05)
        for part in parts(line.difference(zone)):
            if isinstance(part, LineString) and part.length > 2:
                rake.poly(np.asarray(part.coords))
    s.stroke(rake, BG_ALT, 1.5, cap="round", join="round")

    for body, (_, _, r, _, fill, shade) in zip(bodies, STONES):
        s.fill(P().spline(np.asarray(body.exterior.coords)[:-1], closed=True), fill)
        # Crescent in the lower right: the stone minus itself nudged toward the light.
        s.fill(P().shape(body.difference(translate(body, -0.17 * r, -0.22 * r))), shade)
