"""The 1955 Mille Miglia on a halftone relief map of Italy: the route a pixel line through its control towns, lit from Florence over the Futa and Raticosa passes to Bologna."""

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import (
    binary_dilation,
    binary_erosion,
    convolve,
    distance_transform_edt,
    label,
    map_coordinates,
    maximum,
    mean,
    minimum,
)
from shapely.geometry import LineString
from skimage.draw import polygon as fill_poly
from skimage.morphology import skeletonize

from walldye import ACCENT, ACCENT_3, ACCENT_6, BG_ALT, UI_ALT, Canvas, design
from walldye.geom import Polyline
from walldye.pixel import dither, grid_runs

type F64 = NDArray[np.float64]

CELL = 2
MARGIN = 90
LON0 = 12.5  # central meridian of the sinusoidal projection
KM_LAT, KM_LON = 110.57, 111.32  # km per degree of latitude, and of longitude at the equator
# relief.npy: ETOPO1 elevation in 20 m steps on a 0.05 x 0.04 degree grid, row 0 at the north
R_LON, R_LAT, R_DLON, R_DLAT = 6.55, 47.13, 0.05, 0.04
SEA, LAND, ROUTE, GLOW_FAR, GLOW, LIT = range(6)  # ROUTE also marks the towns
PALETTE = [None, BG_ALT, UI_ALT, ACCENT_6, ACCENT_3, ACCENT]


def project(lon: F64, lat: F64) -> tuple[F64, F64]:
    """Sinusoidal projection about LON0, in km east and km south."""
    return (lon - LON0) * KM_LON * np.cos(np.radians(lat)), -lat * KM_LAT


def unproject(x: F64, y: F64) -> tuple[F64, F64]:
    """Inverse of project()."""
    lat = -y / KM_LAT
    return LON0 + x / (KM_LON * np.cos(np.radians(lat))), lat


