"""Depth contours of the Great Belt from a survey grid, the line around its deepest hole picked out."""

import numpy as np
import shapely
from numpy.typing import NDArray
from scipy import ndimage
from shapely import LineString, Point, Polygon

from walldye import ACCENT, ACCENT_3, BG_ALT, UI, UI_ALT, Canvas, P, Path, design
from walldye.field import iso_lines
from walldye.geom import parts

type F64 = NDArray[np.float64]

# belt.npy: depth on a CELL_KM grid, x east and y south, its first sample at ORIGIN_KM from
# 10.95 E, 55.5 N; stored as (depth_m + 5) * 3, so land reads below 5.
CELL_KM = 0.25
ORIGIN_KM = np.array([-60.0, -62.0])
UP = 2  # cubic upsampling before contouring
STEP_M = 5
K = 43  # canvas units per km on a 16:9 screen
SPECK = 55  # closed contours smaller than this across, in canvas units, are dropped
SHALLOW_SPECK, SHALLOW_BLUR = 90, 2.0  # the same for 5 and 10 m, which also get more softening
ISLET = 36  # the same for land, which keeps Sprogø
# Land or water within EDGE of the frame that is under SMALL across, or shows under GLIMPSE
# of itself across or down, reads as a stray crop and takes the other side's part.
EDGE, SMALL, GLIMPSE = 120, 200, 120
CROWD = 3.5  # a 5 m line in deep water is cut where it runs this close to a 10 m line
SHORE_M = 1.0  # the coast is traced this deep, which keeps low islands above the softening
# the deepest hole's innermost rings, outermost first: tone and width
RINGS = ((ACCENT_3, 1.3), (ACCENT, 2.4))
NODE = 8  # ring points closer than this are merged before rounding, in canvas units


def trace(path: Path, line: F64) -> Path:
    """`line` as a smooth curve through its points, closed when it ends where it starts."""
    if np.allclose(line[0], line[-1]):
        return path.spline(line[:-1], closed=True)
    return path.spline(line)


def rounded(ring: F64) -> F64:
    """The closed `ring` with points under NODE apart merged, then cut three times by Chaikin's
    corner cutting, so the curve through it bends smoothly all round; open, last point not
    repeated."""
    pts = [ring[0]]
    for p in ring[1:-1]:
        if np.hypot(*(p - pts[-1])) >= NODE:
            pts.append(p)
    out = np.array(pts)
    for _ in range(3):
        nxt = np.roll(out, -1, axis=0)
        out = np.stack([0.75 * out + 0.25 * nxt, 0.25 * out + 0.75 * nxt], axis=1).reshape(-1, 2)
    return out


def trim_glimpses(
    soft: F64, origin: tuple[float, float], cell: float, size: tuple[int, int]
) -> None:
    """Flip, in place, each patch of land or water in `soft` that lies within EDGE of the
    frame and, measured inside the frame, is under SMALL across or under GLIMPSE across or
    down, to the other side of SHORE_M."""
    lo = np.maximum(np.ceil(-np.array(origin[::-1]) / cell), 0).astype(int)
    hi = np.floor((np.array(size[::-1]) - origin[::-1]) / cell).astype(int) + 1
    hi = np.minimum(hi, soft.shape)
    rim = EDGE / cell
    for is_land in (True, False):
        labels, _ = ndimage.label((soft < SHORE_M) == is_land)
        for i, box in enumerate(ndimage.find_objects(labels), 1):
            if box is None:
                continue
            a = np.maximum([box[0].start, box[1].start], lo)
            b = np.minimum([box[0].stop, box[1].stop], hi)
            if np.any(b <= a):
                continue
            gaps = np.concatenate([a - lo, hi - b])
            extent = np.sort(b - a) * cell
            if gaps.min() < rim and (extent[1] < SMALL or extent[0] < GLIMPSE):
                soft[labels == i] = SHORE_M + 1 if is_land else SHORE_M - 1


