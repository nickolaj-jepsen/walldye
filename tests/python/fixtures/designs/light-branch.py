"""A disc on dark grounds and a square on light ones: a geometry branch on s.light."""

from walldye import ACCENT, FG, Canvas, P, design


@design()
def draw(s: Canvas) -> None:
    c = s.center
    if s.light:
        s.fill(P().rect(c.x - 100, c.y - 100, 200, 200), ACCENT)
    else:
        s.fill(P().circle(c, 100), ACCENT)
    s.stroke(P().M(0, s.h - 10).H(s.w), FG, 1)
