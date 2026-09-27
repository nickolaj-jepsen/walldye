"""Bars merged into one path per colour value, so roles that share a hex also share a path."""

from walldye import ACCENT, MUTED, UI, H, P


def draw(s):
    paths = {}
    for i, colour in enumerate([UI, MUTED, ACCENT, UI]):
        paths.setdefault(colour, P()).M(i * 100, 0).H(i * 100 + 50).V(H).H(i * 100).Z()
    for colour, d in paths.items():
        s.path(d, fill=colour)
