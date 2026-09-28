"""Contour lines of an fBm noise field, traced by marching squares and clipped to a disc inside two rings."""

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, ACCENT_4, BG, UI, Canvas, P, Vec, design, ladder
from walldye.field import iso_lines, sample_field

R, CELL = 330, 6  # disc radius; field lattice spacing
# The noise-plane point under the disc centre. The lattice sits on multiples of CELL in that
# plane, so the 16:9 render samples the same field the 1920-wide original did.
PLANET = Vec(1240, 540)
LEVELS = [-0.3 + k * 0.035 for k in range(18)]
# one tone per level, skipping the near-background end of the ladder so every line reads
TONES = ladder((BG, ACCENT_4, ACCENT), len(LEVELS) + 4)[4:]


@design(aspects="any")
def draw(s: Canvas) -> None:
    # about 0.65 along the long axis (clear of left-side windows), below the clock on a phone
    c = s.pick(landscape=(PLANET.x / 1920, 0.5), portrait=(0.5, 0.6))
    noise = s.noise(7)
    # sample only the disc's box plus two cells, so every aspect shows the same planet
    reach = R + 2 * CELL
    x0, y0 = (PLANET.x - reach) // CELL * CELL, (PLANET.y - reach) // CELL * CELL
    n = int(np.ceil((PLANET.x + reach - x0) / CELL))

    def height(i: NDArray[np.int64], j: NDArray[np.int64]) -> NDArray[np.float64]:
        x, y = x0 + i * CELL, y0 + j * CELL
        d = np.hypot(x - PLANET.x, y - PLANET.y) / R
        # past 0.85 R the field falls away, bunching the lines against the rim like a limb
        return noise.fbm(x / 420, y / 420, 4) - 0.9 * np.maximum(0.0, d - 0.85)

    field = sample_field(height, n, n)
    origin = c - PLANET + (x0, y0)
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
