"""A two-figure patent sheet of Radahn's starfall: the greatsword's gravity crest as barbed field lines, and a terraced crater section under the star's dashed path."""

import itertools
import math
from collections.abc import Sequence

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_3,
    ACCENT_4,
    BG,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    Num,
    P,
    Path,
    Point,
    Rng,
    Vec,
    clamp,
    design,
    polar,
    smoothstep,
)
from walldye.geom import Affine, bezier_points
from walldye.pixel import glyphs

# fig. 1: the Starscourge Greatsword, its blade an even 34-degree bend widening to a clipped tip
S0 = Vec(350, 770)  # blade root at the guard
TH0, TH1 = -55, -89  # heading at the root and at the tip, degrees
LEN = 680
K = math.radians(TH1 - TH0) / LEN  # curvature: heading change per unit of length
CLIP = 175  # run of the curved clip from the edge corner to the point
HILT = 250
NUC = 0.42  # the crest's nucleus, as a fraction of the blade's length
# guard outline and quillon in blade (s, v), clockwise on screen
GUARD = (
    (-48, 10),
    (-40, -58),
    (-14, -70),
    (22, -56),
    (26, 16),
    (58, 32),
    (70, 70),
    (40, 106),
    (-6, 120),
    (-44, 98),
)
QUILLON = ((-14, -94), (14, -112), (36, -102), (22, -80), (-6, -68))
# scrolls on the guard: s, v, radius, start angle (rad), turn direction
SCROLLS = (
    (6, 86, 18, 0.4, 1),
    (44, 54, 14, 2.0, -1),
    (-26, 74, 12, 3.5, 1),
    (22, 28, 9, 5.0, 1),
    (-20, 26, 11, 1.2, -1),
    (-26, -24, 9, 3.0, 1),
    (0, -52, 8, 4.5, -1),
    (14, -94, 8, 0.8, -1),
)
# grip sections from the guard to the pommel: start, end, half-width
GRIP = (
    (0, 16, 20),
    (16, 96, 15),
    (96, 104, 19),
    (104, 112, 21),
    (112, 120, 19),
    (120, 196, 15),
    (196, 210, 20),
    (210, 226, 17),
    (226, 238, 13),
    (238, HILT - 4, 9),
)
TANG = 46  # bare tang between the blade's root and the grip

# fig. 2: a section through Starfall Crater; west (Limgrave) left, east (Caelid) right
G = 590  # ground line
DS = 1.3  # depth scale of the section
# terraced bowl as (x, depth) knots from rim to floor; ledges alternate with short rock drops
WEST = [
    (x, d * DS)
    for x, d in (
        (860, 0),
        (905, 6),
        (930, 34),
        (985, 44),
        (1000, 88),
        (1060, 98),
        (1078, 150),
        (1122, 160),
        (1140, 214),
        (1170, 228),
    )
]
FLOOR = [(x, d * DS) for x, d in ((1170, 228), (1215, 232), (1262, 226), (1310, 234), (1350, 228))]
EAST = [
    (x, d * DS)
    for x, d in (
        (1350, 228),
        (1372, 196),
        (1418, 188),
        (1432, 132),
        (1488, 120),
        (1506, 70),
        (1560, 60),
        (1578, 26),
        (1632, 18),
        (1668, 0),
    )
]
FLOOR_D = 228 * DS
# rubble held up over the bowl: x, height in section units (650 is the ground), size
RUBBLE = (
    (1150, 730, 13),
    (1196, 690, 9),
    (1232, 760, 15),
    (1300, 700, 10),
    (1180, 800, 11),
    (1240, 836, 8),
    (1330, 780, 12),
    (1120, 850, 7),
    (1290, 832, 7),
    (1212, 724, 6),
    (1352, 730, 8),
)
# the star's path: a power curve from high in the east that steepens down onto the bowl floor
START = Vec(1850, 90)
IMPACT = Vec(1256, G + round(226 * DS))
KT = (IMPACT.y - START.y) / (START.x - IMPACT.x) ** 1.7
STAR_X, SR = 1520, 9  # the star's place on its path, and its radius
# tail streaks: offset across the path, splay, length, index into TAIL
STREAKS = (
    (0, 0, 136, 0),
    (-3, -0.025, 98, 1),
    (3, 0.025, 92, 1),
    (-6, -0.05, 58, 2),
    (6, 0.05, 50, 3),
)
TAIL = (ACCENT_1, ACCENT_2, ACCENT_3, ACCENT_4)


