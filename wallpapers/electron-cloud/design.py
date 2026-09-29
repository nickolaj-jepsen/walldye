"""A hydrogen orbital in stipple: points sampled from its probability density, thinned apart, then packed closer and stepped up in tone where the cloud behind them runs deepest."""

import math
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_4,
    BG_ALT,
    MUTED,
    UI_ALT,
    UI_HI,
    Canvas,
    NpRng,
    P,
    Params,
    design,
    knob,
    smoothstep,
)

type Arr = NDArray[np.float64]
type Orbital = Literal["3dz2", "4f"]


class Cloud(Params):
    orbital: Literal["3dz2", "4f"] = knob(
        default="3dz2", doc="3d z-squared (two lobes and a ring) or a planar 4f (six lobes)"
    )


VARIANTS = {"4f": Cloud(orbital="4f")}

# n, where |psi|^2 peaks (Bohr radii), px per Bohr radius, half-width of the sampled cube (Bohr)
ORBITALS: dict[Orbital, tuple[int, tuple[float, float, float], float, float]] = {
    "3dz2": (3, (0.0, 0.0, 6.0), 24.0, 20.0),
    "4f": (4, (12.0, 0.0, 0.0), 14.0, 32.0),
}
TILT = math.radians(16)  # camera elevation: a ring around the z axis reads as an ellipse
DMIN = (4.6, 3.0)  # spacing between dots, px: sparse fringe to dense core
GAMMA = 0.6  # <1 flattens each lobe's interior so the silhouette carries the shape
CUT = (0.045, 0.06)  # soft |psi|^2 floor (share of peak) that draws the lobe edges
# Per tone, sparse fringe to dense core: column density floor, paint, dot diameter.
FLOORS = (0.0, 0.22, 0.5, 0.66, 0.82)
TONES = (UI_ALT, UI_HI, ACCENT_4, ACCENT_2, ACCENT)
DOTS = (2.2, 2.3, 2.5, 2.8, 3.2)
ARMS = (560, 500)  # axis half-lengths, px, unless the canvas edge comes first
TICK, REACH = 5, 480  # Bohr radii between axis ticks; px they reach from the nucleus at most


def angular(orbital: Orbital, x: Arr, y: Arr, z: Arr) -> Arr:
    """The orbital's real solid harmonic, a polynomial of degree n - 1 whose zeros are its nodes."""
    if orbital == "4f":
        return x * (x * x - 3 * z * z)  # r^3 cos 3phi in the xz plane: six lobes face the viewer
    return 3 * z * z - (x * x + y * y + z * z)


def density(orbital: Orbital, x: Arr, y: Arr, z: Arr) -> Arr:
    """|psi|^2 with a nodeless radial part, unnormalized: the harmonic squared times e^(-2r/n)."""
    n = ORBITALS[orbital][0]
    return angular(orbital, x, y, z) ** 2 * np.exp(-2 * np.sqrt(x * x + y * y + z * z) / n)


def accept(orbital: Orbital, x: Arr, y: Arr, z: Arr) -> Arr:
    """Dot probability: |psi|^2 flattened by GAMMA and cut off softly at the CUT isosurface."""
    px, py, pz = (np.array([q]) for q in ORBITALS[orbital][1])
    v = density(orbital, x, y, z) / density(orbital, px, py, pz)
    return v**GAMMA * smoothstep(CUT[0], CUT[1], v)


def sample(orbital: Orbital, rng: NpRng, count: int, extent: float) -> Arr:
    """`count` points, (count, 3), drawn from `accept` by rejection in a cube of half-width `extent`."""
    pts: list[Arr] = []
    while sum(len(p) for p in pts) < count:
        q = rng.uniform(-extent, extent, (3, 500000))
        pts.append(q[:, rng.uniform(0, 1, q.shape[1]) < accept(orbital, q[0], q[1], q[2])].T)
    return np.concatenate(pts)[:count]


def column_density(orbital: Orbital, u: Arr, v: Arr, extent: float) -> Arr:
    """Line-of-sight integral of `accept` behind each screen point (u right, v up, in Bohr radii),
    normalized to its maximum."""
    w = np.linspace(-extent, extent, 160)[:, None]
    c, s = math.cos(TILT), math.sin(TILT)
    col = accept(orbital, u + 0 * w, -v * s + w * c, v * c + w * s).sum(0)
    return col / col.max()


def thin(xy: Arr, dmin: Arr) -> list[int]:
    """Greedy thinning: the indices of the points kept, dropping point i when one already kept
    lies closer than `dmin[i]`."""
    cell = float(dmin.max())
    grid: dict[tuple[int, int], list[int]] = {}
    keep: list[int] = []
    pts: list[list[float]] = xy.tolist()
    for i, ((x, y), d) in enumerate(zip(pts, dmin.tolist(), strict=True)):
        gx, gy, d2 = int(x // cell), int(y // cell), d * d
        near = (grid.get((gx + a, gy + b), ()) for a in (-1, 0, 1) for b in (-1, 0, 1))
        if all((x - pts[j][0]) ** 2 + (y - pts[j][1]) ** 2 >= d2 for c in near for j in c):
            grid.setdefault((gx, gy), []).append(i)
            keep.append(i)
    return keep


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Cloud]) -> None:
    orbital = s.params.orbital
    scale, extent = ORBITALS[orbital][2:]
    # right of center on a landscape screen, a little below the middle on a portrait one
    c = s.pick(landscape=(0.6354, 0.5), portrait=(0.5, 0.55))

    x, y, z = sample(orbital, s.np_rng(7), 40000, extent).T
    u, v = x, z * math.cos(TILT) - y * math.sin(TILT)
    dens = column_density(orbital, u, v, extent)
    xy = np.stack([u * scale, -v * scale], 1)  # px from the nucleus, y down
    k = thin(xy, DMIN[0] + (DMIN[1] - DMIN[0]) * np.sqrt(dens))
    xy, dens = xy[k] + np.asarray(c), dens[k]

    hx = min(ARMS[0], c.x - 40, s.w - c.x - 40)
    hy = min(ARMS[1], c.y - 40, s.h - c.y - 40)
    axis = P().M(c.x - hx, c.y).H(c.x + hx).M(c.x, c.y - hy).V(c.y + hy)
    ticks = int(REACH / (TICK * scale))
    for i in range(-ticks, ticks + 1):
        if i:
            t = i * TICK * scale
            axis.M(c.x + t, c.y - 5).V(c.y + 5).M(c.x - 5, c.y + t).H(c.x + 5)
    s.stroke(axis, BG_ALT, 1.2)

    tone = np.searchsorted(FLOORS, dens, side="right") - 1
    for i, (paint, width) in enumerate(zip(TONES, DOTS, strict=True)):
        dots = P()
        for px, py in xy[tone == i].tolist():
            dots.M(px, py).H(px)
        s.stroke(dots, paint, width, cap="round")
    s.fill(P().circle(c, 3.5), MUTED)
