"""A damped, slightly detuned harmonograph trace whose last inward turns step up in tone around a pen-stop in its eye."""

from itertools import pairwise
from typing import Literal

import numpy as np
import shapely
from scipy.signal import argrelmin
from scipy.spatial import cKDTree
from shapely.geometry import LineString

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_5,
    BG_ALT,
    UI,
    Canvas,
    P,
    Params,
    Rect,
    design,
    knob,
    ladder,
)
from walldye.field import cells


class Pendulums(Params):
    ratio: Literal["2:3", "1:2", "1:3"] = knob(
        default="2:3", doc="frequency ratio of the two pendulums on each axis"
    )


VARIANTS = {"octave": Pendulums(ratio="1:2"), "twelfth": Pendulums(ratio="1:3")}

# Per ratio: the phases of three of the four swings, chosen for a figure with a clear eye.
PHASES = {"2:3": (0.3, 1.7, 0.9), "1:2": (1.6, 0.4, 0.4), "1:3": (0.0, 1.2, 1.2)}
T, N = 320, 40000  # pen time and samples
D, DETUNE = 0.0055, 1.0015  # damping; the second pendulum's slight detune makes the loops precess
A, B = 205, 140  # amplitudes of the two swings on each axis
TONES = ladder((BG_ALT, UI, ACCENT_5, ACCENT_3, ACCENT_2, ACCENT), 16)
# Where each stop sits along the trace: the outer 60% only fades from BG_ALT to UI, the last 40%
# climbs the accent ladder.
ALONG = ((0, 0.6, 0.7, 0.8, 0.9, 1), (0, 0.2, 0.4, 0.6, 0.8, 1))
TURNS = 3  # the pen-stop is searched for inside the hull of this many last turns


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Pendulums]) -> None:
    p1, p2, p3 = PHASES[s.params.ratio]
    fp, fq = (int(v) for v in s.params.ratio.split(":"))
    # the faster swing always turns at 3 radians per unit time, so every figure has as many loops
    w1, w2 = 3 * fp / fq, 3
    # left third on a landscape screen; centered above the middle on a portrait one
    c = s.pick(landscape=(590 / 1920, 0.5), portrait=(0.5, 0.42))
    t = np.linspace(0, T, N)
    e = np.exp(-D * t)
    # mirrored so the long lobe reaches into the empty bottom-left corner
    x = -e * (A * np.sin(w1 * t + p1) + B * np.sin(w2 * DETUNE * t + p2))
    y = e * (A * np.sin(w2 * t) + B * np.sin(w1 * DETUNE * t + p3))
    # chunks break where the pen passes closest to the rest point, so tone steps hide in the core
    cuts = argrelmin(np.hypot(x, y))[0]
    end = cuts[-1]
    pts = np.column_stack([x, y])
    pts -= (pts.min(axis=0) + pts.max(axis=0)) / 2  # the figure's bounding box centered on c
    with s.buckets(TONES, "stroke", stroke_width=1.2) as b:
        for a, z in pairwise([0, *cuts]):
            line = LineString(pts[a : z + 1] + c).simplify(0.35)
            b[TONES.rung(float(np.interp((a + z) / 2 / end, *ALONG)))].poly(line.coords)
    # the last turns rim the eye, so the pen-stop sits at the point inside them farthest from
    # any line
    hull = LineString(pts[cuts[-TURNS - 1] : end + 1]).convex_hull
    x0, y0, x1, y1 = hull.bounds
    gx, gy = cells(Rect(x0, y0, x1 - x0, y1 - y0), 1)
    inside = shapely.contains_xy(hull, gx, gy)
    eye = np.column_stack([gx[inside], gy[inside]])
    gap, _ = cKDTree(pts[: end + 1]).query(eye)
    s.fill(P().circle(c + eye[gap.argmax()], 4), ACCENT)
