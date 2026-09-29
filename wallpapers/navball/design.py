"""A spacecraft attitude ball at an odd tilt: an orthographic latitude-longitude sphere split at its horizon, in a ticked bezel."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_2,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Path,
    Vec,
    design,
    mix,
    polar,
)
from walldye.field import runs

R = 300  # ball radius
SKY, GROUND = mix(BG, BG_ALT, 0.8), mix(BG_ALT, UI, 0.85)
# Grid lines by hemisphere, (sky, ground): minor every 10 degrees, major every 30.
MINOR = (mix(SKY, UI, 0.6), mix(GROUND, BG, 0.5))
MAJOR = (mix(UI, UI_ALT, 0.5), mix(GROUND, UI_ALT, 0.6))
# The fixed aircraft symbol, relative to the ball center.
WING = np.array([(-90, 0), (-36, 0), (-18, 20), (0, 2), (18, 20), (36, 0), (90, 0)])


def rotation(pitch: float, roll: float, yaw: float) -> NDArray[np.float64]:
    """The body-to-view rotation for an attitude in degrees: yaw, then pitch, then roll."""
    p, r, y = math.radians(pitch), math.radians(roll), math.radians(yaw)
    ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    rx = np.array([[1, 0, 0], [0, math.cos(p), -math.sin(p)], [0, math.sin(p), math.cos(p)]])
    rz = np.array([[math.cos(r), -math.sin(r), 0], [math.sin(r), math.cos(r), 0], [0, 0, 1]])
    return rz @ rx @ ry


def body(lat: NDArray[np.float64], lon: NDArray[np.float64]) -> NDArray[np.float64]:
    """Unit vectors (N, 3) on the ball for latitudes and longitudes in degrees; +y is north."""
    la, lo = np.radians(lat), np.radians(lon)
    return np.stack([np.cos(la) * np.sin(lo), np.sin(la), np.cos(la) * np.cos(lo)], -1)


ROT = rotation(25, -18, 30)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: (620, 560) at 16:9, the left third, leaving the right free; portrait: low middle
    c = s.pick(landscape=(31 / 96, 14 / 27), portrait=(0.5, 0.58))

    def project(v: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Screen points of body vectors, and their depth (positive faces the viewer)."""
        w = v @ ROT.T
        return np.stack([c.x + R * w[:, 0], c.y - R * w[:, 1]], -1), w[:, 2]

    def visible(d: Path, pts: NDArray[np.float64], z: NDArray[np.float64]) -> None:
        for a, b in runs(z > 0):
            if b - a > 1:
                d.poly(pts[a:b])

    # Sky cap: the front half of the equator, closed along the limb on the north side.
    eq, ez = project(body(np.zeros(720), np.linspace(0, 360, 720, endpoint=False)))
    k = int(np.argmax(ez <= 0))  # start behind the ball, so the front half is one run
    eq, ez = np.roll(eq, -k, 0), np.roll(ez, -k)
    arc = eq[ez > 0]
    start, end = Vec(*arc[0]) - c, Vec(*arc[-1]) - c
    a0, a1 = math.atan2(end.y, end.x), math.atan2(start.y, start.x)
    sweep = (a1 - a0) % math.tau
    mid = a0 + sweep / 2
    north = ROT[:, 1]  # screen direction (north[0], -north[1])
    if math.cos(mid) * north[0] - math.sin(mid) * north[1] < 0:
        sweep -= math.tau
    ball = P().circle(c, R)
    s.fill(ball, GROUND)
    s.fill(P().poly(arc).A(R, R, 0, abs(sweep) > math.pi, sweep > 0, arc[0]).Z(), SKY)

    with (
        s.buckets(MINOR, "stroke", stroke_width=1.2, stroke_linecap="round") as minor,
        s.buckets(MAJOR, "stroke", stroke_width=1.5, stroke_linecap="round") as major,
    ):
        for lat in range(-70, 80, 10):
            if lat != 0:
                pts, z = project(body(np.full(361, lat), np.linspace(0, 360, 361)))
                visible((major if lat % 30 == 0 else minor)[int(lat < 0)], pts, z)
        for lon in range(0, 360, 10):
            top = 90 if lon % 30 == 0 else 70  # minor meridians stop short of the poles
            for lats in (np.linspace(0, top, 46), np.linspace(-top, 0, 46)):
                pts, z = project(body(lats, np.full(46, lon)))
                visible((major if lon % 30 == 0 else minor)[int(lats[0] < 0)], pts, z)
    s.stroke(P().poly(arc), UI_HI, 2, cap="round")
    shade = s.radial_gradient([(0.55, BG, 0), (1, BG_DEEP, 0.4)], c + (-60, -70), R + 70)
    s.fill(ball, shade)
    s.stroke(ball, UI, 1.6)

    # Bezel with roll ticks every 10 degrees, longer every 30.
    s.stroke(P().circle(c, R + 7), BG_DEEP, 14)
    s.stroke(P().circle(c, R + 14), UI, 1.5)
    ticks = P()
    for b in range(0, 360, 10):
        ticks.M(polar(c, R + 22, bearing=b)).L(polar(c, R + (42 if b % 30 == 0 else 32), bearing=b))
    s.stroke(ticks, UI, 2, cap="round")

    # Two rate needles on the bezel, top and right, both nudged clockwise off their zero.
    needles = P()
    for b in (0, 90):
        p, t = polar(c, R + 7, bearing=b), polar((0, 0), 1, bearing=b).perp()
        needles.M(p - t * 7).L(p + t * 17)
    s.stroke(needles, ACCENT_2, 4, cap="round")
    s.stroke(P().poly(c + WING), ACCENT, 5.5, join="round", cap="round")
