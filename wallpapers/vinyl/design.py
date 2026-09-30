"""An LP cut off by the screen edge: jittered concentric grooves in five tracks and a lead-out spiral."""

import math
from itertools import pairwise

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_5,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    P,
    Vec,
    design,
    lerp,
    mix,
    ramp,
    smoothstep,
)

R, LABEL, INNER = 700, 168, 230  # disc, label and innermost groove radii
LOCK = LABEL + 6  # the locked groove the lead-out settles into
PITCH = 3.5
GAPS = (325, 415, 500, 595)  # track gaps, from the inside out
# Per-track groove tone, BG_DEEP to BG_ALT; loud cuts read lighter.
TRACKS = tuple(mix(BG_DEEP, BG_ALT, t) for t in (0.8, 1.0, 0.7, 0.95, 0.85))
SHEEN = -135  # sheen axis in degrees; its twin points the opposite way
# Sheen steps as half-angles from the axis in degrees, brightest along it.
SHEEN_STEPS = (0, 2.5, 5, 8, 11, 14)
SHEEN_TONES = (UI_ALT, mix(UI, UI_ALT, 0.4), UI, mix(BG_ALT, UI, 0.5), mix(BG_ALT, UI, 0.2))
TONES = (*SHEEN_TONES, *TRACKS)
RUNOUT = ACCENT_5
# The lead-out warms from the inner track's tone to RUNOUT over its first 30 of 900 samples.
LEAD_CUTS = (0, 8, 16, 24, 30, 900)
LEAD_TONES = ramp(TRACKS[0], RUNOUT, len(LEAD_CUTS))[1:]


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: bleeding off the right edge and both long edges; portrait: off the bottom-right
    c = Vec(s.w - 360, 630) if s.landscape else Vec(s.w - 280, s.h - 400)
    rng = s.np_rng(3)
    radii = [
        r + rng.normal(0, 0.25)
        for r in np.arange(INNER, R - 20, PITCH)
        if min(abs(r - g) for g in GAPS) > 6
    ]

    s.fill(P().circle(c, R), BG_DEEP)
    # Every groove is split by angle: stepped sheen tones inside both wedges, its track tone between.
    half = SHEEN_STEPS[-1]
    with s.buckets(TONES, "stroke", stroke_width=1) as grooves:
        for r in radii:
            track = len(SHEEN_TONES) + sum(r > g for g in GAPS)
            for axis in (SHEEN, SHEEN + 180):
                for k, (h0, h1) in enumerate(pairwise(SHEEN_STEPS)):
                    grooves[k].arc(c, r, deg=(axis + h0, axis + h1))
                    grooves[k].arc(c, r, deg=(axis - h1, axis - h0))
                grooves[track].arc(c, r, deg=(axis + half, axis + 180 - half))
    s.stroke(P().circle(c, R - 1), mix(BG_ALT, UI, 0.4), 2)

    # Lead-out: leaves the innermost groove tangentially and eases into the locked groove over
    # three turns.
    t = np.linspace(0, 1, LEAD_CUTS[-1])
    rr = lerp(radii[0], LOCK, smoothstep(0, 1, t))
    a = math.radians(SHEEN + 90) + t * 6 * math.pi
    xy = c + np.column_stack([rr * np.cos(a), rr * np.sin(a)])
    for tone, (i0, i1) in zip(LEAD_TONES, pairwise(LEAD_CUTS), strict=True):
        s.stroke(P().poly(xy[i0 : i1 + 1]), tone, 1.1, cap="round")
    s.stroke(P().circle(c, LOCK), RUNOUT, 1.1)

    s.fill(P().circle(c, LABEL), ACCENT)
    s.stroke(P().circle(c, 132), ACCENT_1, 2)
    s.fill(P().circle(c, 9), BG)
