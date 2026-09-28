"""A geodesic moon of flat triangular facets, lit from behind so only a crescent of facets catches the light."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_5,
    ACCENT_7,
    BG,
    BG_ALT,
    Canvas,
    P,
    Params,
    design,
    knob,
    mix,
    polar,
)


class Moon(Params):
    phase: float = knob(
        default=114,
        lo=0,
        hi=170,
        unit="deg",
        doc="angle between the sun and the viewer, seen from the moon; 90 lights half the disc",
    )
    exposure: float = knob(
        default=1.0,
        lo=0.5,
        hi=3.0,
        doc="gain on each facet's Lambert term before it is cut into tones; above 1 the lit side"
        " reads flatter and brighter",
    )


# At 90 degrees most of the lit half sits at a low Lambert term, so without the extra gain its
# inner facets fall into the two darkest tones and it reads as a wide crescent.
VARIANTS = {"half": Moon(phase=90, exposure=2.6)}

R = 230
FREQ = 4  # geodesic frequency: 320 faces, ~160 facing the viewer
SUN_BEARING = 298  # where the sun sits across the sky: upper left, so the left limb lights
NIGHT = mix(BG, BG_ALT, 0.45)
NIGHT_EDGE = mix(BG, BG_ALT, 0.9)
TONES = (ACCENT, ACCENT_3, ACCENT_5, ACCENT_7)
STEPS = (0.6, 0.4, 0.17, 0.0)  # the Lambert term a lit face must exceed for each tone

type Arr = NDArray[np.float64]

# The icosahedron: 12 vertices, the cyclic permutations of (0, ±1, ±PHI), and its 20 faces.
PHI = (1 + 5**0.5) / 2
ICO_VERTS = (
    (-1, PHI, 0),
    (1, PHI, 0),
    (-1, -PHI, 0),
    (1, -PHI, 0),
    (0, -1, PHI),
    (0, 1, PHI),
    (0, -1, -PHI),
    (0, 1, -PHI),
    (PHI, 0, -1),
    (PHI, 0, 1),
    (-PHI, 0, -1),
    (-PHI, 0, 1),
)
ICO_FACES = (
    (0, 11, 5),
    (0, 5, 1),
    (0, 1, 7),
    (0, 7, 10),
    (0, 10, 11),
    (1, 5, 9),
    (5, 11, 4),
    (11, 10, 2),
    (10, 7, 6),
    (7, 1, 8),
    (3, 9, 4),
    (3, 4, 2),
    (3, 2, 6),
    (3, 6, 8),
    (3, 8, 9),
    (4, 9, 5),
    (2, 4, 11),
    (6, 2, 10),
    (8, 6, 7),
    (9, 8, 1),
)


def icosphere(freq: int) -> tuple[Arr, NDArray[np.intp]]:
    """The unit geodesic sphere with each icosahedron face cut into `freq`**2 triangles.

    Returns the vertices (N, 3) and the faces as vertex indices (20 * freq**2, 3); vertices on
    shared edges are merged.
    """
    base = [np.array(p, float) / np.linalg.norm(p) for p in ICO_VERTS]
    verts: list[Arr] = []
    index: dict[tuple[float, ...], int] = {}
    faces: list[tuple[int, int, int]] = []

    def vid(a: Arr, b: Arr, c: Arr, i: int, j: int) -> int:
        # a barycentric grid point, shared along edges via its rounded position
        p = (a * (freq - i - j) + b * i + c * j) / freq
        p /= np.linalg.norm(p)
        key = tuple(np.round(p, 6).tolist())
        if key not in index:
            index[key] = len(verts)
            verts.append(p)
        return index[key]

    for fa, fb, fc in ICO_FACES:
        a, b, c = base[fa], base[fb], base[fc]
        for i in range(freq):
            for j in range(freq - i):
                faces.append((vid(a, b, c, i, j), vid(a, b, c, i + 1, j), vid(a, b, c, i, j + 1)))
                if i + j < freq - 1:
                    faces.append(
                        (vid(a, b, c, i + 1, j), vid(a, b, c, i + 1, j + 1), vid(a, b, c, i, j + 1))
                    )
    return np.array(verts), np.array(faces, dtype=np.intp)


def tilt(ax: float, ay: float) -> Arr:
    """The rotation by `ay` radians about the y axis, then `ax` about the x axis."""
    ca, sa, cb, sb = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay)
    rx = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]])
    ry = np.array([[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]])
    return rx @ ry


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Moon]) -> None:
    c = s.pick(landscape=(2 / 3, 0.4815), portrait=(0.6, 0.36))
    v, faces = icosphere(FREQ)
    v = v @ tilt(0.5, 0.35).T
    # hand-cut interior facets, but no jitter toward the limb so the silhouette stays round
    v = v + s.np_rng(3).normal(0, 0.014, v.shape) * np.clip(v[:, 2:3], 0, 1)

    # x right, y down, z toward the viewer
    phase = math.radians(s.params.phase)
    across = polar((0, 0), math.sin(phase), bearing=SUN_BEARING)
    sun = np.array([across.x, across.y, math.cos(phase)])

    tri = v[faces]  # (faces, corners, xyz)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    n *= np.sign(np.einsum("ij,ij->i", n, tri.sum(axis=1)))[:, None]  # point every normal out
    lam = (n @ sun) * s.params.exposure
    front = n[:, 2] > 0
    outlines = c + tri[:, :, :2] * R

    night = P()
    for pts in outlines[front & (lam <= 0)]:
        night.poly(pts, closed=True)
    s.path(night, fill=NIGHT, stroke=NIGHT_EDGE, stroke_width=1, stroke_linejoin="round")
    day = front & (lam > 0)
    with s.buckets(TONES, "fill", stroke=BG, stroke_width=1.2, stroke_linejoin="round") as lit:
        for pts, k in zip(outlines[day], lam[day], strict=True):
            lit[next(i for i, t in enumerate(STEPS) if k > t)].poly(pts, closed=True)
