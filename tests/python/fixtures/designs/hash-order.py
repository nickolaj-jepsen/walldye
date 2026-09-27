"""Bars laid out in the iteration order of a set of names, which PYTHONHASHSEED decides."""

from walldye import UI, H

NAMES = {f"bar{i}" for i in range(24)}


def draw(s):
    for i, name in enumerate(NAMES):
        s.rect(i * 60, 0, 10 + int(name[3:]), H, fill=UI)
