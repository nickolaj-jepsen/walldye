"""One dune crest: iso-line ripples comb the windward slope, the slip face lies in shade and the summit is lit."""

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from shapely.geometry import Polygon
from skimage.measure import approximate_polygon

from walldye import (
    ACCENT,
    ACCENT_5,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    Canvas,
    P,
    by_regime,
    design,
    ladder,
    lerp,
    mix,
    smoothstep,
)
from walldye.field import cells, falloff, gauss, iso_lines, noise_grid, runs
from walldye.geom import Polyline, spline_points

# The crest profile as drawn at 16:9, running on past both edges for wider screens.
CREST = np.array(
    [
        (-560, 1040),
        (-300, 925),
        (-40, 792),
        (0, 770),
        (320, 672),
        (640, 522),
        (960, 430),
        (1240, 450),
        (1600, 496),
        (1920, 520),
        (1960, 521),
        (2200, 529),
        (2400, 531),
    ]
)
KMAX = 1.4  # the most a flank stretches; a wider screen shows more of the profile instead
# The slip-face edge leaves the crest right of the summit and bows right out to its foot; the
# points past y 1100 only reach the bottom of a tall canvas.
BRINK = np.array(
    [
        (1149, 538),
        (1209, 642),
        (1263, 750),
        (1303, 863),
        (1330, 981),
        (1345, 1100),
        (1356, 1230),
        (1366, 1400),
        (1374, 1700),
        (1380, 2100),
        (1384, 2600),
    ]
)
LEAVE = 80  # the brink leaves the crest this far right of the summit
CELL = 3  # ripple field sample spacing
SIMPLIFY = 1.2  # ripple tolerance; the spline rounds it off, and finer costs a third more bytes
S0, GROW, FAR = 6.5, 0.5, 650  # ripple spacing at the crest, its growth, and where growth stops
TONES = ladder((ACCENT_5, ACCENT), 16)  # the crest glow, from its dim ends to the summit
# the slip face in shadow: BG_DEEP is paler than the ground on a light theme, so step towards FG
SHADE = by_regime(BG_DEEP, mix(BG, BG_ALT, 0.6))


