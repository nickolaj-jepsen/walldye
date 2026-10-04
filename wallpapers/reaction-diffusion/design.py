"""A reaction-diffusion labyrinth under a feed gradient, simulated on a grid and traced as smoothed contours."""

import math

import numpy as np
import shapely
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter, zoom

from walldye import (
    ACCENT,
    ACCENT_2,
    BG_ALT,
    Canvas,
    NpRng,
    Params,
    cached,
    design,
    knob,
    smoothstep,
)
from walldye.field import iso_lines, noise_grid
from walldye.geom import Polyline

type Field = NDArray[np.float64]


class Regime(Params):
    feed: float = knob(default=0.030, lo=0.02, hi=0.06, doc="feed rate in the corner")
    kill: float = knob(default=0.0625, lo=0.05, hi=0.07, doc="kill rate in the corner")


# The default corner settles into spots; this one into a mesh pierced by holes.
VARIANTS = {"holes": Regime(feed=0.040, kill=0.0585)}


CELL, MG = 4, 10  # px per simulation cell; cells simulated past every frame edge
DU, DV = 0.16, 0.08  # diffusion rates per time unit, in cells squared
DT, STEPS = 2.0, 2000  # the explicit scheme stays stable up to DT of about 2.3
LEVEL, UP = 0.25, 2  # the v concentration traced as outline; upsampling before tracing
# Frame units: a runs along the long side and b along the short one, both from the corner the
# spots gather in. At 16:9 the live side ends at a = 1320 along b = 0 and at 770 along b = 1080.
FRONT, SLOPE = 1320, 550
TONES = (BG_ALT, ACCENT_2, ACCENT)  # far shapes, then the corner bands (0.33 and 0.2 short sides)


def fields(
    p: Regime, a: Field, b: Field, g: float, sh: int, rng: NpRng
) -> tuple[Field, Field, Field]:
    """Feed and kill rates over the frame grid, and the weight (0 to 1) of the dead side."""
    # the corner regime hugs the long edge, widest in the corner
    spots = smoothstep(0.8 * sh, 0.3 * sh, np.hypot(0.55 * a / g, b))
    feed = 0.037 + (p.feed - 0.037) * spots
    # a ragged diagonal edge past which the pattern cannot replicate
    ragged = 154 * noise_grid(a.shape[1], a.shape[0], 90, rng, octaves=2)
    dead = smoothstep(230, -192, g * (FRONT - SLOPE * b / sh) - a + ragged)
    kill = 0.06 + (p.kill - 0.06) * spots + 0.008 * dead
    return feed, kill, dead


