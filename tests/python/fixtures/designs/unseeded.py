"""A disc placed by the unseeded global random generator."""

import random

from walldye import ACCENT, Canvas, P, design


@design()
def draw(s: Canvas) -> None:
    s.fill(P().circle((random.uniform(0, s.w), s.h / 2), 50), ACCENT)
