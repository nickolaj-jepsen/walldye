"""A patent sheet of the Quake rocket jump: the player's hull rides its own rocket's splash onto a ledge, the flight computed from the game's physics."""

import math
from typing import Literal

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_4,
    BG,
    BG_ALT,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Paint,
    Path,
    Point,
    Vec,
    design,
    polar,
)
from walldye.geom import Affine
from walldye.pixel import glyphs, text_width

# Physics follow the v1.01 QuakeC and engine: W_FireRocket, T_MissileTouch, T_RadiusDamage,
# T_Damage knockback, PlayerJump and sv_gravity. Game units with z up, speeds in units/s.
RUN = 320  # sv_maxspeed
JUMP = 270  # PlayerJump: velocity_z += 270
GRAV = 800  # sv_gravity
ROCKET = 1000  # W_FireRocket speed
PITCH = 80  # degrees below level: cl_input clamps looking down at 80
SPLASH = 120  # T_RadiusDamage(self, owner, 120, other)
RADIUS = SPLASH + 40  # findradius(damage + 40)
ORG = 24  # VEC_HULL_MIN z = -24: the origin sits above the feet
LEDGE_H = 220

# the rocket spawns at origin + v_forward * 8 + '0 0 16' on the jump frame
_CA, _SA = math.cos(math.radians(PITCH)), math.sin(math.radians(PITCH))
SPAWN = Vec(8 * _CA, ORG - 8 * _SA + 16)
T_HIT = SPAWN.y / (ROCKET * _SA)
BLAST = Vec(SPAWN.x + ROCKET * _CA * T_HIT, 0)
P_HIT = Vec(RUN * T_HIT, ORG + JUMP * T_HIT - GRAV / 2 * T_HIT**2)
V_PRE = Vec(RUN, JUMP - GRAV * T_HIT)
# damage is measured to the hull centre (origin + 4), knockback points away from the origin
POINTS = (SPLASH - 0.5 * abs(P_HIT + (0, 4) - BLAST)) * 0.5  # the shooter takes half
KICK = (P_HIT - BLAST) * (POINTS * 8 / abs(P_HIT - BLAST))  # T_Damage: dir * damage * 8
V = V_PRE + KICK
T_APEX = T_HIT + V.y / GRAV
# landing: the feet reach the ledge top on the way down
_a, _b, _c = GRAV / 2, -V.y, LEDGE_H - (P_HIT.y - ORG)
T_END = T_HIT + (-_b + math.sqrt(_b * _b - 4 * _a * _c)) / (2 * _a)


def origin(t: float) -> Vec:
    """The player's origin `t` seconds after the jump, in game units."""
    if t <= T_HIT:
        return Vec(RUN * t, ORG + JUMP * t - GRAV / 2 * t * t)
    t -= T_HIT
    return Vec(P_HIT.x + V.x * t, P_HIT.y + V.y * t - GRAV / 2 * t * t)


def velocity(t: float) -> Vec:
    """The derivative of `origin` at `t`."""
    if t <= T_HIT:
        return Vec(RUN, JUMP - GRAV * t)
    return Vec(V.x, V.y - GRAV * (t - T_HIT))


LAND_X = origin(T_END).x
LIP = math.floor(LAND_X - 56)  # the ledge edge sits well behind the landing spot
# the hull's leading edge must clear the lip with its feet above the ledge
assert origin(T_HIT + (LIP - 16 - P_HIT.x) / V.x).y - ORG > LEDGE_H

# --- sheet layout, in canvas units ---
U = 2  # canvas units per game unit
FLOOR = 805
X0 = 560  # the start origin's x
HW, HH = 16 * U, 56 * U  # hull half-width and height
LEDGE = FLOOR - LEDGE_H * U
LX0, LX1 = X0 + LIP * U, X0 + LIP * U + 320
FL0 = 200
HATCH = 18
# arrowheads: their flank length times these gives the head's length and half-width
_HEAD_L, _HEAD_W = math.cos(0.38), math.sin(0.38)
type Anchor = Literal["start", "middle", "end"]


def sheet(p: tuple[float, float]) -> Vec:
    """Canvas position of the game point `p` (x along the run, z up)."""
    return Vec(X0 + p[0] * U, FLOOR - p[1] * U)


def arrow(d: Path, tip: Point, deg: float, size: float = 9) -> Path:
    """Adds a dimension arrowhead with flanks `size` long, pointing along `deg`."""
    return d.arrowhead(tip, size * _HEAD_L, deg=deg, width=size * _HEAD_W)


def label(s: Canvas, text: str, at: Point, anchor: Anchor = "middle", paint: Paint = MUTED) -> None:
    """Spleen 5x8 at 2 units on a knocked-out box; `at` is on the text's vertical centre."""
    w = text_width(text, font="5x8", px=2)
    x = round(at[0] - {"start": 0, "middle": w / 2, "end": w}[anchor])
    y = round(at[1] - 8)
    s.fill(P().rect(x - 4, y - 3, w + 6, 21), BG)
    glyphs(s, [text], paint, at=(x, y), font="5x8", px=2)


