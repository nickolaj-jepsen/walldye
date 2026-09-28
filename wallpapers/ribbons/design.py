"""Fidenza-style ribbons of mixed widths, grown as streamlines through a Perlin flow field and kept from touching by an occupancy grid, with one school of five picked out."""

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

CELL = 4  # occupancy grid cell
STEP = 6  # streamline step length
FIELD = 8  # flow field sample spacing
MARGIN = 10  # gap between neighbouring ribbons
HALO = 26  # wider gap kept clear around the school
TONES = (BG_ALT, UI, ACCENT_3, ACCENT_1, ACCENT)  # paint order; ribbons refer to these by index
# the school, stacked across the flow: width, tone index, length back and forward along it
SCHOOL = (
    (8, 2, 400, 360),
    (14, 3, 440, 470),
    (28, 4, 470, 420),
    (12, 3, 430, 330),
    (6, 2, 460, 400),
)
WIDTHS = (6, 8, 10, 12, 16, 20, 24, 30)
HOME = Vec(1390, 260)  # the school's place in the noise, where the field gives it an S-bend

type Line = list[tuple[float, float]]


@design(aspects="any")
def draw(s: Canvas) -> None:
    rng, noise = s.rng(11), s.noise(11)
    # The school sits high on the right, its forward ends reaching about 430 units past the
    # anchor; on narrow screens it shortens and moves inwards so both ends stay in frame.
    k = min(1.0, s.w / 1500)
    at = s.pick(landscape=(0.73, 0.2407), portrait=(0.62, 0.3))
    anchor = Vec(min(at.x, s.w - 430 * k - 100), at.y)
    # fBm on the field grid, which starts 40 units outside the frame; a feature spans ~880 units.
    # The noise shifts by whole cells to keep HOME under the school on every screen.
    cols, rows = s.w // FIELD + 12, s.h // FIELD + 12
    shift = anchor - HOME
    xs = np.arange(cols) - round(shift.x / FIELD)
    ys = np.arange(rows) - round(shift.y / FIELD)
    field = noise.fbm(xs[None, :] / 110, ys[:, None] / 110, 2, gain=0.35)
    field -= field.mean()
    occ = np.zeros((s.h // CELL + 1, s.w // CELL + 1), bool)  # tracks the frame only
    calm, swirl = 0.052 * s.w, 0.47 * s.w

    def heading(x: float, y: float) -> float:
        """The flow direction at (x, y) in radians: nearly level at the left edge, turning
        more freely from `calm` to `swirl` across the frame."""
        gain = 1.5 * (0.3 + 0.7 * smoothstep(calm, swirl, x))
        i = int((min(max(y, -40), s.h + 40) + 40) / FIELD)
        j = int((min(max(x, -40), s.w + 40) + 40) / FIELD)
        return gain * float(field[i, j])

    def disk(x: float, y: float, rad: float) -> tuple[tuple[slice, slice], NDArray[np.bool_]]:
        """The slice of `occ` around (x, y) and the disk of radius `rad` within it."""
        i0, j0 = max(int((y - rad) / CELL), 0), max(int((x - rad) / CELL), 0)
        i1 = min(max(int((y + rad) / CELL) + 2, i0), occ.shape[0])
        j1 = min(max(int((x + rad) / CELL) + 2, j0), occ.shape[1])
        yy, xx = np.ogrid[i0:i1, j0:j1]
        inside = (yy * CELL - y) ** 2 + (xx * CELL - x) ** 2 <= rad * rad
        return (slice(i0, i1), slice(j0, j1)), inside

    def free(x: float, y: float, rad: float) -> bool:
        if not (-60 < x < s.w + 60 and -60 < y < s.h + 60):
            return True
        sl, inside = disk(x, y, rad)
        return not (occ[sl] & inside).any()

    def grow(x: float, y: float, w: float, back: float, fwd: float) -> Line | None:
        """The streamline through (x, y), up to `back` and `fwd` units each way, stopping at a
        neighbour or past the frame; None when (x, y) itself is taken."""
        if not free(x, y, w / 2):
            return None
        halves: list[Line] = []
        for sign, length in ((1, fwd), (-1, back)):
            px, py, half = x, y, []
            for _ in range(int(length / STEP)):
                a = heading(px, py)
                px, py = px + sign * STEP * math.cos(a), py + sign * STEP * math.sin(a)
                if not free(px, py, w / 2) or not (-80 < px < s.w + 80 and -80 < py < s.h + 80):
                    break
                half.append((px, py))
            halves.append(half)
        return [*halves[1][::-1], (x, y), *halves[0]]

    def stamp(line: Line, w: float, margin: float) -> None:
        for x, y in line:
            if -60 < x < s.w + 60 and -60 < y < s.h + 60:
                sl, inside = disk(x, y, w / 2 + margin)
                occ[sl] |= inside

    # The school is laid first so the current parts around it.
    across = heading(anchor.x, anchor.y) + math.pi / 2
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

    # Seeds near the vertical centre line go first and run long, so most ribbons cross the
    # frame edge to edge.
    seeds = poisson_disk(Rect(-60, -60, s.w + 120, s.h + 120), 52, rng).tolist()
    seeds.sort(key=lambda p: abs(p[0] - s.w / 2) + rng.uniform(0, 0.365 * s.w))
    for x, y in seeds:
        w = rng.choice(WIDTHS)
        length = rng.uniform(0.47 * s.w, 1.25 * s.w)
        line = grow(x, y, w, length / 2, length / 2)
        if line and len(line) * STEP > 0.25 * s.w:
            stamp(line, w, MARGIN)
            # a few thin ribbons are lifted to UI for depth, but never beside the school
            lifted = w <= 12 and rng.random() < 0.15 and LineString(line).distance(halo) > 150
            ribbons.append((line, w, 1 if lifted else 0))

    with s.buckets(TONES, "fill") as fills:
        for line, w, t in ribbons:
            fills[t].shape(LineString(line).buffer(w / 2).simplify(0.5))