def trace(pts: F64) -> list[tuple[int, int]]:
    """The cells of a polyline in cell units as an 8-connected line one cell thin."""
    line = Polyline(pts)
    xy = np.rint(line.at(np.arange(0, line.length, 0.25))).astype(int).tolist()
    seq: list[tuple[int, int]] = []
    for x, y in xy:
        if not seq or seq[-1] != (x, y):
            seq.append((x, y))
    out: list[tuple[int, int]] = []
    for i, c in enumerate(seq):
        # drop a corner cell whose neighbours already touch diagonally
        if out and i + 1 < len(seq):
            a, b = out[-1], seq[i + 1]
            if max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1:
                continue
        out.append(c)
    for i in range(1, len(out) - 1):
        # a one-cell spike off a straight run goes back into the run
        (ax, ay), (bx, by) = out[i - 1], out[i + 1]
        if sorted((abs(ax - bx), abs(ay - by))) == [0, 2]:
            out[i] = ((ax + bx) // 2, (ay + by) // 2)
    return out


def spoke(r0: int, c0: int, n: int, ex: int, ey: int) -> list[tuple[int, int]]:
    """Cells from the middle of the face of the n-cell square at row r0, column c0 that looks
    toward the cell (ex, ey): straight out one cell, then on to that cell along an 8-connected
    line. On an even face the middle is the one of its two middle cells nearer the target."""
    lo, hi = (n - 1) // 2, n // 2
    ox, oy = 2 * ex - 2 * c0 - n + 1, 2 * ey - 2 * r0 - n + 1  # doubled offsets from the centre
    if abs(ox) >= abs(oy):
        x, y = (c0 + n if ox > 0 else c0 - 1), min(max(ey, r0 + lo), r0 + hi)
    else:
        x, y = min(max(ex, c0 + lo), c0 + hi), (r0 + n if oy > 0 else r0 - 1)
    out = [(x, y)]
    while (x, y) != (ex, ey):
        x += int(ex > x) - int(ex < x)
        y += int(ey > y) - int(ey < y)
        out.append((x, y))
    return out


def fold(run: dict[int, int]) -> None:
    """Straighten a line of per-row columns, in row order, in place: a stretch of two rows or
    fewer that steps aside and back, or that hooks off either end, takes its neighbours'
    column. Steps between rows stay within one column."""
    rows = list(run)
    while True:
        segs: list[list[int]] = []
        for r in rows:
            if segs and run[segs[-1][0]] == run[r]:
                segs[-1].append(r)
            else:
                segs.append([r])
        for k, seg in enumerate(segs):
            before = run[segs[k - 1][0]] if k > 0 else None
            after = run[segs[k + 1][0]] if k + 1 < len(segs) else None
            to = after if before is None else before if after in (None, before) else None
            if len(seg) <= 2 and len(segs) > 1 and to is not None:
                for r in seg:
                    run[r] = to
                break
        else:
            return


@design(aspects="any")
def draw(s: Canvas) -> None:
    land: list[list[list[float]]] = s.data("italy.json")["land"]
    rdata = s.data("route.json")
    route = np.array(rdata["route"], dtype=np.float64)
    controls: dict[str, int] = rdata["controls"]
    relief = np.asarray(s.data("relief.npy"), dtype=np.float64) * 20

    rings = [project(np.array(r)[:, 0], np.array(r)[:, 1]) for r in land]
    x0 = min(float(rx.min()) for rx, _ in rings)
    x1 = max(float(rx.max()) for rx, _ in rings)
    y0 = min(float(ry.min()) for _, ry in rings)
    y1 = max(float(ry.max()) for _, ry in rings)
    # Italy is tall: on a landscape screen its full height sits right of centre with the rest
    # empty; on a portrait one it fills the width in the upper half.
    if s.landscape:
        k = (s.h - 2 * MARGIN) / (y1 - y0)
        cx, cy = s.w * 0.64, s.h / 2
    else:
        k = min((s.w - 2 * MARGIN) / (x1 - x0), s.h * 0.62 / (y1 - y0))
        cx, cy = s.w / 2, s.h * 0.44
    ox = round((cx - k * (x0 + x1) / 2) / CELL) * CELL
    oy = round((cy - k * (y0 + y1) / 2) / CELL) * CELL
    cols, rows = s.w // CELL, s.h // CELL

    def to_cell(x: F64, y: F64) -> tuple[F64, F64]:
        return (k * x + ox) / CELL, (k * y + oy) / CELL

    mask = np.zeros((rows, cols), dtype=bool)
    for rx, ry in rings:
        cc, rr = to_cell(rx, ry)
        pr, pc = fill_poly(rr, cc, (rows, cols))
        mask[pr, pc] = True

    # Relief: the plains a sparse screen of small dots, the uplands a step up.
    ys, xs = np.mgrid[0:rows, 0:cols]
    lon, lat = unproject(((xs + 0.5) * CELL - ox) / k, ((ys + 0.5) * CELL - oy) / k)
    at = [((R_LAT - lat) / R_DLAT).ravel(), ((lon - R_LON) / R_DLON).ravel()]
    elev = map_coordinates(relief, at, order=1, mode="nearest").reshape(rows, cols)
    up = np.clip((elev - 200) / 800, 0, 1)
    tone = 0.08 + 0.4 * up * up * (3 - 2 * up)
    dots = (dither(tone, 2, method="clustered") == 1) & mask

    rx, ry = project(route[:, 0], route[:, 1])
    rc, rr = to_cell(rx, ry)
    pts = np.c_[rc, rr]
    lit0, lit1 = controls["Firenze"], controls["Bologna"]
    out_leg, home_leg = trace(pts[: lit0 + 1]), trace(pts[lit1:])
    road = np.zeros((rows, cols), dtype=bool)
    for c, r in out_leg + home_leg:
        road[r, c] = True

    # The lit crossing runs steeper than a diagonal throughout, so it is drawn a row at a time:
    # a run two cells wide, each sideways step half that.
    crossing = Polyline(np.asarray(LineString(pts[lit0 : lit1 + 1]).simplify(0.5).coords))
    xy = crossing.at(np.linspace(0, crossing.length, int(crossing.length * 8) + 2))
    along_rows = np.rint(xy[:, 1]).astype(int)
    run: dict[int, int] = {}
    step = -1 if along_rows[-1] < along_rows[0] else 1
    for r in range(int(along_rows[0]), int(along_rows[-1]) + step, step):
        c = round(float(xy[along_rows == r, 0].mean()) - 0.5)
        if r - step in run:
            c = min(max(c, run[r - step] - 1), run[r - step] + 1)
        run[r] = c
    # the two rows at each end go under the town squares, so only the rows between are folded
    inner = {r: run[r] for r in list(run)[2:-2]}
    fold(inner)
    run.update(inner)
    lit = np.zeros((rows, cols), dtype=bool)
    for r, c in run.items():
        lit[r, c : c + 2] = True

    # Town squares as (row, column, size): the start, the controls, and the crossing's two ends,
    # each set on the lit run that enters it so the run meets the middle of the near face.
    ci, ri = np.rint(rc).astype(int), np.rint(rr).astype(int)
    towns = [(ri[0] - 2, ci[0] - 2, 5)]
    towns += [(ri[i] - 1, ci[i] - 1, 3) for i in controls.values() if i not in (lit0, lit1)]
    for end, back in ((int(along_rows[0]), step), (int(along_rows[-1]), -step)):
        top, face = (end - 1, end - 2) if back < 0 else (end - 2, end + 2)
        towns.append((top, run[face] - 1, 4))
        lit[top : top + 4] = False
    assert set(lit.sum(axis=1).tolist()) <= {0, 2}

    # Tidy the unlit route: a hairpin whose legs touch closes to one tip without a burr, and
    # where it meets Brescia and the crossing's two towns each leg leaves the middle of a face.
    joins = [(towns[0], [out_leg, home_leg[::-1]]), (towns[-2], [out_leg[::-1]])]
    joins.append((towns[-1], [home_leg]))
    cut = np.zeros((rows, cols), dtype=bool)
    guard = np.zeros((rows, cols), dtype=bool)
    for (r, c, n), _ in joins:
        cut[r - 2 : r + n + 2, c - 2 : c + n + 2] = True
        guard[r - 6 : r + n + 6, c - 6 : c + n + 6] = True
    for r, c, n in towns:
        guard[r - 2 : r + n + 2, c - 2 : c + n + 2] = True
    road = skeletonize(road & ~cut)
    for _ in range(2):
        ends = convolve(road.astype(int), np.ones((3, 3), dtype=int), mode="constant") == 2
        road &= ~(ends & road & ~guard)
    road = skeletonize(road)
    for (r, c, n), legs in joins:
        for leg in legs:
            ex, ey = next((x, y) for x, y in leg if not cut[y, x])
            for x, y in spoke(r, c, n, ex, ey):
                road[y, x] = True

    # A clear channel along the route and round the towns, wider along the lit crossing.
    clear = binary_dilation(road) | binary_dilation(lit, iterations=2)
    for r, c, n in towns:
        clear[r - 1 : r + n + 1, c - 1 : c + n + 1] = True
    ids, n = label(dots)
    idx = np.arange(1, n + 1)
    whole = np.bincount(ids.ravel(), minlength=n + 1)
    kept = np.bincount(ids[~clear], minlength=n + 1)
    # Each mountain dot beside the crossing picks up its light, the whole dot in one tone, and
    # only along the stretch between the two towns.
    reach = np.r_[np.inf, minimum(distance_transform_edt(~lit) * CELL, ids, idx)]
    high = np.r_[False, maximum(elev, ids, idx) > 300]
    a, b = pts[lit0], pts[lit1]
    d = b - a
    along = (
        (np.asarray(mean(xs, ids, idx)) - a[0]) * d[0]
        + (np.asarray(mean(ys, ids, idx)) - a[1]) * d[1]
    ) / (d @ d)
    slack = 3 / float(np.hypot(*d))
    beside = np.r_[False, (along > -slack) & (along < 1 + slack)]
    paint = np.where(high & beside & (reach < 36), GLOW_FAR, LAND)
    paint[high & beside & (reach < 18)] = GLOW
    paint[(kept < whole) & ((kept < 4) | (paint != LAND))] = SEA
    paint[0] = SEA
    grid = paint[ids]
    # The coast, except where the route runs along it and stands in for it.
    coast = mask & ~binary_erosion(mask) & ~clear & (distance_transform_edt(~road) > 8)
    cid, cn = label(coast, structure=np.ones((3, 3)))
    grid[coast & (np.bincount(cid.ravel(), minlength=cn + 1)[cid] >= 6)] = LAND
    grid[clear] = SEA
    grid[road] = ROUTE
    grid[lit] = LIT
    for r, c, n in towns:
        grid[r : r + n, c : c + n] = ROUTE
    # Brescia, the start and finish, is an open square.
    grid[ri[0] - 1 : ri[0] + 2, ci[0] - 1 : ci[0] + 2] = SEA
    grid_runs(s, grid, PALETTE, CELL)
