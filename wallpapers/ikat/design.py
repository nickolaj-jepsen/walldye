"""Warp ikat: a stepped double diamond with bleeding dye edges."""

import numpy as np
from shapely.affinity import affine_transform
from shapely.geometry import LineString, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_5,
    BG,
    BG_ALT,
    UI,
    Buckets,
    Canvas,
    NpRng,
    P,
    Vec,
    design,
    mix,
)
from walldye.geom import parts

PITCH = 4
BUNDLE = 3  # threads tied and dyed together, so the resist pattern steps in bundles
HW, HH = 170, 400  # lozenge half-width and half-height at scale 1
GROUND = mix(BG, BG_ALT, 0.35)  # every other bare warp thread
# Dyed thread tones in drawing order: the echo's fringe and core, then the motif's far and near
# fringe steps and its two alternating core tones.
TONES = (
    mix(BG, BG_ALT, 0.7),
    mix(BG_ALT, UI, 0.5),
    ACCENT_5,
    ACCENT_3,
    mix(ACCENT, ACCENT_1, 0.12),
    ACCENT,
)
ECHO_FRINGE, ECHO_CORE, FAR, NEAR, CORE_ALT, CORE = range(len(TONES))


def stepped(hw: float, hh: float, n: int) -> BaseGeometry:
    """Staircase lozenge centered on the origin: n stacked boxes, widest in the middle."""
    return unary_union(
        [
            box(-hw * (k + 1) / n, -hh * (n - k) / n, hw * (k + 1) / n, hh * (n - k) / n)
            for k in range(n)
        ]
    )


def motif(c: Vec, k: float) -> BaseGeometry:
    """Two nested stepped rings, scaled by k and centered on c."""

    def ring(a: float, b: float, n: int) -> BaseGeometry:
        return stepped(HW * a, HH * a, n).difference(stepped(HW * b, HH * b, n))

    shape = unary_union([ring(1, 0.7, 8), ring(0.5, 0.26, 5)])
    return affine_transform(shape, [k, 0, 0, k, c.x, c.y])


def intervals(shape: BaseGeometry, x: float, h: float) -> list[tuple[float, float]]:
    """The (top, bottom) spans where the vertical line at x crosses shape, top to bottom."""
    hit = shape.intersection(LineString([(x, -10), (x, h + 10)]))
    ys = [(g.coords[0][1], g.coords[-1][1]) for g in parts(hit) if g.length > 0]
    return sorted((min(y), max(y)) for y in ys)


def smooth(rng: NpRng, n: int, half: int, lo: float, hi: float) -> np.ndarray:
    """Neighbor-correlated values in [lo, hi]: Gaussian noise under a Hanning window of 2*half+1 threads."""
    v = np.convolve(rng.normal(0, 1, n + 2 * half), np.hanning(2 * half + 1), mode="same")
    v = v[half:-half]
    v = (v - v.min()) / (v.max() - v.min())
    return lo + (hi - lo) * v


def dye(
    b: Buckets,
    shape: BaseGeometry,
    rng: NpRng,
    cores: tuple[int, int],
    fringe: tuple[int, ...],
    n: int,
    h: float,
    amp: float = 9,
) -> None:
    """Dye shape into n warp threads: core spans into b[cores] (alternating by thread), then
    each fringe tone in turn steps outward from both ends of a span."""
    # coherent waves along the weft, plus a small slip per tied bundle and per thread
    slip = np.repeat(rng.uniform(-3, 3, n // BUNDLE + 1), BUNDLE)
    top = smooth(rng, n, 6, -amp, amp) + slip[:n]
    bot = smooth(rng, n, 6, -amp, amp) + slip[:n]
    reach = [smooth(rng, n, 5, 1, 4) for _ in fringe]
    for i in range(n):
        x = i * PITCH + PITCH / 2
        segs = [
            (y1 + top[i] + rng.uniform(-1, 1), y2 + bot[i] + rng.uniform(-1, 1))
            for y1, y2 in intervals(shape, (i // BUNDLE + 0.5) * BUNDLE * PITCH, h)
        ]
        for j, (y1, y2) in enumerate(segs):
            b[cores[i % 2]].M(x, y1).V(y2)
            # each fringe tone steps outward, never past halfway to the neighboring span
            room_up = (y1 - segs[j - 1][1]) / 2 if j else 99
            room_dn = (segs[j + 1][0] - y2) / 2 if j + 1 < len(segs) else 99
            for start, sgn, space in ((y1, -1, room_up), (y2, 1, room_dn)):
                end, room = start, space
                for tone, r in zip(fringe, reach, strict=True):
                    ln = min(r[i] + rng.uniform(0, 6) ** 2 / 6, room)
                    if ln > 0.5:
                        b[tone].M(x, end).V(end + sgn * ln)
                    end, room = end + sgn * ln, room - ln


@design(aspects="any")
def draw(s: Canvas) -> None:
    rng = s.np_rng(11)
    n = s.w // PITCH
    ground = P()
    for i in range(1, n, 2):
        ground.M(i * PITCH + PITCH / 2, 0).V(s.h)
    s.stroke(ground, GROUND, 3)
    main = s.pick(landscape=(620 / 1920, 0.5), portrait=(0.4, 0.38))
    # the echo runs off the right edge, staggered below the motif
    echo = Vec(s.w - 40, s.h * (2 / 3 if s.landscape else 0.68))
    with s.buckets(TONES, "stroke", stroke_width=PITCH + 0.5) as b:
        dye(b, motif(echo, 0.6), rng, (ECHO_CORE, ECHO_CORE), (ECHO_FRINGE,), n, s.h)
        dye(b, motif(main, 0.95), rng, (CORE, CORE_ALT), (NEAR, FAR), n, s.h)
