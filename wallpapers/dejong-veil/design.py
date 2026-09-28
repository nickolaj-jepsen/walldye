"""A Peter de Jong attractor as a veil: its point density cut into stepped tone levels, with the densest fold picked out."""

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import (
    binary_closing,
    binary_dilation,
    binary_fill_holes,
    binary_opening,
    gaussian_filter,
    label,
)
from skimage.draw import line
from skimage.morphology import disk

from walldye import (
    ACCENT,
    ACCENT_2,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    NpRng,
    P,
    Params,
    Path,
    Vec,
    design,
    knob,
    ladder,
    polar,
)
from walldye.field import iso_lines

type Field = NDArray[np.float64]


class Attractor(Params):
    a: float = knob(default=-2.0, lo=-3, hi=3, doc="x' = sin(a y) - cos(b x)")
    b: float = knob(default=-2.0, lo=-3, hi=3, doc="x' = sin(a y) - cos(b x)")
    c: float = knob(default=-1.2, lo=-3, hi=3, doc="y' = sin(c x) - cos(d y)")
    d: float = knob(default=2.0, lo=-3, hi=3, doc="y' = sin(c x) - cos(d y)")
    fold: float = knob(
        default=52, lo=-90, hi=90, unit="deg", doc="picked-out fold direction, clockwise from east"
    )


VARIANTS = {"dome": Attractor(a=1.4, b=-2.3, c=2.4, d=-2.1, fold=60)}

SIZE, N = 870, 580  # side of the square window fitted round the attractor; histogram cells
CELL = SIZE / N
POINTS, WARMUP, STEPS = 400_000, 20, 150  # orbits, iterations discarded, iterations counted
# Fixed cuts on the smoothed log-density, so level edges follow the folds (level, smoothing);
# sparse low levels get more smoothing. The cuts assume POINTS * STEPS samples.
LEVELS = ((2.2, 3.0), (3.6, 2.5), (5.0, 1.6), (6.0, 1.0), (6.6, 0.6), (7.0, 0.4))
TONES = ladder((BG, BG_ALT, UI, UI_ALT), len(LEVELS) + 1)[1:]
HALO, CORE = 6.85, 7.1  # log-density cuts for the rim round the picked-out fold, and the fold


def density(p: Attractor, g: NpRng) -> Field:
    """Visits per cell of an N x N grid (rows along y) over the attractor's square bounding
    window, from POINTS orbits of STEPS iterations each."""
    # float32 trig is about ten times faster; the orbits are chaotic either way, and only
    # their density is drawn
    x, y = g.uniform(-2, 2, (2, POINTS)).astype(np.float32)
    for _ in range(WARMUP):
        x, y = np.sin(p.a * y) - np.cos(p.b * x), np.sin(p.c * x) - np.cos(p.d * y)
    # square window round the attractor's bounds, so it fills the grid without distortion
    mx, my = (x.max() + x.min()) / 2, (y.max() + y.min()) / 2
    k = N / (max(np.ptp(x), np.ptp(y)) * 1.02)
    hist = np.zeros(N * N)
    for _ in range(STEPS):
        x, y = np.sin(p.a * y) - np.cos(p.b * x), np.sin(p.c * x) - np.cos(p.d * y)
        i = np.floor((y - my) * k + N / 2).astype(np.intp)
        j = np.floor((x - mx) * k + N / 2).astype(np.intp)
        ok = (i >= 0) & (i < N) & (j >= 0) & (j < N)
        hist += np.bincount(i[ok] * N + j[ok], minlength=N * N)
    return hist.reshape(N, N)


def region(field: Field, level: float, corner: Vec, min_area: float = 4.0) -> Path:
    """Even-odd path of the smooth region where `field` >= `level`, with the grid's top-left
    cell centred on `corner`; islands under `min_area` square units are dropped."""
    d = P()
    padded = np.pad(field, 1, constant_values=field.min())
    rings = iso_lines(padded, level, cell=CELL, origin=corner - (CELL, CELL), simplify=0.25 * CELL)
    for ring in rings:
        u, v = ring[:-1, 0], ring[:-1, 1]
        area = 0.5 * abs(np.dot(u, np.roll(v, -1)) - np.dot(v, np.roll(u, -1)))
        if len(u) > 3 and area > min_area:
            d.poly(ring[:-1], closed=True)
    return d


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Attractor]) -> None:
    p = s.params
    # right of centre on a landscape screen, the left kept for windows; high on a portrait one
    c = s.pick(landscape=(0.6875, 0.5), portrait=(0.5, 0.42))
    corner = c - (SIZE / 2 - CELL / 2, SIZE / 2 - CELL / 2)
    lg = np.log1p(gaussian_filter(density(p, s.np_rng(1)), 0.7))
    for (lvl, sigma), tone in zip(LEVELS, TONES, strict=True):
        s.fill(region(gaussian_filter(lg, sigma), lvl, corner), tone, rule="evenodd")

    # The picked-out fold is the largest dense blob, with a rim hugging it; opening with a
    # line along the fold strips the ridges that cross it.
    la = gaussian_filter(lg, 1.5)
    head, tail = polar((12, 12), 12, deg=p.fold), polar((12, 12), 12, deg=p.fold + 180)
    streak = np.zeros((25, 25), bool)
    streak[line(round(tail.y), round(tail.x), round(head.y), round(head.x))] = True
    blobs, _ = label(binary_opening(la >= CORE, streak))
    sizes = np.bincount(blobs.ravel())
    sizes[0] = 0
    core = binary_fill_holes(binary_closing(blobs == sizes.argmax(), disk(4)))
    near = binary_dilation(core, disk(10))
    halo = binary_opening((la >= HALO) & near, streak) | binary_dilation(core, disk(2))
    for mask, tone in ((halo, ACCENT_2), (core, ACCENT)):
        s.fill(region(gaussian_filter(mask * 1.0, 2.5), 0.5, corner, 8), tone, rule="evenodd")
