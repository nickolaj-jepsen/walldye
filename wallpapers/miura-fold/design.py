"""A flat Miura-ori crease pattern with one lens of it folded up, each facet shaded in steps by how it faces the light."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import cumulative_trapezoid

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    ACCENT_8,
    BG_ALT,
    UI,
    Canvas,
    P,
    design,
)
from walldye.field import gauss

type Floats = NDArray[np.float64]

A, B, ALPHA = 48, 64.7, math.radians(60)  # crease lengths and sector angle
S0, L0, V0 = B * math.sin(ALPHA), A, B * math.cos(ALPHA)  # flat cell 56x48, zigzag offset 32
LENS = (1440, 560)  # lens center from lattice vertex (0, 0): sets which facets face the light
RX, RY = 177, 156  # fold lens 1/e radii
THETA_MAX = math.radians(58)
TILT = 0.45  # oblique view: screen y -= TILT * height
LIGHT = np.array([0.2, -0.85, 0.5]) / np.linalg.norm([0.2, -0.85, 0.5])
STEPS = np.array([0.015, 0.04, 0.08, 0.13, 0.19, 0.26, 0.33, 0.395])  # lambert gain per tone
# one tone per step; tops out at ACCENT_2, with the full accent only at the very peak
TONES = (ACCENT_8, ACCENT_7, ACCENT_6, ACCENT_5, ACCENT_4, ACCENT_3, ACCENT_2, ACCENT)


def cell(theta: Floats) -> tuple[Floats, Floats, Floats, Floats]:
    """Schenk & Guest unit dimensions at fold angle `theta` (radians): x step S, y step L,
    zigzag offset V and height H; `cell(0)` is (S0, L0, V0, 0)."""
    k = np.sqrt(1 + (np.cos(theta) * math.tan(ALPHA)) ** 2)
    st = np.sin(theta) * math.sin(ALPHA)
    return B * np.cos(theta) * math.tan(ALPHA) / k, A * np.sqrt(1 - st**2), B / k, A * st


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(1420 / 1920, 0.5), portrait=(0.5, 0.58))
    ox, oy = c.x - LENS[0], c.y - LENS[1]
    # two spare cells past each edge cover the pull of the fold and the zigzag
    ii = np.arange(math.floor(-ox / S0) - 2, math.ceil((s.w - ox) / S0) + 3)
    jj = np.arange(math.floor(-oy / L0) - 2, math.ceil((s.h - oy) / L0) + 3)
    I, J = np.meshgrid(ii, jj, indexing="ij")
    dx, dy = (ox + I * S0 - c.x) / RX, (oy + J * L0 - c.y) / RY
    r = np.maximum(np.hypot(dx, dy), 1e-9)
    theta = THETA_MAX * gauss(r, 1)
    fold = theta / THETA_MAX

    # the sheet gathers radially towards the lens by the local contraction of S and L
    rho = np.linspace(0, 30, 8001)
    s_rho, l_rho, _, _ = cell(THETA_MAX * gauss(rho, 1))
    gx = cumulative_trapezoid(s_rho / S0, rho, initial=0)
    gy = cumulative_trapezoid(l_rho / L0, rho, initial=0)
    _, _, v, h = cell(theta)
    x = c.x + dx * RX * np.interp(r, rho, gx) / r
    y = c.y + dy * RY * np.interp(r, rho, gy) / r + (I % 2) * v - V0 / 2
    z = (J % 2) * h
    py = y - TILT * z

    # facets: the lambert gain over flat paper picks a tone; unlit flat paper stays bare
    p3 = np.stack([x, y, z], axis=-1)
    n = np.cross(p3[1:, 1:] - p3[:-1, :-1], p3[:-1, 1:] - p3[1:, :-1])
    n = n / np.linalg.norm(n, axis=-1, keepdims=True) * np.sign(n[..., 2:])
    k = np.searchsorted(STEPS, n @ LIGHT - LIGHT[2], side="right") - 1
    corners = np.stack([fold[:-1, :-1], fold[1:, :-1], fold[1:, 1:], fold[:-1, 1:]])
    k[(k < 0) & (corners.min(axis=0) > 0.45)] = 0  # shadowed paper deep in the fold, not a hole
    with s.buckets(TONES, "fill") as faces:
        for a, b in np.argwhere((k >= 0) & (corners.max(axis=0) >= 0.03)):
            ai, bi = [a, a + 1, a + 1, a], [b, b, b + 1, b + 1]
            faces[k[a, b]].poly(np.stack([x[ai, bi], py[ai, bi]], axis=-1), closed=True)

    # creases hand over to the facet shading across a few cells: mountains drop from UI to
    # BG_ALT, valleys vanish first
    crisp, faint, valley = P(), P(), P()
    rows = (J[:-1, :-1] % 2 == 1, np.maximum(fold[:-1, :-1], fold[1:, :-1]), 1, 0)
    cols = ((I + J)[:-1, :-1] % 2 == 0, np.maximum(fold[:-1, :-1], fold[:-1, 1:]), 0, 1)
    for mountain, f, da, db in (rows, cols):
        for d, sel in (
            (crisp, mountain & (f < 0.06)),
            (faint, mountain & (f >= 0.06) & (f < 0.16)),
            (valley, ~mountain & (f < 0.06)),
        ):
            for a, b in np.argwhere(sel):
                d.M(x[a, b], py[a, b]).L(x[a + da, b + db], py[a + da, b + db])
    s.stroke(valley, BG_ALT, 1.3, dash=(5, 4))
    s.stroke(faint, BG_ALT, 1.5, cap="round")
    s.stroke(crisp, UI, 1.5, cap="round")
