"""A motif whose ring is drawn at its canvas position, so it moves twice as far."""

from walldye import ACCENT, UI, Canvas, P, design


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(0.6, 0.5), portrait=(0.5, 0.4))
    with s.motif(c, 130):
        s.fill(P().circle((0, 0), 100), ACCENT)
        s.stroke(P().circle(c - (900, 400), 120), UI, 4)
