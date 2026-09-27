"""Bars merged into one path per colour, keyed by the colour itself."""

from walldye import ACCENT, MUTED, UI, Canvas, Colour, P, Path, design


@design()
def draw(s: Canvas) -> None:
    paths: dict[Colour, Path] = {}
    for i, colour in enumerate([UI, MUTED, ACCENT, UI]):
        paths.setdefault(colour, P()).rect(i * 100, 0, 50, s.h)
    for colour, d in paths.items():
        s.fill(d, colour)
