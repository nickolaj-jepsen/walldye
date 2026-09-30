"""A synoptic chart: noise-bent isobars round a low, with fronts marked by pennants and domes."""

import math

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely.ops import substring

from walldye import (
    ACCENT,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Path,
    Rect,
    Vec,
    design,
    ladder,
    mix,
    polar,
)
from walldye.field import gauss, iso_lines
from walldye.geom import Polyline, parts, spline_points

type Pts = NDArray[np.float64]

# The storm in units from the low's center: the triple point where the fronts meet, then each
# front's control points, running outward from the low or the triple point.
TRIPLE = (80, 220)
OCCLUDED = ((0, 0), (68, 50), (95, 140), TRIPLE)
COLD = (TRIPLE, (-40, 340), (-220, 460), (-410, 570), (-550, 690))
WARM = (TRIPLE, (220, 240), (390, 300), (550, 380), (710, 450))
FOCUS = (-50, 100)  # the isobars step down in tone with distance from here
CELL = 5  # pressure lattice spacing
TONES = ladder((UI_ALT, UI, mix(UI, BG_ALT, 0.5), BG_ALT), 4)
MERIDIAN = 0.075  # graticule meridian spacing, radians


def blob(dx: NDArray[np.floating], dy: NDArray[np.floating], sx: float, sy: float) -> Pts:
    """A pressure anomaly of height 1: a Gaussian with standard deviations `sx` and `sy`."""
    return gauss(np.hypot(dx / sx, dy / sy), math.sqrt(2))


def run_off(low: Vec, ctrl: tuple[tuple[float, float], ...], box: Rect) -> list[Vec]:
    """The control points `ctrl` placed at `low`, carried on along their last leg until the
    last one lies outside `box`."""
    pts = [low + c for c in ctrl]
    leg = pts[-1] - pts[-2]
    while box.contains(pts[-1]):
        pts.append(pts[-1] + leg)
    return pts


def front_marks(d: Path, pts: Pts, spacing: float, start: float, kinds: str) -> None:
    """Append front symbols along `pts` to `d`, every `spacing` units from `start`: pennants
    ("t") and domes ("s"), cycling through `kinds`, on the left of the direction of travel."""
    half = 15
    line = Polyline(pts)
    at, k = start, 0
    while at < line.length - spacing * 0.4:
        a, b = line.at(at - half), line.at(at + half)
        t = (b - a).unit()
        if kinds[k % len(kinds)] == "t":
            # the apex stands over the chord's midpoint, so teeth stay isosceles on bends
            d.M(a).L((a + b) / 2 - t.perp() * half * 1.25).L(b).Z()
        else:
            th = math.atan2(t.y, t.x)
            d.arc_band(line.at(at), 0, half * 0.85, rad=(th, th - math.pi))
        at += spacing
        k += 1


@design(aspects="any")
def draw(s: Canvas) -> None:
    low = s.pick(landscape=(125 / 192, 7 / 18), portrait=(0.6, 0.33))
    high = s.pick(landscape=(11 / 64, 19 / 27), portrait=(0.25, 0.75))
    box = s.inset(-100)
    occluded = spline_points([low + c for c in OCCLUDED], 24)
    cold = spline_points(run_off(low, COLD, box), 24)
    warm = spline_points(run_off(low, WARM, box), 24)
    fronts = shapely.MultiLineString([occluded, cold, warm])

    xs, ys = np.meshgrid(np.arange(s.w // CELL + 1) * CELL, np.arange(s.h // CELL + 1) * CELL)
    # storm-relative, so the same weather sits round the low on every screen shape
    qx, qy = xs - low.x, ys - low.y
    dist = shapely.distance(shapely.points(xs.ravel(), ys.ravel()), fronts).reshape(xs.shape)
    rise = 0.004 * min(1, 1920 / s.w)  # west to east, at most 8 hPa across the sheet
    pressure = (
        1016
        - 30 * blob(qx, qy, 420, 360)
        + 14 * blob(xs - high.x, ys - high.y, 420, 320)
        + rise * (qx + 350)
        - 3 * np.exp(-dist / 90)  # troughs along the fronts kink the isobars
        + 2.4 * s.noise(4).fbm((qx + 1250) / 480, (qy + 420) / 480, 2)
    )

    # a faint conic graticule: meridians converge on a pole far above the sheet
    pole = Vec(s.w * 41 / 96, -2600)
    corners = [Vec(x, y) - pole for x in (0, s.w) for y in (0, s.h)]
    reach = max(abs(c) for c in corners) + 60
    spread = [math.atan2(c.y, c.x) - math.pi / 2 for c in corners]
    grat = P()
    for k in range(math.floor(min(spread) / MERIDIAN) - 1, math.ceil(max(spread) / MERIDIAN) + 2):
        a = math.pi / 2 + k * MERIDIAN
        grat.M(polar(pole, 2550, rad=a)).L(polar(pole, reach, rad=a))
    fan = max(abs(a) for a in spread) + 0.1
    for r in range(2680, int(reach) + 210, 210):
        grat.arc(pole, r, rad=(math.pi / 2 - fan, math.pi / 2 + fan))
    s.stroke(grat, UI, 1.8, dash=(0.1, 11), cap="round")

    channel = fronts.buffer(11)  # each front runs in a clean gap, never shadowed by an isobar
    focus = low + FOCUS
    with s.buckets(
        TONES, "stroke", stroke_width=1.5, stroke_linejoin="round", stroke_linecap="round"
    ) as iso:
        for level in range(984, 1032, 4):
            for raw in iso_lines(pressure, level, cell=CELL):
                if len(raw) < 8:
                    continue
                for piece in parts(shapely.LineString(raw).difference(channel)):
                    line = np.asarray(piece.coords)
                    # short runs, so the tone can step down along a line as it leaves the storm
                    for i in range(0, len(line) - 1, 12):
                        run = line[i : i + 13]
                        mx, my = run[len(run) // 2]
                        f = math.hypot((mx - focus.x) / 1.4, my - focus.y) / 700
                        iso[TONES.rung(f)].poly(run)

    # the two pressure centers
    s.fill(P().dots([low, high], 3), UI_HI)
    s.stroke(P().circle(low, 9).circle(high, 9), UI_HI, 1.4)

    into_low = shapely.LineString(occluded)
    # stop short of the center ring
    occ = np.asarray(substring(into_low, 15, into_low.length).coords)
    s.stroke(P().poly(occ).poly(cold).poly(warm), ACCENT, 2.2, join="round", cap="round")
    marks = P()
    front_marks(marks, cold, 92, 52, "t")
    front_marks(marks, warm, 92, 52, "s")
    front_marks(marks, occ, 64, 37, "ts")
    s.fill(marks, ACCENT)
