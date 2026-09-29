"""A watch movement in plan: wheels, bridges and balance as a technical drawing in which each part hides the ones beneath, with the hairspring picked out."""

import math
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray
from shapely import LinearRing, LineString, MultiLineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Color,
    P,
    Path,
    Vec,
    by_regime,
    design,
    mix,
    polar,
)
from walldye.geom import Affine, ngon, parts

PLATE, BAL_R = 350, 92  # plate and balance rim radii
DASHDOT = (22, 6, 3, 6)
BRIDGE = mix(BG, BG_ALT, 0.6)
TRAIN_TICK = mix(BG_ALT, UI, 0.5)
# the plate edge, balance, fork and jewels: a step quieter on paper, where the UI ramp reads darker
EDGE = by_regime(UI_HI, UI_ALT)
# club tooth of the escape wheel: (radius, degrees past the tooth's root)
ESC_TOOTH = ((45, 0), (58, 5.7), (55, 9.7), (52, 14.3), (45, 17.8), (45, 20.6))


def toward(p: Vec, q: Vec, d: float) -> Vec:
    """The point `d` from `p` towards `q`."""
    return p + (q - p).unit() * d


# Arbors relative to the movement's center, each one pitch radius plus the next pinion's from
# its driver. The train winds once round the plate: barrel upper left, wheels down the right,
# balance at the bottom.
CENTER = Vec(0, 0)
BARREL = polar(CENTER, 150 + 16, deg=225)
THIRD = polar(CENTER, 110 + 13, deg=-40)
FOURTH = polar(THIRD, 88 + 11, deg=30)
ESCAPE = polar(FOURTH, 80 + 9, deg=100)
BALANCE = polar(CENTER, 225, deg=80)
PALLET = toward(ESCAPE, BALANCE, 66)
CROWN = toward(BARREL, Vec(-240, -30), 96 + 36)
# (arbor, pitch radius, teeth, pinion radius, crossings, tooth tick color), bottom to top
WHEELS = (
    (BARREL, 150, 90, 0, 0, BG_ALT),
    (CENTER, 110, 80, 16, 4, BG_ALT),
    (THIRD, 88, 75, 13, 4, TRAIN_TICK),
    (FOURTH, 80, 70, 11, 4, TRAIN_TICK),
)


@dataclass(frozen=True)
class Layer:
    """Geometry at height `z`, outlined over an optional fill; covers higher up hide it."""

    z: float
    geom: BaseGeometry
    stroke: Color
    width: float = 1.2
    fill: Color | None = None
    dash: tuple[float, ...] | None = None


def ring(c: Vec, r: float) -> LinearRing:
    """A circle as a ring of segments, fine enough to stay round at 4K."""
    return LinearRing(ngon(c, r, max(48, int(r * 2.2)), deg=0))


def disc(c: Vec, r: float) -> Polygon:
    return Point(c).buffer(r, quad_segs=64)


def interleave(*rings: NDArray[np.float64]) -> NDArray[np.float64]:
    """The vertices of (N, 2) arrays taken in turn: a0, b0, ..., a1, b1, ..."""
    return np.stack(rings, axis=1).reshape(-1, 2)


def spokes(c: Vec, r0: float, r1: float, n: int, deg: float = 0) -> MultiLineString:
    """`n` evenly spaced radial segments from `r0` to `r1`, the first at `deg`."""
    return MultiLineString(
        list(np.stack([ngon(c, r0, n, deg=deg), ngon(c, r1, n, deg=deg)], axis=1))
    )


def hull(*shapes: BaseGeometry) -> BaseGeometry:
    return unary_union(shapes).convex_hull


def trace(g: BaseGeometry) -> Path:
    """`g` as path data, closing each line that ends where it starts."""
    d = P()
    for part in parts(g):
        closed = isinstance(part, LineString) and part.is_closed
        d.shape(LinearRing(part.coords) if closed else part)
    return d


