"""A breaking wave in one-bit Jarvis-Judice-Ninke error diffusion."""

from itertools import pairwise

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.ndimage import distance_transform_edt
from skimage.draw import line as draw_line
from skimage.draw import polygon as fill_poly

from walldye import ACCENT, ACCENT_3, BG_ALT, UI, UI_ALT, Canvas, Rect, Vec, design
from walldye.field import cells, falloff, gauss, noise_grid
from walldye.geom import spline_points
from walldye.pixel import dither, grid_runs

type Field = NDArray[np.float64]

CELL = 3
PAD = 64  # cells of margin, so distances count the curve just off the screen
# Wave-local coordinates, in which the wave sits as it does on a 16:9 screen.
SEA = 900  # the sea surface
LIP = (672, 606)  # the tip of the curl, placed by s.pick
# the back rises out of the sea well left of any screen, crests, and curls over into the lip
TOP = (
    (-1700, 897),
    (-1100, 882),
    (-560, 838),
    (-220, 752),
    (0, 660),
    (150, 575),
    (320, 498),
    (460, 454),
    (560, 460),
    (636, 496),
    (682, 548),
    (688, 594),
    (664, 624),
    (636, 624),
)
UNDER = ((636, 624), (652, 600), (644, 574), (612, 560), (574, 568), (550, 606))
FACE = ((548, 600), (550, 690), (600, 790), (700, 862), (860, 893), (1100, SEA))
# spray streamers flung forward off the lip, falling away down-right
STREAMERS = (
    ((692, 566), (735, 572), (772, 596), (796, 634), (806, 676)),
    ((690, 584), (722, 600), (744, 630), (754, 664)),
    ((694, 552), (742, 548), (786, 566), (818, 598)),
)
# body tones 0-3 (0 left bare), then the two foam steps
PALETTE = (None, BG_ALT, UI, UI_ALT, ACCENT_3, ACCENT)


def to_cells(pts: ArrayLike, o: Vec) -> Field:
    """Wave-local points as fractional (col, row) cell indices, cell centers at whole numbers."""
    return (np.asarray(pts, float) + o) / CELL - 0.5


def edge_dist(curve: Field, shape: tuple[int, int]) -> Field:
    """Canvas-unit distance from every cell center to the polyline `curve`, in cell indices."""
    rows, cols = shape
    free = np.ones((rows + 2 * PAD, cols + 2 * PAD), bool)
    q = np.rint(curve).astype(int) + PAD
    for (c0, r0), (c1, r1) in pairwise(q):
        rr, cc = draw_line(r0, c0, r1, c1)
        ok = (rr >= 0) & (rr < free.shape[0]) & (cc >= 0) & (cc < free.shape[1])
        free[rr[ok], cc[ok]] = False
    dist: Field = distance_transform_edt(free)
    return dist[PAD:-PAD, PAD:-PAD] * CELL


@design(aspects=("16:9", "32:9", "9:19.5", "10:16"))
def draw(s: Canvas) -> None:
    # the lip on the left third of a landscape screen; a little right of center and low on a
    # portrait one, with open sky above; whole cells, so the wave draws the same everywhere
    o = s.pick(landscape=(0.35, 0.561), portrait=(0.6, 0.66), snap=CELL) - LIP
    xs, ys = cells(Rect(0, 0, s.w, s.h), CELL)
    rows, cols = xs.shape
    xx, yy = xs - o.x, ys - o.y  # wave-local cell centers

    top = to_cells(spline_points(TOP, 40), o)
    under = to_cells(spline_points(UNDER, 40), o)
    face = to_cells(spline_points(FACE, 40), o)
    base = SEA + 90 + s.h - o.y  # below the screen, so the body reaches its bottom edge
    foot = to_cells(((FACE[-1][0], base), (TOP[0][0], base)), o)
    outline = np.vstack([top, under, face, foot])
    wave = np.zeros((rows, cols), bool)
    rr, cc = fill_poly(outline[:, 1], outline[:, 0], (rows, cols))
    wave[rr, cc] = True
    sea = yy >= SEA

    d_top = edge_dist(np.vstack([top, under]), (rows, cols))
    d_face = edge_dist(face, (rows, cols))
    n = noise_grid(cols, rows, 64, s.np_rng(3), octaves=3)

    # body: parallel streaks following the crest (brighter in the upper swell), a lit concave
    # face, a darker base
    streak = (0.5 + 0.5 * np.sin(d_top / 14 + n * 2.5)) ** 5
    upper = np.clip((640 - yy) / 120, 0, 1)
    body = (
        0.16
        + (0.30 + 0.42 * upper) * streak * np.exp(-d_top / 220)
        + 0.5 * np.exp(-d_face / 70) * np.clip((1060 - xx) / 360, 0, 1)
        - 0.14 * (yy - 450) / 630
    )
    swell = 0.12 + 0.07 * np.sin(np.maximum(yy - SEA, 0) ** 0.8 / 2.2 + n * 2)
    sink = np.clip((yy - SEA + 90) / 180, 0, 1)  # the swell's base settles into the sea
    # faint volume inside the barrel so the hollow doesn't read as a punched hole
    barrel = 0.26 * np.exp(-np.hypot((xx - 610) / 1.3, yy - 660) / 70) * np.exp(-d_face / 90)
    tone = np.where(
        wave, body * (1 - sink) + swell * sink, np.where(sea, swell, barrel * (xx > 540))
    )
    g = dither(tone, 4, method="jarvis", serpentine=True)

    # foam: a band straddling the crest that thins to a hairline away from the lip, and fades
    # where the back sinks toward the sea (only wider screens show that far)
    near = np.maximum(
        np.clip((xx - 420) / 240, 0, 1) ** 1.6,
        np.exp(-np.hypot(xx - LIP[0], yy - LIP[1]) / 90),
    )
    width = 6 + 34 * near
    sd = np.where(wave, d_top, -d_top)
    foam = gauss((sd - 0.45 * width) / width, 0.5) * (0.45 + 0.5 * near) * (1 + 0.6 * n * near)
    foam = np.clip(foam, 0, 1) * (sd > -width) * np.clip((SEA - 60 - yy) / 150, 0, 1)
    grain = noise_grid(cols, rows, 8, s.np_rng(9))
    spray = sum(
        np.exp(-edge_dist(to_cells(spline_points(c, 20), o), (rows, cols)) / 5)
        * falloff(np.hypot(xx - c[0][0], yy - c[0][1]), 160, 1.6)
        for c in STREAMERS
    )
    foam = np.maximum(foam, np.clip(spray * (0.35 + 0.9 * grain), 0, 1) * ~wave)
    f = dither(foam, 3, method="jarvis", serpentine=True)

    grid = np.where(f > 0, 3 + f, g)
    # a thin solid rim right at the lip tip
    grid[wave & (d_top <= CELL * 2) & (np.hypot(xx - LIP[0], yy - LIP[1]) < 34)] = 5
    grid_runs(s, grid, PALETTE, CELL)
