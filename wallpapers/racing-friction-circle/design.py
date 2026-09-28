"""Qualifying at Silverstone as a g-g diagram: every fastest lap stippled, the pole lap traced from the brakes for Vale round into Club."""

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from walldye import ACCENT, BG, BG_ALT, UI, UI_ALT, UI_HI, Canvas, P, by_regime, design, mix
from walldye.geom import Polyline

type Arr = NDArray[np.float64]

K = 72  # units per g
RINGS = 6
LAP_END = 32767  # row value closing each lap in gg.npy
DMIN = (6.0, 4.2)  # closest two dots may sit, units: sparse fringe to crowded core
LINK, CLUSTER = 12.0, 6  # units, dots: a group of fewer dots this close together is dropped
CLEAR = 6.0  # units: dots this close to the lit lap are dropped
BIN = 8  # units, density histogram cell
DOT = by_regime(UI_HI, UI_ALT)
GRID = mix(BG_ALT, UI, 0.5)


def samples(raw: NDArray[np.int16]) -> Arr:
    """Every lap's 10 Hz samples in g with the midpoint of each step added, so 20 Hz."""
    ends = np.flatnonzero(raw[:, 0] == LAP_END)
    out: list[Arr] = []
    for a, b in zip(np.r_[0, ends[:-1] + 1], ends, strict=True):
        lap = raw[a:b] / 100.0
        out += [lap, (lap[1:] + lap[:-1]) / 2]
    return np.concatenate(out)


def thin(xy: Arr, dmin: Arr) -> list[int]:
    """Greedy thinning: the indices of the points kept, dropping point i when one already kept
    lies closer than `dmin[i]`."""
    cell = float(dmin.max())
    grid: dict[tuple[int, int], list[int]] = {}
    keep: list[int] = []
    pts: list[list[float]] = xy.tolist()
    for i, ((x, y), d) in enumerate(zip(pts, dmin.tolist(), strict=True)):
        gx, gy, d2 = int(x // cell), int(y // cell), d * d
        near = (grid.get((gx + a, gy + b), ()) for a in (-1, 0, 1) for b in (-1, 0, 1))
        if all((x - pts[j][0]) ** 2 + (y - pts[j][1]) ** 2 >= d2 for c in near for j in c):
            grid.setdefault((gx, gy), []).append(i)
            keep.append(i)
    return keep


def clusters(xy: Arr) -> NDArray[np.intp]:
    """The size of the group each point belongs to, points linked when closer than LINK."""
    pairs = cKDTree(xy).query_pairs(LINK, output_type="ndarray")
    n = len(xy)
    graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    _, label = connected_components(graph, directed=False)
    return np.bincount(label)[label]


def density(xy: Arr) -> Arr:
    """Each point's share of the busiest cell's count, from a lightly blurred histogram."""
    ij = np.floor((xy - xy.min(0)) / BIN).astype(int)
    h = np.zeros(ij.max(0) + 1)
    np.add.at(h, (ij[:, 0], ij[:, 1]), 1)
    h = gaussian_filter(h, 1.2)
    return h[ij[:, 0], ij[:, 1]] / h.max()


@design(aspects="any")
def draw(s: Canvas) -> None:
    gg = samples(s.data("gg.npy"))
    pole: NDArray[np.int16] = s.data("pole.npy")
    c = s.pick(landscape=(0.64, 0.48), portrait=(0.5, 0.34))

    def at(a: Arr) -> Arr:
        """Lateral and longitudinal g (right turns and traction positive) to canvas points."""
        return np.column_stack([c.x + a[:, 0] * K, c.y - a[:, 1] * K])

    grid = P()
    for g in range(1, RINGS + 1):
        grid.circle(c, g * K)
    R = RINGS * K
    grid.M(c.x - R, c.y).H(c.x + R).M(c.x, c.y - R).V(c.y + R)
    s.stroke(grid, GRID, 1.2)

    pts = at(gg[s.np_rng(3).permutation(len(gg))])
    dens = np.sqrt(density(pts))
    kept = pts[thin(pts, DMIN[0] + (DMIN[1] - DMIN[0]) * dens)]
    lap = at(pole / 1000.0)
    clear, _ = cKDTree(Polyline(lap).resample(1.0).pts).query(kept)
    kept = kept[clear > CLEAR]
    dots = P()
    for x, y in kept[clusters(kept) >= CLUSTER].tolist():
        dots.M(x, y).H(x)
    s.stroke(dots, DOT, 2.5, cap="round")

    trace = P().spline(lap)
    s.stroke(trace, BG, 9, join="round", cap="butt")
    s.stroke(trace, ACCENT, 2.8, join="round", cap="round")
