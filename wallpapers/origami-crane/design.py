"""A paper crane in flat-shaded facets, balanced on one corner of its own bird-base crease pattern."""

import math

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_3,
    ACCENT_5,
    BG_ALT,
    UI,
    Canvas,
    P,
    Params,
    design,
    knob,
)
from walldye.geom import Affine

CP_R = 350  # half-diagonal of the crease-pattern square
K = 1.1  # crane scale
TONES = (ACCENT, ACCENT_1, ACCENT_2, ACCENT_3, ACCENT_5)

# Bird base on the unit square (u, v), turned 45 degrees: (0, 0) is the top corner, (1, 0) the
# right one. FLAP is where the flap creases cross the midlines.
FLAP = 0.5 * math.tan(math.radians(22.5))
CORNERS = ((0, 0), (1, 0), (1, 1), (0, 1))
FLAPS = ((0.5, FLAP), (1 - FLAP, 0.5), (0.5, 1 - FLAP), (FLAP, 0.5))
DIM_OFF, DIM_GAP, DIM_OVER = 80, 10, 8  # dimension line offset; extension-line gap, overshoot

# Crane facets as (tone, points) in draw order; the body's bottom point B is the origin.
# Everything stays steeper than 45 degrees off the corner, so the crane never crosses the pattern.
B, L, T, R = (0, 0), (-64, -102), (8, -120), (98, -86)
NR, TR = (-30, -111), (58, -95)  # inner neck and tail roots on the body's upper edges
NECK, TAIL = (-189, -318), (265, -272)  # the neck rises at 60 degrees, the tail at 48
FACETS = (
    (4, (40, -106), (152, -82), (160, -380)),  # far wing, a darker peek behind the near one
    (2, R, TAIL, (82, -89)),
    (3, (82, -89), TAIL, TR),
    (1, L, NECK, (-47, -106)),
    (3, (-47, -106), NECK, NR),
    (0, NECK, (-234, -292), (-176, -296)),  # head
    (1, L, T, B),  # body
    (3, T, R, B),
    (0, (-60, -110), (46, -97), (127, -400)),  # near wing, swept up and back
    (2, (46, -97), (150, -82), (127, -400)),
)


class Drawing(Params):
    dimensions: bool = knob(default=True, doc="the dimension along the pattern's edge")


@design(aspects="any", variants={"undimensioned": Drawing(dimensions=False)})
def draw(s: Canvas[Drawing]) -> None:
    # Landscape: the crane perches on the right corner and flies clear of the pattern.
    # Portrait: it stands on the top corner, stacking crane over pattern.
    c = s.pick(landscape=(1030 / 1920, 570 / 1080), portrait=(0.53, 0.61))
    sq = Affine.frame(c - (0, CP_R), deg=45, scale=CP_R * math.sqrt(2))

    mountain, valley = P(), P()
    valley.M(sq((0, 0))).L(sq((1, 1))).M(sq((1, 0))).L(sq((0, 1)))
    mountain.M(sq((0.5, 0))).L(sq((0.5, 1))).M(sq((0, 0.5))).L(sq((1, 0.5)))
    mountain.poly(sq.apply(FLAPS), closed=True)
    for k, corner in enumerate(CORNERS):
        for f in (FLAPS[k], FLAPS[k - 1]):
            valley.M(sq(corner)).L(sq(f))
    s.stroke(mountain, BG_ALT, 1.4, dash=(14, 5, 2, 5))
    s.stroke(valley, BG_ALT, 1.4, dash=(8, 6))
    s.stroke(P().poly(sq.apply(CORNERS), closed=True), UI, 1.4)

    if s.params.dimensions:
        # Drafting dimension outside the lower-left edge: local x runs along the edge from the left
        # corner, local y points away from the pattern.
        side = CP_R * math.sqrt(2)
        dim = Affine.frame(sq((0, 1)), deg=45)
        ext = P()
        for x in (0, side):
            ext.M(dim((x, DIM_GAP))).L(dim((x, DIM_OFF + DIM_OVER)))
        ext.M(dim((0, DIM_OFF))).L(dim((side, DIM_OFF)))
        heads = P().arrowhead(dim((0, DIM_OFF)), 14, deg=225, width=4.5)
        heads.arrowhead(dim((side, DIM_OFF)), 14, deg=45, width=4.5)
        s.stroke(ext, UI, 1.2)
        s.fill(heads, UI)

    crane = Affine.frame(sq((1, 0)) if s.landscape else sq((0, 0)), deg=0, scale=K)
    for tone, *pts in FACETS:
        s.path(
            P().poly(crane.apply(pts), closed=True),
            fill=TONES[tone],
            stroke=TONES[tone],
            stroke_width=0.6,
            stroke_linejoin="round",
        )
