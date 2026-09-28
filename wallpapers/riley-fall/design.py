"""After Riley's Fall: one chirped sine curve repeated sideways into a curtain, one copy picked out."""

import numpy as np
import shapely
from numpy.typing import NDArray

from walldye import ACCENT, ACCENT_3, BG_ALT, UI, Canvas, P, design, ramp

X0, GAP = -24, 11  # first line (off the left edge), line pitch
TOL = 0.1  # simplification tolerance: the straight upper part collapses to a few points
AMP0, AMP1 = 18, 14  # amplitude eases off at the bottom so steep neighbours don't close up
F1, POW = 1 / 66, 3  # frequency at the bottom; f(y) ~ y**POW keeps the top straight
TAIL = 19 / 60  # lines past the vein, as a share of the lines before it
TONES = ramp(BG_ALT, UI, 7)


@design(aspects="any")
def draw(s: Canvas) -> None:
    ys = np.arange(0, s.h + 7, dtype=float)
    t = ys / s.h
    phase = 2 * np.pi * F1 * s.h / (POW + 1) * t ** (POW + 1)
    dense = np.column_stack(((AMP0 + (AMP1 - AMP0) * t**2) * np.sin(phase), ys))
    # every line is this curve shifted sideways, so simplify it once
    curve = shapely.get_coordinates(shapely.simplify(shapely.LineString(dense), TOL))

    vein = round((s.pick(landscape=(1 / 3, 0), portrait=(0.45, 0)).x - X0) / GAP)

    def line(i: int) -> NDArray[np.float64]:
        return curve + (X0 + i * GAP, 0)

    with s.buckets(TONES, "stroke", stroke_width=2.4) as b:
        for i in range(vein + round(vein * TAIL) + 1):
            if abs(i - vein) > 1:
                # lines step up the tones towards the vein so the curtain has a lit fold
                lit = max(0.0, 1 - abs(i - vein) / vein) ** 1.5
                b[round(6 * lit)].poly(line(i))
    s.stroke(P().poly(line(vein - 1)).poly(line(vein + 1)), ACCENT_3, 2)
    s.stroke(P().poly(line(vein)), ACCENT, 3)
