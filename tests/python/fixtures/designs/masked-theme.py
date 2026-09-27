"""A mask painted with a theme token: its coverage would change with the theme."""

from walldye import ACCENT, FG, H, W


def draw(s):
    with s.g(mask=s.mask(f'<rect width="{W}" height="{H}" fill="{FG}"/>')):
        s.rect(0, 0, W, H, fill=ACCENT)
