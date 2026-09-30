"""Spa-Francorchamps as a dot-matrix live-timing map in 24 mini-sectors."""

import bisect
import math

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, UI, UI_ALT, UI_HI, Canvas, Paint, design
from walldye.geom import Polyline
from walldye.pixel import glyphs, grid_runs

PITCH, DOT = 8, 4  # dot lattice pitch (the braille pitch of 8x16 glyphs at px=2) and dot size
# Sector ends in centerline meters (S1 to the entry of Les Combes, S2 just past Stavelot), and
# the mini-sectors in each.
SECTORS = ((2370, 8), (5050, 9), (7000, 7))
FAST = (3, 4, 5, 6, 7)  # Eau Rouge and Raidillon, then the Kemmel straight up to the S1 split
BOX = (1240, 540, 1150, 720)  # where the track is fitted: center x, center y, width, height
# (text, centerline meters, dx, dy): a label at that track point plus an offset in px
LABELS = (("LA SOURCE", 385, -104, -6), ("EAU ROUGE", 1080, -112, -20), ("POUHON", 3950, -90, 30))
# A completed lap; S1 is the best sector, marked with ACCENT as a timing screen marks a best.
TIMING = (
    "SPA  7.004 KM",
    "─" * 16,
    "",
    "S1   31.412",
    "S2   46.905",
    "S3   28.337",
    "",
    "",  # the mini-sector blocks
    "",
    "LAP  1:46.654",
)
X0, Y0, LH = 180, 300, 32  # timing column origin and line height (8x16 glyphs at px=2)
TRACK, BEST, SPLIT = 1, 2, 3  # dot roles, indices into the dot palette


def starts() -> list[tuple[float, int]]:
    """(centerline meters, sector index) at the start of every mini-sector, in lap order."""
    out, lo = [], 0
    for si, (hi, n) in enumerate(SECTORS):
        out += [(lo + (hi - lo) * j / n, si) for j in range(n)]
        lo = hi
    return out


STARTS = starts()


def fit(spa: list[list[float]]) -> NDArray[np.float64]:
    """The centerline in broadcast orientation (north to the left: La Source bottom-left,
    Kemmel climbing to the right), fitted into BOX, in dot units."""
    pts = -np.asarray(spa, dtype=np.float64)[:, ::-1]  # (east, north) to screen (-north, -east)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    cx, cy, bw, bh = BOX
    k = min(bw / (hi[0] - lo[0]), bh / (hi[1] - lo[1])) / PITCH
    return (pts - (lo + hi) / 2) * k + np.array([cx, cy]) / PITCH


def raster(line: Polyline) -> list[tuple[tuple[int, int], float]]:
    """Ordered 8-connected, one-dot-thin lattice cells along a closed line, each with the arc
    length where the line enters it."""
    ds = np.arange(int(line.length * 4)) / 4
    xy: list[list[float]] = np.rint(line.at(ds)).tolist()
    seq: list[tuple[tuple[int, int], float]] = []
    for (x, y), d in zip(xy, ds.tolist(), strict=True):
        c = (int(x), int(y))
        if not seq or seq[-1][0] != c:
            seq.append((c, d))
    changed = True
    while changed:  # drop corner cells whose neighbors already touch diagonally
        changed = False
        out: list[tuple[tuple[int, int], float]] = []
        for k, cell in enumerate(seq):
            a = out[-1][0] if out else seq[-1][0]
            b = seq[(k + 1) % len(seq)][0]
            if max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1 and a != b:
                changed = True
                continue
            out.append(cell)
        seq = out
    return seq


def tint(col: int, row: int, ch: str) -> Paint:
    """Timing column colors: labels quiet, times bright, the best sector lit."""
    if row == 1:
        return UI
    if row in (3, 4, 5, 9) and col < 5:
        return UI_ALT
    return ACCENT if row == 3 else UI_HI


@design()
def draw(s: Canvas) -> None:
    # TUMFTM racetrack-database Spa.csv centerline, x east / y north in meters, simplified at
    # 1.5 m; it starts on the start/finish line.
    spa: list[list[float]] = s.data("spa.json")
    # Unsmoothed: smoothing would shift the start/finish vertex and the meter scale.
    line = Polyline(fit(spa), closed=True)
    per_m = line.length / SECTORS[-1][0]  # dot units per centerline meter
    bounds = [m for m, _ in STARTS]

    cells = raster(line)
    dots = np.zeros((s.h // PITCH, s.w // PITCH), dtype=np.int64)
    for (x, y), d in cells:
        mini = bisect.bisect_right(bounds, d / per_m) - 1
        dots[y, x] = BEST if mini in FAST else TRACK
    for m, (meters, si) in enumerate(STARTS):
        bd = meters * per_m
        for (x, y), d in cells:
            if min(abs(d - bd), line.length - abs(d - bd)) < 1.6:
                dots[y, x] = 0  # a gap in the dots at every mini-sector boundary
        if m == 0 or STARTS[m - 1][1] != si:  # start/finish and sector splits get a tick
            p, n = line.at(bd), line.tangent(bd).perp()
            # snapped to one of 8 directions, so the tick is a straight row of dots
            a = math.radians(45 * round(math.degrees(math.atan2(n.y, n.x)) / 45))
            step = (round(math.cos(a)), round(math.sin(a)))
            w = 3 if m == 0 else 2
            for k in range(-w, w + 1):
                dots[round(p.y) + k * step[1], round(p.x) + k * step[0]] = SPLIT
    # Dots sit on every other cell of a DOT grid, so no two ever merge into one run.
    grid = np.zeros((s.h // DOT, s.w // DOT), dtype=np.int64)
    grid[::2, ::2] = dots
    grid_runs(s, grid, (None, UI_ALT, ACCENT, UI_HI), DOT, (DOT / 2, DOT / 2))

    for text, meters, dx, dy in LABELS:
        p = line.at(meters * per_m) * PITCH
        glyphs(s, text, UI, at=(round(p.x + dx), round(p.y + dy)), font="8x16", px=1)

    glyphs(s, TIMING, tint, at=(X0, Y0), font="8x16", px=2)
    with s.buckets((UI_HI, ACCENT), "fill") as blocks:  # one block per mini-sector
        for m, (_, si) in enumerate(STARTS):
            blocks[int(m in FAST)].rect(X0 + m * 10 + si * 8, Y0 + 7 * LH + 8, 6, 16)
