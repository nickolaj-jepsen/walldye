"""After Lissitzky's 1919 poster, in flat shapes: a wedge drives into a disc, and its axis runs on past the rim with small fragments strewn along it."""

import math

from walldye import ACCENT, ACCENT_1, BG_ALT, UI, UI_ALT, UI_HI, Canvas, P, Vec, design, mix
from walldye.geom import Affine

R, HALF = 300, 95  # disc radius; half the width of the wedge's base
AXIS = Vec(860, -330)  # wedge base to tip on a landscape screen
TIP = Vec(0, 20)  # the tip lands just below the disc's centre
PORTRAIT_TURN = -38  # deg: steeper on a portrait screen, so the wedge fits the width
# fragments in wedge-axis space: distance from the base, offset across the axis, width, height
FRAGS = (
    (-70, 0, 50, 5),
    (590, -54, 20, 20),
    (700, 40, 46, 4),
    (1330, -30, 12, 12),
    (1450, 24, 34, 3),
)
# a fragment lying on the disc is lifted a step so it survives there
FRAG_TONES = (UI_ALT, mix(UI_ALT, UI_HI, 0.5))


def corners(w: float, h: float) -> list[tuple[float, float]]:
    """The corners of a `w` by `h` rectangle centred on the origin."""
    return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(1330 / 1920, 480 / 1080), portrait=(0.62, 0.36))
    axis = AXIS if s.landscape else AXIS.rotate(deg=PORTRAIT_TURN)
    u = axis.unit()
    heading = math.degrees(math.atan2(u.y, u.x))
    tip = c + TIP
    base = tip - axis

    def at(t: float, off: float = 0) -> Vec:
        return base + u * t + u.perp() * off

    wedge = P().poly([at(0, HALF), at(0, -HALF), tip], closed=True)

    s.fill(P().circle(c, R), mix(BG_ALT, UI, 0.4))
    # the axis carries on from the tip to the edge, a step lighter across the disc
    d = tip - c
    rim = tip + u * (math.sqrt(d.dot(u) ** 2 - d.dot(d) + R**2) - d.dot(u))
    edge = tip + u * min((s.w - tip.x) / u.x, -tip.y / u.y)
    s.stroke(P().M(tip).L(rim), UI_ALT, 1.2)
    s.stroke(P().M(rim).L(edge), UI, 1.2)
    s.fill(wedge, ACCENT)
    with s.clip() as disc:
        disc.add(P().circle(c, R))
    s.path(wedge, fill=ACCENT_1, clip_path=disc.ref)

    rng = s.rng(4)
    clear = s.inset(80)
    with s.buckets(FRAG_TONES, "fill") as frags:
        for t, off, w, h in FRAGS:
            p = at(t, off)
            turn = Affine.frame(p, deg=heading + rng.uniform(-10, 10))
            # a fragment crowding the edge on a narrower screen is left out, not squeezed in
            if clear.contains(p):
                frags[int(abs(p - c) < R)].poly(turn.apply(corners(w, h)), closed=True)
