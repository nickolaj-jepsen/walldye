"""Pine-forest ridges receding into fog, in flat noise-cut layers."""

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_7,
    BG,
    BG_ALT,
    BG_DEEP,
    BLACK,
    UI,
    UI_ALT,
    Canvas,
    P,
    Rng,
    by_regime,
    design,
    mix,
)
from walldye.field import runs

SUN_X, SUN_R = 560, 72  # the terrain is laid out around the sun as it sits at 16:9
# (base y, ridge amplitude, tree height, tree spacing, tone) far → near, on a 1080-tall canvas;
# the far hill is bare. Nearer ridges sink below BG on dark themes and take more ink on light ones.
RIDGES = (
    (600, 60, 0, 0, by_regime(mix(BG_ALT, UI, 0.55), mix(BG_ALT, UI, 0.15))),
    (665, 80, 28, 10, by_regime(mix(BG_ALT, UI, 0.1), mix(BG_ALT, UI, 0.45))),
    (745, 100, 42, 13, by_regime(mix(BG, BG_ALT, 0.45), mix(BG_ALT, UI, 0.75))),
    (840, 115, 62, 18, by_regime(BG_DEEP, mix(UI, UI_ALT, 0.2))),
    (960, 120, 92, 26, by_regime(mix(BG_DEEP, BLACK, 0.5), mix(UI, UI_ALT, 0.5))),
)
SKY = mix(BG, UI, 0.35)
MIST = mix(BG_ALT, UI, 0.5)


def pine(x: float, y: float, h: float, r: Rng) -> BaseGeometry:
    """Jagged three-tier conifer outline standing on (x, y)."""
    w = h * r.uniform(0.2, 0.26)
    right = [(x, y - h)]
    for k, (ty, tw) in enumerate([(0.36, 0.5), (0.66, 0.78), (0.97, 1.0)]):
        tw *= r.uniform(0.85, 1.1)
        right.append((x + w * tw, y - h + h * ty))
        if k < 2:
            right.append((x + w * tw * 0.42, y - h + h * (ty - 0.04)))
    right.append((x + w * 0.2, y + 4))
    left = [
        (2 * x - px + r.uniform(-0.6, 0.6), py + r.uniform(-1.5, 1.5))
        for px, py in reversed(right[1:])
    ]
    return Polygon(right + left).buffer(0)


@design(aspects="any")
def draw(s: Canvas) -> None:
    n, r = s.noise(21), s.rng(21)
    sun_x = s.pick(landscape=(SUN_X / 1920, 0), portrait=(0.32, 0)).x
    ox = sun_x - SUN_X  # terrain is sun-relative, so the hill under the sun never changes
    # Portrait screens stretch the ridges' depth so the land still fills the lower part.
    k = max(1.0, 0.72 * s.h / 1080)
    xs = np.arange(-20, s.w + 21, 8, dtype=float)

    def base_y(base: float) -> float:
        return s.h - k * (1080 - base)

    def crest(i: int, base: float, amp: float) -> NDArray[np.float64]:
        u = xs - ox
        bump = 0.25 * amp * np.exp(-(((u - SUN_X) / 380) ** 2))
        return base_y(base) + k * (2 * amp * n.fbm(u / 900, i * 3.1 + 0.5, 3) + bump)

    def ridge(i: int, base: float, amp: float, th: float, gap: float) -> BaseGeometry:
        ys = crest(i, base, amp)
        shapes: list[BaseGeometry] = [
            Polygon([*zip(xs, ys), (s.w + 20, s.h + 20), (-20, s.h + 20)])
        ]
        if th:
            walk: list[float] = []
            x = -20.0
            while x < s.w + 20:
                walk.append(x)
                x += gap * r.uniform(0.7, 1.2)
            # Forest in loose stands: a coarse noise mask, short runs dropped so no tree stands alone.
            wood = n((np.array(walk) - ox) / 240, i * 7.7) > -0.05
            for a, b in runs(wood):
                if b - a < 5:
                    continue
                for x in walk[a:b]:
                    y = float(np.interp(x, xs, ys))
                    shapes.append(pine(x, y + th * 0.25, th * r.uniform(0.7, 1.2), r))
        return unary_union(shapes).simplify(0.3)

    hz = base_y(RIDGES[0][0])
    s.fill(
        P().rect(0, 0, s.w, s.h),
        s.linear_gradient([(0, BG), (1, SKY)], (0, hz - 222 * k), (0, hz + 48 * k)),
    )
    # Sink the sun so ~45% of it sits behind the bare far hill.
    base0, amp0 = RIDGES[0][0], RIDGES[0][1]
    cy = float(np.interp(sun_x, xs, crest(0, base0, amp0))) - 0.08 * SUN_R
    sun = (sun_x, cy)
    for f, op in ((2.6, 0.05), (1.9, 0.07), (1.4, 0.09)):
        s.fill(P().circle(sun, f * SUN_R), ACCENT_7, opacity=op)
    s.fill(
        P().circle(sun, SUN_R),
        s.linear_gradient([(0, ACCENT), (1, ACCENT_2)], (0, cy - SUN_R), (0, cy + SUN_R)),
    )
    for i, (base, amp, th, gap, tone) in enumerate(RIDGES):
        # Mist pools in the band the next ridge leaves visible, so each layer's foot lifts off the one in front.
        nxt = base_y(RIDGES[i + 1][0]) if i + 1 < len(RIDGES) else s.h
        fill = s.linear_gradient(
            [(0, tone), (1, mix(tone, MIST, 0.35))],
            (0, base_y(base) - 0.3 * amp * k),
            (0, nxt),
        )
        s.fill(P().shape(ridge(i, base, amp, th, gap)), fill)
