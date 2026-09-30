"""Monaco as a figure-ground map of flat building blocks with the circuit traced through its streets."""

import math

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

from walldye import (
    ACCENT,
    ACCENT_4,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    BG,
    BG_ALT,
    BLACK,
    UI,
    Canvas,
    P,
    Path,
    by_regime,
    design,
    mix,
)
from walldye.field import iso_lines
from walldye.geom import Polyline, parts

type F64 = NDArray[np.float64]
type Rings = list[list[list[int]]]  # polygons, each a list of rings of flat x, y meters

# Map meters are east and north of 43.7384 N, 7.4246 E. The data covers only the ground every
# screen shape shows at this scale and turn.
K = 1.1  # canvas units per meter
BEARING = 60  # compass bearing that points right on a landscape screen; portrait turns 90 more
TUNNEL_MID = (365.0, 75.0)  # placed at the focus
# Below the streets on a dark ground, as far under them as the blocks stand above; paper has no
# room below it, so there it is a half tint.
SEA = by_regime(BLACK, mix(BG, BG_ALT, 0.5))
# The light in each block the tunnel passes under: the whole block takes the fringe tone (a
# step paler on paper), the middle step reaches MID of the way from the tunnel to the block's
# own outline, and the core is a band CORE units either side of the tunnel.
FRINGE = by_regime(mix(BG_ALT, ACCENT_6, 0.5), mix(BG_ALT, ACCENT_7, 0.5))
MIDDLE = by_regime(ACCENT_5, ACCENT_6)
MID, CORE = 0.45, 5
ISLAND = 600  # square canvas units; smaller middle-step parts read as blobs on the line
GRID = 2  # sample spacing of the falloff, canvas units


def share(g: Polygon, line: LineString, xs: F64, ys: F64) -> F64:
    """How far each point is from `line` towards the outline of block `g`, 0 on the line and
    1 at the outline; 1 outside the block."""
    pts = shapely.points(xs, ys)
    near = shapely.distance(pts, line)
    edge = shapely.distance(pts, g.boundary)
    return np.where(shapely.contains_xy(g, xs, ys), near / (near + edge + 1e-9), 1.0)


def middle(g: Polygon, line: LineString) -> list[Polygon]:
    """The parts of block `g` less than MID of the way from `line` to its outline, each at least
    ISLAND in area."""
    x0, y0, x1, y1 = g.bounds
    xs = np.arange(x0 - 2 * GRID, x1 + 3 * GRID, GRID)
    ys = np.arange(y0 - 2 * GRID, y1 + 3 * GRID, GRID)
    field = share(g, line, *np.meshgrid(xs, ys))
    rings = [LineString(c) for c in iso_lines(field, MID, cell=GRID, origin=(xs[0], ys[0]))]
    low: list[Polygon] = []
    for face in polygonize([r for r in rings if len(r.coords) >= 4]):
        p = face.representative_point()  # contours also bound the high side's faces
        if share(g, line, np.array([p.x]), np.array([p.y]))[0] < MID:
            low.append(face)
    mid = parts(unary_union(low).intersection(g))
    return [p for p in mid if isinstance(p, Polygon) and p.area >= ISLAND]


def frame(bearing: float) -> F64:
    """Rows map (east, north) meters onto canvas (x, y), with `bearing` pointing right."""
    b = math.radians(bearing)
    return np.array([[math.sin(b), math.cos(b)], [math.cos(b), -math.sin(b)]]) * K


@design(aspects="any")
def draw(s: Canvas) -> None:
    # OpenStreetMap: buildings unioned into blocks, the sea cut from the coastline, and the
    # circuit's centerline from the start line in racing order, with the tunnel's vertex range.
    data = s.data("monaco.json")
    blocks: Rings = data["blocks"]
    sea: Rings = data["sea"]
    circuit: list[float] = data["circuit"]
    t0, t1 = data["tunnel"]

    m = frame(BEARING if s.landscape else BEARING + 90)
    focus = np.asarray(s.pick(landscape=(0.66, 0.42), portrait=(0.42, 0.3)))

    def to_canvas(flat: list[int] | list[float]) -> F64:
        return (np.asarray(flat, dtype=np.float64).reshape(-1, 2) - TUNNEL_MID) @ m.T + focus

    loop = to_canvas(circuit)
    tunnel = Polyline(loop[t0 : t1 + 1]).resample(6).pts
    near_lo, near_hi = tunnel.min(axis=0) - 10, tunnel.max(axis=0) + 10

    def shapes(polys: Rings, near: list[Polygon]) -> Path:
        """Every polygon on screen as one even-odd path; those by the tunnel also go in `near`."""
        d = P()
        for poly in polys:
            rings = [to_canvas(r) for r in poly]
            lo, hi = rings[0].min(axis=0), rings[0].max(axis=0)
            if (hi < -20).any() or lo[0] > s.w + 20 or lo[1] > s.h + 20:
                continue
            for r in rings:
                d.poly(r, closed=True)
            if (hi > near_lo).all() and (lo < near_hi).all():
                near.append(Polygon(rings[0], rings[1:]))
        return d

    s.fill(shapes(sea, []), SEA, rule="evenodd")
    over: list[Polygon] = []
    s.fill(shapes(blocks, over), BG_ALT, rule="evenodd")

    # The blocks the tunnel runs under are lit from beneath, fading out to their own outlines.
    line = LineString(tunnel)
    lit = [g for g in parts(unary_union(over)) if isinstance(g, Polygon) and g.intersects(line)]
    core = line.buffer(CORE, cap_style="flat")
    s.fill(P().shape(unary_union(lit)), FRINGE)
    s.fill(P().shape(unary_union([p for g in lit for p in middle(g, line)])), MIDDLE)
    s.fill(P().shape(unary_union(lit).intersection(core)), ACCENT_4)

    road = Polyline(np.vstack([loop[t1:], loop[: t0 + 1]])).resample(6).pts
    s.stroke(P().spline(road), UI, 3.5, cap="butt", join="round")  # both ends are portals
    s.stroke(P().spline(tunnel), ACCENT, 4, dash=(12, 5), cap="butt", join="round")
