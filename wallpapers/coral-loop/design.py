"""Differential growth: a closed line folds into a coral outline inside two smoothed offsets."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree
from shapely import Polygon

from walldye import ACCENT, ACCENT_8, UI, UI_ALT, Canvas, NpRng, P, design
from walldye.geom import Affine

type Pts = NDArray[np.float64]

SEED, SCALE = 5, 1.7  # growth stream; canvas units per simulation unit
REPEL, REST, TARGET, RATE = 26, 7, 1050, 0.01
# A soft lobed ellipse keeps the coral from rounding into a disc: long axis toward the lower
# right, semi-axes in sim units, lobes as (harmonic, amplitude, phase).
HEADING, AXES = math.radians(24), (150, 105)
LOBES = ((2, 0.14, 0.6), (3, 0.16, 2.1), (5, 0.07, 4.0))
ECHOES = ((50, UI), (20, UI_ALT))  # outermost first: offset from the outline, stroke
TURN = 56  # degrees clockwise on portrait screens, standing the long axis nearly upright


def bound(p: Pts) -> Pts:
    """Containment radius along each point's direction from the origin."""
    ang = np.arctan2(p[:, 1], p[:, 0]) - HEADING
    a, b = AXES
    r = a * b / np.hypot(b * np.cos(ang), a * np.sin(ang))
    return r * (1 + sum(amp * np.cos(k * ang + ph) for k, amp, ph in LOBES))


def grow(rng: NpRng) -> Pts:
    """Closed differential-growth line around the origin, in simulation units."""
    a = np.linspace(0, 2 * np.pi, 30, endpoint=False)
    p = 20 * np.column_stack([np.cos(a), np.sin(a)])
    settle = 150
    while settle:
        n = len(p)
        prev, nxt = np.roll(p, 1, 0), np.roll(p, -1, 0)
        e = nxt - p
        el = np.linalg.norm(e, axis=1, keepdims=True) + 1e-6
        spring = e / el * (el - REST) * 0.25
        force = spring - np.roll(spring, 1, 0) + 0.3 * ((prev + nxt) / 2 - p)
        # near-neighbours (gap 3+) repel too: that chain stiffness is what stops node-scale zigzags
        i, j = cKDTree(p).query_pairs(REPEL, output_type="ndarray").T
        gap = np.abs(i - j)
        keep = np.minimum(gap, n - gap) > 2
        i, j = i[keep], j[keep]
        d = p[i] - p[j]
        dist = np.linalg.norm(d, axis=1, keepdims=True) + 1e-6
        push = d / dist * (REPEL - dist) / REPEL * 0.5
        np.add.at(force, i, push)
        np.add.at(force, j, -push)
        r = np.linalg.norm(p, axis=1)
        over = np.maximum(0, r - bound(p))[:, None]
        force -= p / (r[:, None] + 1e-6) * over * 0.1
        mag = np.linalg.norm(force, axis=1, keepdims=True)
        p = p + force * np.minimum(1, 1.5 / (mag + 1e-6)) + rng.normal(0, 0.03, p.shape)
        if n < TARGET:
            # split edges at random, favouring uncrowded ones so the tips grow and the core settles
            crowd = np.bincount(np.concatenate([i, j]), minlength=n)
            nxt = np.roll(p, -1, 0)
            w = np.linalg.norm(nxt - p, axis=1) / (1 + crowd)
            idx = np.sort(rng.choice(n, max(1, int(n * RATE)), replace=False, p=w / w.sum()))
            p = np.insert(p, idx + 1, (p[idx] + nxt[idx]) / 2, axis=0)
        else:
            settle -= 1
    return p


def chaikin(pts: Pts, n: int = 3) -> Pts:
    """Corner-cut a closed ring `n` times so offset rings lose their channel-mouth kinks."""
    for _ in range(n):
        q = np.roll(pts, -1, 0)
        pts = np.stack([0.75 * pts + 0.25 * q, 0.25 * pts + 0.75 * q], 1).reshape(-1, 2)
    return pts


@design(aspects="any")
def draw(s: Canvas) -> None:
    # left third on a landscape screen, leaving the right for windows; portrait: below the clock
    c = s.pick(landscape=(1 / 3, 14 / 27), portrait=(0.5, 0.56))
    p = gaussian_filter1d(grow(s.np_rng(SEED)), 2, axis=0, mode="wrap") * SCALE
    if not s.landscape:
        p = Affine.rotate(deg=TURN).apply(p)
    p = p - (p.min(0) + p.max(0)) / 2 + c  # centre the bounding box on c
    coral = Polygon(p)
    for dist, tone in ECHOES:
        # overshoot then shrink back so the ring rounds off channel mouths instead of forming cusps
        ring = coral.buffer(dist + 28, quad_segs=32).buffer(-28, quad_segs=32).simplify(0.8)
        assert isinstance(ring, Polygon)  # a net outward offset of one polygon stays one polygon
        pts = chaikin(np.asarray(ring.exterior.coords)[:-1])
        s.stroke(P().poly(pts, closed=True), tone, 1.3)
    s.path(
        P().spline(p, closed=True),
        fill=ACCENT_8,
        stroke=ACCENT,
        stroke_width=1.7,
        stroke_linejoin="round",
    )