@cached
def simulate(feed: Field, kill: Field, dead: Field, rng: NpRng) -> Field:
    """The v field after STEPS explicit Euler steps from seeds scattered over the live side."""
    rows, cols = feed.shape
    u, v = np.ones((rows, cols)), np.zeros((rows, cols))
    for _ in range(rows * cols // 400):
        y, x = rng.integers(3, rows - 3), rng.integers(3, cols - 3)
        if dead[y, x] < 0.1:
            u[y - 3 : y + 3, x - 3 : x + 3] = 0.5
            v[y - 3 : y + 3, x - 3 : x + 3] = 0.25
    v += rng.random((rows, cols)) * 0.02

    # u and v stacked in one edge-padded float32 buffer and stepped in place, since this loop
    # is nearly all of the draw time. The 9-point Laplacian, isotropic so spots come out
    # round, is ([1 4 1] x [1 4 1] - 36) / 6; its center term and the reaction terms linear
    # in u or v fold into one factor per cell.
    f32 = np.float32
    z = np.empty((2, rows + 2, cols + 2), f32)
    zi = z[:, 1:-1, 1:-1]
    zi[0], zi[1] = u, v
    zu, zv = zi[0], zi[1]
    rate = (np.array([DU, DV])[:, None, None] * DT / 6).astype(f32)
    hold_u = (1 - 6 * DU * DT - feed * DT).astype(f32)
    hold_v = (1 - 6 * DV * DT - (feed + kill) * DT).astype(f32)
    gain = (feed * DT).astype(f32)
    row = np.empty((2, rows + 2, cols), f32)
    ring = np.empty((2, rows, cols), f32)
    uvv = np.empty((rows, cols), f32)
    for _ in range(STEPS):
        # no-flux edges
        z[:, 0], z[:, -1] = z[:, 1], z[:, -2]
        z[:, :, 0], z[:, :, -1] = z[:, :, 1], z[:, :, -2]
        np.multiply(z[:, :, 1:-1], 4, out=row)
        row += z[:, :, :-2]
        row += z[:, :, 2:]
        np.multiply(row[:, 1:-1], 4, out=ring)
        ring += row[:, :-2]
        ring += row[:, 2:]
        ring *= rate
        np.multiply(zv, zv, out=uvv)
        uvv *= zu
        uvv *= DT
        zu *= hold_u
        zu += gain
        zu -= uvv
        zv *= hold_v
        zv += uvv
        zi += ring
    return zv.astype(np.float64)


def lowpass(pts: Field, wavelength: float = 16.0, step: float = 6.0) -> Field:
    """A closed line resampled about every `step` px, without Fourier detail finer than
    `wavelength` px."""
    line = Polyline(pts, closed=True)
    n = max(8, int(line.length / step))
    p = line.at(np.linspace(0, line.length, n, endpoint=False))
    f = np.fft.fft(p[:, 0] + 1j * p[:, 1])
    k = np.abs(np.fft.fftfreq(n, 1 / n))
    z = np.fft.ifft(np.where(k <= max(3, line.length / wavelength), f, 0))
    return np.stack([z.real, z.imag], axis=1)


@design(aspects=("16:9", "32:9", "9:19.5", "10:16"), variants=VARIANTS)
def draw(s: Canvas[Regime]) -> None:
    # Work in a landscape frame (x along the long side, y along the short one, spots towards
    # the far corner); a portrait canvas swaps the axes at the end.
    ln, sh = max(s.w, s.h), min(s.w, s.h)
    g = math.sqrt(ln / 1920)  # longer screens stretch the gradient, but less than in full
    # nothing is drawn past a = g * FRONT, so the grid stops 100 px beyond it
    cols = min(ln, int(g * FRONT) + 100) // CELL + 2 * MG
    rows = sh // CELL + 2 * MG
    x0, y0 = ln - (cols - MG) * CELL, -MG * CELL
    xs = x0 + CELL * np.arange(cols, dtype=np.float64)
    ys = y0 + CELL * np.arange(rows, dtype=np.float64)
    a, b = np.meshgrid(ln - xs, sh - ys)
    feed, kill, dead = fields(s.params, a, b, g, sh, s.np_rng(4))
    v = simulate(feed, kill, dead, s.np_rng(11))

    # Keep 3 cells past each visible edge, upsample, and pad with zeros, so every outline
    # closes outside the frame, where its smoothed corners do not show.
    c0 = max(0, -x0 // CELL - 3)
    v = zoom(
        v[MG - 3 : rows - MG + 3, c0 : cols - MG + 3], UP, order=3, mode="nearest", grid_mode=True
    )
    v = np.pad(gaussian_filter(v, 0.5), 1)
    # upsampled sample k sits at cell (k + 0.5) / UP - 0.5, and the pad moves it one on
    shift = CELL * (0.5 / UP - 0.5 - 1 / UP)
    origin = (x0 + c0 * CELL + shift, y0 + (MG - 3) * CELL + shift)

    def band(pts: Field) -> int:
        """The TONES index for a spot or hole: which corner band its center falls in."""
        dc = math.hypot(ln - pts[:, 0].mean(), sh - pts[:, 1].mean()) / sh
        return 2 if dc < 0.2 else 1 if dc < 0.33 else 0

    lines = [lowpass(c) for c in iso_lines(v, LEVEL, cell=CELL / UP, origin=origin) if len(c) > 3]
    # iso_lines winds round low ground one way and high ground the other, so the signed
    # area is positive for a hole and negative for a spot or a worm (a body)
    areas = [0.5 * (p[:, 0] @ np.roll(p[:, 1], 1) - p[:, 1] @ np.roll(p[:, 0], 1)) for p in lines]
    bodies = [i for i, ar in enumerate(areas) if ar < 0]
    drawn: dict[int, int] = {}  # line index to TONES index
    rng = s.np_rng(3)
    for i in bodies:
        pts, area = lines[i], -areas[i]
        if area < 80:  # half-split specks read as noise
            continue
        ca, cb = ln - pts[:, 0].mean(), sh - pts[:, 1].mean()
        # thin the pattern towards the bare side, over a band that widens along the edge
        keep = smoothstep(0, 550 - 350 * cb / sh, g * (FRONT - SLOPE * cb / sh) - ca)
        k = band(pts) if area < 900 else 0
        if area < 900 and k == 0 and rng.random() > keep:  # far spots thin out at random
            continue
        if area >= 900 and keep < 0.3:  # worms stranded out in the dissolve
            continue
        drawn[i] = k
    # A hole goes with the innermost body around it: cut out of it, or lit near the corner.
    tree = shapely.STRtree([shapely.Polygon(lines[i]) for i in bodies])
    for i, area in enumerate(areas):
        if area < 300:  # bodies, and pinholes that read as noise
            continue
        around = [bodies[j] for j in tree.query(shapely.Point(lines[i][0]), predicate="within")]
        body = max(around, key=lambda j: areas[j], default=-1)
        if body in drawn:
            drawn[i] = (band(lines[i]) if area < 2000 else 0) or drawn[body]

    with s.buckets(TONES, "fill", fill_rule="evenodd") as tone:
        for i, k in drawn.items():
            tone[k].spline(lines[i] if s.landscape else lines[i][:, ::-1], closed=True)
