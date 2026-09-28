"""Müller-Brockmann's Beethoven poster as a score: concentric rings cut into beat-long arcs, rests left open."""

import re

from walldye import ACCENT, ACCENT_1, BG_ALT, UI_ALT, Canvas, P, design, ramp

LO, BEAT = 150, 22.5  # eight beats = a half-turn, so every ring is cut on one diagonal
R0, GROWTH = 48, 1.2  # ring k has radius R0 * GROWTH**k and a stroke a tenth of that
# The score, inner to outer: "#" sounds, "*" is the one lit beat, "." rests. Beat 3 rests on
# every toned ring, leaving one radial spoke of open space; the outer rings drop their last
# beats so the silhouette closes on the upper left.
SCORE = (
    "########",
    "########",
    "###.####",
    "###.##..",
    ".##.####",
    "###.####",
    "###..*..",
    "###.####",
    ".##.##..",
    "###.##..",
    ".##.##..",
    "###.....",
)
LEAD = (ACCENT, ACCENT_1)  # the two innermost rings
TONES = ramp(UI_ALT, BG_ALT, len(SCORE) + 1)  # the rest, quieter towards the outside


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: right of centre at 16:9's (1400, 720); portrait: the fan's box centred, low
    c = s.pick(landscape=(35 / 48, 2 / 3), portrait=(0.63, 0.56))
    s.fill(P().arc_band(c, 0, 38, deg=(LO, LO + 180)), ACCENT)
    for k, bar in enumerate(SCORE, 1):
        r = R0 * GROWTH**k
        ring, lit = P(), P()
        for m in re.finditer(r"#+|\*+", bar):
            span = (LO + m.start() * BEAT, LO + m.end() * BEAT)
            (lit if m.group()[0] == "*" else ring).arc(c, r, deg=span)
        s.stroke(ring, LEAD[k - 1] if k <= len(LEAD) else TONES[k], r * 0.1)
        s.stroke(lit, ACCENT_1, r * 0.1)
