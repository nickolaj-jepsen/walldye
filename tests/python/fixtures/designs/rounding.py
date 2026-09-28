"""Eighteen nested mixes, each rounded, drifting past what their exact coefficients predict."""

from walldye import ACCENT, ACCENT_HI, BG, FG, FG_ALT, MUTED, UI, UI_HI, Canvas, P, design, mix

STEPS = (ACCENT, UI, MUTED, ACCENT_HI, FG_ALT, UI_HI) * 3


@design()
def draw(s: Canvas) -> None:
    c = mix(BG, FG, 0.5)
    for step in STEPS:
        c = mix(c, step, 0.02)
    s.fill(P().rect(0, 0, s.w, s.h), c)
