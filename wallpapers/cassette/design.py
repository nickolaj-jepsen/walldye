"""A Compact Cassette drafted in front, bottom and magnified detail views; only its tape is picked out."""

import math
from itertools import pairwise

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_4,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Path,
    Point,
    Vec,
    design,
    polar,
)
from walldye.geom import Affine

# The cassette is measured in mm about the centre of its front face; S scales it onto the sheet.
S = 7.5  # px per mm
CX, CY = 1180, 486  # front view centre
BY = 852  # bottom view centre line
WD, HT, THK = 100.4, 63.8, 8.7  # shell width, height and thickness
HUB_X, HUB_Y, HUB_R = 21.3, -3.0, 8.5
PACK_L, PACK_R = 20.5, 12.0  # outer radii of the supply and take-up packs
TURN = 0.42  # spacing of the drawn turns in a pack
ROLLER, ROLLER_R = Vec(42.4, 25.2), 2.3
PIN, PIN_R = Vec(32.4, 28.4), 1.1
SCREWS = ((-46, -28), (46, -28), (-47, 18), (47, 18), (0, 17))
OPENINGS = ((-19.5, -12.5), (-6.0, 6.0), (12.5, 19.5))  # windows in the bottom edge
DETAIL_C, DETAIL_R, DETAIL_K = Vec(-42.0, 27.0), 6.6, 3.1  # magnified region and its scale
DETAIL_AT = Vec(560, CY + DETAIL_C.y * S)  # level with the region, so the leader runs flat
TAPE_W = 3.81
DASHDOT = (22, 6, 3, 6)
ARROW, ARROW_W = 12, 3.8  # dimension arrowhead length and half-width

# The tape's route: supply pack, roller, pin, past the head, pin, roller, take-up pack. WANTS
# picks, for each span between two circles, the outer tangent whose normal points nearest it.
CHAIN = (
    (Vec(-HUB_X, HUB_Y), PACK_L),
    (Vec(-ROLLER.x, ROLLER.y), ROLLER_R),
    (Vec(-PIN.x, PIN.y), PIN_R),
    (PIN, PIN_R),
    (ROLLER, ROLLER_R),
    (Vec(HUB_X, HUB_Y), PACK_R),
)
WANTS = (math.pi, math.pi / 2, math.pi / 2, math.pi / 2, 0.0)


def tangent(a: Vec, ra: float, b: Vec, rb: float, want: float) -> float:
    """Normal angle (rad) of the outer tangent of circles `a` and `b` on the side nearest `want`."""
    th = math.atan2(b.y - a.y, b.x - a.x)
    k = math.acos((ra - rb) / abs(b - a))
    return min((th + k, th - k), key=lambda p: abs(math.remainder(p - want, 2 * math.pi)))


def tape(t: Affine, k: float) -> Path:
    """The tape from a quarter turn round the supply pack to a quarter turn onto the take-up
    pack, as tangent lines and arcs; `t` maps mm to the canvas at `k` px per mm."""
    phis = [tangent(a, ra, b, rb, w) for ((a, ra), (b, rb)), w in zip(pairwise(CHAIN), WANTS)]
    # the tape wraps every circle on the outside, so its normal angle only decreases
    spans = [(phis[0] + math.pi / 2, phis[0])]
    spans += [(p0, p0 - (p0 - p1) % (2 * math.pi)) for p0, p1 in pairwise(phis)]
    spans.append((phis[-1], phis[-1] - math.pi / 2))
    d = P()
    for (c, r), (a0, a1) in zip(CHAIN, spans):
        start = t(polar(c, r, rad=a0))
        d.M(start) if d.empty else d.L(start)
        d.A(r * k, r * k, 0, a0 - a1 > math.pi, False, t(polar(c, r, rad=a1)))
    return d


