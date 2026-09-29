"""The Pikes Peak hill climb on a contour map of real elevation, its course traced from the start line through the switchbacks to the summit."""

import numpy as np
import shapely
from numpy.typing import NDArray
from scipy import ndimage
from shapely import LineString
from shapely.prepared import prep

from walldye import ACCENT, BG_ALT, UI, UI_ALT, Canvas, P, by_regime, design
from walldye.field import iso_lines
from walldye.geom import parts

type F64 = NDArray[np.float64]

# terrain.npy: elevation in meters on a CELL_M grid in the map frame (see draw), its first
# sample at ORIGIN_M. course.json: the course in the same frame, start line first.
CELL_M = 100.0
ORIGIN_M = np.array([-15600.0, -4400.0])
UP = 4  # cubic upsampling before contouring, which rounds off the sample-spacing corners
STEP_M, INDEX = 200 * 0.3048, 5  # a contour every 200 ft, an index contour every 1,000 ft
LOWEST = 47  # 9,400 ft, the first 200-ft contour above the start line; below it, index only
# Closed contours smaller than this across, in canvas units, are dropped: minor rings left
# stranded near the start line need the larger bound.
SPECK, SPECK_MINOR = 30, 75
LINE, BAR, DOT = 2.5, 16, 4.5  # the course, half the start line, the finish's radius
GAP, STUB = 5, 22  # contours keep GAP from the course's centerline; pieces left under STUB go
SKIRT = 12  # a ring the clip misses but that runs this close to the course is dropped
# A dark ground sits closer to its first step, so dark themes lift the contours one step.
MINOR_TONE, INDEX_TONE = by_regime(UI, BG_ALT), by_regime(UI_ALT, UI)


def centripetal(pts: F64, spacing: float) -> F64:
    """Points about `spacing` apart on the centripetal Catmull-Rom curve through `pts`: it
    passes every point and, unlike the uniform kind, never loops at a hairpin."""
    keep = np.r_[True, np.any(np.diff(pts, axis=0) != 0, axis=1)]
    p = pts[keep]
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = [p[1:2]]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1 : i + 3]
        t1 = np.hypot(*(p1 - p0)) ** 0.5
        t2 = t1 + np.hypot(*(p2 - p1)) ** 0.5
        t3 = t2 + np.hypot(*(p3 - p2)) ** 0.5
        n = max(1, int(np.ceil(np.hypot(*(p2 - p1)) / spacing)))
        t = np.linspace(t1, t2, n + 1)[1:, None]
        a1 = (t1 - t) / t1 * p0 + t / t1 * p1
        a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        b1 = (t2 - t) / t2 * a1 + t / t2 * a2
        b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
        out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    return np.vstack(out)


def start_line(line: F64) -> F64:
    """The two ends of a line across `line` at its first point, squared to the heading over the
    dozen units after it."""
    near = np.hypot(*(line - line[0]).T)
    ahead = line[np.argmax(near > 12)] - line[0]
    across = np.array([-ahead[1], ahead[0]]) / np.hypot(*ahead) * BAR
    return np.stack([line[0] + across, line[0] - across])


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Map frame, in meters: u runs from the start line towards the summit, v across it, and
    # the origin is the middle of the course. Landscape screens show u to the right; portrait
    # screens turn the map a quarter left so the course climbs.
    terrain: NDArray[np.int16] = s.data("terrain.npy")
    route: list[list[int]] = s.data("course.json")
    k = 0.145  # canvas units per meter
    c = s.pick(landscape=(0.57, 0.52), portrait=(0.5, 0.54))

    def screen(uv: F64) -> F64:
        u, v = uv[:, 0] * k, uv[:, 1] * k
        if s.landscape:
            return np.stack([c.x + u, c.y + v], axis=1)
        return np.stack([c.x + v, c.y - u], axis=1)

    corners = np.array([[0, 0], [s.w, s.h]], dtype=np.float64)
    if s.landscape:
        uv = (corners - (c.x, c.y)) / k
    else:
        uv = np.stack([c.y - corners[:, 1], corners[:, 0] - c.x], axis=1) / k
    lo = np.floor((uv.min(axis=0) - ORIGIN_M) / CELL_M).astype(int) - 2
    hi = np.ceil((uv.max(axis=0) - ORIGIN_M) / CELL_M).astype(int) + 3
    sub = terrain[lo[1] : hi[1], lo[0] : hi[0]].astype(np.float64)
    rows, cols = np.mgrid[0 : (sub.shape[0] - 1) * UP + 1, 0 : (sub.shape[1] - 1) * UP + 1] / UP
    # a 50 m blur on top rounds the sharp turns marching squares makes at saddles
    field = ndimage.gaussian_filter(ndimage.map_coordinates(sub, [rows, cols], order=3), UP / 2)
    origin = ORIGIN_M + lo * CELL_M

    course = centripetal(screen(np.array(route, dtype=np.float64)), 2)
    start = start_line(course)
    # the finish is a dot: a bar across the last short upturn to the summit reads as a letter
    finish = shapely.Point(course[-1])
    gap = shapely.union_all(
        [
            LineString(course).buffer(GAP),
            LineString(start).buffer(GAP),
            finish.buffer(DOT + GAP - LINE / 2),
        ]
    )
    near_gap = prep(gap)
    near_course = prep(LineString(course).buffer(SKIRT))

    minor, index = P(), P()
    for n in range(int(np.ceil(field.min() / STEP_M)), int(field.max() / STEP_M) + 1):
        if n % INDEX and n < LOWEST:
            continue
        for line in iso_lines(field, n * STEP_M, cell=CELL_M / UP, origin=(origin[0], origin[1])):
            pts = screen(line)
            ring = np.allclose(line[0], line[-1])
            if ring and np.ptp(pts, axis=0).max() < (SPECK_MINOR if n % INDEX else SPECK):
                continue
            path = minor if n % INDEX else index
            contour = LineString(pts)
            if not near_gap.intersects(contour):
                if not (ring and near_course.intersects(contour)):
                    path.poly(pts)
                continue
            for piece in parts(shapely.line_merge(contour.difference(gap))):
                if piece.length >= STUB:
                    path.poly(np.asarray(piece.coords))
    s.stroke(minor, MINOR_TONE, 1.1, join="round")
    s.stroke(index, INDEX_TONE, 1.6, join="round")

    s.stroke(P().poly(course), ACCENT, LINE, cap="round", join="round")
    s.stroke(P().poly(start), ACCENT, LINE)
    s.fill(P().circle(course[-1], DOT), ACCENT)
