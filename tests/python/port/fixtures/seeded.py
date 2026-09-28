"""Fixture: the four generator families, seeded helpers and the ones the codemod cannot reach."""

import random

import numpy as np
from wallgen import ACCENT, UI, H, Noise, P, W, noise_grid, poisson_disk, rng


def ng(cols, rows, scale, **kw):
    c, r = -(-cols // scale) * scale, -(-rows // scale) * scale
    return noise_grid(c, r, scale, **kw)[:rows, :cols]


def terrain(seed):
    n = Noise(seed)
    return [n(x / 50, 0.3) for x in range(0, W, 40)]


def picks(seed):
    s = list(range(10))
    random.Random(seed).shuffle(s)
    return s


class Walker:
    def __init__(self, seed):
        self.r = random.Random(seed)


def draw(s):
    r = rng(3)
    n = Noise(5)
    g = np.random.default_rng(7)
    field = noise_grid(40, 20, 8, seed=4, octaves=2)
    pad = ng(30, 30, 8, seed=9, octaves=3)
    d = P()
    for x, y in poisson_disk(r, W - 100, H - 100, 60, x0=50, y0=50):
        d.M(x, y).L(x + 4 * n(x / 100, y / 100), y + g.uniform(-3, 3))
    s.path(d, fill="none", stroke=UI, stroke_width=1)
    ridge = P().poly([(40 * i, 500 + 80 * h) for i, h in enumerate(terrain(11))])
    s.path(ridge, fill="none", stroke=ACCENT, stroke_width=float(field[0, 0] + pad[0, 0] + 2))
    order = picks(2)
    s.circle(100 + 10 * order[0], 100, 5, fill=ACCENT)
    jitter = random.Random()
    s.circle(200, 200, 3 + jitter.random(), fill=UI)
