"""A comb of bars; the light version adds a baseline under them."""

from walldye import ACCENT_3, FG_ALT, UI_HI, Canvas, P, design


@design(aspects=("16:9", "10:16"))
def draw(s: Canvas) -> None:
    bars = P()
    for k in range(12):
        x = s.w * (k + 1) / 13
        bars.M(x, s.h * 0.3).V(s.h * 0.7)
    s.stroke(bars, ACCENT_3, 6, cap="round")
    if s.light:
        s.stroke(P().M(0, s.h * 0.72).H(s.w), UI_HI, 2)
    else:
        s.fill(P().circle(s.center, 8), FG_ALT)