def half_width(s: Num) -> float:
    return 62 + 38 * clamp(s / LEN)


def tangent(s: Num) -> Vec:
    """Unit direction of the blade's centreline at `s`, held at the end values past either end."""
    a = math.radians(TH0) + K * clamp(s, 0, LEN)
    return Vec(math.cos(a), math.sin(a))


def blade(s: Num, v: Num = 0.0) -> Vec:
    """The canvas point at arc length `s` along the centreline from the guard and `v` across it:
    positive on the concave spine side, negative on the convex cutting edge. The centreline is a
    circular arc that runs straight on past either end."""
    sc = clamp(s, 0, LEN)
    a0, a = math.radians(TH0), math.radians(TH0) + K * sc
    t = tangent(s)
    on = S0 + Vec(math.sin(a) - math.sin(a0), math.cos(a0) - math.cos(a)) / K
    return on + t * (s - sc) - t.perp() * v


def blade_pts(sv: Sequence[Point]) -> list[Vec]:
    return [blade(s, v) for s, v in sv]


def crest(q: Point) -> Vec:
    """The canvas point for crest coordinates `q`: along the blade from the nucleus, and across
    it from a line set a little toward the spine."""
    s0 = LEN * NUC
    return blade(s0 + q[0], 0.2 * half_width(s0) + q[1])


def outline(inset: float = 0.0) -> tuple[list[Point], list[Point]]:
    """The cutting edge and the spine as (s, v) runs from the guard, `inset` inside the blade's
    outline. The spine runs straight to the point; the edge sweeps up into it in a curved clip."""

    def spine_v(s: float) -> float:
        return half_width(s) * (1 - 0.16 * smoothstep(LEN - 160, LEN, s)) - inset

    spine: list[Point] = [(s, spine_v(s)) for s in np.linspace(0, LEN - inset * 1.4, 90).tolist()]
    e0 = LEN - CLIP
    edge: list[Point] = [(s, inset - half_width(s)) for s in np.linspace(0, e0, 70).tolist()]
    ctrl = [
        (e0, inset - half_width(e0)),
        (LEN - 0.2 * CLIP, inset - half_width(LEN) * 1.02),
        (LEN - inset * 1.4, spine_v(LEN)),
    ]
    edge += [(s, v) for s, v in bezier_points(ctrl, 39)[1:].tolist()]
    return edge, spine


def lobes(d: Path, pts: list[Vec], size: float, bulge: float = 1.15) -> None:
    """A cloud outline: runs of outward arcs about `size` long round the closed polygon `pts`
    (clockwise on screen)."""
    d.M(pts[0])
    for a, b in itertools.pairwise([*pts, pts[0]]):
        n = max(1, round(abs(b - a) / size))
        rr = abs(b - a) / n / 2 * bulge
        for i in range(1, n + 1):
            d.A(rr, rr, 0, 0, 0, a + (b - a) * (i / n))
    d.Z()


def spiral(d: Path, c: Vec, r0: float, a0: float, sgn: int, turns: float = 1.6) -> None:
    n = int(turns * 14)
    d.poly([polar(c, r0 * (1 - k / (n + 3)), rad=a0 + sgn * k * math.tau / 14) for k in range(n)])


def label(s: Canvas, text: str, at: Point, paint: Colour = MUTED) -> None:
    glyphs(s, text, paint, at=(round(at[0]), round(at[1])), font="5x8", px=2)


