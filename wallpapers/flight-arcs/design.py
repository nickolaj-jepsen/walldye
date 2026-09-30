"""Copenhagen's direct routes as great-circle lines over a dotted map."""

import math
from typing import TypedDict

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely.geometry import Polygon

from walldye import (
    ACCENT,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Params,
    Path,
    Rect,
    by_regime,
    design,
    knob,
    mix,
)
from walldye.field import runs

type Arr = NDArray[np.float64]


class Routes(TypedDict):
    hub: tuple[str, float, float]  # IATA code, lon, lat
    destinations: list[tuple[str, float, float]]


class Map(Params):
    scale: float = knob(default=560, lo=400, hi=2000, doc="px per radian of longitude")


# dots are sized to read on dark grounds, then stepped back on paper
LAND = by_regime(mix(UI, UI_ALT, 0.25), mix(BG_ALT, UI, 0.5))
PITCH = 7  # land dot lattice, units
SAMPLES = 128  # points per route
NEAR = 1.5  # deg; destinations closer than this share one arc


def miller(lon: Arr, lat: Arr) -> Arr:
    """Miller cylindrical: lon/lat in degrees to (N, 2) plane points in radians, +y north."""
    return np.column_stack(
        [np.radians(lon), 1.25 * np.log(np.tan(np.pi / 4 + 0.4 * np.radians(lat)))]
    )


def unmiller(x: Arr, y: Arr) -> tuple[Arr, Arr]:
    """Invert `miller`, wrapping lon into [-180, 180)."""
    lat = np.degrees(2.5 * np.arctan(np.exp(0.8 * y)) - 0.625 * np.pi)
    return (np.degrees(x) + 180) % 360 - 180, lat


def great_circle(a: tuple[float, float], b: tuple[float, float]) -> tuple[Arr, Arr]:
    """Sample the shorter great-circle arc from `a` to `b` (lon, lat in degrees)."""
    lo, la = np.radians([a[0], b[0]]), np.radians([a[1], b[1]])
    u = np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    omega = math.acos(float(np.clip(u[0] @ u[1], -1, 1)))
    t = np.linspace(0, 1, SAMPLES)[:, None]
    v = (np.sin((1 - t) * omega) * u[0] + np.sin(t * omega) * u[1]) / math.sin(omega)
    return np.degrees(np.arctan2(v[:, 1], v[:, 0])), np.degrees(np.arcsin(v[:, 2]))


def great_len(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Central angle in radians between two (lon, lat) points given in degrees."""
    lo1, la1, lo2, la2 = map(math.radians, (*a, *b))
    c = math.sin(la1) * math.sin(la2) + math.cos(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return math.acos(max(-1.0, min(1.0, c)))


@design(aspects="any")
def draw(s: Canvas[Map]) -> None:
    k = s.params.scale * (1 if s.landscape else 0.78)
    # the map may not repeat, so an ultrawide screen spans under 360 degrees and sits higher to
    # keep the longest route's end above the dock
    wide = k * 1.9 * math.pi < s.w
    k = max(k, s.w / (1.9 * math.pi))
    routes: Routes = s.data("routes.json")
    _, hub_lon, hub_lat = routes["hub"]
    hub = (hub_lon, hub_lat)
    spot = s.frac(0.3, 0.22) if wide else s.pick(landscape=(0.3, 0.3), portrait=(0.25, 0.38))
    origin = miller(np.array([hub[0]]), np.array([hub[1]]))[0]

    def screen(lon: Arr, lat: Arr) -> Arr:
        xy = (miller(lon, lat) - origin) * k
        return np.column_stack([spot.x + xy[:, 0], spot.y - xy[:, 1]])

    land_rings: list[list[list[list[float]]]] = s.data("land.json")
    land = shapely.MultiPolygon([Polygon(p[0], p[1:]) for p in land_rings])
    shapely.prepare(land)
    xs, ys = np.arange(3, s.w, PITCH), np.arange(3, s.h, PITCH)
    lon, _ = unmiller((xs - spot.x) / k + origin[0], np.zeros(len(xs)))
    dots = P()
    for y in ys.tolist():
        _, lat = unmiller(np.zeros(1), np.array([-(y - spot.y) / k + origin[1]]))
        on = shapely.contains_xy(land, lon, np.full_like(lon, lat[0]))
        # one dashed run per stretch of land: a zero dash with round caps leaves a dot per pitch
        for a, b in runs(on):
            dots.M(xs[a], y).H(xs[b - 1] + 0.5)
    s.stroke(dots, LAND, 2.4, cap="round", dash=(0, PITCH))

    dests = sorted(routes["destinations"], key=lambda d: -great_len(hub, (d[1], d[2])))
    # farthest first: dests[0] is picked out, and an airport near a farther one shares its arc
    kept: list[tuple[str, float, float]] = []
    for d in dests:
        if all(math.hypot(d[1] - e[1], d[2] - e[2]) > NEAR for e in kept):
            kept.append(d)
    box = s.inset(-20)
    arcs, ends = P(), P()
    for _, dlon, dlat in kept[1:]:
        clip(arcs, screen(*great_circle(hub, (dlon, dlat))), box)
    for x, y in screen(np.array([d[1] for d in dests[1:]]), np.array([d[2] for d in dests[1:]])):
        ends.M(x, y).H(x)
    s.stroke(arcs, UI, 1.0)
    s.stroke(ends, UI_ALT, 3.2, cap="round")
    pts = screen(*great_circle(hub, (dests[0][1], dests[0][2])))
    s.stroke(clip(P(), pts, box), ACCENT, 3.0)
    s.fill(P().circle(pts[-1], 4.5), ACCENT)
    s.fill(P().circle(spot, 3.5), UI_HI)


def clip(d: Path, pts: Arr, box: Rect) -> Path:
    """Add the runs of the polyline `pts` inside `box` to `d`, and return `d`."""
    x, y = pts[:, 0], pts[:, 1]
    for a, b in runs((x > box.x) & (x < box.x1) & (y > box.y) & (y < box.y1)):
        if b - a > 1:
            d.poly(pts[a:b])
    return d
