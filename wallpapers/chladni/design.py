"""A Chladni figure: sand grains stippled along the nodal lines of a vibrating square plate, the loop around its center picked out."""

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely.geometry import Point, Polygon

from walldye import ACCENT, UI, UI_ALT, Canvas, P, Params, Path, design, knob, smoothstep
from walldye.field import gauss, iso_lines, sample_field
from walldye.geom import Affine

type Field = NDArray[np.float64]


class Mode(Params):
    """The vibration mode: two odd numbers of half-waves across the plate, n below m."""

    n: int = knob(default=5, choices=(3, 5, 7), doc="the smaller mode number")
    m: int = knob(default=11, choices=(7, 11, 13, 15), doc="the larger mode number")


VARIANTS = {"low": Mode(n=3, m=7), "high": Mode(n=7, m=15)}

S = 720  # plate side
FADE = 110 / S  # the plate edge dissolves over this band instead of cropping the outer loops
KEEP = 0.46  # share of the grains near a nodal line that stay: sand, not ink
LOOP_SAMPLES = 356_000  # candidate grains per unit plate area for the central loop
LATTICE = 240  # cells across the plate when tracing the central loop


def wave(u: Field, v: Field, p: Mode) -> tuple[Field, Field]:
    """The plate's displacement cos(n pi u) cos(m pi v) - cos(m pi u) cos(n pi v) at plate
    coordinates (u, v) in [0, 1], and the length of its gradient."""
    a, b = p.n * np.pi, p.m * np.pi
    val = np.cos(a * u) * np.cos(b * v) - np.cos(b * u) * np.cos(a * v)
    gu = -a * np.sin(a * u) * np.cos(b * v) + b * np.sin(b * u) * np.cos(a * v)
    gv = -b * np.cos(a * u) * np.sin(b * v) + a * np.cos(b * u) * np.sin(a * v)
    return val, np.hypot(gu, gv)


def curved(u: Field, v: Field, p: Mode) -> Field:
    """The displacement with the four straight nodal lines (both diagonals and both midlines,
    present when n and m are odd) divided out, so its zeros are the curved lines only."""
    return wave(u, v, p)[0] / ((u - v) * (u + v - 1) * (u - 0.5) * (v - 0.5) + 1e-12)


def loop_dist(u: Field, v: Field, p: Mode, e: float = 1e-5) -> Field:
    """Distance in canvas units to the nearest curved nodal line, to first order."""
    h = curved(u, v, p)
    return np.abs(h) / (np.hypot(curved(u + e, v, p) - h, curved(u, v + e, p) - h) / e) * S


def edge_fade(u: Field, v: Field) -> Field:
    """1 inside the plate, easing to 0 over FADE at its edges."""
    return smoothstep(0, FADE, np.minimum.reduce([u, v, 1 - u, 1 - v]))


def central_loop(p: Mode) -> Polygon:
    """The smallest curved nodal loop around the plate center, in plate coordinates.

    Raises ValueError when the mode has none."""
    # offsets that keep every lattice node off the straight lines, where curved() is 0 / 0
    du, dv = 0.3 / LATTICE, 0.6 / LATTICE
    field = sample_field(
        lambda i, j: curved(i / LATTICE + du, j / LATTICE + dv, p), LATTICE, LATTICE
    )
    center = Point(0.5, 0.5)
    loops = [
        Polygon(line)
        for line in iso_lines(field, 0, cell=1 / LATTICE, origin=(du, dv))
        if len(line) > 3 and np.allclose(line[0], line[-1])
    ]
    # the division is ill-conditioned right at the center; loops that close there are noise
    around = [q for q in loops if q.contains(center) and q.exterior.distance(center) > 0.05]
    if not around:
        raise ValueError(f"mode ({p.n}, {p.m}) has no nodal loop around the plate center")
    return min(around, key=lambda q: q.area)


def grains(x: Field, y: Field) -> Path:
    """One zero-length subpath per grain, drawn as a dot by a round-capped stroke."""
    d = P()
    for a, b in zip(x.tolist(), y.tolist(), strict=True):
        d.M(a, b).H(a)
    return d


@design(aspects=("16:9", "32:9", "9:19.5", "10:16"), variants=VARIANTS)
def draw(s: Canvas[Mode]) -> None:
    p = s.params
    # right of center on a landscape screen, leaving the left for windows; high on a portrait one
    corner = s.pick(landscape=(0.7, 0.5), portrait=(0.5, 0.42)) - (S / 2, S / 2)
    band = central_loop(p).exterior.buffer(6 / S)
    shapely.prepare(band)

    g = s.np_rng(3)
    u, v = g.random((2, 400_000))
    val, grad = wave(u, v, p)
    dist = np.abs(val) / np.maximum(grad, 1e-6) * S  # to the nearest nodal line
    keep = np.flatnonzero(g.random(u.size) < KEEP * gauss(dist, 2.6) * edge_fade(u, v))
    # the loop gets its own tighter sampling below
    keep = keep[~shapely.contains_xy(band, u[keep], v[keep])]
    stray = g.random((2, 400))
    stray = stray[:, g.random(400) < edge_fade(stray[0], stray[1])]
    u, v = np.r_[u[keep], stray[0]], np.r_[v[keep], stray[1]]
    axis = S * np.minimum.reduce(
        [np.abs(u - v) / 2**0.5, np.abs(u + v - 1) / 2**0.5, np.abs(u - 0.5), np.abs(v - 0.5)]
    )
    # grains on the straight lines and towards the plate edge settle a step quieter
    quiet = (axis < 5) | (g.random(u.size) > edge_fade(u, v))

    x0, y0, x1, y1 = band.bounds
    n = int(LOOP_SAMPLES * (x1 - x0) * (y1 - y0))
    a = g.random((2, n)) * [[x1 - x0], [y1 - y0]] + [[x0], [y0]]
    on = shapely.contains_xy(band, a[0], a[1])
    a = a[:, (g.random(n) < gauss(loop_dist(a[0], a[1], p), 1.6)) & on]

    def place(u: Field, v: Field, jitter: float) -> tuple[Field, Field]:
        return u * S + g.normal(0, jitter, u.size), v * S + g.normal(0, jitter, v.size)

    x, y = place(u, v, 0.6)
    ax, ay = place(a[0], a[1], 0.3)
    big = g.random(u.size) < 0.4
    # in plate-local coordinates every grain is written a digit shorter
    with s.group(transform=Affine.translate(corner.x, corner.y)):
        for tone, col in ((quiet, UI), (~quiet, UI_ALT)):
            for sel, w in ((~big, 1.3), (big, 1.6)):
                s.stroke(grains(x[tone & sel], y[tone & sel]), col, w, cap="round")
        s.stroke(grains(ax, ay), ACCENT, 1.6, cap="round")
