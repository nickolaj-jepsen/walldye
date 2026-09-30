"""An ensō in dry brush with an eroded square seal, drawn as bristle ribbons."""

import math
from collections.abc import Iterable, Iterator

import numpy as np
from numpy.typing import NDArray
from shapely import affinity
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import ACCENT, UI_ALT, UI_HI, Canvas, P, Point, Rng, Vec, design, polar, smoothstep
from walldye.field import Noise, gauss, runs
from walldye.geom import Affine, ribbon

type F = NDArray[np.float64]

R = 300  # ring radius, about the origin
MAX_X = 1296  # furthest the ring's center sits from the left edge
A0, SWEEP = 150, 328  # where the brush lands and how far it travels, degrees clockwise from east
LENGTH = math.radians(SWEEP) * R  # stroke length in px, to size head features in pixels
BRUSH, BRISTLES = 58, 36
SEAL, SEAL_AT, SEAL_TILT = 88, (370, 320), 2  # side, center from the ring's center, tilt in deg
# (t, half-width) of early dry breaks on the inner edge, around 10-11 o'clock
KASURE = ((0.18, 0.012), (0.255, 0.007))
TOL = 0.1  # px the merged outlines may move when thinned; the ribbons are sampled far finer


def ring_at(n: Noise, t: F, off: F | float = 0.0) -> F:
    """Points `off` px outward of the brush centerline at stroke parameters `t`: a hand-drawn
    circle about the origin that drifts slightly outward as it goes round."""
    a = np.radians(A0 + SWEEP * t)
    r = R + 6 * n(t * 3, 0.5) + 10 * t + off
    return np.column_stack([r * np.cos(a), r * np.sin(a)])


def width(t: F) -> F:
    """Brush load: a blunt press at the head, then a long taper as the ink runs out."""
    press = 0.92 + 0.12 * gauss(t * LENGTH - 18, 16)
    return BRUSH * press * (0.4 + 0.6 * (1 - t) ** 0.9) * np.minimum(1.0, (1 - t) / 0.1) ** 0.6


def steps(end: float, k: int = 520) -> F:
    """Stroke parameters from 0 to `end`, packed densest at the head where the outline curves
    fastest."""
    return end * (np.arange(k + 1) / k) ** 1.35


def taper(t: F, thick: F, fade: float) -> F:
    """Widths along one ribbon: the tail narrows over `fade` points, and so does the start
    unless it is the head of the stroke, where the bristles stay blunt."""
    j = np.arange(len(t))
    head = 1.0 if t[0] == 0 else np.minimum(1.0, j / 2)
    return thick * (np.minimum(head, (len(t) - 1 - j) / fade) * 0.7 + 0.3)


def bristles(n: Noise, r: Rng, r2: Rng) -> Iterator[tuple[F, bool]]:
    """Bristle ribbons that break up as the brush dries, as (outline, loaded): loaded ribbons
    carry full ink and are painted over the thin ones."""
    for i in range(BRISTLES):
        u = (i + 0.5) / BRISTLES * 2 - 1  # across the brush, inner edge -1 to outer edge 1
        end = 1 - 0.14 * abs(u) ** 1.5 - r.uniform(0, 0.05)
        loaded = r.random() < 0.62
        # outer bristles and a few random ones run dry first, which gives the streaky kasure
        bias = 0.45 * max(0.0, u) ** 2 + (0.35 if r.random() < 0.15 else 0.0)
        # thin bristles only show once the load thins, so the head is not evenly ribbed
        covered = 0.0 if loaded else max(0.0, r2.uniform(-0.1, 0.32))
        inner = smoothstep(-0.3, -0.85, u)
        t = steps(end)
        w = width(t) * (1 + 0.14 * n(t * 5, 3.3))
        off = u * w / 2 * (1 + 0.15 * t) + 1.2 * n(i * 2.3, t * 18)
        thick = w / BRISTLES * 1.8 * (0.8 + 0.4 * n(i * 3.1, t * 6))
        dry = n(t * 26, i * 0.7 + 11) + 0.5 * n(t * 70, i * 1.3) - 0.95 + 1.4 * t**2
        dry += bias * np.minimum(1.0, t / 0.2)
        dry += 1.6 * inner * sum(gauss(t - c, hw) for c, hw in KASURE)
        pts = ring_at(n, t, off)
        for a, b in runs((dry < 0) & (thick > 0.3)):
            if b - a < 3:
                continue
            yield ribbon(pts[a:b], taper(t[a:b], thick[a:b], 2)), loaded
            # a loaded ribbon over the start of a thin bristle, fading out along it
            k = a + int(np.searchsorted(t[a:b], covered))
            if k - a > 2:
                yield ribbon(pts[a:k], taper(t[a:k], thick[a:k] * 1.15, 40)), True


def press(n: Noise) -> F:
    """Blunt, slightly bulbous loaded start: a rounded pad ~1.15x brush wide, ~40px along the
    path."""
    sl = np.linspace(-8, 34, 81)  # px along the stroke
    v = (sl - 13) / 21
    hw = BRUSH * 0.575 * np.clip(1 - np.abs(v) ** 2.6, 0, 1) ** (1 / 2.6)
    return ribbon(ring_at(n, sl / LENGTH), 2 * hw * (1 + 0.03 * n(sl / 9, 7.7)))


