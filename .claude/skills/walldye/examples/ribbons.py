"""Fidenza-style ribbons: streamlines grown through a Perlin flow field, kept apart by an occupancy grid, with one accent school."""

import math

import numpy as np
from shapely.geometry import LineString
from shapely.ops import unary_union

from walldye import ACCENT, ACCENT_1, ACCENT_3, BG_ALT, UI, H, P, W, Noise, poisson_disk, rng, smoothstep

ASPECTS = ["any"]

CELL = 4  # occupancy grid resolution
STEP = 6  # streamline step length
PAD = 80  # ribbons may run this far past the frame so they leave it cleanly
MARGIN = 10  # gap between neighbouring ribbons
HALO = 26  # wider gap kept clear around the accent school
FIELD = 8  # flow field sample spacing
TONES = (BG_ALT, UI, ACCENT_3, ACCENT_1, ACCENT)  # paint order; ribbons refer to these by index


def draw(s):
    r, noise = rng(11), Noise(11)
    field = np.array(
        [[noise.fbm(x / 880, y / 880, 2, gain=0.35) for x in range(-PAD, W + PAD + FIELD, FIELD)] for y in range(-PAD, H + PAD + FIELD, FIELD)]
    )
    field -= field.mean()
    occ = np.zeros(((H + 2 * PAD) // CELL + 2, (W + 2 * PAD) // CELL + 2), bool)

    def angle(x, y):
        # the current enters calm on the left and gathers swirl across the first half of the frame
        gain = 1.5 * (0.3 + 0.7 * smoothstep(0.05 * W, 0.47 * W, x))
        return gain * field[int((y + PAD) / FIELD), int((x + PAD) / FIELD)]

    def disk(x, y, rad):
        """Slice of `occ` around (x, y) and the boolean disk of radius `rad` within it."""
        i0, j0 = max(int((y + PAD - rad) / CELL), 0), max(int((x + PAD - rad) / CELL), 0)
        i1, j1 = min(int((y + PAD + rad) / CELL) + 2, occ.shape[0]), min(int((x + PAD + rad) / CELL) + 2, occ.shape[1])
        yy, xx = np.ogrid[i0:i1, j0:j1]
        return (slice(i0, i1), slice(j0, j1)), (yy * CELL - PAD - y) ** 2 + (xx * CELL - PAD - x) ** 2 <= rad * rad

    def free(x, y, rad):
        sl, mask = disk(x, y, rad)
        return -PAD < x < W + PAD and -PAD < y < H + PAD and not (occ[sl] & mask).any()

    def grow(x, y, w, back, fwd):
        """Trace the streamline through (x, y) up to `back`/`fwd` units each way, stopping at any neighbour."""
        if not free(x, y, w / 2):
            return None
        halves = []
        for sign, length in ((1, fwd), (-1, back)):
            px, py, half = x, y, []
            for _ in range(int(length / STEP)):
                a = angle(px, py)
                px, py = px + sign * STEP * math.cos(a), py + sign * STEP * math.sin(a)
                if not free(px, py, w / 2):
                    break
                half.append((px, py))
            halves.append(half)
        return halves[1][::-1] + [(x, y)] + halves[0]

    def stamp(line, w, margin):
        for x, y in line:
            sl, mask = disk(x, y, w / 2 + margin)
            occ[sl] |= mask

    # The school sits high on the right; on narrow screens it shortens and slides inwards so both
    # ragged ends stay in frame. It is laid first so the BG_ALT current parts around it.
    k = min(1.0, W / 1500)
    ax, ay = min(0.72 * W, W - 520 * k), 0.24 * H
    a = angle(ax, ay) + math.pi / 2  # stack the ribbons across the local flow
    ribbons, off = [], 0.0
    school = [(8, 2, 400, 360), (14, 3, 440, 470), (28, 4, 470, 420), (12, 3, 430, 330), (6, 2, 460, 400)]
    for w, t, back, fwd in school:
        off += w / 2
        line = grow(ax + off * math.cos(a), ay + off * math.sin(a), w, back * k, fwd * k)
        off += w / 2 + MARGIN + 3
        if line:
            ribbons.append((line, w, t))
    for line, w, _ in ribbons:
        stamp(line, w, HALO)
    halo = unary_union([LineString(line).buffer(w / 2) for line, w, _ in ribbons])

    # Seeds near the vertical centre line go first and run long, so most ribbons cross the frame edge to edge.
    seeds = poisson_disk(r, W + 2 * PAD, H + 2 * PAD, 52, x0=-PAD, y0=-PAD)
    seeds.sort(key=lambda p: abs(p[0] - W / 2) + r.uniform(0, 0.36 * W))
    for x, y in seeds:
        w = r.choice([6, 8, 10, 12, 16, 20, 24, 30])
        length = r.uniform(0.47, 1.25) * W + 400
        line = grow(x, y, w, length / 2, length / 2)
        if line and len(line) * STEP > min(480, 0.4 * W):
            stamp(line, w, MARGIN)
            # a few thin ribbons are lifted to UI so the field has some depth, but never next to the accent
            lifted = w <= 12 and r.random() < 0.15 and LineString(line).distance(halo) > 150
            ribbons.append((line, w, 1 if lifted else 0))

    for i, tone in enumerate(TONES):
        d = P()
        for line, w, t in ribbons:
            if t == i:
                d.poly(LineString(line).buffer(w / 2).simplify(0.5).exterior.coords, closed=True)
        s.path(d, fill=tone)
