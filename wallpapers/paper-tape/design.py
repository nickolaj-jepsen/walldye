"""Eight-hole paper tape punched with ASCII and even parity loops once across the screen; one short burst of rows is lit."""

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline
from shapely import LineString, Polygon
from shapely.affinity import translate

from walldye import (
    ACCENT,
    ACCENT_3,
    BG_ALT,
    BG_DEEP,
    UI,
    Canvas,
    P,
    Vec,
    by_regime,
    design,
    lerp,
    mix,
    polar,
)
from walldye.geom import Affine, Polyline

R = 180  # loop radius
LOOP = (0.65625, 330)  # loop center: a fraction of the long side across, units down from the top
HALF = 60  # half the tape width
PITCH, STEP = 18, 3  # row pitch; spine sample step (PITCH is a whole number of steps)
SHADOW = (6, 9)
# BG_DEEP is lighter than the page on light themes, so there the shadow steps toward UI instead.
SHADE = by_regime(BG_DEEP, mix(BG_ALT, UI, 0.5))
LANES, FEED = (-48, -36, -24, 0, 12, 24, 36, 48), -12  # feed holes sit between channels 3 and 4
TEXT = b"NIXOS-REBUILD SWITCH --FLAKE .#DESKTOP\r\n"
# Rubouts frame the lit burst; rows outside DATA are feed-only, which keeps the long tails calm.
DATA = (TEXT[:12] + b"\xff\xff" + b"NIXOSNIXOS" + b"\xff\xff" + TEXT[12:] + TEXT * 2)[:106]
BURST = range(12, 26)  # indices into DATA
AHEAD = 69  # rows of DATA punched before the top of the loop


def parity(b: int) -> int:
    """`b` with bit 7 set when that makes the count of set bits even."""
    return b | (b.bit_count() & 1) << 7


def center(long: float) -> Vec:
    """The loop center in a landscape frame `long` by 1080."""
    return Vec(LOOP[0] * long, LOOP[1])


def knots(long: float) -> NDArray[np.float64]:
    """Spline knots in a landscape frame `long` by 1080: in from the lower left, a loop entered
    along its tangent at 60 degrees so the opening stays round, out from its bottom to the upper
    right. At 1920 these are the 16:9 layout."""
    c = center(long)
    start, approach, leave, end = (
        Vec(-120, 1010),
        c + (-360, 360),
        c + (220, 150),
        Vec(long + 160, 170),
    )
    return np.array(
        [
            start,
            # the knots between scale with the tails, so a wide screen gets one long even curve
            (lerp(start.x, approach.x, 0.53), 870),
            approach,
            c + (-80, 256),
            *[polar(c, R, deg=a) for a in range(60, -271, -30)],
            leave,
            (lerp(leave.x, end.x, 0.45), 370),
            end,
        ]
    )


@design(aspects="any")
def draw(s: Canvas) -> None:
    long = max(s.w, s.h)
    # Portrait screens get the landscape layout turned a quarter turn: the tape rises from the bottom.
    frame = Affine.identity() if s.landscape else Affine.frame((0, s.h), bearing=0)
    pts = frame.apply(knots(long))
    t = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    cs = CubicSpline(t, pts)
    line = Polyline(cs(np.linspace(0, t[-1], 6000)))
    spine = line.resample(STEP).pts
    ds = np.arange(PITCH / 2, line.length, PITCH)
    rows = [Vec(x, y) for x, y in line.at(ds)]
    normals = [line.tangent(d).perp() for d in ds]
    top = frame(center(long) + (0, -R))
    split = min(range(len(rows)), key=lambda i: abs(rows[i] - top))
    k = PITCH // STEP

    def spine_of(i0: int, i1: int) -> LineString:
        return LineString(spine[i0 * k : i1 * k + 1])

    # Buffering (not ±HALF offsets) keeps the body clean on tight bends, where offsets swallowtail.
    def body(i0: int, i1: int) -> Polygon:
        return spine_of(i0, i1).buffer(HALF, cap_style="flat", quad_segs=16)

    s.fill(P().shape(translate(body(0, len(rows)), *SHADOW)), SHADE)
    # Segments share row `split` so their fills overlap instead of abutting in an anti-aliased seam.
    for i0, i1 in ((0, split + 1), (split, len(rows))):
        if i0:
            # Where the loop crosses back over the tape; starting past the seam keeps its cap off the lower pass.
            s.fill(P().shape(translate(body(i0 + 20, i1), *SHADOW)), SHADE)
        # Holes are painted, not cut: a cut hole would show the shadow edge or the pass below as a chord.
        holes, lit, sprockets = P(), P(), P()
        for i in range(i0, i1):
            j = i - split + AHEAD
            byte = parity(DATA[j]) if 0 <= j < len(DATA) else 0
            burst = j in BURST
            at, n = rows[i], normals[i]
            (sprockets if burst else holes).circle(at + n * FEED, 2.8)
            for bit, off in enumerate(LANES):
                if byte >> bit & 1:
                    (lit if burst else holes).circle(at + n * off, 4.6)
        s.fill(P().shape(body(i0, i1)), BG_ALT)
        seg = spine_of(i0, i1)
        s.stroke(
            P()
            .shape(seg.offset_curve(HALF, quad_segs=16))
            .shape(seg.offset_curve(-HALF, quad_segs=16)),
            UI,
            1.5,
        )
        s.fill(holes, BG_DEEP)
        s.fill(lit, ACCENT)
        s.fill(sprockets, ACCENT_3)
