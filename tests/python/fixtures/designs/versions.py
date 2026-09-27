"""A disc on a ring, placed by the hour; two more versions show other hours."""

from walldye import ACCENT, UI, Canvas, P, Params, design, knob, polar


class Clock(Params):
    hour: float = knob(default=2, lo=0, hi=12, unit="h", doc="where the disc sits")
    ring: bool = knob(default=True, doc="the ring behind the disc")


VARIANTS = {"late": Clock(hour=8), "bare": Clock(hour=5, ring=False, seed=3)}


@design(aspects=("16:9", "10:16"), variants=VARIANTS)
def draw(s: Canvas[Clock]) -> None:
    p = s.params
    c = s.center
    if p.ring:
        s.stroke(P().circle(c, 300), UI, 4)
    r = 300 + s.rng(1).uniform(-10, 10)
    s.fill(P().circle(polar(c, r, bearing=p.hour * 30), 120), ACCENT)
