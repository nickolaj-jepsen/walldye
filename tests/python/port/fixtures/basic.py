"""Fixture: a v1 nixos design using elements, paths, W/H and the path builder."""

import math

from wallgen import ACCENT, BG_ALT, UI, UI_HI, H, P, W, accent_ramp, mix, polar

CX, CY = W * 0.6, H / 2
R = 300
TONES = accent_ramp(5)
DASH = "8 6"


def spoke(a):
    return polar(CX, CY, R, math.radians(a))


def draw(s):
    s.rect(0, 0, W, H, fill=BG_ALT)
    s.circle(CX, CY, R, fill="none", stroke=UI, stroke_width=2)
    s.circle(*spoke(30), 6, fill=ACCENT)
    s.circle(CX, CY, min(*spoke(45), R), fill="none", stroke=UI, stroke_width=1)
    s.rect(40, 40, 200, 120, rx=12, fill="none", stroke=UI_HI, stroke_width=1.5)
    s.line(0, H - 40, W, H - 40, stroke=UI, stroke_width=1, stroke_dasharray=DASH)
    s.polyline([(10, 10), (60, 30), (110, 10)], stroke=UI_HI, stroke_width=1.2)
    s.polygon([(W - 100, 60), (W - 40, 60), (W - 70, 110)], fill=mix(UI, ACCENT, 0.5))
    rays = P()
    for a in range(0, 360, 30):
        rays.M(CX, CY).L(*spoke(a))
    s.path(rays, fill="none", stroke=UI, stroke_width=1, stroke_dasharray="4 4")
    s.path(rays, stroke=UI_HI)
    arc = P().M(*spoke(0)).A(R, R, 0, int(True), 1, *spoke(90))
    s.path(arc, fill="none", stroke=ACCENT, stroke_width=3, stroke_linecap="round")
    for i, tone in enumerate(TONES):
        wave = P().smooth([(100 + 40 * k, 800 + 20 * i + 10 * (k % 2)) for k in range(12)])
        s.path(wave, fill="none", stroke=tone, stroke_width=f"{1 + i / 2:.1f}")
    s.path(P().poly(zip([500, 560, 620], [900, 950, 900])), fill=UI)
