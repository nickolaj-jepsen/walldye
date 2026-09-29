"""The air swirling behind an open-wheel racing car as a vector plot of modelled vortices over the car's faint rear outline, with one of the rear wing's two tip vortices lit and its twin fainter."""

import math

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely import LineString, Polygon, unary_union
from shapely.geometry.base import BaseGeometry

from walldye import (
    ACCENT,
    ACCENT_3,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Params,
    design,
    knob,
)
from walldye.geom import parts, spline_points

type Pts = NDArray[np.float64]
type Core = tuple[float, float, float, float]


class Plane(Params):
    distance: float = knob(default=5, lo=0.5, hi=12, unit="m", doc="plane behind the car")


U = 70.0  # m/s, road speed
# Right-hand members of the two counter-rotating pairs as they leave the car: y out from the
# centreline and z up from the road (m), circulation (m^2/s) and core radius (m). Both turn the
# way a downforce wing's do: down outboard, up between the pair.
WING = (0.58, 0.92, 30.0, 0.05)  # rear wing tips
DIFFUSER = (0.33, 0.24, 25.0, 0.07)  # diffuser side walls
SPREAD = 0.0012  # m^2 per metre travelled: turbulent growth of each core's area

PITCH = 36  # grid spacing
K_MAX = 0.36  # drawing units per mm; smaller when the field needs the room
TOP, SIDE = 100, 40  # margins kept clear of arrows
CAP = 14.0  # m/s; faster flow gets the longest arrow
LONG = 0.86 * PITCH
SHORT = 12  # a slower node is a dot
SLOW = CAP * SHORT / LONG  # m/s, the slowest flow drawn as an arrow
STEPS = (8.0, 20.0)  # m/s where the arrows step up a tone
HEAD, HEAD_W = 7.0, 3.0
LIT, TWIN = 1.6 * PITCH, 1.15 * PITCH  # reach of the lit arrows round the lit core and its twin
DOT, MARK = 1.3, 4.0  # empty-node radius, half-size of the cross on each wing core

# Rear view of the car, right half, in mm: y out from the centreline, z up from the road. Overall
# width, diffuser exit and rear wing span are the 2022 rules'; the rest is fitted around them.
TYRE = (595, 1000, 0, 720)
DIFF = (375, 0, 300)  # half width, bottom, roof
FLOOR = (800, 0, 48)  # half width, bottom, top
STRAKES = (130, 255)
BOX = (110, 300, 450)  # crash structure: half width, bottom, top
BEAM = (470, 420, 470)  # beam wing: half span, bottom, top
PYLON = (22, 450, 820)
MAIN = (615, 800, 910)  # rear wing: half span, bottom, top of the upper band
# the wing tip curling down to the beam wing, about 90 mm clear of the tyre
LEG = ((595, 860), (560, 810), (500, 750), (465, 665), (452, 560), (448, 445))
LEG_W = 40
BODY = (
    (470, 48),
    (468, 160),
    (440, 300),
    (360, 440),
    (260, 580),
    (190, 720),
    (150, 830),
    (115, 900),
    (60, 928),
    (0, 935),
)
ARMS = (((100, 440), (610, 560)), ((100, 330), (610, 250)))  # upper and lower wishbones


def pair_field(y: Pts, z: Pts, cores: list[Core]) -> tuple[Pts, Pts]:
    """Crossflow (v, w) at (y, z) from each right-hand core (y, z, gamma, rc), its left-hand
    mirror turning the other way, and both of their images under the road, which keep the flow
    along it. Lamb-Oseen cores: solid rotation inside rc, free vortex outside."""
    v, w = np.zeros_like(y), np.zeros_like(y)
    for cy, cz, g, rc in cores:
        for sy, sz, sg in ((cy, cz, -g), (-cy, cz, g), (cy, -cz, g), (-cy, -cz, -g)):
            dy, dz = y - sy, z - sz
            r2 = np.maximum(dy * dy + dz * dz, 1e-12)
            f = sg / (2 * math.pi * r2) * -np.expm1(-r2 / (rc * rc))
            v -= dz * f
            w += dy * f
    return v, w


