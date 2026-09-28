"""A chain of dominoes curving away in perspective as a wave topples it: flat-shaded boxes in painter's order, with the first piece and one mid-fall picked out."""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from shapely import MultiPoint, unary_union

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_4,
    ACCENT_6,
    ACCENT_7,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    NpRng,
    P,
    Params,
    Path,
    Vec,
    by_regime,
    design,
    knob,
)
from walldye.geom import Polyline, spline_points


class Fall(Params):
    wave: float = knob(
        default=0.5,
        lo=0.1,
        hi=0.95,
        doc="where the wavefront stands along the path, from its near end (0) to its far end (1)",
    )


VARIANTS = {"late": Fall(wave=0.8)}

type Arr = NDArray[np.float64]
type State = Literal["standing", "fallen", "picked", "first"]

T, WD, HT = 0.21, 0.65, 1.3  # domino thickness, width and height
GAP = 0.92  # spacing along the path
F = 1250.0  # focal length, canvas units
# Camera height and downward pitch (radians): portrait looks down more steeply, so the chain can
# climb the tall canvas without its near end ballooning.
LANDSCAPE_CAM = (5.0, 0.27)
PORTRAIT_CAM = (8.0, 0.4)
# The path as canvas fractions, laid onto the floor: it enters low on the left, crosses the view
# and bends away into the distance. Landscape keeps the 16:9 original's curve.
LANDSCAPE = (
    (0.1064, 0.7469),
    (0.3164, 0.6252),
    (0.4761, 0.5465),
    (0.5992, 0.5186),
    (0.7206, 0.5079),
    (0.8131, 0.4868),
    (0.8687, 0.4631),
)
PORTRAIT = (
    (0.2, 0.8),
    (0.52, 0.75),
    (0.76, 0.665),
    (0.6, 0.595),
    (0.42, 0.57),
    (0.26, 0.545),
    (0.13, 0.515),
)
WAVE = (66, 54, 43, 31, 19, 7)  # tilts of the wavefront pieces from vertical, degrees
PICKED = 2  # the wavefront piece picked out, an index into WAVE
RESTING = 78  # tilt of a piece lying on the next one
LIGHT = np.array([-0.5, 0.8, -0.35]) / np.linalg.norm([-0.5, 0.8, -0.35])
UP = np.array([0.0, 1.0, 0.0])
# On light themes BG_DEEP is lighter than BG and UI_ALT darker than UI, so the floor shadow and
# the face tones of plain pieces change there, keeping shadows darker and lit faces lighter.
SHADOW = by_regime(BG_DEEP, BG_ALT)
UI_LIT, UI_SHADED = by_regime(UI_ALT, UI), by_regime(UI, UI_ALT)
FALLEN_SHADED = by_regime(BG_DEEP, UI)
# Face tones from shaded to lit, per piece state.
TONES = {
    "standing": (UI_SHADED, UI_SHADED, UI_LIT),
    "fallen": (FALLEN_SHADED, FALLEN_SHADED, BG_ALT),
    "picked": (ACCENT_3, ACCENT_1, ACCENT),
    "first": (ACCENT_7, ACCENT_6, ACCENT_4),
}
PIPS = {
    0: (),
    1: ((0, 0),),
    2: ((-1, -1), (1, 1)),
    3: ((-1, -1), (0, 0), (1, 1)),
    4: ((-1, -1), (1, -1), (-1, 1), (1, 1)),
    5: ((-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)),
    6: ((-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)),
}
PIP_R = WD * 0.075
PIP_RING = [(math.cos(k * math.pi / 5), math.sin(k * math.pi / 5)) for k in range(10)]
# Box corners in local (along, lateral, up) coordinates, and each face but the bottom as a loop.
CORNERS = np.array(
    [(0, -1, 0), (0, 1, 0), (0, 1, 1), (0, -1, 1), (1, -1, 0), (1, 1, 0), (1, 1, 1), (1, -1, 1)]
) * np.array([T, WD / 2, HT])
FACES = (
    ("back", (0, 1, 2, 3)),
    ("front", (4, 5, 6, 7)),
    ("side", (0, 4, 7, 3)),
    ("side", (1, 5, 6, 2)),
    ("top", (3, 2, 6, 7)),
)


@dataclass(frozen=True)
class Camera:
    """A pinhole camera `h` above the floor at the origin, looking along +z and pitched down by
    `pitch` radians; its axis meets the canvas at (cx, cy)."""

    h: float
    pitch: float
    cx: float
    cy: float

    @property
    def eye(self) -> Arr:
        return np.array([0.0, self.h, 0.0])

    def project(self, pts: ArrayLike) -> Arr:
        """Canvas points (N, 2) of world points (N, 3), which must lie in front of the camera."""
        p = np.asarray(pts, float)
        c, s = math.cos(self.pitch), math.sin(self.pitch)
        y = p[:, 1] - self.h
        yc = y * c + p[:, 2] * s
        zc = -y * s + p[:, 2] * c
        return np.stack([self.cx + F * p[:, 0] / zc, self.cy - F * yc / zc], axis=-1)

    def floor(self, q: Vec) -> Vec:
        """The floor point (x, z) seen at canvas point `q`, which must lie below the horizon."""
        u, v = (q.x - self.cx) / F, (self.cy - q.y) / F
        c, s = math.cos(self.pitch), math.sin(self.pitch)
        t = self.h / (s - v * c)
        return Vec(t * u, t * (v * s + c))


