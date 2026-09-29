"""The Mandelbrot set as a 1980s ASCII printout: exterior distance estimates pick density glyphs in bands around a one-glyph rim."""

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from walldye import (
    ACCENT,
    ACCENT_4,
    ACCENT_5,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    Paint,
    Params,
    design,
    knob,
)
from walldye.pixel import glyphs

type Grid = NDArray[np.float64]


class View(Params):
    re: float = knob(default=-0.6, lo=-2, hi=0.5, doc="real part of c at the focal point")
    im: float = knob(default=0.0, lo=-1, hi=1, doc="imaginary part of c at the focal point")
    scale: float = knob(default=300, lo=300, hi=30000, unit="px", doc="px per unit of c")
    depth: int = knob(default=500, lo=100, hi=5000, doc="iterations before c counts as inside")


FW, FH = 5, 8  # 5x8 Spleen at px=1: fine enough for the filigree, crisp at 4K
SS = 4  # supersamples per cell axis
BANDS = (5, 12, 26, 48)  # outer distance in px of each exterior band beyond the rim
GAP = 5  # cells between the outermost band and the axes
ANTENNA = -1.45  # left of this real part the set is only the antenna and its small copies
# Cell roles as (glyph, paint), indexed by the role numbers below; the bands follow in order.
BLANK, INTERIOR, TIP, SPIKE, SPIKE_DOT, RIM, HAIR, AXIS_X, AXIS_Y, BAND0 = range(10)
ROLES: tuple[tuple[str, Paint | None], ...] = (
    (" ", None),
    (":", UI),
    ("@", ACCENT),
    ("-", UI_ALT),
    (".", UI),
    ("@", ACCENT),
    ("%", ACCENT_4),
    ("-", BG_ALT),
    ("|", BG_ALT),
    ("*", ACCENT_5),
    ("+", UI_ALT),
    ("-", UI),
    (".", UI),
)


def centers(start: float, size: float, n: int) -> Grid:
    """Centers of `n` abutting intervals of length `size`, the first starting at `start`."""
    return start + (np.arange(n, dtype=np.float64) + 0.5) * size


def estimate(c: NDArray[np.complex128], depth: int) -> Grid:
    """Exterior distance to the set in units of c; 0 for points that do not escape in `depth`
    iterations."""
    flat = c.ravel()
    dist = np.zeros(flat.shape)
    x, y = flat.real, flat.imag
    q = (x - 0.25) ** 2 + y**2
    # the main cardioid and the period-2 bulb never escape: skip their iterations
    inside = (q * (q + x - 0.25) <= 0.25 * y**2) | ((x + 1) ** 2 + y**2 <= 1 / 16)
    idx = np.nonzero(~inside)[0]
    cc = flat[idx]
    z, dz = np.zeros_like(cc), np.zeros_like(cc)
    for _ in range(depth):
        dz = 2 * z * dz + 1
        z = z * z + cc
        a = np.abs(z)
        esc = a > 1e3
        if esc.any():
            dist[idx[esc]] = a[esc] * np.log(a[esc]) / np.abs(dz[esc])
            live = ~esc
            idx, cc, z, dz = idx[live], cc[live], z[live], dz[live]
            if not idx.size:
                break
    return dist.reshape(c.shape)


@design(aspects=("16:9", "32:9", "9:19.5", "10:16"))
def draw(s: Canvas[View]) -> None:
    p = s.params
    cols, rows = s.w // FW, s.h // FH
    ox, oy = (s.w - cols * FW) // 2, (s.h - rows * FH) // 2
    # right of center on a landscape screen; centered and in the upper half on a portrait one
    at = s.pick(landscape=(1180 / 1920, 0.5), portrait=(0.55, 0.42))
    # the real axis runs through the middle of row j0, so the set's mirror halves match
    j0 = int((at.y - p.im * p.scale - oy) // FH)
    y0 = oy + (j0 + 0.5) * FH

    def re(px: Grid) -> Grid:
        return (px - at.x) / p.scale + p.re

    sx, sy = centers(ox, FW / SS, cols * SS), centers(oy, FH / SS, rows * SS)
    c = re(sx)[None, :] + 1j * ((sy - y0) / p.scale)[:, None]
    d = (estimate(c, p.depth) * p.scale).reshape(rows, SS, cols, SS)  # in px
    near = d.min(axis=(1, 3))  # closest subsample: the rim stays continuous
    solid = (d == 0).mean(axis=(1, 3)) >= 0.35
    rim = ~solid & ndimage.binary_dilation(solid)  # 4-neighbors of the set: one glyph thick
    hair = ~solid & ~rim & (near < 0.6)
    x = re(centers(ox, FW, cols))  # c's real part at each column's center
    jj, ii = np.indices((rows, cols))
    row0 = jj == j0

    # The antenna and the real-axis spike are a thin filament: quiet glyphs along three rows,
    # with one rim glyph at its tip.
    spike = (np.abs(jj - j0) <= 1) & (x < ANTENNA)[None, :] & (near < 26)
    tip = np.zeros_like(spike)
    ends = np.nonzero((spike & row0 & (near < 3)).any(axis=0))[0]
    if ends.size:
        tip[j0, ends.min()] = True

    # Axis dashes beyond the outermost band, thinning out away from the set and ending short of
    # the screen edge where a narrow screen has no room for the full 60-cell fade. A close view
    # whose bands fill the screen has none, and neither does an axis that misses the screen.
    halo = near < BANDS[-1]
    axis_x = axis_y = np.zeros_like(halo)
    if halo.any():
        hx, hy = np.nonzero(halo.any(axis=0))[0], np.nonzero(halo.any(axis=1))[0]
        reach = max(1, min(60, hx.min() - 4, cols - 5 - hx.max()))
        dx = np.minimum(np.abs(ii - hx.min()), np.abs(ii - hx.max()))
        dy = np.minimum(np.abs(jj - hy.min()), np.abs(jj - hy.max()))
        off_x = (ii < hx.min() - GAP) | (ii > hx.max() + GAP)
        off_y = (jj < hy.min() - GAP // 2) | (jj > hy.max() + GAP // 2)
        axis_x = row0 & off_x & (dx < reach) & (ii % (1 + dx * 4 // reach) == 0)
        if np.abs(x).min() <= 0.5 * FW / p.scale:
            i0 = np.argmin(np.abs(x))
            axis_y = (ii == i0) & off_y & (dy < 14) & (jj % (1 + dy // 5) == 0)

    # first match wins, as in an if/elif chain
    rules = [
        (solid & ((ii + jj) % 2 == 0), INTERIOR),
        (solid, BLANK),
        (tip, TIP),
        (spike & row0 & (near < 5), SPIKE),
        (spike & (row0 | (near < 5)), SPIKE_DOT),
        (spike, BLANK),
        (rim, RIM),
        (hair, HAIR),
        *((near < b, BAND0 + k) for k, b in enumerate(BANDS)),
        (axis_x, AXIS_X),
        (axis_y, AXIS_Y),
    ]
    role = np.select([m for m, _ in rules], [r for _, r in rules], BLANK)
    chars = np.array([g for g, _ in ROLES])[role]
    glyphs(
        s,
        ["".join(r) for r in chars],
        lambda i, j, g: ROLES[role[j, i]][1],
        at=(ox, oy),
        font="5x8",
        px=1,
    )