def grooves(n: Noise, r: Rng) -> Iterator[F]:
    """A few broken, uneven dry streaks across the loaded half; some drift together and merge."""
    lanes = [r.uniform(-0.75, 0.75) for _ in range(6)]
    v = np.linspace(0, 1, 241)
    for g, u0 in enumerate(lanes):
        t0, span = r.uniform(0.004, 0.2), r.uniform(0.12, 0.28)
        u1 = lanes[(g + 1) % len(lanes)] if g < 3 else u0 + r.uniform(-0.12, 0.12)
        wmax = r.uniform(1.6, 4.6)
        t = t0 + span * v
        u = u0 + (u1 - u0) * smoothstep(0.3, 1.0, v) + 0.06 * n(g * 4.1, t * 12)
        th = wmax * np.sin(np.pi * v) ** 0.6 * (0.75 + 0.35 * n(t * 30, g * 2.9))
        pts = ring_at(n, t, u * width(t) / 2)
        for a, b in runs((n(t * 40, g * 1.7 + 5) > -0.25) & (th > 0.4)):
            if b - a > 2:
                yield ribbon(pts[a:b], taper(t[a:b], th[a:b], 2))


def merged(outlines: Iterable[F]) -> BaseGeometry:
    """The union of closed outlines, thinned to the vertices that move it by more than TOL."""
    return unary_union([Polygon(o) for o in outlines]).simplify(TOL)


def chip(r: Rng, c: Point, size: float) -> Polygon:
    """An irregular 5-7 sided chip around `c`."""
    k = r.randint(5, 7)
    return Polygon(
        [
            polar(c, size * r.uniform(0.6, 1.1), rad=math.tau * (j + r.uniform(-0.25, 0.25)) / k)
            for j in range(k)
        ]
    )


def seal(r: Rng) -> BaseGeometry:
    """Eroded square seal at SEAL_AT with a carved baiwen pseudo-glyph: a left radical, a boxed
    right part and a base that runs out of the stone."""
    h = SEAL / 2
    corners = [Vec(-h, -h), Vec(h, -h), Vec(h, h), Vec(-h, h)]
    edge: list[Vec] = []
    for a, b in zip(corners, corners[1:] + corners[:1], strict=True):
        out = -((b - a) / SEAL).perp()  # the sides run clockwise, so this points out of the stone
        edge += [a + (b - a) * (k / 12) + out * r.gauss(0, 0.5) for k in range(12)]
    body: BaseGeometry = Polygon(edge)
    for _ in range(7):  # chips knocked out of the rim
        a = r.uniform(0, math.tau)
        rim = (h + 1.6) / max(abs(math.cos(a)), abs(math.sin(a)))
        body = body.difference(chip(r, polar((0, 0), rim, rad=a), r.uniform(2.5, 4.5)))

    # strokes in unit coords (x0, y0, x1, y1, weight); the stone spans -1..1
    strokes = [
        (-0.55, -0.78, -0.55, 0.42, 1.1),  # radical spine
        (-0.86, -0.42, -0.26, -0.42, 0.95),
        (-0.86, 0.06, -0.26, 0.06, 0.9),
        (-0.08, -0.66, 0.84, -0.66, 0.8),  # top bar, kept light
        (0.0, -0.66, 0.0, 0.24, 1.05),
        (0.72, -0.66, 0.72, 0.24, 1.0),
        (0.0, -0.22, 0.72, -0.22, 0.85),
        (0.0, 0.24, 0.72, 0.24, 1.0),
        (-0.86, 0.64, 1.5, 0.64, 1.1),  # base, carved out through the right edge
        (0.34, 0.24, 0.34, 1.12, 1.0),  # stem, into the bottom margin
        (-0.7, 0.42, -0.34, 0.42, 0.9),  # fills the lower-left
    ]
    k = h - 7
    cuts = [
        LineString([(x0 * k, y0 * k), (x1 * k, y1 * k)]).buffer(
            2.9 * wt * r.uniform(0.9, 1.1), cap_style="flat", join_style="mitre"
        )
        for x0, y0, x1, y1, wt in strokes
    ]
    glyph = unary_union(cuts).buffer(1.6, join_style="round").buffer(-1.6, join_style="round")
    specks = [chip(r, (r.uniform(-h, h), r.uniform(-h, h)), r.uniform(0.8, 1.7)) for _ in range(9)]
    body = body.difference(unary_union([glyph, *specks]))
    return affinity.translate(affinity.rotate(body, SEAL_TILT, origin=(0, 0)), *SEAL_AT)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # left of center on a landscape screen, so the seal lands right of the middle, and never
    # past MAX_X, which keeps the seal out of the middle of a 32:9 screen too; centered a little
    # high on a portrait one, clear of the clock and the dock
    c = s.pick(landscape=(0.40625, 17 / 36), portrait=(0.46, 0.4))
    c = Vec(min(c.x, MAX_X), c.y)
    n = s.noise(21)
    r, r2 = s.rng(21), s.rng(22)
    with s.group(transform=Affine.translate(c.x, c.y)):
        thin: list[F] = []
        loaded = [press(n)]
        for outline, full in bristles(n, r, r2):
            (loaded if full else thin).append(outline)
        # painted in this order, so the dry grooves cut back through the loaded bristles
        s.fill(P().shape(merged(thin)), UI_ALT)
        s.fill(P().shape(merged(loaded)), UI_HI)
        s.fill(P().shape(merged(grooves(n, r2))), UI_ALT)
        s.fill(P().shape(seal(s.rng(2))), ACCENT)
