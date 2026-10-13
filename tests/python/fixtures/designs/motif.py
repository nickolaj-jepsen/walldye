"""A disc and its ring as a motif a visitor may move, over a ground of its own."""

from walldye import ACCENT, UI, Canvas, P, design


@design(aspects="any")
def draw(s: Canvas) -> None:
    s.fill(P().rect(0, 0, s.w, 40), UI)
    c = s.pick(landscape=(0.6, 0.5), portrait=(0.5, 0.4))
    with s.motif(c, 130):
        s.fill(P().circle((0, 0), 100), ACCENT)
        s.stroke(P().circle((0, 0), 120), UI, 4)
