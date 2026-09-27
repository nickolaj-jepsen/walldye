"""Markup the templates may not hold: font text and a filter."""

from walldye import FG, UI, W


def draw(s):
    s.defs('<filter id="soft"><feGaussianBlur stdDeviation="2"/></filter>')
    s.rect(0, 0, W, 10, fill=UI, filter="url(#soft)")
    s.text(10, 50, "hello", fill=FG)
