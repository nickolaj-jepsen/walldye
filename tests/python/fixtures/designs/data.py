"""Dots at points read from a data file."""

from walldye import ACCENT, Canvas, P, design


@design()
def draw(s: Canvas) -> None:
    points: list[list[float]] = s.data("points.json")
    s.fill(P().dots(points, 12), ACCENT)
