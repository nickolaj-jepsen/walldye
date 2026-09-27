"""A fade mask: its gradient stops and shapes are constant slots, which masks allow."""

from walldye import ACCENT, MASK_BLACK, MASK_WHITE, UI, Canvas, P, design


@design()
def draw(s: Canvas) -> None:
    c = s.center
    with s.mask() as m:
        fade = m.linear_gradient([(0, MASK_BLACK), (1, MASK_WHITE)], (0, 0), (s.w, 0))
        m.fill(P().rect(0, 0, s.w, s.h), fade)
        m.fill(P().circle(c, 100), MASK_BLACK)
    with s.group(mask=m.ref):
        s.fill(P().rect(0, 0, s.w, s.h), ACCENT)
    s.fill(P().circle(c, 50), UI)
