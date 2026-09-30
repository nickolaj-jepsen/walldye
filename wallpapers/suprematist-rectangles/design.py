"""Suprematist rectangles at one shared tilt, spaced along a curve and shrinking as they drift into empty space."""

from itertools import accumulate, pairwise

from walldye import ACCENT, ACCENT_1, UI, UI_ALT, UI_HI, Canvas, Vec, clamp, design
from walldye.geom import Affine, Polyline, bezier_points

CURVE = ((400, 750), (790, 580), (1160, 320))  # quadratic Bézier the shoal follows, 16:9 units
HUB = Vec(713, 614)  # center of the shoal's bounds: the point each screen shape places
TURN = -24  # extra turn on portrait screens, so the drift climbs the long side
BASE = -28  # shared tilt of the blocks, deg; each gets up to 2deg of jitter
GAP, PAD = 1.0, 16  # center spacing along the curve: GAP x the neighbors' mean width + PAD
LANE = 40  # half-width of the corridor between the two rows at hero scale; shrinks with depth
BAR = (360, 320)  # hairline counter-stroke: center arc position, length
BAR_W = 2.4

TONES = (ACCENT, ACCENT_1, UI, UI_ALT, UI_HI)
HERO, EMBER, DIM, MID, HI = range(5)
# (tone, width, aspect, side of the corridor, tilt override); the hero leads, the -14deg one is the deliberate outlier.
PLAN = [
    (HERO, 300, 2.7, 0.5, None),
    (DIM, 160, 3.1, -1, None),
    (MID, 122, 2.6, 1, None),
    (EMBER, 94, 2.5, -1, None),
    (DIM, 72, 3.2, 1, None),
    (MID, 55, 2.4, -1, -14),
    (EMBER, 42, 2.6, 1, None),
    (DIM, 32, 2.8, -1, None),
    (MID, 24, 2.4, 1, None),
    (HI, 11, 1.0, 0, None),
]
CORNERS = (Vec(-0.5, -0.5), Vec(0.5, -0.5), Vec(0.5, 0.5), Vec(-0.5, 0.5))


def box(c: Vec, w: float, h: float, deg: float) -> list[Vec]:
    """The corners of a `w` by `h` rectangle centered on `c`, turned `deg` clockwise."""
    return [c + Vec(k.x * w, k.y * h).rotate(deg=deg) for k in CORNERS]


@design(aspects="any")
def draw(s: Canvas) -> None:
    r = s.rng(8)
    turn = 0 if s.landscape else TURN
    hub = s.pick(landscape=(HUB.x / 1920, HUB.y / 1080), portrait=(0.5, 0.56))
    place = Affine.frame(hub, deg=turn) @ Affine.translate(-HUB.x, -HUB.y)
    line = Polyline(bezier_points(place.apply(CURVE), 400))

    steps = (GAP * (w0 + w1) / 2 + PAD for (_, w0, *_), (_, w1, *_) in pairwise(PLAN))
    at = list(accumulate(steps, initial=0.0))
    stretch = line.length / at[-1]
    with s.buckets(TONES, "fill") as b:
        for (tone, w, aspect, side, tilt), a in zip(PLAN, at, strict=True):
            h = w / aspect
            d = a * stretch
            c = line.at(d) + line.tangent(d).perp() * (side * (h / 2 + LANE * w / 300))
            deg = tilt if tilt is not None else BASE + clamp(r.gauss(0, 1), -2, 2)
            b[tone].poly(box(c, w, h, deg + turn), closed=True)
        b[HI].poly(box(line.at(BAR[0]), BAR[1], BAR_W, BASE + turn), closed=True)
