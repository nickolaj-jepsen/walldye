"""Four gradient-shaded ribbons sweep up from the lower left; the top one turns over once to show its picked-out underside."""

import itertools
import math

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import PchipInterpolator

from walldye import (
    ACCENT,
    ACCENT_2,
    BG,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    Color,
    P,
    by_regime,
    design,
    mix,
    smoothstep,
)
from walldye.geom import bezier_points, ribbon

N = 480  # samples along each ribbon
W = 160  # ribbon width
# the sweep's control points as drawn for 1920 x 1080, around the twist at LENS
SWEEP = ((-300, 1300), (500, 1000), (1100, 650), (1500, -200))
LENS = 1010, 530
TAPER = 880  # arc length past the twist over which the top ribbon turns face up again
# offsets across the sweep (in 0.8 widths) in paint order: each ribbon shadows the one below it,
# and the twisted ribbon (0) lies on top so nothing hides its underside
STACK = (-2, -1, 1, 0)
GATHER = 0.8
SHADOW = (10, 16)
SHADE = by_regime(BG_DEEP, UI_ALT)  # BG_DEEP is paler than BG on paper, so it cannot shade there


def left(p: NDArray[np.float64]) -> NDArray[np.float64]:
    """Unit normals of the sampled curve `p`, pointing left of the direction of travel on
    screen."""
    d = np.gradient(p, axis=0)
    return np.stack([d[:, 1], -d[:, 0]], 1) / np.linalg.norm(d, axis=1)[:, None]


def tone(v: float, under: bool, accent: bool) -> Color:
    """The ribbon color for brightness `v` in [0, 1]: the accent ladder on the twisted
    ribbon's underside, else a step from BG toward UI, dimmer on an underside."""
    if under and accent:
        return mix(ACCENT_2, ACCENT, v**1.4)
    return mix(BG, UI, 0.08 + 0.5 * v * (0.55 if under else 1))


@design(aspects="any")
def draw(s: Canvas) -> None:
    t = np.linspace(0, 1, N)
    lens = s.frac(LENS[0] / 1920, LENS[1] / 1080)
    # wide screens stretch the sweep only partly, so it still rises steeply out of the top edge
    kx, ky = ((s.w / 1920) ** 0.5, 1.0) if s.landscape else (s.w / 1920, s.h / 1080)
    ctrl = [lens + ((x - LENS[0]) * kx, (y - LENS[1]) * ky) for x, y in SWEEP]
    base = bezier_points(ctrl, N - 1)
    nb = left(base)
    for off in STACK:
        accent = off == 0
        # the lower folds gather up under the twisted one, as if the cloth is drawn through the top edge
        gather = 1 - GATHER * smoothstep(0.5, 1, t) * (off < 0)
        c = base + nb * (off * 0.8 * W * gather)[:, None]
        arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))])
        width = W * (1 + 0.04 * off)
        if accent:
            # underside run: short lead-in, long taper toward the upper right
            sl = arc[np.argmin(np.linalg.norm(c - lens, axis=1))]
            phi = PchipInterpolator(
                [0, sl - 130, sl, sl + 270, sl + TAPER],
                [0.2, math.pi / 2, math.pi, 1.5 * math.pi, 2 * math.pi + 0.25],
            )(np.minimum(arc, sl + TAPER))
        else:
            phi = 0.25 + 0.1 * smoothstep(0.5, 1, t)
        cos = np.cos(phi)
        # pin each fold to one sample of zero width so neighboring runs meet in a clean point
        pins = [
            i if abs(cos[i]) < abs(cos[i + 1]) else i + 1
            for i in np.flatnonzero(np.diff(np.sign(cos)))
        ]
        cos[pins] = 0
        # ribbon() puts its first half right of travel, so a twist (cos < 0) swaps the sides
        edge = ribbon(c, width * cos)
        a, b = edge[:N], edge[N:][::-1]

        # the shadow pulls in near a pinch so it can't leave a dark halo around the point
        near = np.ones(N)
        for i in pins:
            near = np.minimum(near, smoothstep(0, 70, np.abs(arc - arc[i])))
        shadow = ribbon(c, width * cos * near) + SHADOW
        s.fill(P().poly(shadow, closed=True), SHADE, opacity=0.45)

        # light from the upper left: brightness follows the facing angle of whichever side is visible
        back = cos < 0
        lit = 0.5 + 0.5 * np.cos(phi - np.where(back, math.pi, 0) + 0.5)
        lit *= smoothstep(-0.1, 0.45, t)
        edges = [0, *pins, N - 1]
        for run in (np.arange(i, j + 1) for i, j in itertools.pairwise(edges)):
            under = back[run[len(run) // 2]]
            # shading is a gradient along the run's chord; projected offsets are forced monotonic
            p0, p1 = c[run[0]], c[run[-1]]
            u = p1 - p0
            pos = np.maximum.accumulate(np.clip((c[run] - p0) @ u / (u @ u), 0, 1))
            picks = np.linspace(0, len(run) - 1, 16).astype(int)
            grad = s.linear_gradient(
                [(pos[i], tone(lit[run[i]], under, accent)) for i in picks], p0, p1
            )
            s.fill(P().poly(np.vstack([a[run], b[run][::-1]]), closed=True), grad)
        # the upper silhouette stays one line through any twist, so the eye follows a single ribbon
        s.stroke(P().poly(np.where(back[:, None], a, b)), UI_ALT, 1.2)
