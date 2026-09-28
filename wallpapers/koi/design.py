"""Koi seen from above: bodies unioned from discs along swimming spines, noise-edged patches, teardrop fins and ripple rings."""

import math
from typing import NamedTuple

from shapely import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    P,
    Vec,
    design,
    mix,
    polar,
)
from walldye.field import Noise
from walldye.geom import Affine, parts

type Patch = tuple[float, float, float, float]


class Koi(NamedTuple):
    head: Vec
    heading: float  # degrees the nose points, screen convention
    length: float  # nose to tail root
    turn: float  # radians the spine bends from nose to tail root
    phase: float  # of the swimming undulation
    half: float  # half-width at the fullest point
    body: Colour
    fins: Colour
    tail: Colour
    patch: Colour
    fade: float  # how strongly fins and tail tips show over the water, 0..1
    patches: tuple[Patch, ...]  # (spine from, spine to, radius and sideways drift in half-widths)


RIPPLES = (BG_ALT, mix(BG, BG_ALT, 0.7), mix(BG, BG_ALT, 0.5))  # inner to outer ring


def spine(
    head: Vec, heading: float, length: float, turn: float, phase: float, n: int = 60
) -> tuple[list[Vec], list[float]]:
    """`n + 1` points from nose to tail root, and the direction towards the tail at each in
    screen radians: a steady turn plus a swimming undulation that grows towards the tail."""
    pts, angs = [head], []
    back = math.radians(heading) + math.pi
    for i in range(n):
        t = i / (n - 1)
        a = back + turn * t + 0.28 * t * t * math.sin(phase + t * 2.2 * math.pi)
        angs.append(a)
        pts.append(polar(pts[-1], length / (n - 1), rad=a))
    angs.append(angs[-1])
    return pts, angs


def half_width(t: float, w: float) -> float:
    """Half-width at spine fraction `t`: round head, fullest behind the pectorals, slim peduncle."""
    if t < 0.32:
        return w * (0.62 + 0.38 * math.sin(math.pi / 2 * t / 0.32))
    return w * (1 - 0.8 * ((t - 0.32) / 0.68) ** 1.6)


def fin(root: Vec, a: float, size: float, width: float = 0.34) -> Polygon:
    """Teardrop fin from `root` along `a` (screen radians), broadening to a rounded trailing edge."""
    side = [
        (u * size, width * size * math.sin(math.pi * u) ** 0.6 * (0.45 + 0.55 * u))
        for u in (k / 40 for k in range(41))
    ]
    outline = side + [(x, -y) for x, y in side[::-1]]
    return Polygon(Affine.frame(root, rad=a).apply(outline))


def koi(k: Koi) -> tuple[BaseGeometry, BaseGeometry, BaseGeometry, list[Vec], list[float]]:
    """Body, paired fins and tail of one fish, plus its spine points and directions."""
    pts, angs = spine(k.head, k.heading, k.length, k.turn, k.phase, n=160)
    n = len(pts) - 1
    body = unary_union(
        [
            Point(p).buffer(half_width(i / n, k.half), quad_segs=16)
            for i, p in enumerate(pts)
            if i / n > 0.02
        ]
    )

    # two long slim lobes splayed ~35 degrees, rooted inside the peduncle so the fork doesn't pinch
    end, ea = pts[-1], angs[-1]
    root = polar(end, -0.07 * k.length, rad=ea)
    tail = unary_union([fin(root, ea + side * 0.3, 0.42 * k.length, 0.2) for side in (1, -1)])
    tail = tail.buffer(2, quad_segs=8).buffer(-2, quad_segs=8)

    # mirrored about the local spine direction: pectorals at 25%, pelvics at 55%
    fins: list[Polygon] = []
    for t, size, sweep in ((0.25, 0.22 * k.length, 0.95), (0.55, 0.12 * k.length, 0.75)):
        i = int(t * n)
        d = pts[i + 6] - pts[i - 6]
        a = math.atan2(d.y, d.x)
        for side in (1, -1):
            at = polar(pts[i], half_width(t, k.half) * 0.7, rad=a + side * math.pi / 2)
            fins.append(fin(at, a + side * sweep, size))
    return body, unary_union(fins), tail, pts, angs


