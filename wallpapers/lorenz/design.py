"""The Lorenz attractor as one integrated trajectory in faint overlapping strokes."""

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import LineString

from walldye import ACCENT, UI_HI, Canvas, P, Path, Vec, design, smoothstep
from walldye.geom import Affine

type Pts = NDArray[np.float64]

SIGMA, RHO, BETA = 10.0, 28.0, 8 / 3  # Lorenz's classic chaotic parameters
DT, STEPS, SKIP = 0.004, 25_000, 500  # RK4 step, steps drawn, transient dropped
SCALE, TILT = 19.25, 14  # units per attractor unit; clockwise turn of the side view, in degrees
CHUNK = 150  # steps per stroke of the thread
# accent window around the switch, in steps: fade-in, bright diagonal + crossing, fade-out
FADE_IN, CORE, FADE_OUT = (-70, -42), (-42, 66), (66, 96)


def lorenz(p: Pts) -> Pts:
    """The Lorenz vector field at `p` = (x, y, z)."""
    x, y, z = p
    return np.array([SIGMA * (y - x), x * (RHO - z) - y, x * y - BETA * z])


def trajectory() -> Pts:
    """(STEPS, 3) points of one RK4 trajectory from (0.1, 0, 0), after SKIP transient steps."""
    p, out = np.array([0.1, 0.0, 0.0]), []
    for _ in range(STEPS + SKIP):
        k1 = lorenz(p)
        k2 = lorenz(p + DT / 2 * k1)
        k3 = lorenz(p + DT / 2 * k2)
        k4 = lorenz(p + DT * k3)
        p = p + DT / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        out.append(p)
    return np.array(out[SKIP:])


def project(t: Pts, c: Vec, scale: float) -> Pts:
    """The x-z side view of `t`, tilted by TILT, scaled, with its bounding box centered on `c`."""
    xy = Affine.rotate(deg=TILT).apply(np.c_[t[:, 0], -t[:, 2]])
    return (xy - (xy.min(0) + xy.max(0)) / 2) * scale + c


def poly(xy: Pts, tol: float = 0.3) -> Path:
    """An open polyline through `xy`, simplified to within `tol` units."""
    return P().poly(np.asarray(LineString(xy).simplify(tol).coords))


@design(aspects="any")
def draw(s: Canvas) -> None:
    # left of center on a landscape screen, leaving the right for windows; centered and a little
    # larger below the clock on a portrait one
    c = s.pick(landscape=(0.34375, 0.5), portrait=(0.5, 0.55))
    t = trajectory()
    xy = project(t, c, SCALE if s.landscape else SCALE * 1.2)

    # a wing switch after the longest dwell on one lobe in the first half of the run
    flips = np.flatnonzero(np.diff(np.sign(t[:, 0])))
    dwell = np.diff(flips)
    k = int(flips[1 + int(np.argmax(dwell[: len(dwell) // 2]))])

    # short translucent strokes, so overlapping passes build up density in the core
    with s.group(
        stroke=UI_HI,
        stroke_width=0.9,
        stroke_opacity=0.32,
        stroke_linecap="round",
        stroke_linejoin="round",
    ):
        for i in range(0, len(xy), CHUNK):
            s.path(poly(xy[i : i + CHUNK + 1]), fill="none")
    s.stroke(poly(xy[k + CORE[0] : k + CORE[1] + 1]), ACCENT, 2, cap="round", join="round")
    # the ends dissolve by opacity into the thread; butt caps keep chunk joints from doubling up
    for (a, b), rising in ((FADE_IN, True), (FADE_OUT, False)):
        for lo in range(a, b, 3):
            u = smoothstep(a, b, lo + 1.5)
            op = u if rising else 1 - u
            chunk = poly(xy[k + lo : k + min(lo + 3, b) + 1])
            s.stroke(chunk, ACCENT, 1.2 + 0.8 * op, cap="butt", join="round", opacity=op)
