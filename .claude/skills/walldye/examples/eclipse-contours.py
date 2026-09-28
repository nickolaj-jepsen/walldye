"""Noise contour lines confined to a disc inside two rings: an fBm field traced by marching squares and clipped."""

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, ACCENT_4, BG, UI, Canvas, P, design, ladder
from walldye.field import iso_lines, sample_field

R, CELL = 330, 6  # disc radius; field sample spacing
LEVELS = [-0.3 + k * 0.035 for k in range(18)]
# one tone per level, skipping the near-background end of the ladder so every line reads
TONES = ladder((BG, ACCENT_4, ACCENT), len(LEVELS) + 4)[4:]


@design(aspects="any")
def draw(s: Canvas) -> None:
    # about 0.65 along the long axis (clear of the left-side windows on a desktop, below the
    # clock on a phone), centred on the short axis
    c = s.pick(landscape=(0.646, 0.5), portrait=(0.5, 0.6))
    noise = s.noise(7)
    # Sample only the disc's bounding box, relative to its centre, so every aspect shows the
    # same planet.
    half = int(np.ceil((R + 2 * CELL) / CELL))

    def height(i: NDArray[np.int64], j: NDArray[np.int64]) -> NDArray[np.float64]:
        dx, dy = (i - half) * CELL, (j - half) * CELL
        d = np.hypot(dx, dy) / R
        # the negative falloff past 0.85 R bunches the lines against the rim, like a limb
        return noise.fbm(2.95 + dx / 420, 1.29 + dy / 420, 4) - 0.9 * np.maximum(0.0, d - 0.85)

    field = sample_field(height, 2 * half, 2 * half)
    origin = c - (half * CELL, half * CELL)
    with s.clip() as disc:
        disc.add(P().circle(c, R))
    with (
        s.group(clip_path=disc.ref),
        s.buckets(TONES, "stroke", stroke_width=1.6, stroke_linejoin="round") as lines,
    ):
        for k, level in enumerate(LEVELS):
            for line in iso_lines(field, level, cell=CELL, origin=origin):
                if len(line) > 3:
                    lines[k].poly(line)
    s.stroke(P().circle(c, R + 18), UI, 2)
    s.stroke(P().circle(c, R), ACCENT, 3)
