"""Saturn cropped by a corner: its rings as fine elliptical arcs and its globe as latitude hatching, shaded by the sun and by the shadows each casts on the other."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Path,
    Vec,
    design,
    mix,
)
from walldye.field import runs
from walldye.geom import Affine

type Arr = NDArray[np.float64]

R = 420  # equatorial radius
RP = 0.9 * R  # Saturn is visibly oblate
TILT = 18  # degrees the ring plane leans on screen, clockwise
OPEN = math.radians(16)  # seen from the north: the near rings cross the lower globe only
# Planet frame: +x right, +y toward the viewer, +z north.
SUN = np.array([-0.7, -0.6, 0.3]) / math.hypot(-0.7, -0.6, 0.3)
VIEW = np.array([0, math.cos(OPEN), math.sin(OPEN)])
HATCH = 11  # latitude line spacing
N = 720  # samples round each circle
# The planet's center, measured in from the bottom-right corner: in landscape the globe's east limb
# meets the right edge; in portrait it is cut by the right edge so the rings reach the left one.
CORNER = Vec(420, 320)
CORNER_TALL = Vec(140, 320)

# Ring stroke tones: the C ring and every ring in the globe's shadow, the B and A rings, the outer
# B ring, and the two lifted edges that give the ring system its outline.
RING_TONES = (BG_ALT, UI, UI_ALT, UI_HI)
# (inner, outer, tone, lines) in Saturn radii: C ring, inner and outer B ring, A ring, and the
# strip of A ring outside the Encke gap.
RINGS = (
    (1.24, 1.52, 0, 9),
    (1.53, 1.72, 1, 7),
    (1.72, 1.925, 2, 9),
    (2.06, 2.21, 1, 8),
    (2.225, 2.27, 1, 3),
)
EDGES = (1.925, 2.27)  # outer edges of the B and A rings
C_RING = (1.24, 1.53)  # translucent: it halves the light through it and half hides the hatch
OPAQUE = (1.53, 2.27)  # B ring to A ring: hides the globe, leaving the Cassini gap empty
CASSINI = (1.925, 2.06)  # about twice its true width, so it shows at this size

# Hatch tones from the sunlit limb inward, and the Lambert value each needs (brightest first).
TONES = (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    mix(ACCENT_2, ACCENT_3, 0.5),
    ACCENT_3,
    mix(ACCENT_3, ACCENT_5, 0.5),
    ACCENT_5,
    ACCENT_6,
    UI,
    BG_ALT,
)
CUTS = np.array([0.62, 0.5, 0.4, 0.31, 0.23, 0.16, 0.1, 0.05, -0.15])
LIT = 8  # tones before this one are the lit limb and draw heavier


def ellipse(
    d: Path, proj: Affine, w0: float, a: float, b: float, l0: float, l1: float, *, move: bool = True
) -> Path:
    """Append the arc of the (u, w)-plane ellipse (a cos l, w0 - b sin l) from l0 to l1, starting
    a subpath (`move`) or joining the current one with a line.

    Pieces span at most a quarter turn: SVG recenters an arc on its rounded end points, and near
    a half turn that moves the arc by pixels."""
    n = max(1, math.ceil(abs(l1 - l0) / (math.pi / 2) - 1e-9))
    for k in range(n + 1):
        lam = l0 + (l1 - l0) * k / n
        p = proj((a * math.cos(lam), w0 - b * math.sin(lam)))
        if k:
            d.A(a, b, TILT, 0, l1 > l0, p)
        elif move:
            d.M(p)
        else:
            d.L(p)
    return d


def circle(d: Path, proj: Affine, z: float, rho: float, l0: float, l1: float) -> Path:
    """Append the arc from angle l0 to l1 of the planet-frame circle of radius `rho` at height
    `z` (a latitude line, or a ring at z = 0) as a new subpath."""
    return ellipse(d, proj, z * math.cos(OPEN), rho, rho * math.sin(OPEN), l0, l1)


def near_band(proj: Affine, r0: float, r1: float) -> Path:
    """The near half of the ring-plane annulus between radii `r0` and `r1`."""
    d = ellipse(P(), proj, 0, r1, r1 * math.sin(OPEN), 0, math.pi)
    return ellipse(d, proj, 0, r0, r0 * math.sin(OPEN), math.pi, 0, move=False).Z()


def in_globe(x: Arr, y: Arr, z: Arr | float) -> NDArray[np.bool_]:
    return (x * x + y * y) / R**2 + z * z / RP**2 < 1


def ring_cover(r: Arr) -> NDArray[np.int64]:
    """0 clear, 1 the translucent C ring, 2 the opaque B and A rings."""
    rr = r / R
    opaque = ((OPAQUE[0] <= rr) & (rr <= CASSINI[0])) | ((CASSINI[1] <= rr) & (rr <= OPAQUE[1]))
    return np.where(opaque, 2, np.where((C_RING[0] <= rr) & (rr < C_RING[1]), 1, 0))


def ring_arcs(lam: Arr) -> list[tuple[bool, int, float, float, float]]:
    """Every ring stroke as (near side, tone, radius, l0, l1) runs over the angles `lam`: the lit
    runs in the ring's own tone, the runs in the globe's shadow in tone 0."""
    out: list[tuple[bool, int, float, float, float]] = []
    for a, b, tone, n in RINGS:
        for rr in np.linspace(a, b, n):
            lift = any(abs(rr - e) < 1e-6 for e in EDGES)
            r = rr * R
            x, y = r * np.cos(lam), r * np.sin(lam)
            # march toward the sun: ring points behind the globe sit in its shadow
            steps = np.linspace(0, 2.5 * R, 60)
            shade = np.any([in_globe(x + t * SUN[0], y + t * SUN[1], t * SUN[2]) for t in steps], 0)
            for near, side in ((False, y < 0), (True, y >= 0)):
                for k, m in ((3 if lift else tone, side & ~shade), (0, side & shade)):
                    out += [(near, k, r, lam[i], lam[j]) for i, j in runs(m[:-1])]
    return out


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = Vec(s.w, s.h) - (CORNER if s.landscape else CORNER_TALL)
    # (u, w) screen plane: u along the equator, w up the projected pole
    proj = Affine.frame(c, deg=TILT) @ Affine.scale(1, -1)
    rng = s.np_rng(3)
    lam = np.linspace(0, 2 * math.pi, N + 1)
    arcs = ring_arcs(lam)

    with s.buckets(RING_TONES, "stroke", stroke_width=1.4) as far:
        for near, tone, r, l0, l1 in arcs:
            if not near:
                circle(far[tone], proj, 0, r, l0, l1)

    # the globe's silhouette: an ellipse whose minor axis is the pole foreshortened by OPEN
    ry = math.hypot(R * math.sin(OPEN), RP * math.cos(OPEN))
    globe = ellipse(P(), proj, 0, R, ry, 0, 2 * math.pi).Z()
    s.fill(globe, BG)

    # Latitude hatch shaded by Lambert; the rings' shadow drops the lit side to UI or BG_ALT. Each
    # line jitters its own thresholds so tone boundaries don't stack into a staircase.
    with (
        s.buckets(TONES[: LIT - 1 : -1], "stroke", stroke_width=1.6) as dim,
        s.buckets(TONES[LIT - 1 :: -1], "stroke", stroke_width=2.3) as lit,
    ):
        # both blocks run darkest first; hatch[k] is the builder for TONES[k]
        hatch = [lit[LIT - 1 - k] for k in range(LIT)]
        hatch += [dim[len(TONES) - 1 - k] for k in range(LIT, len(TONES))]
        for z in np.arange(-RP + HATCH / 2, RP, HATCH):
            rho = R * math.sqrt(1 - (z / RP) ** 2)
            if rho < 0.25 * R:  # skip the tiny polar loop, it reads as a target
                continue
            x, y = rho * np.cos(lam), rho * np.sin(lam)
            nrm = np.stack([x / R**2, y / R**2, np.full_like(x, z / RP**2)], -1)
            nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
            lum = nrm @ SUN
            t = -z / SUN[2]
            cover = (
                ring_cover(np.hypot(x + t * SUN[0], y + t * SUN[1])) if t > 0 else np.zeros_like(x)
            )
            lum = np.where(cover == 2, np.minimum(lum, -1), np.where(cover == 1, lum * 0.5, lum))
            tone = np.digitize(-lum, -CUTS + rng.uniform(-0.025, 0.025, len(CUTS)))
            vis = nrm @ VIEW > 0
            for k in range(len(TONES)):
                for i, j in runs((vis & (tone == k))[:-1]):
                    circle(hatch[k], proj, z, rho, lam[i], lam[j])

    # The near B and A rings are opaque where they cross the globe; the C ring half hides the hatch.
    s.fill(near_band(proj, OPAQUE[0] * R, OPAQUE[1] * R), BG)
    s.fill(near_band(proj, C_RING[0] * R, C_RING[1] * R), BG, opacity=0.6)
    with s.buckets(RING_TONES, "stroke", stroke_width=1.4) as front:
        for near, tone, r, l0, l1 in arcs:
            if near:
                circle(front[tone], proj, 0, r, l0, l1)
    s.stroke(globe, UI, 1.2)
