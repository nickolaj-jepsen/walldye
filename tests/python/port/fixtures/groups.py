"""Fixture: groups whose fill moves onto their children, transforms, clips and gradients."""

from wallgen import ACCENT, BG, UI, UI_ALT, H, P, W


def tick(s, x):
    s.path(P().M(x, 0).V(20))


def draw(s):
    with s.g(fill="none", stroke=UI, stroke_width=2):
        s.circle(400, 400, 100)
        s.path(P().M(0, 0).L(100, 100), stroke=ACCENT)
        tick(s, 50)
    with s.g(fill=UI_ALT, transform=f"translate({W / 2} {H / 2}) rotate(15)"):
        s.rect(-50, -50, 100, 100)
        s.rect(60, -50, 40, 40, fill=ACCENT)
    grad = s.linear_gradient([(0, BG), (1, ACCENT, 0.5)], 0, 0, W, 0, units="userSpaceOnUse")
    glow = s.radial_gradient([(0, ACCENT), (1, BG)])
    s.rect(0, H - 200, W, 200, fill=grad)
    s.circle(W / 2, 300, 80, fill=glow)
    clip = s.clip(f'<circle cx="{W / 2}" cy="{H / 2}" r="200"/>')
    with s.g(clip_path=clip):
        s.rect(0, 0, W, H, fill=UI_ALT, opacity=0.5)
    edge = P()
    if edge.parts:
        s.path(edge, fill=UI)
