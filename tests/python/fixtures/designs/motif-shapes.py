"""A motif on a piece composed for two shapes only."""

from walldye import ACCENT, Canvas, P, design


@design(aspects=("16:9", "9:19.5"))
def draw(s: Canvas) -> None:
    with s.motif(s.center, 100):
        s.fill(P().circle((0, 0), 100), ACCENT)