@design(aspects="any")
def draw(s: Canvas) -> None:
    layers: list[Layer] = []
    covers: list[tuple[float, BaseGeometry]] = []  # (z, area hiding every layer below z)

    def add(
        z: float,
        g: BaseGeometry,
        stroke: Color,
        width: float = 1.2,
        fill: Color | None = None,
        dash: tuple[float, ...] | None = None,
    ) -> None:
        layers.append(Layer(z, g, stroke, width, fill, dash))

    def screws(z: float, centers: list[Vec], r: float = 10, deg: float = 35) -> None:
        add(z, unary_union([disc(c, r) for c in centers]), UI_ALT, fill=BRIDGE)
        slots = [(polar(c, r, deg=deg), polar(c, r, deg=deg + 180)) for c in centers]
        add(z, MultiLineString(slots), UI_ALT)

    # plate, center lines and winding stem: the lowest layer
    add(0, ring(CENTER, PLATE), EDGE, 2)
    e = PLATE + 50
    add(0, MultiLineString([((-e, 0), (e, 0)), ((0, -e), (0, e))]), UI, dash=DASHDOT)
    x0, x1 = CROWN.x - 46, -PLATE - 18
    add(
        0.5,
        MultiLineString([((x0, -7), (x1, -7)), ((x0, 7), (x1, 7)), ((x0, -7), (x0, 7))]),
        UI_ALT,
        1.3,
    )

    # wheels: pitch circle, tooth ticks, rim and crossings, pinion; each hides the ones beneath
    for i, (c, r, teeth, pinion, arms, tick) in enumerate(WHEELS, start=1):
        hub = max(10, r * 0.14)
        add(i, ring(c, r), UI_ALT, 1.4)
        add(i, spokes(c, r, r + 6, teeth), tick)
        lines: list[BaseGeometry] = [ring(c, r * 0.82 if arms else r - 12), ring(c, hub)]
        if arms:
            lines.append(spokes(c, hub, r * 0.82, arms, deg=23))
        if pinion:
            lines.append(ring(c, pinion))
        add(i, unary_union(lines), UI)
        covers.append((i, disc(c, r + 7)))

    # escape wheel: 15 club teeth, rim and five crossings
    teeth = interleave(*(ngon(ESCAPE, r, 15, deg=a) for r, a in ESC_TOOTH))
    esc = [LinearRing(teeth), ring(ESCAPE, 36), ring(ESCAPE, 8), spokes(ESCAPE, 8, 36, 5)]
    add(5, unary_union(esc), UI_ALT, 1.3)
    covers.append((5, disc(ESCAPE, 59)))

    # pallet fork: two arms into the escape teeth, a lever reaching under the balance to its roller
    to_esc = math.degrees(math.atan2(ESCAPE.y - PALLET.y, ESCAPE.x - PALLET.x))
    tip = toward(PALLET, BALANCE, abs(BALANCE - PALLET) - 12)
    bars = [LineString([PALLET, polar(PALLET, 48, deg=to_esc + da)]) for da in (-52, 52)]
    bars.append(LineString([PALLET, tip]))
    fork = unary_union([b.buffer(3.2, quad_segs=6) for b in bars] + [disc(PALLET, 9)])
    add(6, fork, EDGE, fill=BG)
    covers.append((6, fork))

    # balance cock: a plate reaching out from under the balance to two screws, clear of the train
    cock_screws = [polar(BALANCE, 150, deg=140), polar(BALANCE, 162, deg=182)]
    cock = hull(disc(BALANCE, 40), *(disc(c, 20) for c in cock_screws))
    add(6.5, cock.intersection(disc(CENTER, PLATE - 12)), UI, fill=BRIDGE)
    screws(6.6, cock_screws)

    # balance: rim, arms, timing screws
    bal = [ring(BALANCE, BAL_R), ring(BALANCE, BAL_R - 8), ring(BALANCE, 10)]
    bal += [ring(polar(BALANCE, BAL_R + 4, deg=6 + 30 * k), 3) for k in range(12)]
    add(7, unary_union([*bal, spokes(BALANCE, 10, BAL_R - 8, 3, deg=17)]), EDGE, 1.4)
    covers.append((7, disc(BALANCE, BAL_R + 8)))

    # bridges over the barrel and the train
    barrel_screws = [polar(BARREL, 138, deg=a) for a in (195, 292)]
    t_end, e_end = polar(THIRD, 100, deg=-75), polar(ESCAPE, 70, deg=40)
    train = [t_end, THIRD, FOURTH, ESCAPE, e_end]
    bridges = [
        unary_union([hull(disc(BARREL, 108), disc(c, 20)) for c in barrel_screws]),
        unary_union([hull(disc(a, 22), disc(b, 22)) for a, b in pairwise(train)]),
    ]
    for g in bridges:
        g = g.intersection(disc(CENTER, PLATE - 12))
        add(8, g, UI, fill=BRIDGE)
        covers.append((8, g))
    screws(9, [*barrel_screws, t_end, e_end])

    # ratchet wheel over the barrel bridge, meshing with the crown wheel
    ratchet = Polygon(interleave(ngon(BARREL, 96, 36, deg=0), ngon(BARREL, 89, 36, deg=10)))
    add(9, ratchet, UI_ALT, fill=BG)
    add(9.1, ring(BARREL, 70), UI)
    covers.append((9, ratchet))
    screws(9.2, [BARREL], 16, 60)
    add(9, disc(CROWN, 36), UI_ALT, fill=BG)
    add(9.1, unary_union([ring(CROWN, 26), ring(CROWN, 8), spokes(CROWN, 36, 41, 24)]), UI_ALT)
    covers.append((9, disc(CROWN, 42)))

    # jewels at the arbors that show through the bridges
    jeweled = (CENTER, THIRD, FOURTH, ESCAPE, PALLET, BALANCE)
    add(9.5, unary_union([ring(c, r) for c in jeweled for r in (6, 2.5)]), EDGE)

    # hairspring: an Archimedean spiral whose outer coil lifts away to the stud
    turns, r0, r1 = 10, 14, 66
    end = 2 * math.pi * turns
    t = np.linspace(0, 1, turns * 90 + 1)
    u = np.arange(1, 31) / 30
    radii = np.concatenate([r0 + (r1 - r0) * t, r1 + 8 * u * u])
    angles = np.concatenate([end * t, end + 0.9 * u])
    spring = BALANCE + np.column_stack([radii * np.cos(angles), radii * np.sin(angles)])

    # landscape: right of center, leaving the left for windows; portrait: a little below middle
    c = s.pick(landscape=(31 / 48, 0.5), portrait=(0.5, 0.58), snap=1)
    with s.group(transform=Affine.translate(c.x, c.y)):
        for layer in sorted(layers, key=lambda k: k.z):
            above = unary_union([g for z, g in covers if z > layer.z])
            d = trace(layer.geom.difference(above))
            if layer.fill is None:
                s.stroke(d, layer.stroke, layer.width, join="round", dash=layer.dash)
            else:
                s.path(
                    d,
                    fill=layer.fill,
                    stroke=layer.stroke,
                    stroke_width=layer.width,
                    stroke_linejoin="round",
                )
        s.stroke(P().poly(spring), ACCENT, 1.3, join="round")
        stud = polar(BALANCE, r1 + 8, rad=end + 0.9)
        s.path(P().circle(stud, 4), fill=BG, stroke=EDGE, stroke_width=1.2)
