"""A moon in 1-bit void-and-cluster dither: a shaded tone field of maria and ray craters quantised to square cells."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, Canvas, Params, design, knob
from walldye.field import gauss, noise_grid
from walldye.pixel import dither, grid_runs


class Moon(Params):
    phase: float = knob(
        default=58,
        lo=-150,
        hi=150,
        unit="deg",
        doc="sun angle from the viewer; above 0 lights the right limb",
    )


VARIANTS = {"crescent": Moon(phase=120)}

R, CELL = 270, 3  # moon radius and dither cell
MAX_TONE = 0.75  # keep the background showing through even the brightest limb
# Albedo blobs: dark maria across the upper half, like the near side (x, y, radius, weight).
MARIA = ((-0.1, -0.35, 0.22, 0.5), (0.3, -0.05, 0.16, 0.45), (-0.35, 0.05, 0.14, 0.35))
TYCHO = (0.2, 0.6)  # the ray crater, low on the disc

type Field = NDArray[np.float64]


def blobs(u: Field, v: Field, spots: list[tuple[float, float, float, float]]) -> Field:
    """Sum of Gaussian bumps at disc coordinates (x, y) with radius r and weight a."""
    out = np.zeros_like(u)
    for x, y, r, a in spots:
        out += a * gauss(np.hypot(u - x, v - y), r)
    return out


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Moon]) -> None:
    # right of centre on a landscape screen (the left stays free for windows), the upper third
    # on a portrait one (below the clock, above the dock); snapped to whole cells, since a
    # fractional grid origin blurs every cell edge
    c = s.pick(landscape=(0.68, 0.46), portrait=(0.56, 0.34), snap=CELL)
    n = int(R * 1.04 / CELL)
    size = 2 * n
    ys, xs = np.mgrid[0:size, 0:size]
    # Disc coordinates: u, v in [-1, 1] across the moon, z the sphere's height toward the viewer.
    u = (xs + 0.5 - n) * CELL / R
    v = (ys + 0.5 - n) * CELL / R
    rr = np.hypot(u, v)
    inside = rr < 1
    z = np.sqrt(np.clip(1 - rr * rr, 0, 1))

    # Albedo carries the texture: dark maria and bright ejecta.
    mare = 1.6 * noise_grid(size, size, 60, s.np_rng(4), octaves=3) + 0.3 * (-v) - 0.1
    mare += blobs(u, v, list(MARIA))
    albedo = (
        0.95
        - 0.62 * np.clip((mare - 0.02) * 2.8, 0, 1)
        + 0.08 * noise_grid(size, size, 6, s.np_rng(11), octaves=2)
    )
    rng = s.np_rng(3)
    ejecta = [(*rng.uniform(-0.8, 0.8, 2), rng.uniform(0.015, 0.04), 0.4) for _ in range(18)]
    albedo += blobs(u, v, ejecta)

    # Tycho: a bright halo plus thin rays.
    tx, ty = TYCHO
    ang = np.arctan2(v - ty, u - tx)
    dist = np.hypot(u - tx, v - ty)
    rays = sum(
        np.exp(-((((ang - a + np.pi) % (2 * np.pi) - np.pi) * dist / 0.014) ** 2))
        * np.exp(-dist / w)
        for a, w in zip(rng.uniform(-np.pi, np.pi, 18), rng.uniform(0.15, 0.45, 18), strict=True)
    )
    albedo += 0.3 * np.clip(rays, 0, 1) + 0.45 * gauss(dist, 0.06)

    sun = math.radians(s.params.phase)
    lit = np.clip((u * math.sin(sun) + z * math.cos(sun)) * 3 + 0.2, 0, 1) ** 0.8
    limb = 1 - 0.35 * np.clip((rr - 0.88) / 0.12, 0, 1)
    tone = np.clip(lit * albedo * limb * 0.62, 0, MAX_TONE)
    tone = np.maximum(tone, 0.07)  # faint earthshine on the dark side
    if s.light:
        # on paper, ink the shadows instead: a pencil moon, not a negative
        tone = 0.8 * (MAX_TONE - tone)
    tone = np.where(inside, tone, 0)

    grid = dither(tone, 2, method="bluenoise", rng=s.np_rng(5))
    grid[~inside] = 0
    # A sparse one-cell limb ring keeps the silhouette round where the dark side fades out.
    ring = (np.abs(rr - 1 + 0.5 * CELL / R) < 0.5 * CELL / R) & ((xs + ys) % 2 == 0)
    grid[ring] = 1
    grid_runs(s, grid, [None, ACCENT], CELL, c - (n * CELL, n * CELL))
