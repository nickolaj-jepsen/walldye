"""Vogel's sunflower spiral of dots rising from a corner, with the Fibonacci florets along one ray and their neighbours picked out."""

import math

import numpy as np
from scipy.spatial import cKDTree

from walldye import ACCENT, ACCENT_2, ACCENT_3, BG, BG_ALT, Canvas, Vec, design, ladder, mix

N, C = 2800, 18.9  # florets; spacing, so the head's radius is C * sqrt(N), about 1000
DIVERGENCE = 2 * math.pi / ((1 + 5**0.5) / 2) ** 2  # 2 pi / phi^2 radians between florets
FIB = (377, 610, 987, 1597, 2584)  # florets that land on the ray at angle 0
# angle between that ray and the long side of the screen: 16:9's diagonal
RAY = math.degrees(math.atan2(9, 16))
# body in BG_ALT, the outer 15% dissolving toward the background
FADE = ladder((BG_ALT, mix(BG, BG_ALT, 0.5)), 4)
TONES = (*FADE, ACCENT_3, ACCENT_2, ACCENT)
RING, LEAD_RING, HOT = 4, 5, 6  # indices into TONES


@design(aspects="any")
def draw(s: Canvas) -> None:
    # centre just off the lower right corner, so the tiny central florets are cropped
    c = Vec(s.w + 40, s.h + 30)
    # the ray points up and to the left, into the screen
    tilt = math.radians(180 + (RAY if s.landscape else 90 - RAY))
    i = np.arange(1, N + 1)
    r, a = C * np.sqrt(i), i * DIVERGENCE + tilt
    pts = c + r[:, None] * np.c_[np.cos(a), np.sin(a)]
    size = 1.2 + 6 * np.sqrt(i / N)
    half = np.asarray(s.center)
    seen = (np.abs(pts - half) < half + size[:, None]).all(axis=1)
    tone = FADE.rung((r / r[-1] - 0.85) / 0.15)

    # each Fibonacci floret with its six nearest neighbours; the outermost rosette leads the
    # chain, larger and with brighter neighbours
    tree = cKDTree(pts)
    hot = [k - 1 for k in FIB]
    for h in hot:
        lead = h == hot[-1]
        ring = [k for k in tree.query(pts[h], 7)[1][1:] if k not in hot]
        tone[ring], tone[h] = LEAD_RING if lead else RING, HOT
        rosette = [h, *ring]
        size[rosette] = np.maximum(size[rosette], 3) * (1.2 if lead else 1)

    with s.buckets(TONES, "fill") as b:
        for k in np.flatnonzero(seen):
            b[tone[k]].circle(pts[k], size[k])
