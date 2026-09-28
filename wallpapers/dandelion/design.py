"""A dandelion clock of foreshortened hairline rays on a Fibonacci sphere, with six seeds drifting off its bald side."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_1,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    NpRng,
    P,
    Path,
    Vec,
    design,
    mix,
)
from walldye.geom import Affine, Polyline, bezier_points, ribbon

type Arr = NDArray[np.float64]

R, N = 190, 260  # head radius; seeds on the head
TILT = (0.35, 0.2)  # the head's turn about x and y, radians
BEAK, FIL = 0.66, 0.34  # beak and pappus-hair lengths, in head radii
SPREAD, DRIFT_SPREAD = math.radians(38), math.radians(62)  # pappus half-angle: packed, then open
GAP_HALF = math.radians(20)  # half-width of the bald patch that faces the drift
# back rays dim and thinned so the radial structure reads; only the silhouette umbrellas catch light
BEAK_TONES = (BG_ALT, UI, UI, UI)
HAIR_TONES = (UI, mix(UI, UI_ALT, 0.5), UI_ALT, UI_HI)
# drifting seeds: tilt from vertical, turn towards the viewer, size, pappus scale, tone, stroke
DRIFT = (
    (-0.22, 0.4, 0.86, 1.0, UI_ALT, 1.2),
    (0.18, -0.5, 0.87, 1.0, UI_ALT, 1.2),
    (-0.08, 0.7, 0.88, 1.0, UI_HI, 1.2),
    (0.30, 0.2, 0.9, 1.0, UI_HI, 1.2),
    (-0.20, -0.6, 0.92, 1.0, ACCENT_1, 1.6),
    (0.42, 0.5, 1.0, 1.15, ACCENT, 1.6),
)
# The drift at 16:9, from its start on the head's rim: a steep lift that eases off. Other screens
# turn and scale it to fit.
CURVE = ((0, 0), (200, -75), (540, -150), (1005, -200))
# where each seed sits along the 16:9 drift (1027 long); the gaps grow about 1.4x each, so the
# last seed, at the far end, clearly breaks free
ALONG = (70, 165, 295, 475, 725, 1027)
STEM = ((0, 0), (12, 230), (70, 390), (44, 562))  # the stem at 16:9, from the head down


def rot(ax: float, ay: float) -> Arr:
    """The 3x3 rotation that turns by `ay` about y, then by `ax` about x (radians)."""
    ca, sa, cb, sb = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay)
    return np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]]) @ np.array(
        [[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]]
    )


def basis(d: Arr) -> tuple[Arr, Arr]:
    """Two unit vectors perpendicular to the unit vector `d` and to each other."""
    u = np.cross(d, [0, 0, 1] if abs(d[2]) < 0.9 else [1, 0, 0])
    u /= np.linalg.norm(u)
    return u, np.cross(d, u)


def seed(d: Arr, rng: NpRng, nf: int, spread: float, fil: float) -> tuple[Arr, Arr, Arr]:
    """Beak start, beak tip and the (nf, 3) pappus-hair ends, in head radii, of a seed along the
    unit vector `d`; the hairs fan out `spread` radians from it."""
    tip = d * BEAK
    u, v = basis(d)
    hairs = []
    for k in range(nf):
        phi = 2 * math.pi * (k + rng.uniform(-0.2, 0.2)) / nf
        f = math.cos(spread) * d + math.sin(spread) * (math.cos(phi) * u + math.sin(phi) * v)
        hairs.append(tip + f * fil * rng.uniform(0.85, 1.05))
    return d * 0.07, tip, np.array(hairs)


def hang(p: Arr, anchor: Vec, d: Arr, scale: float) -> Arr:
    """Screen points of the (N, 3) seed points `p`, scaled by `scale` and hung so the point
    0.35 along the seed's axis `d` lands on `anchor`."""
    return anchor + scale * (p[:, :2] - d[:2] * 0.35)