def front(s: Canvas, t: Affine, k: float) -> None:
    """The front view; `t` maps mm to the canvas at `k` px per mm, so line weights stay put."""

    def rbox(d: Path, a: Point, b: Point, r: float) -> None:
        p, q = t(a), t(b)
        d.rrect(p.x, p.y, q.x - p.x, q.y - p.y, r * k)

    shell = P()
    rbox(shell, (-WD / 2, -HT / 2), (WD / 2, HT / 2), 3)
    # head-area bridge and the openings in the bottom edge
    shell.M(t((-37.5, HT / 2))).L(t((-31, 21.5))).L(t((31, 21.5))).L(t((37.5, HT / 2)))
    for a, b in OPENINGS:
        shell.M(t((a, HT / 2))).L(t((a, HT / 2 - 3.6))).L(t((b, HT / 2 - 3.6))).L(t((b, HT / 2)))
    s.stroke(shell, UI_HI, 1.6, join="round")

    detail = P()
    rbox(detail, (-45, -27.5), (45, 14.5), 2)  # label recess
    rbox(detail, (-30, -11.5), (30, 5.5), 2.2)  # window
    for sx in (-1, 1):  # write-protect tabs
        a, b = sorted((sx * 38, sx * 44))
        detail.M(t((a, -HT / 2))).L(t((a, -HT / 2 + 3))).L(t((b, -HT / 2 + 3))).L(t((b, -HT / 2)))
    for c in SCREWS:
        detail.circle(t(c), 1.7 * k)
    for sx in (-1, 1):
        roller, pin = t((sx * ROLLER.x, ROLLER.y)), t((sx * PIN.x, PIN.y))
        detail.circle(roller, ROLLER_R * k)
        detail.circle(roller, 0.8 * k)
        detail.circle(pin, PIN_R * k)
    rbox(detail, (-3.2, HT / 2 - 5.6), (3.2, HT / 2 - 4.2), 0.3)  # pressure pad
    s.stroke(detail, UI_ALT, 1.3, join="round")

    rules = P()
    for i in range(4):
        rules.M(t((-40, -23.5 + i * 3.4))).L(t((40, -23.5 + i * 3.4)))
    s.stroke(rules, BG_ALT, 1.2)

    # wound packs, drawn as if the shell were clear: they cover the label lines
    discs, turns, edge, hub, teeth = P(), P(), P(), P(), P()
    for sx, pack, spin in ((-1, PACK_L, 0.26), (1, PACK_R, 0.7)):
        c = t((sx * HUB_X, HUB_Y))
        discs.circle(c, pack * k)
        edge.circle(c, pack * k)
        for r in np.arange(HUB_R + 0.6, pack - 0.3, TURN):
            turns.circle(c, r * k)
        hub.circle(c, HUB_R * k)
        hub.circle(c, 6.2 * k)
        for i in range(6):
            a = spin + i * math.pi / 3
            teeth.M(polar(c, 6.2 * k, rad=a)).L(polar(c, 4.6 * k, rad=a))
    s.fill(discs, BG)
    s.stroke(turns, ACCENT_7, 1)
    s.stroke(edge, ACCENT_5, 1.4)
    s.stroke(hub, UI_ALT, 1.3)
    s.stroke(teeth, UI_ALT, 2.4, cap="round")

    s.stroke(tape(t, k), ACCENT, 2.4, cap="round", join="round")


def dim(lines: Path, heads: Path, a: Vec, b: Vec) -> None:
    """A dimension line from `a` to `b` with an arrowhead at each end, pointing outwards."""
    lines.M(a).L(b)
    ang = math.atan2(b.y - a.y, b.x - a.x)
    heads.arrowhead(b, ARROW, rad=ang, width=ARROW_W)
    heads.arrowhead(a, ARROW, rad=ang + math.pi, width=ARROW_W)


