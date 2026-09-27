"""Noise contour lines confined to a disc, with a crisp accent ring: fBm field + marching squares, clipped."""

import math

from walldye import ACCENT, UI, H, Noise, P, W, accent_ramp, contours, sample_field

ASPECTS = ["any"]

U = min(W, H) / 1080  # 1 unit of the 1080-tall reference design; scales every size and stroke
R = 330 * U
# Focal point ~0.65 along the long axis (clear of the left-side windows on a desktop,
# below the clock on a phone), centred on the short axis.
CX, CY = (0.646 * W, H / 2) if W >= H else (W / 2, 0.6 * H)


def draw(s):
    n = Noise(7)
    cell = 6 * U
    # Sample only the disc's bounding box, in disc-local units, so every aspect shows the same "planet".
    half = math.ceil((R + 2 * cell) / cell)
    ox, oy = CX - half * cell, CY - half * cell

    def f(i, j):
        dx, dy = (ox + i * cell - CX) / U, (oy + j * cell - CY) / U
        d = math.hypot(dx, dy) / 330
        # the negative falloff past 0.85 R bunches the rings against the rim, like a limb
        return n.fbm(2.95 + dx / 420, 1.29 + dy / 420, 4) - 0.9 * max(0.0, d - 0.85)

    field = sample_field(f, 2 * half, 2 * half)
    levels = [-0.3 + k * 0.035 for k in range(18)]
    tones = accent_ramp(len(levels) + 4)[4:]  # skip the near-background end so every line reads
    clip = s.clip(f'<circle cx="{CX:.1f}" cy="{CY:.1f}" r="{R:.1f}"/>')
    with s.g(clip_path=clip, fill="none", stroke_width=1.6 * U, stroke_linejoin="round"):
        for lvl, tone in zip(levels, tones):
            d = P()
            for line in contours(field, lvl, cell, ox, oy):
                if len(line) > 3:
                    d.poly(line)
            s.path(d, stroke=tone)
    s.circle(CX, CY, R + 18 * U, fill="none", stroke=UI, stroke_width=2 * U)
    s.circle(CX, CY, R, fill="none", stroke=ACCENT, stroke_width=3 * U)
