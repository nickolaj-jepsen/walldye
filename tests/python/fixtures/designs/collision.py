"""Two roles that land on one fireproof hex: a step of the ramp and a mix of two others."""

from walldye import BLACK, MUTED, UI_HI, Canvas, P, design, mix


@design()
def draw(s: Canvas) -> None:
    s.fill(P().rect(0, 0, s.w / 2, s.h), UI_HI)
    # Under fireproof this mix equals UI_HI; under any other theme it does not.
    s.fill(P().rect(s.w / 2, 0, s.w / 2, s.h), mix(BLACK, MUTED, 0.6))
