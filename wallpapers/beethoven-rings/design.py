"""Concentric rings of beat-long arcs in a short-short-short-long rhythm, each started a beat after the last."""

from walldye import ACCENT, ACCENT_1, BG_ALT, UI_ALT, Canvas, P, design, ramp

LO, BEAT, BEATS = 200, 22.5, 12  # twelve beats make a three-quarter turn
R0, GROWTH = 48, 1.18  # ring k has radius R0 * GROWTH**k and a stroke a tenth of that
RINGS = 13
# One bar, "#" sounds and "." rests: three short notes, then a long one. Ring k starts it k
# beats late, so each ring's rests sit one beat further round than the ring inside it.
MOTIF = "#.#.#.#####."
LIT = 7  # the ring whose long note is lit
LEAD = ACCENT_1  # the innermost ring
TONES = ramp(UI_ALT, BG_ALT, RINGS + 1)  # the rest, quieter towards the outside


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: right of center; portrait: centered, low
    c = s.pick(landscape=(0.7, 0.6), portrait=(0.6, 0.56))
    s.fill(P().circle(c, 22), ACCENT)
    for k in range(1, RINGS + 1):
        r = R0 * GROWTH**k
        bar = MOTIF[-(k - 1) % len(MOTIF) :] + MOTIF[: -(k - 1) % len(MOTIF)]
        ring, lit = P(), P()
        b = 0
        while b < BEATS:
            if bar[b] == ".":
                b += 1
                continue
            e = b
            while e < BEATS and bar[e] == "#":
                e += 1
            span = (LO + b * BEAT, LO + e * BEAT)
            (lit if k == LIT and e - b > 1 else ring).arc(c, r, deg=span)
            b = e
        s.stroke(ring, LEAD if k == 1 else TONES[k], r * 0.1)
        s.stroke(lit, ACCENT, r * 0.1)
