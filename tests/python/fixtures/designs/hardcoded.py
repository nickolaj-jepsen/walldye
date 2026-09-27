"""A band in a fixed colour outside any mask: a hardcoded slot."""

from walldye import UI, H, W


def draw(s):
    s.rect(0, 0, W, H / 2, fill=UI)
    s.rect(0, H / 2, W, H / 2, fill="#FF0000")
