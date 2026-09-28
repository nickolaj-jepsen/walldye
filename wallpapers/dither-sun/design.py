"""A solid sun of square cells in a halo that thins out through Bayer-ordered checkers into loose dots."""

import numpy as np

from walldye import ACCENT, ACCENT_3, ACCENT_4, ACCENT_7, BG, BG_ALT, Canvas, by_regime, design, mix
from walldye.field import cells, falloff
from walldye.pixel import dither, grid_runs

CELL = 4  # a finer cell pushes the widest screens past the file-size limit
R_SUN, R_HALO = 170, 840  # the solid disc, and where the last dots give out
# The halo from the outside in. On paper BG_ALT would make the outermost step a veil darker
# than the one inside it, so there it is ACCENT_7 alone.
LAYERS = (
    by_regime(mix(BG_ALT, ACCENT_7, 0.47), ACCENT_7),
    mix(BG, ACCENT_4, 0.37),
    ACCENT_4,
    ACCENT_3,
    ACCENT,
)


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(0.6875, 0.52), portrait=(0.56, 0.36), snap=CELL)
    xs, ys = cells(s.inset(0), CELL)
    r = np.hypot(xs - c.x, ys - c.y)
    # squared, so the rings crowd close to the sun and the last one spreads wide
    tone = falloff(r - R_SUN, R_HALO - R_SUN, power=2)
    level = dither(tone, len(LAYERS), method="bayer", matrix=8)
    level[r < R_SUN] = len(LAYERS)
    # Each layer is drawn whole over the one outside it, so its runs carry on under the next
    # and only its own ring breaks into cells: about half the runs of one flat index grid.
    for k, paint in enumerate(LAYERS, start=1):
        grid_runs(s, (level >= k).astype(np.int64), [None, paint], CELL)
