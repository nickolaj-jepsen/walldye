"""A hypercube's edges in its Coxeter-plane projection, one shortest path through the centre traced from rim to rim."""

import itertools

import numpy as np

from walldye import ACCENT, UI, Canvas, P, Params, Vec, design, knob, polar

R = 400  # rim radius


class Cube(Params):
    dim: int = knob(default=6, choices=(5, 6, 7), doc="dimension of the cube")


# Start vertex and the axes flipped in turn, per dimension: rim to rim through a centre vertex,
# every edge advancing along the chord, the sharpest turn at the centre.
WALKS = {
    5: (0b11100, (0, 3, 1, 4)),
    6: (0b111100, (5, 4, 1, 0)),
    7: (0b1111000, (1, 6, 4, 2, 0, 5)),
}


@design(aspects="any", variants={"5-cube": Cube(dim=5)})
def draw(s: Canvas[Cube]) -> None:
    n = s.params.dim
    c = s.pick(landscape=(0.323, 0.5), portrait=(0.5, 0.4))
    # vertex v sits at the sum of the n unit axes, 180/n degrees apart, signed by v's bits
    axes = np.array([polar((0, 0), 1, deg=180 * k / n) for k in range(n)])
    bits = (np.arange(2**n)[:, None] >> np.arange(n)) & 1
    raw = (2 * bits - 1) @ axes
    pts = [c + Vec(x, y) for x, y in (raw * (R / np.hypot(*raw.T).max())).tolist()]

    edges = P()
    for v in range(2**n):
        for k in range(n):
            if not v >> k & 1:
                edges.M(pts[v]).L(pts[v | 1 << k])
    s.stroke(edges, UI, 1.2)

    start, order = WALKS[n]
    walk = [pts[v] for v in itertools.accumulate(order, lambda v, k: v ^ 1 << k, initial=start)]
    s.stroke(P().poly(walk), ACCENT, 3, join="round", cap="round")
    s.fill(P().dots(walk, 4), ACCENT)
