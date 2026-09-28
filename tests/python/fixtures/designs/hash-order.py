"""Bars laid out in the iteration order of a set of names, which PYTHONHASHSEED decides."""

from walldye import UI, Canvas, P, design

NAMES = {f"bar{i}" for i in range(24)}


@design()
def draw(s: Canvas) -> None:
    bars = P()
    for i, name in enumerate(NAMES):
        bars.rect(i * 60, 0, 10 + int(name[3:]), s.h)
    s.fill(bars, UI)
