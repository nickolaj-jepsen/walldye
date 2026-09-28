"""A dune crest under a low sun, its lit face dithered in square cells with a void-and-cluster mask."""

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, ACCENT_3, ACCENT_5, ACCENT_7, Canvas, Vec, clamp, design
from walldye.field import cells
from walldye.pixel import dither, grid_runs

type Field = NDArray[np.float64]

CELL = 4
BULGE = 0.09  # the crest's sideways swell mid-way, as a share of its horizontal run
MAX_RUN = 1.5  # the crest's longest horizontal run, in screen heights


def crest_x(y: Field, tip: Vec, foot: Vec) -> Field:
    """Crest x at screen row y: flat as it recedes from `tip`, steepening towards `foot`."""
    t = clamp((y - tip.y) / (foot.y - tip.y))
    run = foot.x - tip.x
    return tip.x + run * t**0.62 + BULGE * abs(run) * np.sin(np.pi * t**0.8) ** 2 * (1 - t)


@design(aspects="any")
def draw(s: Canvas) -> None:
    horizon = s.pick(landscape=(0, 0.52), portrait=(0, 0.58)).y
    # The tip sits just under the horizon. The foot leaves by the left edge on portrait screens
    # (else the crest stands up as a cliff) and its run is capped on ultrawide (else a sliver).
    tip = Vec(s.pick(landscape=(0.74, 0), portrait=(0.84, 0)).x, horizon + 18)
    foot = s.pick(landscape=(0.094, 1), portrait=(-0.3, 1))
    foot = Vec(max(foot.x, tip.x - MAX_RUN * s.h), foot.y)

    xs, ys = cells(s.inset(0), CELL)
    near = clamp((ys - horizon) / (s.h - horizon))  # 0 at the horizon, 1 at the frame bottom
    rows = ys[:, 0]
    gx = crest_x(rows, tip, foot)[:, None]
    slope = np.gradient(gx[:, 0], rows)[:, None]
    d = (xs - gx) / np.sqrt(1 + slope**2)  # perpendicular distance, >0 on the lit windward face

    reach = 16 + 230 * near  # the lit face widens with perspective
    fade = clamp(near * 3.2) ** 1.2  # crest dissolves into the far ridge
    ripple = 0.035 * np.sin((xs * 0.35 + ys) / (6 + 16 * near))
    shade = 1 - 0.7 * clamp((xs - 0.625 * s.w) / (0.375 * s.w)) * near  # lower right turns away
    lit = clamp(0.86 * np.exp(-d / reach) - 0.08 + ripple) * fade * shade
    tone = np.where(d > 0, lit, 0.0)
    tone = np.where((d > 0) & (d < CELL * 1.5), 0.9 * fade, tone)  # the sunlit rim

    # One faint far ridge sitting on the horizon, no rim.
    ridge = horizon - 16 - 18 * np.sin(xs / 260 + 1.2) ** 2 - 5 * np.sin(xs / 83)
    far = 0.14 * clamp((ys - ridge) / 14) * clamp((horizon + 20 - ys) / 24)
    tone = np.maximum(tone, far)
    tone = np.where(ys < ridge, 0, tone)

    grid = dither(tone, 5, method="bluenoise", rng=s.np_rng(2))
    grid_runs(s, grid, [None, ACCENT_7, ACCENT_5, ACCENT_3, ACCENT], CELL)