def distance(
    line: NDArray[np.float64], xs: NDArray[np.float64], ys: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Distance from each point (xs, ys) to the polyline `line`: to its nearest point when
    resampled every 2 units, which overshoots by at most 0.1 units from 5 units out (a k-d
    tree is several times faster than shapely here)."""
    dense = Polyline(line).resample(2.0).pts
    dist, _ = cKDTree(dense).query(np.c_[xs.ravel(), ys.ravel()])
    return np.asarray(dist).reshape(xs.shape)


@design(aspects="any")
def draw(s: Canvas) -> None:
    profile = CubicSpline(CREST[:, 0], CREST[:, 1], bc_type="natural")
    grid = np.linspace(0, 1920, 1921)
    sx = float(grid[np.argmin(profile(grid))])
    sy = float(profile(sx))
    peak = s.pick(landscape=(sx / 1920, sy / 1080), portrait=(0.56, 0.4))
    # each flank of the profile stretches or squeezes to meet its canvas edge
    kl, kr = min(KMAX, peak.x / sx), min(KMAX, (s.w - peak.x) / (1920 - sx))
    # the slip face keeps its 16:9 steepness on wide screens and steepens on narrow ones
    kb = min(1.0, kr)
    ul = np.linspace(sx - (peak.x + 40) / kl, sx, 600)
    ur = np.linspace(sx, sx + (s.w - peak.x + 40) / kr, 600)[1:]
    top = len(ul) - 1
    crest = np.c_[
        peak.x + np.r_[(ul - sx) * kl, (ur - sx) * kr], peak.y + profile(np.r_[ul, ur]) - sy
    ]
    bx0 = peak.x + LEAVE * kb
    by0 = float(np.interp(bx0, crest[:, 0], crest[:, 1]))
    ctrl = np.r_[[(bx0, by0)], np.c_[peak.x + (BRINK[:, 0] - sx) * kb, peak.y + BRINK[:, 1] - sy]]
    brink = spline_points(ctrl, 60)
    # stop one sample past the bottom edge
    brink = brink[: int(np.argmax(brink[:, 1] > s.h + 20)) + 1]
    foot = s.h + 40
    left, right = crest[crest[:, 0] < bx0], crest[crest[:, 0] > bx0]
    windward = Polygon(np.r_[left, brink, [(brink[-1, 0], foot), (-40, foot)]])
    lee = Polygon(np.r_[right, [(s.w + 40, foot), (brink[-1, 0], foot)], brink[::-1]])

    xs, ys = cells(s.inset(-2 * CELL), CELL)
    rows, cols = xs.shape
    origin = (xs[0, 0], ys[0, 0])
    d = distance(crest, xs, ys)
    # deeper down, blurred, so ripples round over where the nearest crest point jumps flanks
    d = lerp(d, gaussian_filter(d, 12), smoothstep(0, 150, d))
    db = distance(brink, xs, ys)
    # ripple spacing widens with distance from the crest (S0 to S0 * (1 + GROW)): perspective
    # down the slope
    k = GROW / FAR
    phi = np.log1p(k * np.minimum(d, FAR)) / (k * S0) + np.maximum(d - FAR, 0) / (S0 * (1 + GROW))
    phi += 4.8 * noise_grid(cols, rows, 220, s.np_rng(3), octaves=3)
    grain = 1.1 * noise_grid(cols, rows, 18, s.np_rng(8), octaves=2)
    near = falloff(db, 150)
    lit = falloff(d, 450)
    coin = s.np_rng(5)

    with s.clip() as slope:
        slope.add(P().shape(windward))
    with (
        s.group(clip_path=slope.ref),
        s.buckets((BG_ALT, UI), "stroke", stroke_width=1.2) as ripples,
    ):

        def emit(c: NDArray[np.float64]) -> None:
            # short pieces and near-closed loops read as eyes or hooks rather than ripples
            if np.hypot(*np.diff(c, axis=0).T).sum() < 30 or np.hypot(*(c[0] - c[-1])) < 40:
                return
            j, i = ((c[len(c) // 2] - origin) / CELL).astype(int)
            p = 0.8 * near[i, j] + 0.3 * lit[i, j]
            ripples[int(coin.random() < p)].spline(c)

        for c in iso_lines(
            np.sin(np.pi * phi) + grain, 0, cell=CELL, origin=origin, simplify=SIMPLIFY
        ):
            emit(c)
        # half-phase ripples interleave only beside the brink, so the slope is densest where the
        # light ends
        for c in iso_lines(np.cos(np.pi * phi) + grain, 0, cell=CELL, origin=origin):
            ji = np.clip(((c - origin) / CELL).astype(int), 0, [cols - 1, rows - 1])
            # each ripple reaches a different distance in from the brink: a ragged inner edge
            inside = db[ji[:, 1], ji[:, 0]] < coin.uniform(30, 170)
            for a, b in runs(inside):
                if b - a > 4:
                    emit(approximate_polygon(c[a:b], SIMPLIFY))

    s.fill(P().shape(lee), SHADE)
    s.stroke(P().poly(brink), BG_ALT, 1.2)

    # the crest glows over ~300 px at the summit, cooling and thinning towards both ends
    ridge = Polyline(crest)
    along = np.arange(0, ridge.length, 2.0)
    summit = Polyline(crest[: top + 1]).length
    rung = TONES.rung(gauss(np.maximum(0, np.abs(along - summit) - 90), 130))
    seg = ridge.at(along)
    for i in range(len(TONES)):
        glow = P()
        for a, b in runs(rung[:-1] == i):
            glow.poly(seg[a : b + 1])
        s.stroke(glow, TONES[i], 1.6 + 1.8 * i / (len(TONES) - 1), cap="round")
