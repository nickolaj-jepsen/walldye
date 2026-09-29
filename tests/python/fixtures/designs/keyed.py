"""Bars merged into one path per color, keyed by the color itself."""

from walldye import ACCENT, MUTED, UI, Canvas, Color, P, Path, design


@design()
def draw(s: Canvas) -> None:
    paths: dict[Color, Path] = {}
    for i, color in enumerate([UI, MUTED, ACCENT, UI]):
        paths.setdefault(color, P()).rect(i * 100, 0, 50, s.h)
    for color, d in paths.items():
        s.fill(d, color)
