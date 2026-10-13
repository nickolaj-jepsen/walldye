"""A Penrose tribar built from depth-sorted isometric cubes and flat-shaded by face."""

import math
from itertools import pairwise

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import ACCENT, ACCENT_2, ACCENT_4, BG_ALT, UI, Canvas, P, Rect, Vec, by_regime, design
from walldye.geom import Affine

N = 9  # cubes per bar, corners shared
E = 56  # cube edge
OVER = 4  # construction lines run this many cube edges past each outer corner (3 on a phone)
# +x, +y, +z faces, lit from the upper left in both regimes: +y takes the lightest accent step
# and +z the deepest
FACES = (ACCENT_2, by_regime(ACCENT, ACCENT_4), by_regime(ACCENT_4, ACCENT))
DOT = 1.5  # lattice dot radius
TILE = (12, 10)  # lattice cells across and down one pattern tile

type Cube = tuple[int, int, int]


def face(v: Cube, axis: int) -> Polygon:
    """The +axis face of the unit cube at `v`, projected to exact integer lattice coords
    (x - z, y - z)."""
    corners = []
    for s, t in ((0, 0), (1, 0), (1, 1), (0, 1)):
        p = list(v)
        p[axis] += 1
        p[(axis + 1) % 3] += s
        p[(axis + 2) % 3] += t
        corners.append((p[0] - p[2], p[1] - p[2]))
    return Polygon(corners)


def tribar() -> list[BaseGeometry]:
    """The visible +x, +y and +z faces of the tribar's cubes, one merged region per axis, in
    lattice coords."""
    bar1: list[Cube] = [(i, 0, 0) for i in range(N)]
    bar2: list[Cube] = [(N - 1, j, 0) for j in range(1, N)]
    bar3: list[Cube] = [(N - 1, N - 1, k) for k in range(1, N - 1)]  # the last would land on bar1
    cubes = bar1 + bar2 + bar3
    hexes = {v: unary_union([face(v, a) for a in range(3)]) for v in cubes}

    def depth(v: Cube, other: Cube) -> int:
        # the impossible joint: next to bar 1, the far end of bar 3 counts as one full diagonal
        # further back
        if v in bar3 and v[2] > (N - 1) / 2 and other in bar1[:3]:
            return sum(v) - 3 * (N - 1)
        return sum(v)

    regions: list[list[BaseGeometry]] = [[] for _ in FACES]
    for v in cubes:
        cover = unary_union(
            [
                hexes[w]
                for w in cubes
                if w != v and depth(w, v) > depth(v, w) and hexes[w].intersects(hexes[v])
            ]
        )
        for axis in range(3):
            regions[axis].append(face(v, axis).difference(cover))
    return [unary_union(r) for r in regions]


@design(aspects="any")
def draw(s: Canvas) -> None:
    regions = tribar()
    outline = unary_union(regions).simplify(1e-6)
    assert isinstance(outline, Polygon)  # the silhouette is one piece, with the inner hole
    ring = np.asarray(outline.exterior.coords)

    # lattice x runs along screen +x, lattice y up and to the left; one cube edge is E units, and
    # the silhouette's bounding box is centered on c (right of center, or high on a phone)
    iso = Affine(1, 0, -0.5, -math.sqrt(3) / 2, 0, 0)
    flat = iso.apply(ring)
    lo, hi = flat.min(axis=0), flat.max(axis=0)
    mid = (lo + hi) / 2
    c = s.pick(landscape=(1220 / 1920, 560 / 1080), portrait=(0.5, 0.42))
    to_local = Affine.scale(E) @ Affine.translate(-float(mid[0]), -float(mid[1])) @ iso
    half = (hi - lo) * E / 2
    over = OVER if s.landscape else OVER - 1

    with s.motif(c, "cover", handle=Rect(-half[0], -half[1], 2 * half[0], 2 * half[1])) as m:
        # the lattice at half a cube edge, wherever the tribar goes, as a pattern of TILE
        # centered rectangular cells; renderers round a tile to whole pixels, so a large one
        # keeps the dots from drifting off the tribar's vertices, and its edge dots repeat so
        # that each is whole
        w, h = E / 2, E * math.sqrt(3) / 2
        cols, rows = TILE
        o = to_local.apply([(0, 0)])[0]
        shift = Affine.translate(float(o[0]), float(o[1]))
        with s.pattern(cols * w, rows * h, transform=shift) as tile:
            dots = P()
            for i in range(cols + 1):
                for j in range(rows + 1):
                    dots.M(i * w, j * h).H(i * w)  # a round-capped zero-length segment: a disc
                    if i < cols and j < rows:
                        dots.M((i + 0.5) * w, (j + 0.5) * h).H((i + 0.5) * w)
            tile.stroke(dots, BG_ALT, 2 * DOT, cap="round")
        s.fill(P().rect(*m.cover), tile.ref)

        # construction: the three long outer edges run on past the truncated corners and cross
        # at the ideal triangle's apexes, each end marked with a small ring; one edge shorter on
        # a portrait screen, whose width would otherwise leave the rings about 60 units from its
        # sides
        lines = P()
        for p0, p1 in pairwise(ring):
            steps = float(np.abs(p1 - p0).max())
            if steps < N / 2:
                continue
            unit = (p1 - p0) / steps
            for p, k in ((p0, -over), (p1, over)):
                a, b = to_local.apply([p, p + unit * k])
                lines.M(a[0], a[1]).L(b[0], b[1]).circle(Vec(b[0], b[1]), 3)
        s.stroke(lines, UI, 1.2)

        for g, paint in zip(regions, FACES, strict=True):
            s.fill(P().shape(shapely.transform(g, to_local.apply)), paint)
