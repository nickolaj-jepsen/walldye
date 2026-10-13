"""A motif that draws past the extent it declares."""

from walldye import ACCENT, Canvas, P, design


@design(aspects="any")
def draw(s: Canvas) -> None:
    with s.motif(s.center, 60):
        s.fill(P().circle((0, 0), 100), ACCENT)
