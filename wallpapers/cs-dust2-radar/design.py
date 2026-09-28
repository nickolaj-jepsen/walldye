"""Dust II as a hairline CS2 radar traced from the game's overview; the one lit mark is the bomb ticking on B."""

import math
from typing import TypedDict

import shapely
from shapely import Polygon, unary_union

from walldye import (
    ACCENT,
    ACCENT_4,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Path,
    design,
    ladder,
    mix,
    polar,
)
from walldye.geom import Affine, hatch

type Ring = list[list[float]]


class Prop(TypedDict):
    at: str
    pts: Ring


class Overview(TypedDict):
    """The traced overview in grid units (1 unit = 32 px of the 1024 px radar image)."""

    grid: int
    floor: Ring
    voids: list[Ring]
    sites: dict[str, Ring]
    spawns: dict[str, Ring]
    walls: dict[str, Ring]
    doors: dict[str, Ring]
    props: list[Prop]


FLOOR = mix(BG, BG_ALT, 0.5)
PULSE = ladder((BG, ACCENT_4, ACCENT), 4)  # the bomb's rings take rungs 1 and 2
BOMB = (6.72, 3.84)  # the overview's bombB marker
# CTs holding long, (x, y, bearing faced): goose, A ramp, long cross, car
PLAYERS = ((27.6, 3.6, 200), (28.2, 9.2, 180), (27.4, 15.4, 205), (24.6, 15.9, 150))


@design(aspects="any")
def draw(s: Canvas) -> None:
    radar: Overview = s.data("dust2.json")
    k = 20 if s.landscape else 24  # px per grid unit; a phone is width-bound, so larger
    side = radar["grid"] * k
    # landscape: the frame's centre at (1400, 540) on 16:9, leaving the left for windows
    c = s.pick(landscape=(1400 / 1920, 0.5), portrait=(0.5, 0.54), snap=1)
    o = c - (side / 2, side / 2)
    place = Affine.translate(o.x, o.y) @ Affine.scale(k)

    def outline(rings: list[Ring], closed: bool = True) -> Path:
        d = P()
        for ring in rings:
            d.poly(place.apply(ring), closed=closed)
        return d

    plan = P().shape(shapely.transform(Polygon(radar["floor"], radar["voids"]), place.apply))
    s.fill(plan, FLOOR)

    # bomb-site hatch at 45 degrees, held inside the site and clear of the props
    props = unary_union([Polygon(p["pts"]) for p in radar["props"]]).buffer(
        0.15, join_style="mitre"
    )
    rules = P()
    for site in radar["sites"].values():
        area = Polygon(site).buffer(-0.08, join_style="mitre").difference(props)
        for seg in hatch(shapely.transform(area, place.apply), 0.21 * k, deg=-45):
            if math.dist(seg[0], seg[1]) > 1:
                rules.poly(seg)
    s.stroke(rules, UI, 0.8)
    s.stroke(outline(list(radar["sites"].values())), UI_ALT, 1)
    s.stroke(outline(list(radar["spawns"].values())), UI, 1, dash=(3, 3))

    s.stroke(plan, UI_ALT, 1.2, join="miter")
    s.stroke(outline(list(radar["walls"].values()), closed=False), UI_ALT, 2)
    s.stroke(outline(list(radar["doors"].values()), closed=False), UI_HI, 1.5)
    s.stroke(outline([p["pts"] for p in radar["props"]]), UI_ALT, 1)

    # frame with corner ticks set 8 px outside it
    s.stroke(P().rect(o.x, o.y, side, side), UI, 1)
    ticks = P()
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        sx, sy = 1 - 2 * dx, 1 - 2 * dy  # pointing into the frame
        q = o + (dx * side - 8 * sx, dy * side - 8 * sy)
        ticks.M(q.x + 12 * sx, q.y).H(q.x).V(q.y + 12 * sy)
    s.stroke(ticks, UI_ALT, 1.5)

    # players: the CS2 radar dot with a small pointer on its rim
    dots, pointers = P(), P()
    for x, y, bearing in PLAYERS:
        p = place((x, y))
        dots.circle(p, 4)
        tip = polar(p, 8.5, bearing=bearing)
        pointers.poly(
            [polar(p, 4, bearing=bearing - 40), tip, polar(p, 4, bearing=bearing + 40)], closed=True
        )
    s.fill(pointers, UI_HI)
    s.fill(dots, UI_HI)

    bomb = place(BOMB)
    s.stroke(P().circle(bomb, 2 * k), PULSE[1], 1)
    s.stroke(P().circle(bomb, 1.1 * k), PULSE[2], 1)
    s.fill(P().rect(bomb.x - 4.5, bomb.y - 4.5, 9, 9), ACCENT)
