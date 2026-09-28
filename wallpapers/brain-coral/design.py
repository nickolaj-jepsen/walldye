"""A brain-coral boulder on an empty seabed: a reaction-diffusion labyrinth wrapped over a lit dome and cut into tone bands."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter, label, map_coordinates

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_5,
    ACCENT_8,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    NpRng,
    P,
    Params,
    Path,
    Vec,
    design,
    knob,
)
from walldye.field import iso_lines

type Field = NDArray[np.float64]
type Grid = NDArray[np.float32]


class Coral(Params):
    feed: float = knob(default=0.055, lo=0.02, hi=0.07, doc="feed rate of the reaction")
    kill: float = knob(default=0.062, lo=0.05, hi=0.07, doc="kill rate of the reaction")


RX, RY = 315, 292  # dome radii
LIFT = 140  # dome centre above the seabed
CELL = 2.2  # screen px per simulation cell at the dome's centre
STEPS = 10000
LIGHT = np.array([-0.45, -1.0, 0.4])
# each band paints everything lit at least that much; the last catches the rest
BANDS = ((0.6, ACCENT), (0.36, ACCENT_2), (0.14, ACCENT_3), (-9.0, ACCENT_5))
STEP = 1.2  # contouring resolution in px
RIM = 4  # bare ACCENT_8 band between the ridges and the silhouette
PEBBLES = ((430, 5), (456, 3))  # offset right of the dome centre, radius


def lap_into(a: Grid, out: Grid) -> Grid:
    """The 5-point Laplacian of `a` with wrap-around edges, written into `out`."""
    np.multiply(a, -4, out=out)
    out[1:] += a[:-1]
    out[:1] += a[-1:]
    out[:-1] += a[1:]
    out[-1:] += a[:1]
    out[:, 1:] += a[:, :-1]
    out[:, :1] += a[:, -1:]
    out[:, :-1] += a[:, 1:]
    out[:, -1:] += a[:, :1]
    return out


def gray_scott(rng: NpRng, gw: int, gh: int, f: float, k: float) -> Grid:
    """The V field after STEPS updates of a two-chemical reaction-diffusion with feed `f` and
    kill `k` on a wrap-around (gh, gw) grid, started from scattered 4x4 patches.

    In place and in float32: the float64 pattern in a quarter of the time, and every render
    reruns it."""
    u, v = np.ones((gh, gw), np.float32), np.zeros((gh, gw), np.float32)
    for _ in range(gw * gh // 150):
        x, y = rng.integers(0, gw), rng.integers(0, gh)
        u[y : y + 4, x : x + 4], v[y : y + 4, x : x + 4] = 0.5, 0.25
    v += rng.random((gh, gw)) * 0.02
    lu, lv, uvv = np.empty_like(u), np.empty_like(u), np.empty_like(u)
    for _ in range(STEPS):
        np.multiply(v, v, out=uvv)
        uvv *= u
        lap_into(u, lu)
        lap_into(v, lv)
        # u += 0.16 lap(u) - uvv + f (1 - u), and v += 0.08 lap(v) + uvv - (f + k) v
        lu *= 0.16
        lu -= uvv
        lu += f
        u *= 1 - f
        u += lu
        lv *= 0.08
        lv += uvv
        v *= 1 - (f + k)
        v += lv
    return v


@design(aspects="any")
def draw(s: Canvas[Coral]) -> None:
    p = s.params
    # the dome's foot on the seabed: left third on a landscape screen, low on a portrait one
    cx, bed = s.pick(landscape=(1 / 3, 940 / 1080), portrait=(0.42, 0.7))
    cy = bed - LIFT
    x0, y0 = cx - RX - 30, cy - RY - 30
    X, Y = np.meshgrid(np.arange(x0, cx + RX + 30, STEP), np.arange(y0, bed + 8, STEP))
    ang = np.arctan2(Y - cy, X - cx)
    calm = 1 - 0.75 * np.clip(-np.sin(ang), 0, 1) ** 2  # a quiet crown so the dome rounds over
    wobble = 1 + 0.035 * calm * s.noise(9).fbm(np.cos(ang) * 1.3, np.sin(ang) * 1.3 + 7, 3)
    nx, ny = (X - cx) / (RX * wobble), (Y - cy) / (RY * wobble)
    r2 = nx**2 + ny**2
    # signed distance to the silhouette in px (approximate but smooth)
    dome = np.minimum(
        (1 - np.sqrt(r2)) * np.hypot(RX * np.cos(ang), RY * np.sin(ang)) * wobble, bed - Y
    )
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    lambert = (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / np.linalg.norm(LIGHT)
    # a high light plus rim falloff keeps full accent on the upper-left cap; the rest turns away
    light = gaussian_filter(lambert - 0.25 * r2, 14 / STEP)

    # wrap the periodic labyrinth over the dome so grooves foreshorten towards the rim
    stretch = 1 + 0.45 * r2
    tx, ty = nx * stretch * RX / CELL, ny * stretch * RY / CELL
    gw, gh = int(math.pi * RX / CELL) + 8, int(math.pi * RY / CELL) + 8
    v = gray_scott(s.np_rng(3), gw, gh, p.feed, p.kill)
    ridge = map_coordinates(v, [ty + gh / 2, tx + gw / 2], order=3, mode="grid-wrap") - 0.25
    grad = np.hypot(*np.gradient(ridge, STEP))
    ridge = np.minimum(ridge / np.median(grad[np.abs(ridge) < 0.02]), dome - RIM)
    # drop crumbs the rim cut off, so the silhouette ends on whole ridge ends
    lab, count = label(ridge > 0)
    small = np.flatnonzero(np.bincount(lab.ravel(), minlength=count + 1) * STEP**2 < 40)
    ridge[np.isin(lab, small[small > 0])] = -1

    def outline(field: Field) -> Path:
        d = P()
        # padded so every contour closes; the pad shifts the origin by one step
        padded = np.pad(field, 1, constant_values=-1)
        for line in iso_lines(padded, 0, cell=STEP, origin=(x0 - STEP, y0 - STEP), simplify=0.3):
            if len(line) >= 4:
                d.poly(line, closed=True)
        return d

    s.fill(P().ellipse((cx + 30, bed + 3), RX * 1.05, 12), BG_DEEP)  # contact shadow on the sand
    s.fill(outline(dome), ACCENT_8)
    # darkest band first, so each brighter one lies on top and the bands share no seams
    for lo, tone in reversed(BANDS):
        s.fill(outline(np.minimum(ridge, 60 * (light - lo))), tone)

    # the seabed: a hairline fading in at the left and out towards the right
    a, b = (s.w * t for t in ((60 / 1920, 1500 / 1920) if s.landscape else (0.04, 0.96)))
    sea = s.linear_gradient([(0, UI, 0), (0.12, UI), (0.6, UI), (1, UI, 0)], (a, 0), (b, 0))
    s.fill(P().rect(a, bed - 0.75, b - a, 1.5), sea)
    pebbles = P()
    for dx, r in PEBBLES:
        pebbles.ellipse(Vec(cx + dx, bed - r * 0.6), r * 1.4, r * 0.8)
    s.fill(pebbles, UI_ALT)