@dataclass(frozen=True)
class Piece:
    """A domino whose back bottom edge is centred on floor point `base`, facing along the unit
    floor direction `tan` and toppled forward by `tilt` radians about its front bottom edge."""

    base: Arr
    tan: Arr
    tilt: float
    state: State
    pair: tuple[int, int]

    def at(self, local: ArrayLike) -> Arr:
        """World points (N, 3) of local points (N, 3): along `tan`, lateral, and up."""
        a, b, h = np.asarray(local, float).T
        lat = np.array([self.tan[2], 0.0, -self.tan[0]])
        c, s = math.cos(self.tilt), math.sin(self.tilt)
        da = a - T
        along = T + da * c + h * s
        up = -da * s + h * c
        return self.base + np.outer(along, self.tan) + np.outer(b, lat) + np.outer(up, UP)

    def corners(self) -> Arr:
        return self.at(CORNERS)

    def faces(self) -> list[tuple[str, Arr, Arr]]:
        """(name, corners (4, 3), outward unit normal) of each face but the bottom."""
        v = self.corners()
        centre = v.mean(axis=0)
        out = []
        for name, idx in FACES:
            quad = v[list(idx)]
            n = np.cross(quad[1] - quad[0], quad[3] - quad[0])
            n /= np.linalg.norm(n)
            if n @ (quad.mean(axis=0) - centre) < 0:
                n = -n
            out.append((name, quad, n))
        return out

    def pips(self, cam: Camera, face: str, d: Path) -> None:
        """Add the divider and pips of the back or front face to `d`, unless too small to read."""
        a = -0.004 if face == "back" else T + 0.004
        probe = cam.project(self.at([(a, 0, HT / 2), (a, 2 * PIP_R, HT / 2)]))
        if abs(probe[1, 0] - probe[0, 0]) < 1.6:
            return
        bar = [(-0.38, -0.007), (0.38, -0.007), (0.38, 0.007), (-0.38, 0.007)]
        d.poly(cam.project(self.at([(a, WD * b, HT * (0.5 + h)) for b, h in bar])), closed=True)
        for half, n in zip((0.25, 0.75), self.pair, strict=True):
            for i, j in PIPS[n]:
                cu, cv = i * WD * 0.24, HT * half + j * WD * 0.24
                ring = [(a, cu + PIP_R * x, cv + PIP_R * y) for x, y in PIP_RING]
                d.poly(cam.project(self.at(ring)), closed=True)


def chain(route: list[Vec], wave: float, rng: NpRng) -> list[Piece]:
    """Pieces GAP apart along a smooth path through the floor points `route`, toppled up to the
    wavefront at fraction `wave` of the way through the route's points."""
    n = 64  # curve samples per route segment
    line = Polyline(spline_points(route, n))
    front = Polyline(line.pts[: max(2, round(wave * (len(route) - 1) * n) + 1)]).length
    ds = np.arange(0.2, line.length, GAP)
    picked = int(np.argmin(np.abs(ds - front)))
    out = []
    for i, d in enumerate(ds):
        x, z = line.at(float(d))
        tx, tz = line.tangent(float(d))
        k = i - picked + PICKED
        deg = RESTING if k < 0 else WAVE[k] if k < len(WAVE) else 0
        state: State = (
            "first" if i == 0 else "picked" if k == PICKED else "fallen" if k < 0 else "standing"
        )
        a, b = rng.integers(0, 7, 2)
        base, tan = np.array([x, 0.0, z]), np.array([tx, 0.0, tz])
        out.append(Piece(base, tan, math.radians(deg), state, (int(a), int(b))))
    return out


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Fall]) -> None:
    h, pitch = LANDSCAPE_CAM if s.landscape else PORTRAIT_CAM
    cam = Camera(h, pitch, s.center.x, s.center.y)
    route = [
        cam.floor(s.pick(landscape=lp, portrait=pp))
        for lp, pp in zip(LANDSCAPE, PORTRAIT, strict=True)
    ]
    pieces = chain(route, s.params.wave, s.np_rng(7))
    eye = cam.eye
    # painter's order: farthest first
    pieces.sort(key=lambda pc: -float(np.linalg.norm(pc.corners().mean(axis=0) - eye)))

    shadows = []
    for pc in pieces:
        v = pc.corners()
        foot = v - np.outer(v[:, 1] / LIGHT[1], LIGHT)
        shadows.append(MultiPoint(cam.project(foot)).convex_hull)
    s.fill(P().shape(unary_union(shadows)), SHADOW)

    for pc in pieces:
        shade = [P(), P(), P()]
        dots = P()
        for name, quad, n in pc.faces():
            if n @ (eye - quad[0]) <= 0:
                continue
            lum = 0.5 + 0.5 * float(n @ LIGHT)
            shade[min(2, int(lum * 3))].poly(cam.project(quad), closed=True)
            if name in ("back", "front") and pc.state in ("standing", "picked"):
                pc.pips(cam, name, dots)
        for d, tone in zip(shade, TONES[pc.state], strict=True):
            # a matching stroke closes the hairline seams between faces
            s.path(d, fill=tone, stroke=tone, stroke_width=0.6, stroke_linejoin="round")
        s.fill(dots, ACCENT_3 if pc.state == "picked" else BG_ALT)
