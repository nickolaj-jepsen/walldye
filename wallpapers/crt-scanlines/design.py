"""A curved CRT face whose only picture is a round lit patch, drawn by scanlines that swell where it is lit."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_4,
    BG_ALT,
    BG_DEEP,
    BLACK,
    UI,
    Canvas,
    P,
    Vec,
    by_regime,
    design,
    ladder,
    mix,
    smoothstep,
)
from walldye.field import gauss, runs
from walldye.geom import ribbon

SQUARENESS = 7  # superellipse exponent: bulged sides, rounded corners
BEZEL = 40
PITCH, DX, HAIR_DX = 8, 4, 40  # scanline pitch; sample steps for the bands and the bare lines
STRIDE = 4  # band outlines keep every 4th sample; their edges are smooth at that spacing
K = 0.08  # barrel distortion strength
ORB_R = 200
# Rung 0 is the bare line; rungs 1-12 are bands, 0.08 of intensity apart from 0.04 up.
TONES = ladder((BG_ALT, ACCENT_4, ACCENT), 13)
FLOOR = 0.04
JITTER = 0.04  # per-row threshold shift so tone seams don't stack into vertical staircases
GLASS = mix(BG_DEEP, BLACK, 0.5)
# on paper the recessed tones go paler than the page, so the bezel steps toward the ink instead
BEZEL_FILL, BEZEL_EDGE = by_regime(BG_DEEP, BG_ALT), by_regime(BG_ALT, UI)


def superellipse(c: Vec, a: float, b: float, n: int = 360) -> NDArray[np.float64]:
    """`n` points around the superellipse of half-axes `a`, `b` centred on `c`."""
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    cos, sin = np.cos(t), np.sin(t)
    e = 2 / SQUARENESS
    return np.column_stack(
        [c.x + a * np.sign(cos) * np.abs(cos) ** e, c.y + b * np.sign(sin) * np.abs(sin) ** e]
    )


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.center
    # a tube turned on end for portrait screens, the glow up and right of its middle
    a, b = (500, 370) if s.landscape else (370, 500)
    orb = c + ((121, -60) if s.landscape else (40, -110))

    def barrel(x: NDArray[np.float64], y: float) -> NDArray[np.float64]:
        u, v = (x - c.x) / a, (y - c.y) / b
        f = 1 + K * (u * u + v * v)
        return np.column_stack([c.x + u * f * a, c.y + v * f * b])

    bezel = P().poly(superellipse(c, a + BEZEL, b + BEZEL), closed=True)
    s.path(bezel, fill=BEZEL_FILL, stroke=BEZEL_EDGE, stroke_width=1)
    outline = P().poly(superellipse(c, a, b), closed=True)
    s.fill(outline, GLASS)
    with s.clip() as screen:
        screen.add(outline)

    # rows run past the glass on both sides so the clip, not the samples, ends them
    x0, x1 = c.x - a - 60, c.x + a + 60
    xs = np.arange(x0, x1 + DX / 2, DX)
    hair_xs = np.linspace(x0, x1, round((x1 - x0) / HAIR_DX) + 1)
    ys = c.y - b + PITCH * (np.arange(int(2 * b / PITCH)) + 0.5)
    hair = P()
    for y in ys:
        hair.poly(barrel(hair_xs, y))

    rng = s.rng(3)
    with s.group(clip_path=screen.ref):
        s.stroke(hair, BG_ALT, 1)
        with s.buckets(TONES, "fill") as bands:
            for y in ys:
                d = np.hypot(xs - orb.x, y - orb.y)
                glow = gauss(d, ORB_R / math.sqrt(2.2)) * smoothstep(1.6 * ORB_R, 1.2 * ORB_R, d)
                dt = rng.uniform(-JITTER, JITTER)
                rung = TONES.rung((glow - dt + FLOOR) / (1 + FLOOR))
                line = barrel(xs, y)
                # Each run of one rung is a band 1 + 3.2 * glow thick, ending on the next run's
                # first sample so neighbouring bands meet without a gap.
                for k in range(1, len(TONES)):
                    for i0, i1 in runs(rung == k):
                        end = min(i1, len(xs) - 1)
                        idx = np.r_[i0:end:STRIDE, end]
                        bands[k].poly(ribbon(line[idx], 1 + 3.2 * glow[idx]), closed=True)
    s.stroke(outline, BG_ALT, 1.6)