@design()
def draw(s: Canvas) -> None:
    t = Affine.frame((CX, CY), deg=0, scale=S)
    x0, y0 = t((-WD / 2, -HT / 2))
    x1, y1 = t((WD / 2, HT / 2))
    front(s, t, S)

    # bottom view: the edge with the head openings, tape seen face-on inside them
    bt, bb = BY - THK / 2 * S, BY + THK / 2 * S
    bottom, band, edges = P(), P(), P()
    bottom.rrect(x0, bt, x1 - x0, bb - bt, 1.2 * S)
    for a, b in OPENINGS:
        xa, xb = t((a, 0)).x, t((b, 0)).x
        bottom.rect(xa, bt + 1.2 * S, xb - xa, bb - bt - 2.4 * S)
        band.rect(xa, BY - TAPE_W / 2 * S, xb - xa, TAPE_W * S)
        for e in (-1, 1):
            edges.M(xa, BY + e * TAPE_W / 2 * S).H(xb)
    for sx in (-1, 1):
        bottom.M(t((sx * 37.5, 0)).x, bt).V(bb)
    s.stroke(bottom, UI_HI, 1.5, join="round")

    cl, proj = P(), P()
    cl.M(x0 - 34, CY + HUB_Y * S).H(x1 + 34)
    for sx in (-1, 1):
        hx = t((sx * HUB_X, 0)).x
        cl.M(hx, CY + (HUB_Y - PACK_L) * S - 18).V(CY + (HUB_Y + PACK_L) * S + 18)
    cl.M(CX, y0 - 30).V(bb + 30)
    cl.M(x0 - 34, BY).H(x1 + 34)
    s.stroke(cl, UI, 1.2, dash=DASHDOT)
    for a, b in OPENINGS:
        for x in (a, b):
            proj.M(t((x, 0)).x, y1 + 10).V(bt - 10)
    s.stroke(proj, BG_ALT, 1.2)
    s.fill(band, ACCENT_5)
    # the ribbon's edges run on as hidden lines behind the shell, pin to pin
    hidden = P()
    for e in (-1, 1):
        hidden.M(t((-PIN.x, 0)).x, BY + e * TAPE_W / 2 * S).H(t((PIN.x, 0)).x)
    s.stroke(hidden, ACCENT_6, 1.2, dash=(8, 5))
    s.stroke(edges, ACCENT_4, 1.3)

    # dimensions: overall width above, height and thickness to the right
    ext, dl, heads = P(), P(), P()
    yd = y0 - 68
    for x in (x0, x1):
        ext.M(x, y0 - 10).V(yd - 12)
    dim(dl, heads, Vec(x0, yd), Vec(x1, yd))
    xd = x1 + 64
    for y in (y0, y1, bt, bb):
        ext.M(x1 + 10, y).H(xd + 12)
    dim(dl, heads, Vec(xd, y0), Vec(xd, y1))
    dl.M(xd, bt - 44).V(bt).M(xd, bb).V(bb + 44)
    heads.arrowhead((xd, bt), ARROW, deg=90, width=ARROW_W)
    heads.arrowhead((xd, bb), ARROW, deg=-90, width=ARROW_W)

    # detail view: the tape turning the corner roller, magnified off to the left
    dr = DETAIL_R * S * DETAIL_K
    zoom = Affine.frame(DETAIL_AT, deg=0, scale=S * DETAIL_K) @ Affine.translate(
        -DETAIL_C.x, -DETAIL_C.y
    )
    with s.clip() as lens:
        lens.add(P().circle(DETAIL_AT, dr))
    with s.group(clip_path=lens.ref):
        front(s, zoom, S * DETAIL_K)
    src = t(DETAIL_C)
    rings = P().circle(src, DETAIL_R * S)
    s.stroke(rings.circle(DETAIL_AT, dr), UI_ALT, 1.3, dash=(10, 6))
    # leader between the two circles, rim to rim
    u = (DETAIL_AT - src).unit()
    dl.M(src + u * (DETAIL_R * S + 6)).L(DETAIL_AT - u * (dr + 6))

    s.stroke(ext, UI, 1.2)
    s.stroke(dl, UI_ALT, 1.2)
    s.fill(heads, UI_ALT)
