"""A dry garden from above: rake lines follow potential flow past three stones inside raked rings, one stone picked out."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from shapely.affinity import translate
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_HI,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    NpRng,
    P,
    Vec,
    by_regime,
    design,
)
from walldye.field import iso_lines, sample_field
from walldye.geom import Polyline, parts

GAP = 16  # rake pitch
BUTT = 0.6  # share of the lines that end at a ring zone rather than bend around it
STEP = 2  # rake field lattice spacing
# (group, offset from the group's anchor, radius, rings, fill, shade): rings follow stone size.
# The shade stays a step darker than the fill in both regimes.
STONES = (
    (0, Vec(0, 0), 75, 6, UI, by_regime(BG_ALT, UI_ALT)),
    (0, Vec(180, 170), 42, 4, UI_ALT, by_regime(UI, UI_HI)),
    (1, Vec(0, 0), 55, 5, ACCENT, by_regime(ACCENT_2, ACCENT_HI)),
)
GROUPS = sorted({st[0] for st in STONES})
NMAX = max(st[3] for st in STONES)
SHARED = 5  # from this ring level out, a group's rings wrap all its stones as one outline
BRIDGE = 110  # closing radius that fills the waist between grouped stones


def stone_outline(rng: NpRng, c: Vec, r: float) -> NDArray[np.float64]:
    """A rounded, slightly lopsided outline of radius about `r` around `c`, 360 points."""
    a = (rng.uniform(0.04, 0.06), rng.uniform(0.02, 0.035), 0.012)
    p = rng.uniform(0, 2 * np.pi, 3)
    th = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    rr = r * (
        1
        + a[0] * np.cos(2 * th + p[0])
        + a[1] * np.cos(3 * th + p[1])
        + a[2] * np.cos(5 * th + p[2])
    )
    return np.column_stack([c.x + rr * np.cos(th), c.y + rr * np.sin(th)])


def ring(bodies: Sequence[Polygon], group: int, level: int) -> list[Polygon]:
    """The polygons `level` rings out from `group`'s stones; stones with fewer rings start
    further out, and from SHARED on the group's rings bridge the waist between its stones."""
    offs = [(b, (level - NMAX + st[3]) * GAP) for b, st in zip(bodies, STONES) if st[0] == group]
    shape = unary_union([b.buffer(o, 32) for b, o in offs if o > 0])
    if level >= SHARED and len(offs) > 1:
        shape = shape.buffer(BRIDGE, 32).buffer(-BRIDGE, 32)
    return [g for g in parts(shape) if isinstance(g, Polygon)]


def stream(
    xs: NDArray[np.int64], ys: NDArray[np.int64], centres: Sequence[Vec]
) -> NDArray[np.float64]:
    """The rake lines' stream function: y, bent by potential flow past each stone's ring zone.
    It stays monotonic in y, so the lines bend but never fold."""
    psi = ys.astype(np.float64)
    for c, (_, _, r, n, _, _) in zip(centres, STONES):
        rz = r + (n + 1) * GAP
        psi += (c.y - ys) * (1 - BUTT) * (rz / np.maximum(np.hypot(xs - c.x, ys - c.y), rz)) ** 2
    return psi


def even(outline: Polygon) -> NDArray[np.float64]:
    """Points about 6 apart, evenly spaced round the exterior of `outline`: buffers leave
    uneven vertices that a Catmull-Rom spline turns into wobbles."""
    line = Polyline(np.asarray(outline.exterior.coords), closed=True)
    return line.at(np.linspace(0, line.length, int(line.length // 6), endpoint=False))


def trimmed(line: LineString) -> NDArray[np.float64]:
    """The simplified vertices of `line`, less those within 8 of a cut end, which would hook
    the spline."""
    pts = np.asarray(line.simplify(0.4).coords)
    near = np.linalg.norm(pts[1:-1, None] - pts[None, [0, -1]], axis=2).min(axis=1, initial=np.inf)
    return np.vstack([pts[:1], pts[1:-1][near > 8], pts[-1:]])


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the pair high on the right and the single stone low on the left, a diagonal on any screen
    anchors = (
        s.pick(landscape=(1360 / 1920, 420 / 1080), portrait=(0.56, 0.3)),
        s.pick(landscape=(480 / 1920, 770 / 1080), portrait=(0.3, 0.7)),
    )
    centres = [anchors[g] + off for g, off, *_ in STONES]
    bodies = [
        Polygon(stone_outline(s.np_rng(40 + k), c, st[2]))
        for k, (c, st) in enumerate(zip(centres, STONES))
    ]

    rake = P()
    for g in GROUPS:
        for level in range(1, NMAX + 1):
            for p in ring(bodies, g, level):
                pts = even(p)
                if len(pts) > 2:
                    rake.spline(pts, closed=True)

    # Rake lines stop one pitch outside the outermost ring, so the butt ends trace an implied ring.
    zone = unary_union([p for g in GROUPS for p in ring(bodies, g, NMAX + 1)])
    psi = sample_field(lambda i, j: stream(i * STEP, j * STEP, centres), s.w // STEP, s.h // STEP)
    for level in np.arange(GAP / 2, psi.max(), GAP):
        for iso in iso_lines(psi, level, cell=STEP):
            if len(iso) > 2:
                for line in parts(LineString(iso).difference(zone)):
                    if isinstance(line, LineString) and len(pts := trimmed(line)) > 2:
                        rake.spline(pts)
    s.stroke(rake, BG_ALT, 1.5, cap="round")

    for body, (_, _, r, _, fill, shade) in zip(bodies, STONES):
        s.fill(P().spline(np.asarray(body.exterior.coords)[:-1], closed=True), fill)
        # Crescent in the lower right: the stone minus itself nudged toward the light.
        s.fill(P().shape(body.difference(translate(body, -0.17 * r, -0.22 * r))), shade)
