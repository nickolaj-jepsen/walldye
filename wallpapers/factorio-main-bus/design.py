"""A main-bus split-off in plan view: a splitter on the nearest belt of an eastbound bus sends half its plates north to an inserter feeding a gear assembler."""

import math

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
from walldye.geom import Polyline

T = 36  # tile pitch; belts are 28 wide, centred in their tile
BW = 28
NEAR, FAR = (0, 1, 2, 3), (6, 7, 8, 9)  # bus rows; rows 4-5 are the service gap
END_ROW, INS_ROW, ASM_ROW = -6, -7, -10  # last branch tile, inserter, assembler top (rows -10..-8)
PITCH = T / 2  # chevron spacing on the branch
EAST, NORTH = Vec(1, 0), Vec(0, -1)
MID = mix(BG_ALT, UI, 0.5)
# one gear tooth: (degrees off the tooth's centre line, radius)
TOOTH = ((-17.2, 9.5), (-11.5, 13), (11.5, 13), (17.2, 9.5))


def chev(d: Path, p: Vec, u: Vec, a: float = 4, b: float = 5) -> None:
    """Append a tread chevron at `p` pointing along the unit vector `u`, `2a` deep and `2b` wide."""
    n = u.perp()
    d.M(p - u * a + n * b).L(p + u * (a * 0.2)).L(p - u * a - n * b)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # west edge of the splitter tile and top of bus row 0 (the belt nearest the factory), on the
    # tile grid so the floor pattern lines up without an offset
    sx, y0 = s.pick(landscape=(0.58, 0.6), portrait=(0.52, 0.62), snap=T)
    lx = sx + 1.5 * T  # branch centreline: the curve tile right after the splitter
    xb, yb = sx + T, y0 - T  # the curve's pivot: the NW corner of that tile, row -1
    spot = min(520, 0.3 * s.w)  # half-width of the lit stretch of bus around the tap

    def ry(r: int) -> float:
        return y0 + r * T

    with s.pattern(T, T) as floor:
        floor.stroke(P().M(0, 0).H(T).M(0, 0).V(T), mix(BG, BG_ALT, 0.8), 1)
    s.fill(P().rect(0, 0, s.w, s.h), floor.ref)

    # bus: the near group carries the tap, the far group recedes
    for rows, rail, lit, dim in (
        (FAR, mix(BG_ALT, UI, 0.6), MID, BG_ALT),
        (NEAR, UI_ALT, UI, MID),
    ):
        rails = P()
        with s.buckets(
            (lit, dim), "stroke", stroke_width=1.2, stroke_linecap="round", stroke_linejoin="round"
        ) as tread:
            for r in rows:
                yt = ry(r) + (T - BW) / 2
                for y in (yt, yt + BW):
                    rails.M(-20, y).H(s.w + 20)
                for k in range(math.ceil(s.w / T)):
                    x = (k + 0.5) * T
                    if r == 0 and sx < x < sx + T:  # the splitter's tile
                        continue
                    chev(tread[0 if abs(x - lx) < spot else 1], Vec(x + 2, yt + BW / 2), EAST)
        s.stroke(rails, rail, 1.5)

    # branch: the splitter's north output turns left in one tile, then runs north
    lane = P()
    for sgn in (-1, 1):
        rad = T / 2 + sgn * BW / 2
        lane.M(sx + T / 2 + 7, yb + rad).H(xb).A(rad, rad, 0, 0, 0, xb + rad, yb).V(ry(END_ROW))
    lane.M(lx - BW / 2, ry(END_ROW)).H(lx + BW / 2)
    arrows = P()
    y = yb - PITCH / 2
    while y > ry(END_ROW) + 6:
        chev(arrows, Vec(lx, y), NORTH, 3, 4)
        y -= PITCH

    # plates spread thinly along both lanes from the splitter to the belt end, none on the bend
    rng = s.rng(7)
    plates = P()
    straight = xb - (sx + T / 2 + 7)
    for sgn in (-1, 1):
        rr = T / 2 + sgn * 9  # the lane's radius round the bend
        bend = [polar((xb, yb), rr, deg=90 - 7.5 * k) for k in range(13)]
        path = Polyline([(sx + T / 2 + 7, yb + rr), *bend, (xb + rr, ry(END_ROW))])
        t = rng.uniform(4, 20)
        while t < path.length - 4:
            if not straight < t < straight + rr * math.pi / 2 + 1:
                p = path.at(t)
                plates.rect(p.x - 2.5, p.y - 2.5, 5, 5)
            t += rng.uniform(34, 70)

    # splitter: 1 tile along the flow, 2 across (rows -1, 0); only the row-0 input is fed, as in-game
    body = P()
    yt = ry(-1) + (T - BW) / 2
    for y in (yt, yt + BW):
        body.M(sx + 1, y).H(sx + T)
    for x in (sx + 8, sx + 30):
        for r in (-1, 0):
            chev(body, Vec(x, ry(r) + T / 2), EAST, 3, 4)
    s.stroke(body, UI_ALT, 1.5, cap="round", join="round")
    hx = sx + T / 2 - 7
    s.path(P().rrect(hx, ry(-1) + 2, 14, 2 * T - 4, 3), fill=BG, stroke=UI_HI, stroke_width=1.5)
    caps = P()
    for r in (-1, 0):
        caps.rect(hx + 3, ry(r) + T / 2 - 5, 8, 10)
    s.stroke(caps, UI_HI, 1)

    # assembler: 3x3 frame, inset body, corner bolts, the gear recipe as a small alt-mode overlay
    ax, ay, size = lx - 1.5 * T, ry(ASM_ROW), 3 * T
    bolts = P()
    for cx in (ax + 8, ax + size - 8):
        for cy in (ay + 8, ay + size - 8):
            bolts.rect(cx - 2.5, cy - 2.5, 5, 5)
    s.path(
        P().rect(ax + 2, ay + 2, size - 4, size - 4), fill=BG_DEEP, stroke=UI_ALT, stroke_width=1.5
    )
    s.path(
        P().rect(ax + 14, ay + 14, size - 28, size - 28), fill=BG, stroke=UI_HI, stroke_width=1.5
    )
    s.fill(bolts, UI_ALT)
    g = Vec(lx, ay + size / 2)
    s.path(P().circle(g, 19), fill=BG_DEEP, stroke=UI_ALT, stroke_width=1)
    teeth = [polar(g, r, deg=45 * i + 22.5 + da) for i in range(8) for da, r in TOOTH]
    s.stroke(P().poly(teeth, closed=True).circle(g, 4), UI_HI, 1.3, join="round")

    # inserter: base on its tile, arm straight north one tile, hand dropping just inside the machine
    iy = ry(INS_ROW) + T / 2
    hy = ry(INS_ROW) - T / 2 + 4
    hand = P()
    for sgn in (-1, 1):
        hand.M(lx + sgn * 5, hy - 5).L(lx + sgn * 5, hy + 1).L(lx + sgn * 2, hy + 3)

    s.stroke(lane, ACCENT, 2, join="round")
    s.stroke(arrows, ACCENT, 1.5, cap="round", join="round")
    s.fill(plates, ACCENT_2)
    s.path(
        P().rect(lx - 9, iy - 9, 18, 18),
        fill=BG,
        stroke=UI_HI,
        stroke_width=1.5,
        stroke_linejoin="round",
    )
    s.stroke(P().M(lx, iy).V(hy + 2), UI_HI, 2.5, cap="round")
    s.fill(P().circle((lx, iy), 3), UI_HI)
    s.stroke(hand, ACCENT, 2, cap="round", join="round")