@design(aspects="any")
def draw(s: Canvas) -> None:
    raw: NDArray[np.uint8] = s.data("belt.npy")
    depth = raw.astype(np.float64) / 3 - 5
    span = (np.array(depth.shape[::-1]) - 1) * CELL_KM
    k = max(K, s.w / (span[0] - 2), s.h / (span[1] - 2))
    view = np.array([s.w, s.h]) / k
    hole = np.unravel_index(np.argmax(depth), depth.shape)
    hole_km = ORIGIN_KM + np.array([hole[1], hole[0]]) * CELL_KM
    at = s.pick(landscape=(0.62, 0.70), portrait=(0.42, 0.6))
    lo_km = hole_km - np.array([at.x, at.y]) / k
    lo_km = np.clip(lo_km, ORIGIN_KM + 0.5, ORIGIN_KM + span - view - 0.5)

    lo = np.floor((lo_km - ORIGIN_KM) / CELL_KM).astype(int) - 2
    hi = np.ceil((lo_km + view - ORIGIN_KM) / CELL_KM).astype(int) + 3
    lo = np.maximum(lo, 0)
    sub = depth[lo[1] : hi[1], lo[0] : hi[0]]
    rows, cols = np.mgrid[0 : (sub.shape[0] - 1) * UP + 1, 0 : (sub.shape[1] - 1) * UP + 1] / UP
    field = ndimage.gaussian_filter(ndimage.map_coordinates(sub, [rows, cols], order=3), UP / 2)
    ox, oy = (ORIGIN_KM + lo * CELL_KM - lo_km) * k
    origin = (float(ox), float(oy))
    cell = CELL_KM / UP * k
    deepest = Point((hole_km - lo_km) * k)

    # The coast is softened a further 150 m, which rounds harbor moles into the shore, and
    # padded with water, which closes every coastline past the frame so land fills as rings.
    soft = ndimage.gaussian_filter(field, UP * 0.6)
    trim_glimpses(soft, (ox, oy), cell, (s.w, s.h))
    # Water that never reaches the grid's edge, or only through a neck a few cells wide, is a
    # lake or a cut-off lagoon: fill it as land.
    labels, _ = ndimage.label(ndimage.binary_opening(soft >= SHORE_M, iterations=2))
    open_sea = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    sea = np.isin(labels, open_sea) & (labels > 0)
    sea = ndimage.binary_dilation(sea, iterations=2) & (soft >= SHORE_M)
    soft[(soft >= SHORE_M) & ~sea] = SHORE_M - 1

    def ashore(line: F64) -> bool:
        x, y = line[len(line) // 2]
        r, c = round((y - oy) / cell), round((x - ox) / cell)
        inside = 0 <= r < soft.shape[0] and 0 <= c < soft.shape[1]
        return inside and bool(soft[r, c] < SHORE_M)

    shore = np.pad(soft, 1, constant_values=STEP_M)
    coast, land = P(), P()
    for line in iso_lines(shore, SHORE_M, cell=cell, origin=(ox - cell, oy - cell)):
        if np.ptp(line, axis=0).max() >= ISLET:
            trace(land, line)
            trace(coast, line)
    s.fill(land, BG_ALT, rule="evenodd")

    lines: list[tuple[int, F64]] = []
    around: list[F64] = []
    shallows = ndimage.gaussian_filter(field, SHALLOW_BLUR)
    for n in range(1, int(field.max() // STEP_M) + 1):
        shallow = n <= 2  # the busiest lines
        f, tol, speck = (shallows, 2.5, SHALLOW_SPECK) if shallow else (field, 0.6, SPECK)
        for line in iso_lines(f, n * STEP_M, cell=cell, origin=origin, simplify=tol):
            ring = np.allclose(line[0], line[-1])
            if ring and np.ptp(line, axis=0).max() < speck or ashore(line):
                continue
            if ring and len(line) > 3 and Polygon(line).contains(deepest):
                around.append(line)
            lines.append((n, line))
    inner = around[-len(RINGS) :]
    kept = [(n, line) for n, line in lines if not any(line is r for r in inner)]
    walls = {
        n: shapely.union_all([LineString(ln).buffer(CROWD) for m, ln in kept if m == n])
        for n in {m for m, _ in kept if m % 2 == 0}
    }
    minor, index = P(), P()
    for n, line in kept:
        if n % 2 == 0:
            trace(index, line)
        elif n < 3:
            trace(minor, line)
        else:
            near = [walls[m] for m in (n - 1, n + 1) if m in walls]
            rest = (
                LineString(line).difference(shapely.union_all(near)) if near else LineString(line)
            )
            for piece in parts(
                shapely.line_merge(rest) if rest.geom_type == "MultiLineString" else rest
            ):
                if piece.length >= 20:
                    trace(minor, np.asarray(piece.coords))
    s.stroke(minor, UI, 0.9, join="round")
    s.stroke(index, UI, 1.6, join="round")
    s.stroke(coast, UI_ALT, 1.2, join="round")
    for line, (tone, width) in zip(inner, RINGS[len(RINGS) - len(inner) :], strict=True):
        s.stroke(P().spline(rounded(line), closed=True), tone, width)
