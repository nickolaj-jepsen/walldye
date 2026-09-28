"""Fixture: a v1 walldye (M1) design with ASPECTS, the short-side unit and is_light()."""

from walldye import ACCENT, BG_ALT, UI, H, P, W, is_light, rng

ASPECTS = ["any"]

U = min(W, H) / 1080
R = 300 * U


def draw(s):
    cx, cy = (W * 0.7, H / 2) if W > H else (W / 2, H * 0.6)
    edge = UI if is_light() else BG_ALT
    s.circle(cx, cy, R, fill="none", stroke=edge, stroke_width=2 * U)
    r = rng(5)
    for _ in range(12):
        s.circle(cx + r.uniform(-R, R), cy + r.uniform(-R, R), 4 * U, fill=ACCENT)
    if is_light():
        s.path(P().M(0, 0).L(W, H), fill="none", stroke=UI, stroke_width=U)
