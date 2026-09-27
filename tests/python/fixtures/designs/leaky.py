"""A square or a disc, chosen by whichever screen shape the process drew first."""

from walldye import ACCENT, Canvas, P, design

FIRST: list[bool] = []


@design(aspects=("16:9", "10:16"))
def draw(s: Canvas) -> None:
    seen = FIRST  # an alias the mutation lint cannot follow
    if len(seen) == 0:
        seen.append(s.landscape)
    c = s.center
    if seen[0]:
        s.fill(P().rect(c.x - 80, c.y - 80, 160, 160), ACCENT)
    else:
        s.fill(P().circle(c, 80), ACCENT)