def draw_sword(s: Canvas) -> None:
    edge, spine = outline()
    body = P().poly(blade_pts(edge) + blade_pts(spine[::-1]), closed=True)
    e2, s2 = outline(14)
    bevel = P().poly(blade_pts([q for q in e2 if q[0] > 30]))
    bevel.poly(blade_pts([q for q in s2 if 30 < q[0] < LEN - 60]))
    s.stroke(bevel, UI, 1)
    s.stroke(body, UI_HI, 1.5, join="round")

    # hilt, drawn along the grip away from the blade: banded collars and a stepped pommel cap
    hilt, lozenges = P(), P()
    for d0, d1, w in GRIP:
        hilt.rect(d0, -w, d1 - d0, 2 * w)
    hilt.M(HILT - 4, 9).Q(HILT + 8, 0, HILT - 4, -9)
    for c in (38, 74, 142, 176):
        lozenges.poly([(c - 12, 0), (c, 9), (c + 12, 0), (c, -9)], closed=True)
    with s.group(transform=Affine.frame(blade(-TANG), deg=TH0 + 180)):
        s.stroke(hilt, UI_HI, 1.3, join="round")
        s.stroke(lozenges, UI_ALT, 1.2, cap="round")

    # guard: an uneven knot of cloud scrolls, heavy over the spine and lapping onto the blade,
    # with a small quillon on the edge side
    guard, scrolls = P(), P()
    lobes(guard, blade_pts(GUARD), 20)
    lobes(guard, blade_pts(QUILLON), 13)
    for u, v, r0, a0, sgn in SCROLLS:
        spiral(scrolls, blade(u, v), r0, a0, sgn)
    s.path(guard, fill=BG, stroke=UI_HI, stroke_width=1.3, stroke_linejoin="round")
    s.stroke(scrolls, UI_ALT, 1.2, cap="round")


def draw_crest(s: Canvas, r: Rng) -> None:
    """The gravity crest in crest coordinates, clipped to the blade: dipole loops round the
    nucleus, spikes off their flanks and a web fanning from each pole, every line barbed."""
    lines, barbs = P(), P()

    def barbed(pts: list[Vec], every: float = 12, ln: float = 4.5, jit: float = 0.0) -> None:
        if jit:
            pts = [q + Vec(r.uniform(-jit, jit), r.uniform(-jit, jit)) for q in pts]
        lines.poly([crest(q) for q in pts])
        run = 0.0
        for q0, q1 in itertools.pairwise(pts):
            run += abs(q1 - q0)
            if run >= every * r.uniform(0.7, 1.4):
                run = 0.0
                barb = (q1 - q0).unit().rotate(rad=0.9 * r.choice((-1, 1)))
                barbs.M(crest(q1)).L(crest(q1 + barb * ln))

    hw = half_width(LEN * NUC) - 18
    # dipole field loops, r = k sin^2(theta) about the blade axis, stretched along it
    for k in (np.linspace(0.3, 1.0, 6) * hw).tolist():
        for side in (1, -1):
            loop: list[Vec] = []
            for th in np.linspace(0.1, math.pi - 0.1, 50).tolist():
                rr = k * math.sin(th) ** 2
                q = Vec(2.4 * rr * math.cos(th), side * rr * math.sin(th))
                if math.hypot(q.x / 1.6, q.y) > 13:
                    loop.append(q)
            barbed(loop, jit=0.8)
    # spikes flaring off the loops' flanks
    for side in (1, -1):
        for th in np.linspace(0.5, math.pi - 0.5, 6).tolist():
            th += r.uniform(-0.1, 0.1)
            d0 = hw * 0.62 * math.sin(th) ** 2 + 6
            d1 = d0 + r.uniform(12, 26)
            ray = Vec(2.4 * math.cos(th), side * math.sin(th))
            barbed([ray * d for d in np.linspace(d0, d1, 4).tolist()], every=8)
    # end webs: uneven fans from each pole crossed by broken, wobbling arcs; the tip side's is larger
    for sgn, length in ((1, 250), (-1, 200)):
        pole = Vec(sgn * 22, 0)
        for a in np.linspace(-0.6, 0.6, 8).tolist():
            a += r.uniform(-0.07, 0.07)
            ln = length * r.uniform(0.72, 1.0)
            bend = r.uniform(-0.07, 0.07)
            fan = [
                pole + Vec(sgn * d * math.cos(a + bend * d / ln), d * math.sin(a + bend * d / ln))
                for d in np.linspace(55, ln, 22).tolist()
            ]
            barbed(fan, every=13, jit=0.7)
        for f in (0.55, 0.76, 0.95):
            radius = length * f * r.uniform(0.95, 1.03)
            a = -0.7
            while a < 0.7:
                a1 = min(0.7, a + r.uniform(0.5, 1.1))
                arc = [
                    pole
                    + Vec(
                        sgn * (radius + r.uniform(-1.5, 1.5)) * math.cos(t),
                        (radius + r.uniform(-1.5, 1.5)) * math.sin(t),
                    )
                    for t in np.linspace(a, a1, 7).tolist()
                ]
                barbed(arc, every=16, ln=3.5)
                a = a1 + r.uniform(0.04, 0.12)

    edge, spine = outline(20)
    with s.clip() as inside:
        inside.add(P().poly(blade_pts(edge) + blade_pts(spine[::-1]), closed=True))
    with s.group(clip_path=inside.ref):
        s.stroke(lines, MUTED, 1.1, cap="round", join="round")
        s.stroke(barbs, UI_HI, 1, cap="round")
    nucleus = P()
    for rr in (3.5, 7, 10.5):
        nucleus.circle(crest((0, 0)), rr)
    s.stroke(nucleus, MUTED, 1.1)


