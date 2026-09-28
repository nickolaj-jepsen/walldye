"""An Apollonian gasket grown from four tangent circles by Descartes' theorem, drawn as hairlines, with one tangent chain into a cusp filled in."""

import math
from collections import deque

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_3,
    ACCENT_5,
    BG_ALT,
    BG_DEEP,
    UI_ALT,
    Canvas,
    P,
    Params,
    Vec,
    design,
    knob,
    ramp,
)
from walldye.geom import Affine

# A circle as its curvature k and k times its centre, in coordinates where the disc is the unit
# circle; the outer circle has k = -1.
type Circle = tuple[float, complex]


class Gasket(Params):
    split: float = knob(
        default=0.6, lo=0.5, hi=0.75, doc="radius of the larger root circle, as a share of the disc"
    )
    tilt: float = knob(
        default=35, lo=-180, hi=180, unit="deg", doc="clockwise turn of the root circles' diameter"
    )


VARIANTS = {"integral": Gasket(split=0.5, tilt=0)}

R, MIN_R = 440, 1.6  # disc radius; circles smaller than MIN_R are left out
SKIP, HOT = 1, 5  # chain circles skipped before the filled run, and its length
LEVELS = 10  # stroke width steps from the smallest circles up to the disc
TONES = ramp(BG_ALT, UI_ALT, 5)
CHAIN = (ACCENT, ACCENT_1, ACCENT_2, ACCENT_3, ACCENT_5)


def root(ra: float) -> tuple[Circle, Circle, Circle, Circle]:
    """Four mutually tangent circles in the unit disc: the disc itself, two circles of radius
    `ra` and `1 - ra` on a diameter, and the one below them."""
    rb = 1 - ra
    ax, bx = -1 + ra, ra
    kc = -1 + 1 / ra + 1 / rb  # Descartes' root term vanishes when ra + rb = 1
    rc = 1 / kc
    # |c| = 1 - rc and |c - a| = ra + rc
    d0, d1 = 1 - rc, ra + rc
    x = (d0 * d0 - d1 * d1 + ax * ax) / (2 * ax)
    y = math.sqrt(d0 * d0 - x * x)
    return (
        (-1.0, 0j),
        (1 / ra, complex(ax) / ra),
        (1 / rb, complex(bx) / rb),
        (kc, complex(x, y) * kc),
    )


def reflect(x: Circle, y: Circle, z: Circle, d: Circle) -> Circle:
    """The other circle tangent to `x`, `y` and `z` besides `d` (Descartes' complex theorem)."""
    return 2 * (x[0] + y[0] + z[0]) - d[0], 2 * (x[1] + y[1] + z[1]) - d[1]


def gasket(o: Circle, a: Circle, b: Circle, c: Circle) -> list[Circle]:
    """Every circle of the packing grown from the root quadruple, breadth first, down to MIN_R
    on the canvas (capped at 4000 circles)."""
    circles = [o, a, b, c]
    q = deque([((o, a, b), c), ((o, a, c), b), ((o, b, c), a), ((a, b, c), o)])
    while q and len(circles) < 4000:
        (x, y, z), d = q.popleft()
        n = reflect(x, y, z, d)
        if R / n[0] < MIN_R:
            continue
        circles.append(n)
        q.extend([((x, y, n), z), ((x, z, n), y), ((y, z, n), x)])
    return circles


def key(c: Circle) -> tuple[float, float, float]:
    """`c` rounded, to match a circle reached by two routes."""
    return round(c[0], 5), round(c[1].real, 4), round(c[1].imag, 4)


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Gasket]) -> None:
    # left third on a landscape screen; on a portrait one the disc fills the width, high up
    frame = Affine.frame(
        s.pick(landscape=(660 / 1920, 560 / 1080), portrait=(0.5, 0.4)), deg=s.params.tilt, scale=R
    )

    def place(c: Circle) -> tuple[Vec, float]:
        z = c[1] / c[0]
        return frame((z.real, z.imag)), R / abs(c[0])

    o, a, b, c = root(s.params.split)
    # circles tangent to both o and b march into their cusp
    run, prev, cur = [], a, c
    for _ in range(SKIP + HOT):
        run.append(cur)
        prev, cur = cur, reflect(o, b, cur, prev)
    hot = run[SKIP:]
    hot_keys = {key(h) for h in hot}

    s.fill(P().circle(*place(a)), BG_DEEP)

    # stroke width and tone step up with log radius
    rings = [P() for _ in range(LEVELS + 1)]
    for circle in gasket(o, a, b, c):
        if key(circle) not in hot_keys:
            centre, r = place(circle)
            t = min(1.0, math.log(r / MIN_R) / math.log(R / MIN_R))
            rings[round(t * LEVELS)].circle(centre, r)
    for i, d in enumerate(rings):
        s.stroke(d, TONES[round(i / LEVELS * 4)], 0.6 + i / LEVELS)

    for h, paint in zip(hot, CHAIN, strict=True):
        centre, r = place(h)
        # inset so the tangent hairlines around the chain stay unbroken
        s.fill(P().circle(centre, r - min(1.2, 0.1 * r)), paint)
