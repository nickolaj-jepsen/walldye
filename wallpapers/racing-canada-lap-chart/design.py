"""The 2011 Canadian Grand Prix as a lap chart: one line per car stepping between positions over 70 laps."""

from typing import TypedDict

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import LineString, Point

from walldye import ACCENT, ACCENT_3, ACCENT_4, BG, UI, UI_ALT, Canvas, P, by_regime, design

type Arr = NDArray[np.float64]


class Car(TypedDict):
    id: str
    grid: int
    out: bool  # retired, so the line stops short
    pos: list[int]  # position at the end of each lap
    pits: list[int]  # laps with a stop or a drive-through


LAPS, CARS = 70, 24
HALT = 24  # the race was stopped for two hours during the next lap; the chart breaks here
GAP = 3.0  # width of the break, in laps
# Safety car laps, read off the leader's lap times; the one across the break is split round it.
SC = ((1, 4), (9, 12), (20, 24), (25, 34), (38, 40), (57, 60))
DROP = 36  # the winner's last lap before the puncture put him last
SPAN = LAPS + GAP
LEAD = by_regime(ACCENT_4, ACCENT_3)  # the winner's line before the drop


def lap_u(k: float) -> float:
    """Distance along the lap axis, in lap widths, with the break after HALT."""
    return k + (GAP if k > HALT else 0.0)


def line(car: Car) -> Arr:
    """(u, v) chart points from the grid to the last lap, one per lap plus the break's far edge."""
    pts = [(0.0, car["grid"] - 1.0)]
    for k, p in enumerate(car["pos"], 1):
        if k == HALT + 1:
            pts.append((HALT + GAP, pts[-1][1]))
        pts.append((lap_u(k), p - 1.0))
    return np.array(pts)


def idx(k: int) -> int:
    """Index of lap k's point in line()'s output."""
    return k if k <= HALT else k + 1


@design(aspects="any")
def draw(s: Canvas) -> None:
    cars: list[Car] = s.data("laps.json")

    if s.landscape:
        du, dv = min(18.0, s.w * 0.68 / SPAN), 20.0
        x0 = min(s.w - 150, s.w * 0.62 + SPAN * du / 2) - SPAN * du
        y0 = s.h * 0.64 - (CARS - 1) * dv / 2
    else:  # laps stay across, P1 on top, so the chart spans the short side
        du, dv = (s.w - 180) / SPAN, 24.0
        x0, y0 = 90, s.h * 0.66 - (CARS - 1) * dv / 2
    x0, y0 = round(x0), round(y0)

    def at(uv: Arr) -> Arr:
        """Chart (lap, position - 1) to canvas."""
        return np.column_stack([x0 + uv[:, 0] * du, y0 + uv[:, 1] * dv])

    def x(u: float) -> float:
        return x0 + u * du

    # lap axis under the chart, broken where the race stopped, with a longer tick every ten laps
    # and the laps run behind the safety car as a strip beneath it
    ay = y0 + (CARS - 1) * dv + 22
    axis = P().M(x(0), ay).H(x(HALT)).M(x(HALT + GAP), ay).H(x(SPAN))
    for k in range(LAPS + 1):
        axis.M(x(lap_u(k)), ay).V(ay + (10 if k % 10 == 0 else 5))
    s.stroke(axis, UI, 1.2)
    shade = P()
    for a, b in SC:
        ua = HALT + GAP if a == HALT + 1 else lap_u(a - 1)
        shade.rect(x(ua), ay + 14, (lap_u(b) - ua) * du, 4)
    s.fill(shade, UI)

    # positions held through the stoppage, four dots across the break
    held = [
        (HALT + GAP * i / 5, car["pos"][HALT - 1] - 1.0)
        for car in cars
        if len(car["pos"]) >= HALT
        for i in range(1, 5)
    ]
    s.fill(P().dots(at(np.array(held)), 1.0), UI)

    win = next(car for car in cars if car["id"] == "button")
    wpts, cut = line(win), idx(DROP)
    lit = at(wpts[cut:])
    lit_path = LineString(lit)

    def clear(marks: list[Arr]) -> Arr:
        """Marks in canvas units, less those the lit line's knock-out would bite into."""
        xy = at(np.array(marks))
        return xy[[lit_path.distance(Point(p)) >= 6 for p in xy.tolist()]]

    gray = P()
    ends, pit = [], []
    for car in cars:
        if car is win:
            continue
        pts = line(car)
        gray.poly(at(pts[: HALT + 1]))
        if len(pts) > HALT + 1:
            gray.poly(at(pts[HALT + 1 :]))
        if car["out"]:
            ends.append(pts[-1])
        pit += [pts[idx(k)] for k in car["pits"]]
    s.stroke(gray, UI, 1.2, join="round")
    s.fill(P().dots(clear(pit), 2.2), UI_ALT)
    s.fill(P().dots(clear(ends), 2.5), UI_ALT)

    # the winner: dim up to the drop, then lit over a knock-out that cuts the lines it crosses
    lead = P().poly(at(wpts[: HALT + 1])).poly(at(wpts[HALT + 1 : cut + 1]))
    stops = {k: wpts[idx(k)] for k in win["pits"]}
    s.stroke(P().poly(lit), BG, 7, join="round", cap="round")
    s.stroke(lead, LEAD, 1.5, join="round")
    s.fill(P().dots(at(np.array([p for k, p in stops.items() if k <= DROP])), 2.4), LEAD)
    s.stroke(P().poly(lit), ACCENT, 3, join="round", cap="round")
    s.fill(P().dots(at(np.array([p for k, p in stops.items() if k > DROP])), 3.8), ACCENT)
