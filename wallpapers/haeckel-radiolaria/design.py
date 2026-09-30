"""A radiolarian after Haeckel's plates in fine line work: three nested geodesic lattice shells with an eighth cut away to show the smallest."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import ConvexHull
from shapely import Polygon
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from walldye import (
    ACCENT,
    ACCENT_4,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Paint,
    Path,
    Vec,
    by_regime,
    design,
    mix,
)

type Arr = NDArray[np.float64]

R = 210  # outer shell radius
MID, CORE = 0.68, 0.18  # shell radii as a share of R; the middle cut must clear the core
FREQ = (5, 4, 2)  # geodesic frequency of each shell, outer first
PORE = 0.46  # pore radius as a share of the distance to the nearest pore
SPINE_LEN = (256, 160)  # reach beyond the shell: the six main spines, the eight between them
SPINE_BASE = 4.5  # half-width of a spine where it leaves the shell
STUB = 90  # spines showing less than this beyond the rim read as strays and are left out
OCTANT_AXIS = (
    0.281,
    -0.162,
    1.0,
)  # 18 degrees off the line of sight, so the cut opens to the right
OCTANT_SPIN = 1.7  # keeps every spine root well clear of the cut
FAR = by_regime(mix(BG_ALT, UI, 0.5), UI)  # the far side of a shell, seen through the cut
BEAM = by_regime(UI, UI_ALT)
INK = by_regime(UI_ALT, UI_HI)  # pores, cut edges, rim and spines
SECTION = by_regime(BG_ALT, UI)  # the shell walls where the cut crosses them
WALL = 9  # shell thickness where the cut crosses it


def rotation(yaw: float, pitch: float, roll: float) -> Arr:
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    ry = np.array([[cr, 0, sr], [0, 1, 0], [-sr, 0, cr]])
    return ry @ rx @ rz


VIEW = rotation(0.31, 1.07, 0.42)  # body frame -> (screen x, screen y, depth toward the viewer)


def octant_edges() -> Arr:
    """Three orthonormal view-space axes whose positive octant is the cut, one per row."""
    d = np.array(OCTANT_AXIS) / np.linalg.norm(OCTANT_AXIS)
    u = np.cross(d, (0.0, 1.0, 0.0))
    u /= np.linalg.norm(u)
    w = np.cross(d, u)
    beta = math.acos(1 / math.sqrt(3))
    a = OCTANT_SPIN + np.arange(3) * 2 * math.pi / 3
    return d * math.cos(beta) + math.sin(beta) * (np.cos(a)[:, None] * u + np.sin(a)[:, None] * w)


def icosphere(n: int) -> Arr:
    """Unit vertices of an icosahedron with each face cut into n * n triangles."""
    t = (1 + math.sqrt(5)) / 2
    ico = np.array(
        [(s1, s2 * t, 0) for s1 in (-1, 1) for s2 in (-1, 1)]
        + [(0, s1, s2 * t) for s1 in (-1, 1) for s2 in (-1, 1)]
        + [(s2 * t, 0, s1) for s1 in (-1, 1) for s2 in (-1, 1)],
        dtype=float,
    )
    ico /= np.linalg.norm(ico, axis=1, keepdims=True)
    pts = [
        ico[a] + (ico[b] - ico[a]) * i / n + (ico[c] - ico[a]) * j / n
        for a, b, c in ConvexHull(ico).simplices
        for i in range(n + 1)
        for j in range(n + 1 - i)
    ]
    v = np.array(pts)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return np.unique(np.round(v, 6), axis=0)


def pore_rings(sites: Arr, radius: Arr) -> Arr:
    """Each site's pore as a 20-point ring on the unit sphere, shape (sites, 20, 3); `radius`
    is each pore's angular radius."""
    ref = np.where(np.abs(sites[:, :1]) < 0.9, [[1.0, 0, 0]], [[0, 1.0, 0]])
    u = np.cross(sites, ref)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    w = np.cross(sites, u)
    th = np.linspace(0, 2 * math.pi, 20, endpoint=False)[None, :, None]
    rad = radius[:, None, None]
    return sites[:, None] * np.cos(rad) + (
        u[:, None] * np.cos(th) + w[:, None] * np.sin(th)
    ) * np.sin(rad)


