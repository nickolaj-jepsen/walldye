"""Level lines that ripple faster toward the right, each lagging the one below."""

import numpy as np
import shapely
from numpy.typing import NDArray

from walldye import ACCENT, ACCENT_3, BG_ALT, UI, Canvas, P, design, ramp

Y0, GAP = 24, 11  # first line below the bottom edge, line pitch
TOL = 0.1  # simplification tolerance: the flat left part collapses to a few points
AMP0, AMP1 = 16, 12  # amplitude eases off at the right so steep neighbors don't close up
F1, POW = 1 / 60, 3  # frequency at the right edge; f(x) ~ x**POW keeps the left flat
DRIFT = 0.3  # phase lag per line, in radians: the crests lean instead of stacking
TAIL = 19 / 60  # lines above the picked-out one, as a share of the lines below it
TONES = ramp(BG_ALT, UI, 7)


@design(aspects="any")
def draw(s: Canvas) -> None:
    xs = np.arange(-4, s.w + 5, dtype=float)
    t = np.clip(xs / s.w, 0, 1)
    phase = 2 * np.pi * F1 * s.w / (POW + 1) * t ** (POW + 1)
    amp = AMP0 + (AMP1 - AMP0) * t**2

    vein = round((s.h + Y0 - s.pick(landscape=(0, 0.6), portrait=(0, 0.55)).y) / GAP)

    def line(i: int) -> NDArray[np.float64]:
        # line i sits i pitches above the bottom edge and lags i steps behind line 0
        dense = np.column_stack((xs, s.h + Y0 - i * GAP + amp * np.sin(phase - i * DRIFT)))
        return shapely.get_coordinates(shapely.simplify(shapely.LineString(dense), TOL))

    with s.buckets(TONES, "stroke", stroke_width=2.4) as b:
        for i in range(vein + round(vein * TAIL) + 1):
            if abs(i - vein) > 1:
                # lines step up the tones towards the picked-out one, so the band has a lit fold
                lit = max(0.0, 1 - abs(i - vein) / vein) ** 1.5
                b[round(6 * lit)].poly(line(i))
    s.stroke(P().poly(line(vein - 1)).poly(line(vein + 1)), ACCENT_3, 2)
    s.stroke(P().poly(line(vein)), ACCENT, 3)
