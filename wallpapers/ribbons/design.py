"""Fidenza-style ribbons: streamlines grown through a Perlin flow field, kept apart by an occupancy grid, with one school picked out."""

import math

import numpy as np
from numpy.typing import NDArray
from shapely import LineString
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    BG_ALT,
    UI,
    Canvas,
    Rect,
    Vec,
    design,
    polar,
    smoothstep,
)
from walldye.geom import poisson_disk

CELL = 4  # occupancy grid resolution
STEP = 6  # streamline step length
PAD = 80  # ribbons may run this far past the frame so they leave it cleanly
MARGIN = 10  # gap between neighboring ribbons
HALO = 26  # wider gap kept clear around the picked-out school
FIELD = 8  # flow field sample spacing
TONES = (BG_ALT, UI, ACCENT_3, ACCENT_1, ACCENT)  # paint order; ribbons refer to these by index
# the school, laid across the flow: width, tone index, length back and forward along it
SCHOOL = (
    (8, 2, 400, 360),
    (14, 3, 440, 470),
    (28, 4, 470, 420),
    (12, 3, 430, 330),
    (6, 2, 460, 400),
)
WIDTHS = (6, 8, 10, 12, 16, 20, 24, 30)

type Line = list[tuple[float, float]]


@design(aspects="any")
def draw(s: Canvas) -> None:
    width, height = s.w, s.h
    rng, noise = s.rng(11), s.noise(11)
    xs = np.arange(-PAD, width + PAD + FIELD, FIELD)
    ys = np.arange(-PAD, height + PAD + FIELD, FIELD)
    field = noise.fbm(xs[None, :] / 880, ys[:, None] / 880, 2, gain=0.35)
    field -= field.mean()
    occ = np.zeros(((height + 2 * PAD) // CELL + 2, (width + 2 * PAD) // CELL + 2), bool)

    def heading(x: float, y: float) -> float:
        """The flow direction at (x, y) in radians: calm on the left, gathering swirl across
        the first half of the frame."""
        gain = 1.5 * (0.3 + 0.7 * smoothstep(0.05 * width, 0.47 * width, x))
        return gain * float(field[int((y + PAD) / FIELD), int((x + PAD) / FIELD)])

    def disk(x: float, y: float, rad: float) -> tuple[tuple[slice, slice], NDArray[np.bool_]]:
        """The slice of `occ` around (x, y) and the boolean disk of radius `rad` within it."""
        i0, j0 = max(int((y + PAD - rad) / CELL), 0), max(int((x + PAD - rad) / CELL), 0)
        i1 = min(int((y + PAD + rad) / CELL) + 2, occ.shape[0])
        j1 = min(int((x + PAD + rad) / CELL) + 2, occ.shape[1])
        yy, xx = np.ogrid[i0:i1, j0:j1]
        inside = (yy * CELL - PAD - y) ** 2 + (xx * CELL - PAD - x) ** 2 <= rad * rad
        return (slice(i0, i1), slice(j0, j1)), inside

    def free(x: float, y: float, rad: float) -> bool:
        sl, mask = disk(x, y, rad)
        return -PAD < x < width + PAD and -PAD < y < height + PAD and not (occ[sl] & mask).any()

    def grow(x: float, y: float, w: float, back: float, fwd: float) -> Line | None:
        """The streamline through (x, y), up to `back` and `fwd` units each way, stopping at
        any neighbor; None when (x, y) itself is taken."""
        if not free(x, y, w / 2):
            return None
        halves: list[Line] = []
        for sign, length in ((1, fwd), (-1, back)):
            px, py, half = x, y, []
            for _ in range(int(length / STEP)):
                a = heading(px, py)
                px, py = px + sign * STEP * math.cos(a), py + sign * STEP * math.sin(a)
                if not free(px, py, w / 2):
                    break
                half.append((px, py))
            halves.append(half)
        return [*halves[1][::-1], (x, y), *halves[0]]

    def stamp(line: Line, w: float, margin: float) -> None:
        for x, y in line:
            sl, mask = disk(x, y, w / 2 + margin)
            occ[sl] |= mask

    # The school sits high on the right; on narrow screens it shortens and slides inwards so
    # both ragged ends stay in frame. It is laid first so the current parts around it.
    k = min(1.0, width / 1500)
    anchor = Vec(min(0.72 * width, width - 520 * k), 0.24 * height)
    across = heading(*anchor) + math.pi / 2  # stack the ribbons across the local flow
    ribbons: list[tuple[Line, float, int]] = []
    off = 0.0
    for w, t, back, fwd in SCHOOL:
        off += w / 2
        start = polar(anchor, off, rad=across)
        line = grow(start.x, start.y, w, back * k, fwd * k)
        off += w / 2 + MARGIN + 3
        if line:
            ribbons.append((line, w, t))
    for line, w, _ in ribbons:
        stamp(line, w, HALO)
    halo = unary_union([LineString(line).buffer(w / 2) for line, w, _ in ribbons])

    # Seeds near the vertical center line go first and run long, so most ribbons cross the
    # frame edge to edge.
    seeds = poisson_disk(Rect(-PAD, -PAD, width + 2 * PAD, height + 2 * PAD), 52, rng).tolist()
    for x, y in sorted(seeds, key=lambda p: abs(p[0] - width / 2) + rng.uniform(0, 0.36 * width)):
        w = rng.choice(WIDTHS)
        length = rng.uniform(0.47, 1.25) * width + 400
        line = grow(x, y, w, length / 2, length / 2)
        if line and len(line) * STEP > min(480, 0.4 * width):
            stamp(line, w, MARGIN)
            # a few thin ribbons are lifted to UI so the field has some depth, but never next
            # to the school
            lifted = w <= 12 and rng.random() < 0.15 and LineString(line).distance(halo) > 150
            ribbons.append((line, w, 1 if lifted else 0))

    with s.buckets(TONES, "fill") as fills:
        for line, w, t in ribbons:
            fills[t].shape(LineString(line).buffer(w / 2).simplify(0.5))