def advect(distance: float) -> list[Core]:
    """The two right-hand cores carried `distance` metres downstream at road speed, each moved
    by the others and the images (RK4), their cores widening as they go."""
    pos = np.array([WING[:2], DIFFUSER[:2]])
    gam = [WING[2], DIFFUSER[2]]
    rc0 = [WING[3], DIFFUSER[3]]
    n = max(1, round(distance / 0.05))
    dx = distance / n

    def rate(p: Pts, x: float) -> Pts:
        cores = [(p[i, 0], p[i, 1], gam[i], math.sqrt(rc0[i] ** 2 + SPREAD * x)) for i in (0, 1)]
        v, w = pair_field(p[:, 0], p[:, 1], cores)
        return np.column_stack([v, w]) / U

    for i in range(n):
        x = i * dx
        k1 = rate(pos, x)
        k2 = rate(pos + dx / 2 * k1, x + dx / 2)
        k3 = rate(pos + dx / 2 * k2, x + dx / 2)
        k4 = rate(pos + dx * k3, x + dx)
        pos = pos + dx / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    return [
        (pos[i, 0], pos[i, 1], gam[i], math.sqrt(rc0[i] ** 2 + SPREAD * distance)) for i in (0, 1)
    ]


def reach(cores: list[Core]) -> tuple[float, float]:
    """Height and half width (mm) of the region where the crossflow is fast enough for an
    arrow, sampled every 20 mm."""
    ys, zs = np.meshgrid(np.arange(0, 4000, 20) / 1000, np.arange(0, 6000, 20) / 1000)
    v, w = pair_field(ys, zs, cores)
    fast = np.hypot(v, w) >= SLOW
    return float(zs[fast].max()) * 1000, float(ys[fast].max()) * 1000


def both(pts: Pts) -> list[Pts]:
    """The right-hand outline `pts` and its mirror across the centreline."""
    return [pts, pts * (-1, 1)]


def rrect(y0: float, y1: float, z0: float, z1: float, r: float) -> Polygon:
    return shapely.box(y0 + r, z0 + r, y1 - r, z1 - r).buffer(r, quad_segs=8)


def car_parts() -> tuple[list[BaseGeometry], BaseGeometry]:
    """The car's rear-view solids in mm, nearest first, and the body behind them."""
    ty0, ty1, tz0, tz1 = TYRE
    dw, dz0, dz1 = DIFF
    bw, bz0, bz1 = BOX
    mw, mz0, mz1 = MAIN
    band = rrect(-mw, mw, mz0, mz1, 40)
    legs = [
        LineString(spline_points(pts, 8)).buffer(LEG_W / 2, cap_style="flat")
        for pts in both(np.asarray(LEG, dtype=float))
    ]
    # rounds the joins between the band and its tips, inside and out
    wing = unary_union([band, *legs]).buffer(40).buffer(-52).buffer(12)
    solids: list[BaseGeometry] = [
        wing,
        rrect(-BEAM[0], BEAM[0], BEAM[1], BEAM[2], 20),
        shapely.box(-PYLON[0], PYLON[1], PYLON[0], PYLON[2]),
        rrect(-bw, bw, bz0, bz1, 24),
        rrect(-dw, dw, dz0, dz1, 16),
        rrect(ty0, ty1, tz0, tz1, 60),
        rrect(-ty1, -ty0, tz0, tz1, 60),
        shapely.box(-FLOOR[0], FLOOR[1], FLOOR[0], FLOOR[2]),
    ]
    solids += [LineString(pts).buffer(9) for a in ARMS for pts in both(np.asarray(a, dtype=float))]
    half = np.asarray(BODY, dtype=float)
    body = Polygon(np.concatenate([half, (half * (-1, 1))[::-1]]))
    return solids, body


