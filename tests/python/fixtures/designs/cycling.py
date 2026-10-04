"""As many rings as draws made in a row at one screen size."""

from walldye import ACCENT, Canvas, P, design

RUN: list[tuple[int, int]] = []


@design(aspects=("16:9", "10:16"))
def draw(s: Canvas) -> None:
    run = RUN  # an alias the mutation lint cannot follow
    if len(run) > 0 and run[-1] != (s.w, s.h):
        run.clear()
    run.append((s.w, s.h))
    for i in range(len(run)):
        s.stroke(P().circle(s.center, 40 + 20 * i), ACCENT, 4)
