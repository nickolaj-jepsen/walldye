"""Both Voyager paths through the outer solar system seen from above, over the planets' orbits in hairlines, with a tick at each flyby."""

from typing import TypedDict

import numpy as np

from walldye import ACCENT, BG, UI, UI_ALT, UI_HI, Canvas, P, Vec, design
from walldye.geom import Affine

type Pts = list[list[float]]


class Tour(TypedDict):
    # heliocentric ecliptic x, y (AU), launch to 2040, predicted past the flybys
    craft: dict[str, Pts]
    orbits: dict[str, Pts]  # one period of each planet, ecliptic x, y (AU)
    flybys: dict[str, list[tuple[str, float, float]]]  # planet, its x, y on the flyby date


SCALE = 22.0  # px per AU
TICK = 8.0  # half length of a flyby tick, across the orbit


@design(aspects="any")
def draw(s: Canvas) -> None:
    tour: Tour = s.data("grand-tour.json")
    # Uranus clears the near edge by 80 or more and Neptune crosses it by as much, except on
    # tall phones, where Neptune's orbit sits whole inside the top edge
    if s.landscape:
        sun = Vec(s.w * 0.3, s.h / 2)
    else:
        sun = Vec(s.w / 2, 540 if s.h < 1.8 * s.w else 790)
    # ecliptic y flipped so the planets run counterclockwise, as seen from the north
    frame = Affine.frame(sun, deg=-56 if s.landscape else 8, scale=SCALE)
    flip = Affine.scale(1, -1)
    at = frame @ flip

    orbits = P()
    for pts in tour["orbits"].values():
        orbits.poly(at.apply(np.array(pts)), closed=True)
    s.stroke(orbits, UI, 1.4)

    s.fill(P().circle(sun, 4), UI_HI)
    v1 = P().poly(at.apply(np.array(tour["craft"]["voyager1"])))
    s.stroke(P().poly(at.apply(np.array(tour["craft"]["voyager2"]))), UI_ALT, 1.8)

    ticks = P()
    for fly in tour["flybys"].values():
        for _, x, y in fly:
            r = np.hypot(x, y)
            u = np.array([x, y]) / r * TICK / SCALE
            ticks.poly(at.apply(np.array([[x, y] - u, [x, y] + u])))
    s.stroke(ticks, UI_HI, 2)

    # a gap either side of Voyager 1: Voyager 2 branches from under it, orbits and ticks break
    s.stroke(v1, BG, 8)
    s.stroke(v1, ACCENT, 3.5)
