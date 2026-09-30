"""Curiosity's drive from its landing site up the foot of Mount Sharp, traced over contours of Gale crater's floor from orbital elevation data."""

import math

import numpy as np
import shapely
from numpy.typing import NDArray
from scipy import ndimage
from shapely import LineString
from shapely.prepared import prep

from walldye import ACCENT, BG_ALT, UI, UI_HI, Canvas, P, by_regime, design, mix
from walldye.field import iso_lines
from walldye.geom import parts

type F64 = NDArray[np.float64]

# traverse.json: the drive in meters east and south of terrain.npy's first sample.
# terrain.npy: elevation in decimeters above -5,000 m on a 96 m grid, row 0 at the north edge.
# terrain-wide.npy: the same on a 120 m grid already turned by TURN, its first sample at
# WIDE_ORIGIN meters from the latest position; outside the detailed model it holds a coarser
# global one, blended in over 3 km.
CELL, WIDE_CELL = 96.0, 120.0
WIDE_ORIGIN = np.array([-44500.0, -7500.0])
TURN = math.radians(-137.6)  # sets the landing-to-latest line 35 degrees above the horizontal
UP = 3  # cubic upsampling before contouring, so the grid's corners don't show
STEP_M, INDEX = 50.0, 5  # a contour every 50 m, an index contour every 250 m
SPECK = 18  # closed contours smaller than this across, in canvas units, are dropped
LINE, GAP, STUB = 2.2, 6, 16  # the drive; contours keep GAP from it and drop pieces under STUB
LAND, NOW = 9, 7  # radii of the landing ring and the latest position
CLEAR = 110  # closed contours this close to the landing ring are dropped, so it stands alone
TAIL_M = 8000.0  # the last stretch of the drive, picked out with the latest position
# Out-and-back side trips: the drive skips any stretch shorter than SPUR_M that comes back
# within REACH_M of where it left.
SPUR_M, REACH_M = 1500.0, 100.0
# On paper the quietest step vanishes, so light themes draw the minor contours one step up.
MINOR = by_regime(BG_ALT, mix(BG_ALT, UI, 0.5))


def unspur(pts: F64) -> NDArray[np.int64]:
    """Indices into `pts` that skip each stretch shorter than SPUR_M returning within REACH_M
    of its start, jumping from its start to the furthest point that comes back; the first and
    last points are always kept."""
    walked = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    keep, i = [], 0
    while i < len(pts):
        keep.append(i)
        end = int(np.searchsorted(walked, walked[i] + SPUR_M, side="right"))
        back = np.flatnonzero(np.hypot(*(pts[i + 1 : end] - pts[i]).T) < REACH_M)
        i = i + 1 + int(back[-1]) if back.size else i + 1
    return np.array(keep)


@design(aspects="any")
def draw(s: Canvas) -> None:
    drive = np.array(s.data("traverse.json"), dtype=np.float64)
    # Each orientation contours its own grid, in grid meters g drawn at c + flip * k * (g - at).
    # Landscape screens use the turned grid, with g measured from the latest position, so the
    # drive climbs to the upper right. Portrait screens put south up on the plain grid.
    if s.landscape:
        raw: NDArray[np.uint16] = s.data("terrain-wide.npy")
        cell, origin0, k, flip = WIDE_CELL, WIDE_ORIGIN, 0.06, 1.0
        c = s.pick(landscape=(0.68, 0.38), portrait=(0.5, 0.5))
        cos, sin = math.cos(TURN), math.sin(TURN)
        rel = drive - drive[-1]
        path_g = np.stack([cos * rel[:, 0] - sin * rel[:, 1], sin * rel[:, 0] + cos * rel[:, 1]], 1)
        at = np.zeros(2)
    else:
        raw = s.data("terrain.npy")
        cell, origin0, flip = CELL, np.zeros(2), -1.0
        extent_v, extent_u = raw.shape[0] * CELL, raw.shape[1] * CELL
        k = max(0.05, s.h / (extent_v - 1500), s.w / (extent_u - 1500))
        c = s.pick(landscape=(0.5, 0.5), portrait=(0.5, 0.56))
        path_g = drive
        at = (drive.min(axis=0) + drive.max(axis=0)) / 2
    terrain = raw.astype(np.float64) / 10 - 5000
    extent = origin0 + np.array([terrain.shape[1], terrain.shape[0]], dtype=np.float64) * cell

    # slide the view so the screen stays over the grid
    corners = at + flip * (np.array([[0, 0], [s.w, s.h]], dtype=np.float64) - (c.x, c.y)) / k
    lo, hi = corners.min(axis=0), corners.max(axis=0)
    margin = 3 * cell
    shift = np.maximum(0, origin0 + margin - lo) - np.maximum(0, hi - (extent - margin))
    at, lo, hi = at + shift, lo + shift, hi + shift

    def screen(g: F64) -> F64:
        return np.array([c.x, c.y]) + flip * k * (g - at)

    i0 = np.maximum(np.floor((lo - origin0) / cell).astype(int) - 2, 0)
    i1 = np.ceil((hi - origin0) / cell).astype(int) + 3
    sub = terrain[i0[1] : i1[1], i0[0] : i1[0]]
    rows, cols = np.mgrid[0 : (sub.shape[0] - 1) * UP + 1, 0 : (sub.shape[1] - 1) * UP + 1] / UP
    field = ndimage.gaussian_filter(ndimage.map_coordinates(sub, [rows, cols], order=3), UP / 2)
    origin = origin0 + i0 * cell

    walked = np.r_[0, np.cumsum(np.hypot(*np.diff(drive, axis=0).T))]
    kept = unspur(path_g)
    route = screen(path_g[kept])
    split = int(np.argmax(walked[kept] >= walked[-1] - TAIL_M))
    land, now = route[0], route[-1]
    early = LineString(route[: split + 1]).simplify(1.0)
    tail = np.asarray(LineString(route[split:]).simplify(1.0).coords)
    drawn = early.difference(shapely.Point(land).buffer(LAND + 3))
    keep_out = shapely.union_all(
        [
            LineString(route).buffer(GAP),
            shapely.Point(land).buffer(LAND + GAP),
            shapely.Point(now).buffer(NOW + GAP),
        ]
    )
    near = prep(keep_out)

    minor, index = P(), P()
    for n in range(int(np.ceil(field.min() / STEP_M)), int(field.max() / STEP_M) + 1):
        path = minor if n % INDEX else index
        for line in iso_lines(
            field, n * STEP_M, cell=cell / UP, origin=(origin[0], origin[1]), simplify=8
        ):
            pts = screen(line)
            if np.allclose(line[0], line[-1]) and (
                np.ptp(pts, axis=0).max() < SPECK or np.hypot(*(pts - land).T).min() < CLEAR
            ):
                continue
            contour = LineString(pts)
            if not near.intersects(contour):
                path.poly(pts)
                continue
            for piece in parts(shapely.line_merge(contour.difference(keep_out))):
                if piece.length >= STUB:
                    path.poly(np.asarray(piece.coords))
    s.stroke(minor, MINOR, 1.1, join="round")
    s.stroke(index, UI, 1.3, join="round")

    trail = P()
    for piece in parts(drawn):
        trail.poly(np.asarray(piece.coords))
    s.stroke(trail, UI_HI, LINE, cap="round", join="round")
    s.stroke(P().circle(land, LAND), UI_HI, 1.6)
    s.stroke(P().poly(tail), ACCENT, LINE + 0.6, cap="round", join="round")
    s.fill(P().circle(now, NOW), ACCENT)