def jag(r: Rng, pts: Sequence[tuple[float, float]], amp: float, step: float) -> list[Vec]:
    """A broken-rock line through `pts`: each leg cut into pieces about `step` long whose joints
    are jittered by up to `amp`."""
    out: list[Vec] = []
    for p0, p1 in itertools.pairwise([Vec(p[0], p[1]) for p in pts]):
        n = max(1, int(abs(p1 - p0) / step))
        for i in range(n):
            out.append(p0 + (p1 - p0) * (i / n) + Vec(r.uniform(-amp, amp), r.uniform(-amp, amp)))
    out.append(Vec(pts[-1][0], pts[-1][1]))
    return out


def fall_y(x: float) -> float:
    return START.y + KT * (START.x - x) ** 1.7


def fall_x(y: float) -> float:
    return START.x - ((y - START.y) / KT) ** (1 / 1.7)


def draw_crater(s: Canvas, r: Rng) -> None:
    rock, strata, rubble, fall = P(), P(), P(), P()
    bowl = jag(r, [(x, G + d) for x, d in WEST + FLOOR[1:] + EAST[1:]], 2.0, 11)
    west = jag(r, [(700, G), (860, G)], 1.6, 12)
    east = jag(r, [(1668, G), (1820, G)], 1.6, 12)
    rock.poly(west[:-1] + bowl + east[1:])
    for x in (700, 1820):
        rock.M(x - 6, G + 10).L(x + 6, G - 10)  # break marks at the section's ends
    # a short shadow line under each terrace
    for (xa, da), (xb, db) in itertools.pairwise(WEST + EAST):
        if abs(db - da) < 16 and abs(xb - xa) > 30:
            y = G + max(da, db) + 9
            strata.M(xa + 6, y).L(xb - 6, y + r.uniform(-1, 1))

    # bedding: broken level runs in the rock, cut by the bowl
    wx, wd = zip(*WEST, strict=True)
    ex, ed = zip(*EAST[::-1], strict=True)
    for d in (46, 100, 160, 222, 280, 334):
        spans: tuple[tuple[float, float], ...] = ((780, 1740),)
        if d < FLOOR_D:
            spans = ((740, np.interp(d, wd, wx) - 16), (np.interp(d, ed, ex) + 16, 1780))
        for x0, x1 in spans:
            x = x0 + r.uniform(0, 24)
            while x < x1 - 20:
                xe = min(x + r.uniform(40, 120), x1 - 4)
                y = G + d + r.uniform(-2, 2)
                strata.M(x, y).L(xe, y + r.uniform(-1.5, 1.5))
                x = xe + r.uniform(14, 40)

    # a waterfall down the west terraces, just clear of each rock drop
    for (xa, da), (xb, db) in list(itertools.pairwise(WEST))[3:8]:
        if db - da > 30:
            for off in (7, 13):
                fall.M(xa + off, G + da + 2).L(xb + off, G + db - 3)

    # rubble held up in the air over the bowl, kept off the star's path
    extra = [(r.uniform(1110, 1390), r.uniform(670, 850), r.uniform(2.2, 3.8)) for _ in range(18)]
    rocks: list[tuple[float, float, float]] = [*RUBBLE, *extra]
    for bx, h, sz in rocks:
        by = G + (h - 650) * DS
        if abs(bx - fall_x(by)) < sz + 10:
            continue
        n = r.randint(5, 7)
        a0 = r.uniform(0, math.tau)
        stone = [
            (
                bx + sz * r.uniform(0.6, 1.1) * math.cos(a0 + math.tau * i / n),
                by + sz * r.uniform(0.6, 1.1) * math.sin(a0 + math.tau * i / n),
            )
            for i in range(n)
        ]
        rubble.poly(stone, closed=True)

    s.stroke(strata, UI, 1)
    s.stroke(fall, UI_ALT, 1.2, dash=(6, 4))
    s.stroke(rock, UI_HI, 1.5, join="round")
    s.stroke(rubble, UI_HI, 1.2, join="round")
    label(s, "W", (695, G + 22), UI_HI)
    label(s, "E", (1815, G + 22), UI_HI)


