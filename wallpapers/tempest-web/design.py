"""The Tempest playfield in vector line work: a 16-lane star tube seen from above its axis, one lane lit and the claw-shaped Blaster on its rim."""

import itertools
import math

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_5,
    ACCENT_7,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    P,
    Vec,
    design,
    polar,
)
from walldye.geom import Affine

R, N = 390, 16  # rim radius; lanes
INNER = 0.8  # radius of the notch vertices; star points sit on every other vertex
EYE = Vec(-40, -80)  # vanishing point from the rim's centre: the camera sits above the tube axis
DEPTHS = (1.0, 0.56, 0.33, 0.2)  # ring scales toward the vanishing point, rim first
LANE = 9  # the lit lane runs between vertices 9 and 10
SHOTS = (0.66, 0.42)  # depths of the two shots; a shot's half-side is 7 x its depth
# The Blaster's outline in rim-segment units: along the segment from its midpoint, then into the tube.
CLAW = np.array(
    [
        (-0.42, 0),
        (-0.34, 0.15),
        (-0.13, 0.36),
        (-0.07, 0.13),
        (0.07, 0.13),
        (0.13, 0.36),
        (0.34, 0.15),
        (0.42, 0),
    ]
)


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(1300 / 1920, 0.5), portrait=(0.5, 0.6))
    vp = c + EYE

    def vertex(k: int, t: float) -> Vec:
        """Vertex `k` of the ring at depth `t` (1 is the rim, 0 the vanishing point)."""
        rim = polar(c, R if k % 2 == 0 else R * INNER, bearing=360 * k / N)
        return vp + (rim - vp) * t

    def lane(u: float, t: float) -> Vec:
        """The point `u` of the way across the lit lane at depth `t`."""
        a, b = vertex(LANE, t), vertex(LANE + 1, t)
        return a + (b - a) * u

    rings = [[vertex(k, t) for k in range(N)] for t in DEPTHS]
    # lanes stay UI only near the rim, so the web recedes quickly behind windows
    near, far = P(), P()
    for a, b in zip(rings[0], rings[1], strict=True):
        near.M(a).L(b)
    for ring in rings[2:]:
        far.poly(ring, closed=True)
    for outer, inner in itertools.pairwise(rings[1:]):
        for a, b in zip(outer, inner, strict=True):
            far.M(a).L(b)
    s.stroke(P().poly(rings[0], closed=True), UI_ALT, 2.2, join="round")
    s.stroke(P().poly(rings[1], closed=True), BG_ALT, 1.4, join="round")
    s.stroke(far, BG_ALT, 1.2, cap="round", join="round")
    s.stroke(near, UI, 1.2, cap="round")

    end = DEPTHS[-1]
    o0, o1, i0, i1 = lane(0, 1), lane(1, 1), lane(0, end), lane(1, end)
    mo, mi = lane(0.5, 1), lane(0.5, end)
    fade = (1 - 0.5) / (1 - end)  # the glow is gone by depth 0.5
    glow = s.linear_gradient([(0, ACCENT_7), (fade, BG)], mo, mi)
    s.fill(P().poly([o0, o1, i1, i0], closed=True), glow)
    s.stroke(P().poly([i0, o0]).poly([o1, i1]), ACCENT, 1.6, cap="round")
    s.stroke(P().M(o0).L(o1), ACCENT, 2.6, cap="round")

    shots = P()
    for t in SHOTS:
        h = 7 * t
        corner = lane(0.5, t) - (h, h)
        shots.rect(corner.x, corner.y, 2 * h, 2 * h)
    s.fill(shots, ACCENT)

    # The Blaster sits upright in the rim segment's own frame. Local +y is a quarter turn
    # clockwise from the segment direction, so pick the direction that turns it into the tube.
    along = o1 - o0
    if along.perp().dot(mi - mo) < 0:
        along = -along
    frame = Affine.frame(mo, rad=math.atan2(along.y, along.x), scale=abs(along))
    s.path(
        P().poly(frame.apply(CLAW), closed=True),
        fill=ACCENT_5,
        stroke=ACCENT,
        stroke_width=2.4,
        stroke_linejoin="round",
    )
