"""A felled trunk's end grain seen from one corner: noise-wobbled year rings as splines, one fire year and a drying check."""

import math

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import Polygon

from walldye import ACCENT, ACCENT_3, BG_ALT, BG_DEEP, UI, Canvas, Num, P, Vec, design

type Arr = NDArray[np.float64]

R_BARK = 1250
N = 46  # year rings; ring N lies under the bark
FIRE = 19  # ring index of the fire year (~60% out)
WIDE = (4, 8, 12, 27)  # fat years: three early, one rebound after the drought
CRACK = math.radians(-35)
# With the pith off the bottom-left corner, every on-canvas point of a ring lies in this sweep.
TH = np.linspace(math.radians(-100), math.radians(12), 150)
TH_FINE = np.linspace(TH[0], TH[-1], 700)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Portrait pulls the pith further left so the bark curves back into frame above the bottom edge.
    pith = Vec(-120 if s.landscape else -330, s.h + 100)
    rg = s.np_rng(11)
    n = s.noise(5)

    # Year widths: climate swings narrowing with age, a few fat years, and a drought run right after the fire.
    raw = (
        rg.lognormal(0, 0.3, N)
        * np.linspace(1.3, 0.75, N)
        * (1 + 0.15 * np.sin(np.arange(N) / 5 + 1.3))
    )
    med = np.median(raw)
    raw[list(WIDE)] *= rg.uniform(2.4, 3.0, len(WIDE))
    raw[FIRE + 1 : FIRE + 4] = med * np.array([0.5, 0.38, 0.45])
    radii = np.cumsum(raw) / raw.sum() * (R_BARK - 30) + 30

    def ring(k: int, r: Num | Arr, th: Arr = TH) -> Arr:
        """Points of ring `k` at radius `r` over the angles `th`; lobes and eccentric growth grow with age."""
        f = k / N
        wob = n.n3(np.cos(th) * 5, np.sin(th) * 5, k * 0.04)
        rr = r * (1 + 0.025 * f * wob) + 30 * f * np.cos(th + 0.6)
        return pith + np.column_stack((rr * np.cos(th), rr * np.sin(th)))

    frame = s.inset(-40)
    lo, hi = (frame.x, frame.y), (frame.x1, frame.y1)

    def seen(*lines: Arr) -> slice:
        """The index run where any of `lines` comes within 40 of the canvas, two points wider
        each side, so a spline through it matches the full spline on canvas."""
        near = np.any([np.all((p >= lo) & (p <= hi), axis=1) for p in lines], axis=0)
        hit = np.flatnonzero(near)
        return slice(max(int(hit[0]) - 2, 0), int(hit[-1]) + 3) if hit.size else slice(0, 0)

    def arc(k: int, r: Num) -> Arr:
        """Ring `k` trimmed to its on-canvas run (about 40% of each ring lies off it)."""
        pts = ring(k, r)
        return pts[seen(pts)]

    # Rings 0 (BG_ALT, about one in six) and 1 (UI); the innermost ones never reach the canvas.
    with s.buckets((BG_ALT, UI), "stroke", stroke_width=1.3, stroke_linecap="round") as rings:
        for k, r in enumerate(radii[:-1]):
            if k != FIRE:
                rings[0 if rg.random() < 0.18 else 1].spline(arc(k, r))
    s.stroke(P().spline(arc(FIRE, radii[FIRE] + 5)), ACCENT_3, 1.5, cap="round")
    s.stroke(P().spline(arc(FIRE, radii[FIRE])), ACCENT, 3, cap="round")

    # Bark: a thin band with a finely ragged outside; its closing corners are off-canvas.
    inner = ring(N, radii[-1], TH_FINE)
    outer = ring(N, radii[-1] + 15 + 5 * n.fbm(TH_FINE * 70, 3.1, 4), TH_FINE)
    cut = seen(inner, outer)
    s.fill(P().spline(np.vstack((inner[cut], outer[cut][::-1])), closed=True), BG_ALT)
    s.stroke(P().spline(inner[cut]), UI, 1.3)

    # Drying check: a V-wedge split in from the bark, tapering to nothing a few rings outside the fire year.
    rs = np.linspace(R_BARK + 40, (radii[FIRE + 4] + radii[FIRE + 5]) / 2, 60)
    t = (rs - rs[-1]) / (R_BARK - rs[-1])
    spine = CRACK + 0.006 * np.sin(t * 2.2)
    half = (13 * t + 0.8 * n(rs / 90, 7.5) * t) / rs
    lips = [
        pith + np.column_stack((rs * np.cos(a), rs * np.sin(a)))
        for a in (spine + half, spine - half)
    ]
    log = Polygon(np.vstack(([pith], outer)))
    s.fill(P().shape(Polygon(np.vstack((lips[0], lips[1][::-1]))).intersection(log)), BG_DEEP)