def achene(p: Vec, q: Vec) -> Path:
    """Spindle-shaped seed body from `p` (beak end) to `q`."""
    ax = q - p
    n = ax.perp().unit() * 2.6
    return P().poly([p, p + ax * 0.45 + n, q + ax * 0.08, p + ax * 0.45 - n], closed=True)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: head on the left third, seeds blown right; portrait: head low, seeds blown up
    c = s.pick(landscape=(7 / 24, 13 / 27), portrait=(0.3, 0.64))
    gap = -30 if s.landscape else -35  # screen angle of the bald patch, degrees
    rng = s.np_rng(4)

    def at(p: Arr) -> Vec:
        return Vec(c.x + R * p[0], c.y + R * p[1])

    # stem: a sliver that thickens towards the ground, stretched to reach the bottom edge
    reach = (s.h + 2 - c.y) / STEM[-1][1]
    spine = bezier_points(c + reach * np.array(STEM), 39)
    s.fill(P().poly(ribbon(spine, np.linspace(2.4, 5.6, 40)), closed=True), UI)

    i = np.arange(N) + 0.5
    y = 1 - 2 * i / N
    r = np.sqrt(1 - y * y)
    th = math.pi * (3 - math.sqrt(5)) * i
    dirs = np.c_[r * np.cos(th), y, r * np.sin(th)] @ rot(*TILT).T
    stubs = P()
    with (
        s.buckets(BEAK_TONES, "stroke", stroke_width=1.1, stroke_linecap="round") as beaks,
        s.buckets(HAIR_TONES, "stroke", stroke_width=1, stroke_linecap="round") as hairs,
    ):
        for d in dirs[np.argsort(dirs[:, 2], kind="stable")]:  # back to front
            flat = math.hypot(d[0], d[1])
            off = abs(math.remainder(math.atan2(d[1], d[0]) - math.radians(gap), math.tau))
            # only the near hemisphere is bald, so the dim back rays still show through the gap
            bald = flat > 0.3 and off < GAP_HALF + rng.uniform(-0.06, 0.06)
            if bald and d[2] > -0.35:
                # the seeds that left bared their stalks
                stubs.M(at(d * 0.08)).L(at(d * rng.uniform(0.28, 0.4)))
                continue
            if d[2] < -0.35 and rng.random() < (0.6 if bald else 0.4):
                continue
            band = 3 if flat > 0.975 else min(2, int((d[2] + 1) / 2 * 3))
            a, tip, ends = seed(d, rng, int(rng.integers(8, 13)), SPREAD, FIL)
            beaks[band].M(at(a)).L(at(tip))
            for e in ends:
                hairs[band].M(at(tip)).L(at(e))
    s.stroke(stubs, UI_ALT, 1.4, cap="round")
    s.fill(P().circle(c, 9), UI)

    # The drift leaves the head's rim beside the bald patch and ends in the upper corner. On a
    # portrait screen its bow flips, so the seeds head out sideways before rising instead of
    # stacking up above the head.
    start = c + Vec(180, -90).rotate(deg=gap + 30)
    end = Vec(min(s.w - 175, start.x + 1500), 230) if s.landscape else s.frac(0.84, 0.12)
    chord, base = end - start, Vec(*CURVE[-1])
    drift = (
        Affine.frame(start, rad=math.atan2(chord.y, chord.x), scale=abs(chord) / abs(base))
        @ Affine.scale(1, 1 if s.landscape else -1)
        @ Affine.rotate(rad=-math.atan2(base.y, base.x))
    )
    line = Polyline(bezier_points(drift.apply(CURVE), 799))
    anchors = line.at(np.array(ALONG) / ALONG[-1] * line.length)
    for (x, y0), (tilt, spin, size, fil, tone, sw) in zip(anchors.tolist(), DRIFT, strict=True):
        d = np.array(
            [math.sin(tilt) * math.cos(spin), -math.cos(tilt), math.sin(tilt) * math.sin(spin)]
        )
        a, tip, ends = seed(d, rng, 14, DRIFT_SPREAD, FIL * fil)
        anchor, scale = Vec(x, y0), R * size
        foot, t0, body = (Vec(*q) for q in hang(np.array([a, tip, a - d * 0.13]), anchor, d, scale))
        # pappus hairs curl slightly upward towards their tips
        bends = t0 + (hang(ends, anchor, d, scale) - t0) * 0.55
        curled = hang(ends + d * 0.05, anchor, d, scale)
        pappus = P()
        for q, e in zip(bends.tolist(), curled.tolist(), strict=True):
            pappus.M(t0).Q(Vec(*q), Vec(*e))
        s.stroke(P().M(foot).L(t0), mix(tone, UI, 0.35), sw, cap="round")
        s.stroke(pappus, tone, sw, cap="round")
        s.fill(achene(foot, body), tone)