@design()
def draw(s: Canvas) -> None:
    r = s.rng(7)
    draw_sword(s)
    draw_crest(s, r)
    draw_crater(s, r)

    star = Vec(STAR_X, fall_y(STAR_X))
    t = Vec(-1, 1.7 * KT * (START.x - STAR_X) ** 0.7).unit()  # direction of travel
    n = t.perp()
    # the dashed path, broken round the star and its tail and stopping short of the floor
    path = [Vec(x, fall_y(x)) for x in np.linspace(START.x, IMPACT.x, 900).tolist()]
    pre = [p for p in path if p.x > STAR_X and abs(p - star) > 158]
    post = [p for p in path if p.x < STAR_X and abs(p - star) > SR + 6 and p.y < IMPACT.y - 12]
    trail = P().poly([*pre[::6], pre[-1]]).poly([post[0], *post[6::6], post[-1]])
    s.stroke(trail, UI_HI, 1.2, dash=(10, 6))
    impact = P().M(IMPACT + (-12, -3)).L(IMPACT + (-4, -9)).M(IMPACT + (12, -3))
    impact.L(IMPACT + (4, -9)).M(IMPACT + (0, -6)).L(IMPACT + (0, -16))
    s.stroke(impact, ACCENT_3, 1.4, cap="round")

    with s.buckets(TAIL, "stroke", stroke_width=1.3, stroke_linecap="round") as tail:
        for off, splay, ln, tone in STREAKS:
            root = star - t * (SR + 4) + n * off
            tail[tone].M(root).L(root + (n * splay - t).unit() * ln)
    s.fill(P().circle(star, SR), ACCENT)

    # leaders from each numbered part to its numeral
    hw = half_width(LEN * NUC) - 18
    marks = (
        (crest((0, -12)), blade(LEN * NUC - 30, -155), "1"),  # the nucleus
        (crest(Vec(-0.35, -0.26) * hw), blade(LEN * NUC - 150, 170), "2"),  # a field loop
        (crest((212, 0)), blade(LEN * NUC + 230, -200), "3"),  # the tip-side web
        (blade(-20, half_width(0) + 56), blade(-60, 200), "4"),  # the guard
        (star + Vec(1, 1) * (0.7 * (SR + 8)), star + (80, 60), "5"),  # the star
        (Vec(1244, G + 110 * DS - 12), Vec(1480, G - 80), "6"),  # the held rubble
        (Vec(1060, G + 97 * DS), Vec(960, G - 90), "7"),  # the waterfall
    )
    heads, lead = P(), P()
    for p, at, num in marks:
        lead.M(p).Q((p + at) / 2 - (at - p).perp() * 0.12, at)
        heads.circle(p, 2.2)
        label(s, num, at + ((4 if at.x >= p.x else -14), -8))
    s.stroke(lead, UI_ALT, 1)
    s.fill(heads, UI_HI)
    label(s, "FIG. 1", (640, 930), UI_HI)
    label(s, "FIG. 2", (1600, 960), UI_HI)

    reg, mg, arm = P(), 40, 18
    for x, y, dx, dy in (
        (mg, mg, 1, 1),
        (s.w - mg, mg, -1, 1),
        (mg, s.h - mg, 1, -1),
        (s.w - mg, s.h - mg, -1, -1),
    ):
        reg.M(x + dx * arm, y).H(x).V(y + dy * arm)
    s.stroke(reg, UI, 1.2)
