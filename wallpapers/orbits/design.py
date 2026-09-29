"""Seven concentric orbits in one tilted plane round a filled sun, a planet on each, drawn as ellipses of one line weight."""

import math

from walldye import ACCENT, MUTED, UI, UI_ALT, Canvas, P, Vec, design
from walldye.geom import Affine

SUN = 40  # radius
FLAT = 0.34  # minor over major semi-axis: the tilt of the orbital plane
# Major semi-axes, each gap 20 wider than the last; the innermost clears the sun by about as
# much as the first two orbits clear each other.
ORBITS = (190, 250, 330, 430, 550, 690, 850)
# One planet per orbit: angle along it (degrees, 0 at one end of the long axis, clockwise),
# radius, and tone (0 UI_ALT, 1 MUTED, 2 ACCENT: the one filled in like the sun).
PLANETS = (
    (-166, 7, 0),
    (20, 10, 1),
    (133, 9, 0),
    (135, 16, 1),
    (-4.5, 20, 2),
    (-132, 13, 1),
    (-117, 8, 0),
)
PAINTS = (UI_ALT, MUTED, ACCENT)
EDGE = 760  # sun to right edge: the outer orbit runs off it, the next stays clear of it


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: right of center, the outer orbit running off the right edge; portrait: turned
    # a quarter so the orbits run down the screen, the filled planet near the top
    c = Vec(s.w - EDGE, s.h * 0.52) if s.landscape else Vec(s.w / 2, s.h * 0.56)
    turn = Affine.rotate(deg=-14 if s.landscape else -104, about=c)
    with s.group(transform=turn):
        orbits = P()
        for rx in ORBITS:
            orbits.ellipse(c, rx, rx * FLAT)
        s.stroke(orbits, UI, 2)
        with s.buckets(PAINTS, "fill") as b:
            for rx, (deg, r, tone) in zip(ORBITS, PLANETS, strict=True):
                t = math.radians(deg)
                b[tone].circle((c.x + rx * math.cos(t), c.y + rx * FLAT * math.sin(t)), r)
            b[2].circle(c, SUN)
