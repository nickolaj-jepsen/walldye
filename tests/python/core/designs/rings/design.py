"""Rings around an offset disc over a strip of bucketed squares and a graded bar."""

from walldye import (
    ACCENT,
    ACCENT_4,
    BG,
    BG_ALT,
    MUTED,
    UI,
    Canvas,
    P,
    by_regime,
    design,
    ladder,
    mix,
)

TONES = ladder((ACCENT_4, UI, BG_ALT), 5)
STRUCT = by_regime(UI, MUTED)


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(0.62, 0.5), portrait=(0.5, 0.4))
    rings = P()
    for k in range(1, 9):
        rings.circle(c, 40 * k)
    s.stroke(rings, STRUCT, 1.5)
    with s.buckets(TONES, "fill", fill_opacity=0.8) as b:
        for i in range(20):
            b[i % len(TONES)].rect(20 + i * 30, 40, 20, 20)
    s.fill(P().circle(c, 12), ACCENT)
    fade = mix(ACCENT, BG, 0.5)
    bar = s.linear_gradient([(0, ACCENT), (0.5, fade, 0.8), (1, BG)], (0, 0), (s.w, 0))
    s.fill(P().rect(0, s.h - 40, s.w, 40), bar)
    with s.group(opacity=0.5, stroke=UI, stroke_width=2):
        s.fill(P().ngon(c, 200, 6, bearing=0), "none")
