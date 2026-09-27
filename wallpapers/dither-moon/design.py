"""A gibbous moon in 1-bit void-and-cluster dither: a shaded numpy tone field quantised to BG/ACCENT cells."""

import math

import numpy as np

from walldye import ACCENT, BG, H, W, dither, grid_runs, is_light, noise_grid

ASPECTS = ["any"]

U = min(W, H) / 1080  # the moon and its dither cell scale with the short side, never the long one
R, CELL = 270 * U, 3 * U
PHASE = math.radians(58)  # sun angle from the viewer; >0 lights from the right, terminator on the left
MAX_TONE = 0.75  # keep BG showing through even the brightest limb


def blobs(u, v, spots):
    return sum(a * np.exp(-((u - x) ** 2 + (v - y) ** 2) / r**2) for x, y, r, a in spots)


def draw(s):
    # Focal point: right of centre on a landscape screen (the left stays free for windows),
    # upper third on a portrait one (below the clock, above the dock).
    fx, fy = (0.68, 0.46) if W >= H else (0.56, 0.34)
    # Snapped to whole cells so the grid origin is too: a fractional one blurs every cell edge.
    cx, cy = round(fx * W / CELL) * CELL, round(fy * H / CELL) * CELL

    n = int(R * 1.04 / CELL)
    size = 2 * n
    ys, xs = np.mgrid[0:size, 0:size]
    # Disc coordinates: u, v in [-1, 1] across the moon, z the sphere's height toward the viewer.
    u = (xs + 0.5 - n) * CELL / R
    v = (ys + 0.5 - n) * CELL / R
    rr = np.hypot(u, v)
    inside = rr < 1
    z = np.sqrt(np.clip(1 - rr * rr, 0, 1))

    # Albedo carries the texture: dark maria (upper half, like the near side) and bright ejecta.
    mare = 1.6 * noise_grid(size, size, 60, seed=4, octaves=3) + 0.3 * (-v) - 0.1
    mare += blobs(u, v, [(-0.1, -0.35, 0.22, 0.5), (0.3, -0.05, 0.16, 0.45), (-0.35, 0.05, 0.14, 0.35)])
    albedo = 0.95 - 0.62 * np.clip((mare - 0.02) * 2.8, 0, 1) + 0.08 * noise_grid(size, size, 6, seed=11, octaves=2)

    rng = np.random.default_rng(3)
    albedo += blobs(u, v, [(*rng.uniform(-0.8, 0.8, 2), rng.uniform(0.015, 0.04), 0.4) for _ in range(18)])

    # Tycho-like ray crater low on the disc: bright halo plus thin rays.
    tx, ty = 0.2, 0.6
    ang = np.arctan2(v - ty, u - tx)
    dist = np.hypot(u - tx, v - ty)
    rays = sum(
        np.exp(-(((ang - a + np.pi) % (2 * np.pi) - np.pi) * dist / 0.014) ** 2) * np.exp(-dist / w)
        for a, w in zip(rng.uniform(-np.pi, np.pi, 18), rng.uniform(0.15, 0.45, 18))
    )
    albedo += 0.3 * np.clip(rays, 0, 1) + 0.45 * np.exp(-(dist / 0.06) ** 2)

    lam = np.clip((u * math.sin(PHASE) + z * math.cos(PHASE)) * 3 + 0.2, 0, 1) ** 0.8
    limb = 1 - 0.35 * np.clip((rr - 0.88) / 0.12, 0, 1)
    tone = np.clip(lam * albedo * limb * 0.62, 0, MAX_TONE)
    tone = np.maximum(tone, 0.07)  # faint earthshine on the dark side
    if is_light():
        tone = 0.8 * (MAX_TONE - tone)  # on paper, ink the shadows instead: a pencil moon, not a negative
    tone = np.where(inside, tone, 0)

    grid = np.array(dither(lambda i, j: tone[j, i], size, size, 2, "bluenoise", seed=5))
    grid[~inside] = 0
    # A sparse one-cell limb ring keeps the silhouette round where the dark side fades out.
    ring = (np.abs(rr - 1 + 0.5 * CELL / R) < 0.5 * CELL / R) & ((xs + ys) % 2 == 0)
    grid[ring] = 1
    grid_runs(s, grid.tolist(), [BG, ACCENT], CELL, cx - n * CELL, cy - n * CELL)
