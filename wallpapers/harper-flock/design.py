"""Charley Harper-style skein of flat faceted birds past a half moon; birds crossing the disc become silhouettes."""

import math

from walldye import ACCENT, BG_ALT, BG_DEEP, UI, UI_ALT, UI_HI, Canvas, P, Path, Vec, design, polar
from walldye.geom import Affine

R = 340  # moon radius
APEX = Vec(-350, -630)  # the leader, from the moon's centre on the horizon
HEADING = 32  # deg: from the leader back along the V's bisector
SPREAD, ARM, BIRDS = 16, 640, 11  # half-angle of the V (deg), arm length, birds per arm
SIZE = 80  # wingspan of the nearest bird
# Kite body in units of one wingspan, nose up.
BODY = (
    Vec(0, -0.1),
    Vec(0.035, -0.035),
    Vec(0.03, 0.04),
    Vec(0, 0.11),
    Vec(-0.03, 0.04),
    Vec(-0.035, -0.035),
)
TONES = (ACCENT, UI_ALT, UI_HI)  # the leader, then far and near birds


def ccw(pts: list[Vec]) -> list[Vec]:
    """`pts` in one fixed winding, so overlapping facets of a bird add up under the nonzero
    fill rule instead of cancelling."""
    area = sum(a.x * b.y - a.y * b.x for a, b in zip(pts, pts[1:] + pts[:1], strict=True))
    return pts if area > 0 else pts[::-1]


def facets(flap: float) -> list[list[Vec]]:
    """A front-view bird in units of one wingspan: the kite body, then two flat facets per gull
    wing, right wing first, both raised `flap` radians."""
    arm = polar((0, 0), 1, rad=-flap - 0.25)  # the inner wing kinks up, the hand droops
    hand = polar((0, 0), 1, rad=0.3 - flap)
    n_arm, n_hand = -arm.perp(), -hand.perp()  # towards the trailing edge
    root = Vec(0.025, -0.02)
    wrist = root + arm * 0.19
    hand0 = wrist + hand * 0.025  # the gap between the two facets reads as a crisp cut
    tip = hand0 + hand * 0.3 + n_hand * 0.04
    right = [
        [root - n_arm * 0.035, wrist - n_arm * 0.03, wrist + n_arm * 0.065, root + n_arm * 0.1],
        [
            hand0 - n_hand * 0.03,
            tip,
            hand0 + (tip - hand0) * 0.5 + n_hand * 0.045,
            hand0 + n_hand * 0.07,
        ],
    ]
    left = [[Vec(-p.x, p.y) for p in shape] for shape in right]
    return [list(BODY), *right, *left]


def bird(d: Path, c: Vec, span: float, bank: float, flap: float) -> None:
    """Add a bird centred on `c`, `span` wide and rolled `bank` radians, to `d`."""
    m = Affine.frame(c, rad=bank, scale=span)
    for shape in facets(flap):
        d.poly(m.apply(ccw(shape)), closed=True)


@design(aspects="any")
def draw(s: Canvas) -> None:
    rng = s.rng(5)
    # the moon's centre, on the horizon: right of centre on a landscape screen, clear of the
    # right edge on 16:10; centred under the clock on a portrait one
    c = s.pick(landscape=(0.78, 0.86), portrait=(0.524, 0.66))
    c = Vec(min(c.x, s.w - R - 80), c.y)
    moon = P().arc(c, R, deg=(180, 360)).Z()
    s.fill(moon, BG_ALT)
    s.stroke(P().M(0, c.y).H(s.w), UI, 1.5)

    apex = c + APEX
    flock = [(apex, SIZE * 1.05, -0.08, 0.1, 0)]
    scales = [0.55 + 0.45 * k / BIRDS for k in range(1, BIRDS + 1)]
    for side, phase in ((1, 0.0), (-1, 1.7)):
        back = polar((0, 0), 1, deg=HEADING + SPREAD * side)
        dist = 70
        for k, scale in enumerate(scales, 1):
            pos = apex + back * dist
            # spacing grows with size, like the birds' perspective
            dist += (ARM - 70) * scale / sum(scales[1:])
            pos += Vec(rng.gauss(0, 3), rng.gauss(0, 3)) * scale
            flap = 0.05 + 0.3 * math.sin(2 * math.pi * k / 7 + phase)  # a wingbeat down the arm
            near = k > BIRDS - 3  # the nearest birds read brightest
            flock.append((pos, SIZE * scale, -0.08 + 0.04 * math.sin(k + phase), flap, 1 + near))

    silhouettes = P()
    with s.buckets(TONES, "fill") as birds:
        for pos, span, bank, flap, tone in flock:
            bird(birds[tone], pos, span, bank, flap)
            bird(silhouettes, pos, span, bank, flap)
    # against the moon the birds turn to cut-out silhouettes
    with s.clip() as disc:
        disc.add(moon)
    s.path(silhouettes, fill=BG_DEEP, clip_path=disc.ref)
