"""Half a century of strong earthquakes stippled on a Pacific-centered map, dots sized by magnitude, with plate boundaries as hairlines."""

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from walldye import ACCENT, BG, BG_ALT, UI, UI_ALT, UI_HI, Canvas, P, by_regime, design
from walldye.field import runs

type Arr = NDArray[np.float64]

LAT_SPAN = 150.0  # degrees of latitude the short side covers at least
K_MAX = 10.0  # px per degree; caps portrait zoom so the Pacific's rim stays on screen
K_BASE = 1080 / LAT_SPAN  # the scale the dot sizes are set for
EDGE = 40  # how close a plate line may come to the frame without crossing it
QUIET_SPAN, QUIET_REACH = 15.0, 3.0  # degrees: short plate lines with no quake this near drop
FOCUS = (142.4, 38.3)  # the 2011 Tohoku quake, lon/lat
# Quake dots by magnitude: events at or above the bound get this diameter and tone.
DOTS = (
    (5.5, 1.8, UI),
    (6.0, 2.8, by_regime(UI_ALT, UI)),
    (6.5, 4.4, UI_ALT),
    (7.0, 6.5, UI_ALT),
    (8.0, 10.0, UI_HI),
)
RING = 44


@design(aspects="any")
def draw(s: Canvas) -> None:
    k = max(s.w / 360, min(s.h / LAT_SPAN, K_MAX))  # px per degree, plate carree
    spot = s.pick(landscape=(0.31, 0.34), portrait=(0.25, 0.36))
    west = FOCUS[0] - spot.x / k  # longitude at the left edge; the map seams there

    def at(lon: Arr, lat: Arr) -> Arr:
        x = ((lon - west) % 360) * k
        y = spot.y - (lat - FOCUS[1]) * k
        return np.column_stack([x, y])

    # USGS epicenters of M5.5 and up, 1976 to 2025: lon, lat and magnitude, each times ten
    cat = np.asarray(s.data("quakes.npy"), dtype=np.float64) / 10
    near = cKDTree(cat[:, :2])

    plates: list[list[list[float]]] = s.data("plates.json")
    frame = s.inset(0)
    lines = P()
    for line in plates:
        ll = np.array(line)
        span = np.hypot(*np.diff(ll, axis=0).T).sum()
        if span < QUIET_SPAN and not any(near.query_ball_point(ll, QUIET_REACH)):
            continue  # a short boundary nothing on this map has shaken
        xy = at(*ll.T)
        cuts = np.flatnonzero(np.abs(np.diff(xy[:, 0])) > 180 * k) + 1
        for run in np.split(xy, cuts):
            x, y = run.T
            gap = np.minimum.reduce([x - frame.x, frame.x1 - x, y - frame.y, frame.y1 - y])
            # a line that never leaves the frame keeps clear of its edges
            keep = gap >= EDGE if gap.min() >= 0 else np.ones(len(run), dtype=bool)
            for i, j in runs(keep):
                if j - i > 1:
                    lines.poly(run[i:j])
    s.stroke(lines, BG_ALT, 1.2)

    xy = at(cat[:, 0], cat[:, 1])
    mag = cat[:, 2]
    on = (xy[:, 1] > -20) & (xy[:, 1] < s.h + 20)
    bounds = [b for b, _, _ in DOTS[1:]] + [99.0]
    for (lo, dia, tone), hi in zip(DOTS, bounds, strict=True):
        pick = on & (mag >= lo) & (mag < hi)
        pts = np.unique(np.round(xy[pick]), axis=0)
        d = P()
        for x, y in pts.tolist():
            d.M(x, y).H(x)
        s.stroke(d, tone, dia * k / K_BASE, cap="round")

    ring = P().circle(spot, RING)
    s.stroke(ring, BG, 10)  # a clear channel through the aftershock cloud
    s.stroke(ring, ACCENT, 3)
    s.fill(P().circle(spot, 7), ACCENT)
