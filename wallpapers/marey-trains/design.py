"""One day of trains on the old Paris-Lyon line as a graphical timetable, distance against time, one through train lit."""

from typing import TypedDict

from walldye import ACCENT, BG_ALT, UI, Canvas, P, design


class Train(TypedDict):
    kind: str  # "ter" regional, "ic" intercity, "hs" high-speed on the classic line
    stops: list[list[int]]  # [station index, arrival, departure], minutes after midnight


class Timetable(TypedDict):
    km: list[float]  # kilometre posts from Paris, one per station
    trains: list[Train]


T0, T1 = 3 * 60 + 45, 24 * 60 + 30  # the day's window, minutes after midnight; no hour on an edge
# Stations ruled across the chart, by kilometre post: the main ones from Paris to Lyon Part-Dieu.
RULED = (
    0.0,
    44.076,
    78.627,
    112.627,
    145.456,
    154.874,
    196.22,
    242.232,
    256.78,
    314.208,
    351.181,
    366.206,
    382.15,
    407.753,
    439.735,
    477.0,
    507.505,
)
LIT = (0, 935)  # the lit train: first station index and departure, the 15:35 from Paris


@design(aspects="any")
def draw(s: Canvas) -> None:
    tt: Timetable = s.data("timetable.json")
    km = tt["km"]
    span = km[-1]

    # the day runs edge to edge along the time axis; the line keeps a margin
    if s.landscape:
        x0, x1, y0, y1 = 0, s.w, 120, s.h - 140
    else:
        x0, x1, y0, y1 = 120, s.w - 120, 0, s.h

    def at(t: float, d: float) -> tuple[float, float]:
        """Minutes and kilometres to canvas: time runs across a landscape screen, down a portrait one."""
        ft, fd = (t - T0) / (T1 - T0), d / span
        if s.landscape:
            return x0 + ft * (x1 - x0), y0 + fd * (y1 - y0)
        return x0 + fd * (x1 - x0), y0 + ft * (y1 - y0)

    hours, noon = P(), P()  # noon ruled a step brighter
    for h in range(-(-T0 // 60), T1 // 60 + 1):
        a, b = at(h * 60, 0), at(h * 60, span)
        (noon if h == 12 else hours).M(*a).L(*b)
    rules = P()
    for d in RULED:
        a, b = at(T0, d), at(T1, d)
        rules.M(*a).L(*b)
    s.stroke(hours, BG_ALT, 1)
    s.stroke(rules, BG_ALT, 1.2)
    s.stroke(noon, UI, 1)

    runs, lit = P(), P()
    for tr in tt["trains"]:
        pts: list[tuple[float, float]] = []
        for i, arr, dep in tr["stops"]:
            pts.append(at(arr, km[i]))
            if dep > arr:
                pts.append(at(dep, km[i]))
        first = tr["stops"][0]
        target = lit if (first[0], first[2]) == LIT else runs
        target.poly(pts)
    s.stroke(runs, UI, 1.7, join="round")
    s.stroke(lit, ACCENT, 3, cap="round", join="round")