def markings(nz: Noise, key: int, pts: list[Vec], k: Koi) -> BaseGeometry:
    """Kohaku-style patches: irregular blobs over the back, each drifting a little off the spine."""
    n = len(pts) - 1
    out = []
    for s0, s1, size, drift in k.patches:
        blobs = []
        for i in range(int(s0 * n), int(s1 * n) + 1):
            t = i / n
            w = half_width(t, k.half)
            swell = max(0.0, math.sin(math.pi * (t - s0) / (s1 - s0))) ** 0.3
            rad = w * size * swell * (1 + 0.4 * nz.fbm(t * 14, key, 3))
            d = pts[min(i + 1, n)] - pts[i - 1]
            off = (drift + 0.35 * nz.fbm(t * 11, key + 3.7, 2)) * w
            if rad > 1:
                at = polar(pts[i], off, rad=math.atan2(d.y, d.x) + math.pi / 2)
                blobs.append(Point(at).buffer(rad, quad_segs=12))
        out.append(unary_union(blobs))
    return unary_union(out)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: the pair right of centre, its outer ripple kept ~120 from the right edge;
    # portrait: the pair low and to the right, under a clock
    if s.landscape:
        lit, stray = Vec(min(0.615 * s.w, s.w - 740), 430), Vec(150, 700)
    else:
        lit, stray = s.frac(0.3, 0.42), s.frac(0.14, 0.82)
    fish = [
        Koi(
            lit, -160, 300, 0.9, 0.6, 36, ACCENT, ACCENT_1, ACCENT_2, ACCENT_1, 0.55,
            ((0.04, 0.15, 0.6, 0.2), (0.24, 0.52, 0.75, -0.2), (0.6, 0.72, 0.55, 0.3)),
        ),
        Koi(
            lit + (320, 170), -150, 270, 0.75, 2.2, 32, UI_ALT, UI, UI, UI_HI, 0.8,
            ((0.08, 0.2, 0.55, -0.15), (0.32, 0.56, 0.7, 0.2)),
        ),
        # a third, barely there, nosing in from the left edge
        Koi(
            stray, -12, 190, -0.35, 1.1, 22, BG_ALT, BG_ALT, BG_ALT, UI, 0.8,
            ((0.3, 0.5, 0.55, 0.0),),
        ),
    ]  # fmt: skip

    # three rings spreading from where each tail of the pair last flicked, the outermost faintest
    with s.buckets(RIPPLES, "stroke", stroke_width=1.4) as rings:
        for k in fish[:2]:
            pts, _ = spine(k.head, k.heading, k.length * 1.35, k.turn * 1.35, k.phase)
            for j in range(len(RIPPLES)):
                rings[j].circle(pts[-1], 0.12 * k.length * (j + 1) ** 1.3)

    for i, k in enumerate(fish):
        body, fins, tail, pts, angs = koi(k)
        # the tail thins towards its tips, sinking a little into the water
        end = pts[-1]
        tip = mix(BG, k.tail, 0.7 * k.fade)
        fade = s.linear_gradient(
            [(0, k.tail), (0.25, k.tail), (1, tip)], end, polar(end, 0.4 * k.length, rad=angs[-1])
        )
        s.fill(P().shape(fins), mix(BG, k.fins, k.fade))
        s.fill(P().shape(body), k.body)
        # tail over the body so its root hides the rounded end of the peduncle
        s.fill(P().shape(tail), fade)
        mk = markings(s.noise(5 + i), 5 + i, pts, k)
        mk = mk.buffer(-9).buffer(13).buffer(-4).intersection(body.buffer(-5))
        patches = P()
        for g in parts(mk):
            if isinstance(g, Polygon):
                patches.shape(g)
        s.fill(patches, k.patch)
