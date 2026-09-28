"""A colour field after Rothko: three stacked blocks with wobbling, feathered edges, the two large ones scumbled with long tapered brush strokes."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import Polygon

from walldye import (
    ACCENT_4,
    ACCENT_5,
    ACCENT_6,
    BG,
    BG_ALT,
    UI,
    Canvas,
    Colour,
    NpRng,
    P,
    Rect,
    Vec,
    design,
    mix,
    smoothstep,
)
from walldye.field import Noise

GROUND = mix(BG, BG_ALT, 1 / 3)  # the painting's ground, a step off the page
LAYERS = 20  # feather steps per block
SIDE_AMP = (1.0, 0.6, 1.2, 0.7)  # edge wobble per side: top, right, bottom, left
U = np.linspace(0, 1, 40)  # samples along a brush stroke
# The vertical stack, in canvas units at 16:9: top and bottom edges as fractions of the height,
# fixed gaps and band, and the two blocks sharing the rest 450:268.
TOP, BOTTOM, GAP, BAND, UPPER_SHARE = 110 / 1080, 972 / 1080, 52, 40, 450 / 718
UPPER_TONES = (mix(BG_ALT, UI, 1 / 12), mix(BG_ALT, UI, 2 / 12), mix(BG_ALT, GROUND, 1 / 8))
LOWER_TONES = (
    mix(ACCENT_5, ACCENT_4, 0.08),
    mix(ACCENT_5, ACCENT_4, 0.15),
    mix(ACCENT_5, ACCENT_6, 0.08),
)


def wobble(p: Vec, q: Vec, noise: Noise, amp: float, z: float) -> NDArray[np.float64]:
    """Points along p→q pushed sideways by low-frequency noise (slice `z`), pinned at both ends."""
    ln = abs(q - p)
    side = (p - q).perp() / ln
    u = np.linspace(0, 1, max(8, int(ln / 12)))
    pin = smoothstep(0, 1, np.minimum(u, 1 - u) * ln / 90)
    d = amp * pin * noise.fbm(u * ln / 600, z, 3, gain=0.45)
    return np.asarray(p) + np.outer(u, q - p) + np.outer(d, side)


def soft_block(
    s: Canvas,
    box: Rect,
    paint: Colour,
    feather: float,
    noise: Noise,
    amp: float = 16.0,
    radius: float = 26.0,
) -> None:
    """A block whose wobbling edges fade into the ground over about `feather` units.

    Nested outlines of a drifting core step from the ground to `paint` along a smoothstep, so
    the fade is tight in places and loose in others.
    """
    r = min(radius, box.h / 2 - 4)
    x0, y0, x1, y1 = box.x + r, box.y + r, box.x1 - r, box.y1 - r
    corners = (Vec(x0, y0), Vec(x1, y0), Vec(x1, y1), Vec(x0, y1))
    for i in range(LAYERS):
        cover = smoothstep(0, 1, (i + 1) / LAYERS)
        if cover < 0.03:  # indistinguishable from the ground
            continue
        z = 0.5 * i / LAYERS
        ring = np.concatenate(
            [
                wobble(corners[e], corners[(e + 1) % 4], noise, amp * SIDE_AMP[e], 3.7 * e + z)[:-1]
                for e in range(4)
            ]
        )
        grow = r + feather * (0.5 - i / (LAYERS - 1))
        s.fill(
            P().shape(Polygon(ring).buffer(grow, quad_segs=12).simplify(0.3)),
            mix(GROUND, paint, cover),
        )


def brush(
    s: Canvas,
    box: Rect,
    tones: Sequence[Colour],
    rng: NpRng,
    noise: Noise,
    count: int,
    bias: float = 0.5,
) -> None:
    """Long tapered horizontal strokes inside `box`, each a solid tone a level or two off the
    block, for its scumbled surface; `bias` places their centres across the box."""
    with s.buckets(tones, "fill") as strokes:
        for k in range(count):
            ln = rng.uniform(0.3, 0.75) * box.w
            mid = rng.normal(box.x + bias * box.w, 0.22 * box.w)
            cx = float(np.clip(mid, box.x + ln / 2, box.x1 - ln / 2))
            cy, th = rng.uniform(box.y, box.y1), rng.uniform(5, 26)
            xs = cx - ln / 2 + ln * U
            half = th / 2 * np.sin(np.pi * U) ** 0.6
            ys = cy + 6 * noise.fbm(xs / 500, k * 1.9, 2)
            top = np.column_stack([xs, ys - half])
            bottom = np.column_stack([xs, ys + half])[::-1]
            strokes[rng.integers(len(tones))].poly(np.concatenate([top, bottom]), closed=True)


@design(aspects="any", bg=GROUND)
def draw(s: Canvas) -> None:
    # the upper block and band share side margins; the lower block reaches a little wider
    inner, outer = s.w * 0.125, s.w * 0.09375
    top, bottom = s.h * TOP, s.h * BOTTOM
    upper = Rect(inner, top, s.w - 2 * inner, (bottom - top - 2 * GAP - BAND) * UPPER_SHARE)
    band = Rect(inner, upper.y1 + GAP, upper.w, BAND)
    lower = Rect(outer, band.y1 + GAP, s.w - 2 * outer, bottom - band.y1 - GAP)
    # strokes keep clear of the feathered edges; their number follows the block's height
    up_strokes = Rect(upper.x + 50, upper.y + 40, upper.w - 100, upper.h - 80)
    low_strokes = Rect(lower.x + 50, lower.y + 36, lower.w - 100, lower.h - 72)

    soft_block(s, upper, BG_ALT, 22, s.noise(1))
    brush(
        s,
        up_strokes,
        UPPER_TONES,
        s.np_rng(3),
        s.noise(3),
        round(40 * up_strokes.h / 370),
        bias=0.45,
    )
    soft_block(s, band, mix(ACCENT_5, ACCENT_4, 0.25), 16, s.noise(5), amp=6, radius=12)
    soft_block(s, lower, ACCENT_5, 22, s.noise(9))
    brush(
        s,
        low_strokes,
        LOWER_TONES,
        s.np_rng(7),
        s.noise(7),
        round(30 * low_strokes.h / 196),
        bias=0.4,
    )
