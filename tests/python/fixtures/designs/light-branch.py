"""A disc on dark grounds and a square on light ones: a geometry branch under is_light()."""

from walldye import ACCENT, FG, H, W, is_light


def draw(s):
    if is_light():
        s.rect(W / 2 - 100, H / 2 - 100, 200, 200, fill=ACCENT)
    else:
        s.circle(W / 2, H / 2, 100, fill=ACCENT)
    s.line(0, H - 10, W, H - 10, stroke=FG)
