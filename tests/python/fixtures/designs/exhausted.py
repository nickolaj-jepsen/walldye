"""A bar one step wider on each draw, until the steps run out."""

from walldye import ACCENT, Canvas, P, design

CALLS: list[int] = []


@design()
def draw(s: Canvas) -> None:
    calls = CALLS  # an alias the mutation lint cannot follow
    calls.append(len(calls))
    if len(calls) > 3:
        raise RuntimeError("out of steps")
    s.fill(P().rect(0, 0, 100 * len(calls), 50), ACCENT)
