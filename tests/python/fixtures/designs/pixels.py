"""Pixel cells anchored off the whole-unit grid, on every screen shape."""

from walldye import ACCENT, Canvas, P, design


@design(aspects="any")
def draw(s: Canvas) -> None:
    o = s.frac(0.37, 0.41)
    cells = P().rect(o.x, o.y, 3, 3).rect(o.x + 6, o.y, 3, 3).rect(o.x + 3, o.y + 3, 3, 3)
    s.pixel_path(cells, ACCENT, cell=3, origins=[o])