def shell(c: Vec, r: float, n: int, cut: Arr | None = None) -> tuple[Path, Path]:
    """A lattice shell of radius r around c, as its front pores and its rear pores, leaving out
    the pores inside the octant whose axes are the rows of `cut`."""
    sites = icosphere(n)
    # each pore is sized by its nearest neighbor, so no two rings ever touch
    near = np.sort(np.linalg.norm(sites[:, None] - sites[None], axis=2), axis=1)[:, 1]
    view = sites @ VIEW.T
    rings = pore_rings(sites, PORE * near) @ VIEW.T
    front, rear = P(), P()
    for ring, site in zip(rings, view, strict=True):
        if cut is None or not (cut @ site > 0).all():
            (front if site[2] > 0 else rear).poly(c + r * ring[:, :2], closed=True)
    return front, rear


def clipped(s: Canvas, region: BaseGeometry, d: Path, paint: Paint, width: float) -> None:
    with s.clip() as cp:
        cp.add(P().shape(region))
    with s.group(clip_path=cp.ref):
        s.stroke(d, paint, width)


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(
        landscape=(0.36, 0.5), portrait=(0.33, 0.36)
    )  # the long left spine runs off the edge
    edges = octant_edges()
    t = np.linspace(0, math.pi / 2, 32)
    arcs = [
        np.cos(t)[:, None] * edges[i] + np.sin(t)[:, None] * edges[(i + 1) % 3] for i in range(3)
    ]

    def window(r: float) -> Polygon:
        """What the cut takes off the near side of the shell of radius r, on screen."""
        return Polygon(np.asarray(c) + r * np.concatenate(arcs)[:, :2])

    def disc(r: float) -> BaseGeometry:
        return Point(c).buffer(r, quad_segs=64)

    w_out, w_mid = window(R), window(MID * R)
    outer = shell(c, R, FREQ[0], edges)
    middle = shell(c, MID * R, FREQ[1], edges)
    core = shell(c, CORE * R, FREQ[2])[0]

    # spines: six along the body axes, eight on the diagonals between them
    axes = np.concatenate([np.eye(3), -np.eye(3)])
    diag = np.array([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]) / math.sqrt(3)
    front, front_fill, back, beams = P(), P(), P(), P()
    for dirs, reach in ((axes, SPINE_LEN[0]), (diag, SPINE_LEN[1])):
        for d in dirs @ VIEW.T:
            if (edges @ d > 0).all():
                continue  # its base went with the cut
            if (R + reach) * math.hypot(d[0], d[1]) - R < STUB:
                continue
            base, tip = c + R * d[:2], c + (R + reach) * d[:2]
            side = Vec(-d[1], d[0])
            side = side / max(abs(side), 1e-6) * SPINE_BASE
            blade = np.array([base + side, tip, base - side])
            if d[2] > 0:
                front.poly(blade)
                front_fill.poly(blade, closed=True)
            else:
                back.poly(blade)
                beams.M(c + CORE * R * d[:2]).L(base)

    everything = Polygon([(0, 0), (s.w, 0), (s.w, s.h), (0, s.h)])
    clipped(s, everything.difference(disc(R)), back, INK, 1.2)

    # seen through the cut: the far inside of each shell, then the beams and the middle shell
    far_out = w_out.difference(disc(MID * R))
    far_mid = w_mid.difference(disc(CORE * R))
    clipped(s, far_out, outer[1], FAR, 1.0)
    clipped(s, far_mid, middle[1], FAR, 1.0)
    clipped(s, far_mid.union(far_out), beams, BEAM, 1.2)
    clipped(s, w_out.intersection(disc(MID * R).difference(w_mid)), middle[0], INK, 1.2)
    s.stroke(core, ACCENT, 1.6)
    s.stroke(P().circle(c, CORE * R), ACCENT_4, 1.2)
    clipped(s, disc(R).difference(w_out), outer[0], INK, 1.3)

    # the cut faces: each shell's wall in section, a band on each of the three planes
    faces, rims = P(), P().circle(c, R)
    for r in (R, MID * R):
        for arc in arcs:
            band = np.concatenate([r * arc[:, :2], (r - WALL) * arc[::-1, :2]])
            faces.poly(np.asarray(c) + band, closed=True)
            rims.poly(np.asarray(c) + r * arc[:, :2]).poly(np.asarray(c) + (r - WALL) * arc[:, :2])
    s.fill(faces, SECTION)
    s.stroke(rims, INK, 1.4)
    clipped(s, w_out, P().circle(c, MID * R), INK, 1.6)
    s.fill(front_fill, BG)
    s.stroke(front, INK, 1.2, join="round")