@design(aspects="any", variants={"ten": Plane(distance=10)})
def draw(s: Canvas[Plane]) -> None:
    cores = advect(s.params.distance)
    c = s.pick(landscape=(0.34, 0.5), portrait=(0.5, 0.5))
    cx = round(c.x)
    gy = s.h - 120 if s.landscape else round(s.h * 0.8)
    top, side = reach(cores)
    k = min(K_MAX, (gy - TOP) / top, (min(cx, s.w - cx) - SIDE) / side)

    def screen(g: BaseGeometry) -> BaseGeometry:
        return shapely.transform(g, lambda a: np.column_stack([cx + a[:, 0] * k, gy - a[:, 1] * k]))

    solids, body = car_parts()
    solids = [screen(g) for g in solids]
    body = screen(body)
    # the whole silhouette, windows between the parts filled in
    whole = parts(unary_union([*solids, body]))
    car = unary_union([Polygon(g.exterior) for g in whole if isinstance(g, Polygon)])

    # the outline, each part hidden where a nearer one stands in front of it; the floor's
    # underside is left to the road line
    outline = P()
    front: BaseGeometry = shapely.Polygon()
    for g in solids:
        outline.shape(g.boundary.difference(front).difference(shapely.box(0, gy - 1, s.w, s.h)))
        front = front.union(g)
    outline.shape(body.boundary.difference(front))
    detail = P()
    _, dz0, dz1 = DIFF
    for y in STRAKES:
        for sy in (y, -y):
            detail.M(cx + sy * k, gy - dz0 * k).V(gy - (dz1 - 20) * k)
    s.stroke(detail, BG_ALT, 1.2)
    s.stroke(outline, UI, 1.2, join="round")
    s.stroke(P().M(0, gy).H(s.w), UI, 1.2)

    # grid nodes, on the centreline and a whole number of pitches above the road
    cols = np.arange(-(cx // PITCH), (s.w - cx) // PITCH + 1)
    rows = np.arange(1, gy // PITCH + 1)
    gx, gyy = np.meshgrid(cx + cols * PITCH, gy - rows * PITCH)
    xs, ys = gx.ravel().astype(float), gyy.ravel().astype(float)
    v, w = pair_field((xs - cx) / k / 1000, (gy - ys) / k / 1000, cores)
    speed = np.hypot(v, w)
    length = LONG * np.minimum(1, speed / CAP)
    ux, uy = v / np.maximum(speed, 1e-9), -w / np.maximum(speed, 1e-9)
    half = length / 2
    tails = np.column_stack([xs - ux * half, ys - uy * half])
    tips = np.column_stack([xs + ux * half, ys + uy * half])
    segs = shapely.linestrings(np.stack([tails, tips], axis=1))
    # the rear wing's cores: the left one lit, its twin a step down
    wy, wz = cores[0][0] * 1000 * k, gy - cores[0][1] * 1000 * k
    lit = [(cx - wy, wz), (cx + wy, wz)]
    to_lit, to_twin = (np.hypot(xs - lx, ys - ly) for lx, ly in lit)
    blocked = unary_union([car.buffer(5), *(shapely.Point(p).buffer(MARK + 4) for p in lit)])
    clear = ~shapely.intersects(blocked, segs)
    arrow = clear & (length >= SHORT)
    tone = np.digitize(speed, STEPS)
    tone = np.where(to_twin < TWIN, 3, tone)
    tone = np.where(to_lit < LIT, 4, tone)

    s.fill(P().dots(np.column_stack([xs, ys])[clear & ~arrow], DOT), BG_ALT)
    paints = (UI, UI_ALT, UI_HI, ACCENT_3, ACCENT)
    shafts = [P() for _ in paints]
    heads = [P() for _ in paints]
    for i in np.flatnonzero(arrow):
        t = int(tone[i])
        a = math.degrees(math.atan2(uy[i], ux[i]))
        base = tips[i] - (ux[i] * HEAD * 0.8, uy[i] * HEAD * 0.8)
        shafts[t].M(tails[i]).L(base)
        heads[t].arrowhead(tips[i], HEAD, deg=a, width=HEAD_W)
    for t, paint in enumerate(paints):
        s.stroke(shafts[t], paint, 1.8, cap="butt")
        s.fill(heads[t], paint)

    marks = P()
    for lx, ly in lit:
        marks.M(lx - MARK, ly).H(lx + MARK).M(lx, ly - MARK).V(ly + MARK)
    s.stroke(marks, UI_HI, 1.2)
