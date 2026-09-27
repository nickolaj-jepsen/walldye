"""A fade mask: its #fff/#000 gradient stops and shapes are constant slots, which masks allow."""

from walldye import ACCENT, UI, H, W


def draw(s):
    fade = s.linear_gradient([(0, "#000"), (1, "#fff")])
    mask = s.mask(f'<rect width="{W}" height="{H}" fill="{fade}"/><circle cx="{W / 2}" cy="{H / 2}" r="100" fill="black"/>')
    with s.g(mask=mask):
        s.rect(0, 0, W, H, fill=ACCENT)
    s.circle(W / 2, H / 2, 50, fill=UI)
