"""Molnár's Interruptions: a grid of randomly turned strokes broken by clearings, with order found in the largest."""

import math

import numpy as np
from scipy import ndimage

from walldye import ACCENT, ACCENT_1, ACCENT_3, UI, Canvas, P, Rect, Vec, design, polar
from walldye.field import cells, gauss, noise_grid

# grid pitch, stroke length, least margin, pitch of the ordered sub-grid
PITCH, SEG, M, SUB = 30, 24, 40, 34
NOISE_SEED = 33
# (fx, fy, radius) of the clearings: the hero that holds the ordered strokes, a secondary echo,
# three small ones. Portrait keeps the diagonal from the hero down to the echo.
LANDSCAPE = (
    (0.719, 0.389, 195),
    (0.224, 0.731, 72),
    (0.401, 0.269, 52),
    (0.552, 0.787, 56),
    (0.901, 0.778, 48),
)
PORTRAIT = (
    (0.62, 0.36, 195),
    (0.27, 0.7, 72),
    (0.28, 0.2, 52),
    (0.8, 0.6, 56),
    (0.66, 0.85, 52),
)
ORDER_DEG = -35  # the ordered strokes all point this way
TONES = (ACCENT, ACCENT_1, ACCENT_3)  # ordered strokes, core outwards


@design(aspects="any")
def draw(s: Canvas) -> None:
    rng = s.np_rng(1969)
    cols, rows = (s.w - 2 * M) // PITCH + 1, (s.h - 2 * M) // PITCH + 1
    gw, gh = cols * PITCH, rows * PITCH
    X, Y = cells(Rect((s.w - gw) / 2, (s.h - gh) / 2, gw, gh), PITCH)
    voids = [(s.frac(fx, fy), r) for fx, fy, r in (LANDSCAPE if s.landscape else PORTRAIT)]

    noise = noise_grid(cols, rows, 12, s.np_rng(NOISE_SEED), octaves=2)
    noise = (noise - noise.min()) / np.ptp(noise)
    # each bump crosses 0.5 at its radius; the noise only roughens the rims
    field = 0.5 * (noise - 0.5)
    for c, r in voids:
        field += gauss(np.hypot(X - c.x, Y - c.y), r / math.sqrt(math.log(2)))
    void = field > 0.5
    # fill back rim fragments and slits: they read as dropped strokes, not interruptions
    labels, n = ndimage.label(void)
    for k in range(1, n + 1):
        blob = labels == k
        js, iis = np.nonzero(blob)
        h, w = np.ptp(js) + 1, np.ptp(iis) + 1
        if blob.sum() < 6 or max(h, w) > 3 * min(h, w):
            void[blob] = False
    labels, _ = ndimage.label(void)
    hc = voids[0][0]
    hero = labels == labels.flat[np.argmin(np.hypot(X - hc.x, Y - hc.y))]
    # optical centre: the middle of the clearing's deepest core, not its centre of mass
    depth = ndimage.distance_transform_edt(np.pad(hero, 1))[1:-1, 1:-1]
    core = depth > 0.75 * depth.max()
    centre = Vec(X[core].mean(), Y[core].mean())

    strokes = P()
    ang = rng.uniform(0, math.pi, X.shape)
    for j, i in zip(*np.nonzero(~void), strict=True):
        c, half = Vec(X[j, i], Y[j, i]), polar((0, 0), SEG / 2, rad=ang[j, i])
        strokes.M(c - half).L(c + half)
    s.stroke(strokes, UI, 1.4, cap="round")

    # 14 ordered strokes: a 4x4 sub-grid on the optical centre minus the corners off the stroke axis
    half = polar((0, 0), SEG / 2, deg=ORDER_DEG)
    with s.buckets(TONES, "stroke", stroke_width=2, stroke_linecap="round") as tone:
        for u in range(-1, 3):
            for v in range(-1, 3):
                if (u, v) in ((-1, -1), (2, 2)):
                    continue
                p = centre + (
                    (u - 0.5) * SUB + rng.normal(0, 1.5),
                    (v - 0.5) * SUB + rng.normal(0, 1.5),
                )
                r = math.hypot(u - 0.5, v - 0.5)
                tone[0 if r < 1 else 1 if r < 1.6 else 2].M(p - half).L(p + half)
