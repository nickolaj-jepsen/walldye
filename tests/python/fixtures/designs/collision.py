"""Two roles that land on one fireproof hex: a bg-fg midpoint and an accent mix with a constant."""

from walldye import ACCENT, BG, FG, H, W, mix


def draw(s):
    s.rect(0, 0, W / 2, H, fill=mix(BG, FG, 0.5))
    # Under fireproof this equals the midpoint above; under any other theme it does not.
    s.rect(W / 2, 0, W / 2, H, fill=mix(ACCENT, "#278A9C", 0.5))