def vector(s: Canvas, a: Vec, b: Vec, paint: Paint, width: float, head: float = 10) -> None:
    """An arrow from `a` to `b` whose shaft stops inside the head."""
    u = (b - a).unit()
    s.stroke(P().M(a).L(b - u * (head * 0.6)), paint, width)
    s.fill(arrow(P(), b, math.degrees(math.atan2(u.y, u.x)), head), paint)


@design()
def draw(s: Canvas) -> None:
    s.stroke(P().rect(*s.inset(60)), BG_ALT, 1.5)

    with s.pattern(12, 12, transform=Affine.rotate(deg=45)) as hatch:
        hatch.stroke(P().M(0, 0).V(12), UI, 1.2)
    cut = P().rect(FL0, FLOOR, LX1 - FL0, HATCH).rect(LX0, LEDGE, LX1 - LX0, FLOOR - LEDGE)
    s.fill(cut, hatch.ref)

    # break lines where the floor and the ledge are cut off
    ym = (LEDGE + FLOOR + HATCH) / 2
    brk = P().poly(
        [(FL0, FLOOR - 6), (FL0, FLOOR + 4), (FL0 - 5, FLOOR + 9), (FL0 + 5, FLOOR + 14)]
        + [(FL0, FLOOR + 18), (FL0, FLOOR + 26)]
    )
    brk.M(LX1, LEDGE - 6).V(ym - 10).L(LX1 - 6, ym - 4).L(LX1 + 6, ym + 4).L(LX1, ym + 10)
    brk.V(FLOOR + HATCH + 6)
    s.stroke(brk, UI_ALT, 1)

    # the event: splash radius and falloff (120 - 0.5 * d, halved for the shooter)
    b = sheet(BLAST)
    for r, paint, w in ((40, ACCENT, 2), (80, ACCENT_2, 1.5), (RADIUS, ACCENT_4, 1.25)):
        s.stroke(P().arc(b, r * U, deg=(180, 360)), paint, w)
    s.stroke(P().M(FL0, FLOOR).H(LX0).V(LEDGE).H(LX1), UI_HI, 2, join="miter")

    # the path of the player's origin, ticked every 0.1 s
    n = 120
    flight = [sheet(origin(T_END * i / n)) for i in range(n + 1)]
    s.stroke(P().spline(flight), UI_ALT, 1, dash=(6, 6))
    ticks = P()
    for k in range(1, math.ceil(T_END / 0.1)):
        p, v = sheet(origin(k * 0.1)), velocity(k * 0.1)
        side = Vec(v.x, -v.y).unit().perp() * 5
        ticks.M(p - side).L(p + side)
    s.stroke(ticks, UI_ALT, 1.25)

    # ghosted keyframe hulls, the one at the apex dashed
    hulls, apex_hull, cross = P(), P(), P()
    for t in (0.3, T_APEX * 0.7, T_APEX, T_END):
        o = sheet(origin(t))
        (apex_hull if t == T_APEX else hulls).rect(o.x - HW, o.y - HH + ORG * U, 2 * HW, HH)
        cross.M(o.x - 5, o.y).H(o.x + 5).M(o.x, o.y - 5).V(o.y + 5)
    s.stroke(hulls, UI_ALT, 1.25)
    s.stroke(apex_hull, UI_ALT, 1.25, dash=(5, 4))
    s.stroke(cross, UI, 1)

    # splash radius leader up and to the left, passing behind the start hull
    r_end = polar(b, RADIUS * U, deg=-158)
    s.stroke(P().M(b).L(polar(b, RADIUS * U - 3, deg=-158)), UI_ALT, 1)

    # the start hull, standing at t = 0; its fill hides the floor-level rings behind it
    s.path(P().rect(X0 - HW, FLOOR - HH, 2 * HW, HH), fill=BG, stroke=UI_HI, stroke_width=1.5)
    o = sheet((0, ORG))
    s.stroke(P().M(o.x - 6, o.y).H(o.x + 6).M(o.x, o.y - 6).V(o.y + 6), UI_ALT, 1)

    # the player's own rocket, spawned inside the hull and fired 80 degrees down at the floor;
    # local x runs along the flight, in game units
    rocket = Affine.frame(sheet(SPAWN), deg=PITCH, scale=U)
    s.stroke(P().M(sheet(SPAWN)).L(b), ACCENT_3, 1.25)
    body = rocket.apply([(-12, -2.5), (6, -2.5), (12, 0), (6, 2.5), (-12, 2.5)])
    s.path(
        P().poly(body, closed=True),
        fill=BG,
        stroke=UI_HI,
        stroke_width=1.25,
        stroke_linejoin="miter",
    )
    fins = P()
    for sg in (-1, 1):
        fins.poly(rocket.apply([(-5, 2.5 * sg), (-12, 5.5 * sg), (-12, 2.5 * sg)]))
    fins.poly(rocket.apply([(6, -2.5), (6, 2.5)]))
    s.stroke(fins, UI_HI, 1.25, join="miter")
    s.fill(P().circle(b, 3), ACCENT)

    # dimensions: ledge height, run to the landing, hull width and height, splash radius
    dim, heads = P(), P()
    dx, ly = LX1 + 60, (LEDGE + FLOOR) / 2
    dim.M(LX1 + 14, LEDGE).H(dx + 10).M(LX1 + 14, FLOOR).H(dx + 10)
    dim.M(dx, LEDGE + 2).V(ly - 16).M(dx, ly + 16).V(FLOOR - 2)
    dy = FLOOR + HATCH + 34
    x1 = sheet((LAND_X, 0)).x
    lx = (X0 + x1) / 2
    dim.M(X0, FLOOR + HATCH + 6).V(dy + 10).M(x1, FLOOR + HATCH + 6).V(dy + 10)
    dim.M(X0 + 2, dy).H(lx - 32).M(lx + 32, dy).H(x1 - 2)
    hx, hy = X0 - HW - 22, FLOOR - HH - 22
    dim.M(X0 - HW - 6, FLOOR - HH).H(hx - 8).M(hx, FLOOR - HH + 2).V(FLOOR - 2)
    dim.M(X0 - HW, FLOOR - HH - 6).V(hy - 8).M(X0 + HW, FLOOR - HH - 6).V(hy - 8)
    dim.M(X0 - HW + 2, hy).H(X0 + HW - 2)
    s.stroke(dim, UI_ALT, 1)
    arrow(heads, (dx, LEDGE), -90)
    arrow(heads, (dx, FLOOR), 90)
    arrow(heads, (X0, dy), 180)
    arrow(heads, (x1, dy), 0)
    arrow(heads, (hx, FLOOR - HH), -90, 7)
    arrow(heads, (hx, FLOOR), 90, 7)
    arrow(heads, (X0 - HW, hy), 180, 7)
    arrow(heads, (X0 + HW, hy), 0, 7)
    arrow(heads, r_end, -158, 8)
    s.fill(heads, UI_ALT)

    label(s, str(LEDGE_H), (dx, ly))
    label(s, str(round(LAND_X)), (lx, dy))
    label(s, "56", (hx - 8, FLOOR - HH / 2), "end")
    label(s, "32", (X0, hy - 16))
    label(s, f"R{RADIUS}", (r_end.x - 8, r_end.y - 14), "end")

    # reference numerals on leaders: 1 hull, 2 rocket, 3 splash, 4 flight path, 5 ledge
    arc_pt = sheet(origin(T_APEX * 0.45))
    rim = polar(b, RADIUS * U, deg=-40)
    marks = (
        (1, Vec(x1 + HW, LEDGE - HH * 0.6), Vec(x1 + 110, LEDGE - HH - 70)),
        (2, rocket((-6, 3)), Vec(X0 + 120, FLOOR - 50)),
        (3, rim, rim + (90, -60)),
        (4, arc_pt, arc_pt + (-150, -30)),
        (5, Vec(LX0 + 30, ly + 30), Vec(LX0 - 110, ly + 30)),
    )
    lead, rings = P(), P()
    for _, start, end in marks:
        c = Vec(round(end.x), round(end.y))
        lead.M(start).L(c - (c - start).unit() * 13)
        rings.circle(c, 13)
    s.stroke(lead, UI_ALT, 1)
    s.path(rings, fill=BG, stroke=UI_ALT, stroke_width=1.25)
    for num, _, end in marks:
        glyphs(s, [str(num)], MUTED, at=(round(end.x) - 5, round(end.y) - 8), font="5x8", px=2)
    label(s, "FIG. 1", (X0 + 60, FLOOR + HATCH + 90), "start", UI_HI)

    # FIG. 2: the velocity at the splash, the running jump plus the knockback
    k2 = 0.3
    f = Vec(190, 440)
    a = f + (V_PRE.x * k2, -V_PRE.y * k2)
    e = f + (V.x * k2, -V.y * k2)
    s.stroke(P().M(f.x - 14, f.y).H(f.x + 130).M(f.x, f.y + 14).V(f.y - 250), BG_ALT, 1)
    vector(s, f, e, UI_HI, 1.25)
    vector(s, f, a, MUTED, 1.5)
    vector(s, a, e, ACCENT, 2)
    s.fill(P().circle(f, 3), UI_HI)
    label(s, str(round(abs(V_PRE))), (f + a) / 2 + (14, 12), "start")
    label(s, str(round(abs(KICK))), (a + e) / 2 + (14, 0), "start")
    label(s, str(round(abs(V))), (f + e) / 2 + (-12, 0), "end")
    label(s, "FIG. 2", (f.x, f.y + 46), "start", UI_HI)

    # seal: the Quake nail emblem, traced from the id logo (ring centre near 300, 248)
    emblem: dict[str, list[list[float]]] = s.data("emblem.json")
    seal = Affine.translate(1770, 920) @ Affine.scale(0.2) @ Affine.translate(-300, -300)
    q = P().poly(seal.apply(emblem["outer"]), closed=True)
    q.poly(seal.apply(emblem["inner"]), closed=True)
    s.path(
        q, fill=BG_ALT, fill_rule="evenodd", stroke=UI_ALT, stroke_width=1, stroke_linejoin="miter"
    )
