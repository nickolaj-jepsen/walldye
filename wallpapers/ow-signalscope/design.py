"""The Outer Wilds signalscope zoomed in on Riebeck's banjo: a lens with a numbered zoom arc, a lock ring, pixel-font readouts and a waveform traced from noise."""

from collections.abc import Callable

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    BG,
    BG_ALT,
    BG_DEEP,
    MUTED,
    UI_HI,
    Canvas,
    P,
    Paint,
    Vec,
    by_regime,
    design,
    polar,
)
from walldye.geom import Affine
from walldye.pixel import glyphs, text_width

# layout scaled from an in-game capture of the zoomed HUD (vignette r≈270 of a 505px frame)
VR, VIGNETTE = 500, 60  # lens radius; the vignette reaches the ground this far beyond it
AR, SPAN = 444, 46  # zoom arc radius, and its half-span in degrees about due west
HOOK, NUM_R = 15, 396  # hook at each end of the arc; radius of its numerals, clear of the hooks
ZOOM = 4  # the arc reads 1 at its bottom end to 7 at its top
BRACKET = 424  # side brackets, either side of the centre
LOCK, LOCK_R = Vec(74, -120), 58  # lock ring offset from the centre, and its radius
WAVE_Y, WAVE_HALF = 365, 248  # waveform box below the centre, and its half-width

# the ground round the lens sits a step away from the lens: deeper on dark themes, inkier on light
GROUND = by_regime(BG_DEEP, BG_ALT)

type TextPaint = Paint | Callable[[int, int, str], Paint | None]


def zoom_deg(i: int) -> float:
    """Screen angle of the zoom mark reading i + 1, climbing the arc from its bottom end."""
    return 180 - SPAN + 2 * SPAN * i / 6


def label(s: Canvas, text: str, paint: TextPaint, cx: float, y: float, px: int = 2) -> None:
    """One line of 5x8 text centred on cx, its origin rounded to a whole unit."""
    w = text_width(text, font="5x8", px=px, gap=1)
    glyphs(s, text, paint, at=(round(cx - w / 2), round(y)), font="5x8", px=px, gap=1)


@design(aspects="any", bg=GROUND)
def draw(s: Canvas) -> None:
    c = s.center

    # the lens, flat inside and darkening to the ground over its rim
    edge = s.radial_gradient([(0, BG), (0.9, BG), (1, GROUND)], c, VR + VIGNETTE)
    s.fill(P().circle(c, VR + VIGNETTE), edge)
    s.stroke(P().circle(c, VR), BG_ALT, 1.2)
    s.stroke(P().M(c.x, c.y - VR + 20).V(c.y + VR - 20), BG_ALT, 1)

    # zoom arc with a tick per level, its ends hooked inward like a bracket
    lo, hi = zoom_deg(0), zoom_deg(6)
    arc = P().arc(c, AR, deg=(lo, hi))
    for a, dy in ((hi, HOOK), (lo, -HOOK)):
        end = polar(c, AR, deg=a)
        arc.M(end).L(end + (HOOK, dy))
    for i in range(7):
        arc.M(polar(c, AR, deg=zoom_deg(i))).L(polar(c, AR - 11, deg=zoom_deg(i)))
    s.stroke(arc, UI_HI, 2, cap="round", join="round")
    for i in range(7):
        a = zoom_deg(i)
        n = polar(c, NUM_R, deg=a)
        with s.group(transform=Affine.rotate(deg=a - 180, about=n)):
            glyphs(s, str(i + 1), MUTED, at=(round(n.x - 7), round(n.y - 12)), font="5x8", px=3)

    # side brackets at mid-height; the zoom marker rides the left one
    brackets = P()
    for side in (-1, 1):
        brackets.M(c.x + side * BRACKET, c.y - 64).V(c.y + 64)
    s.stroke(brackets, UI_HI, 2.4)
    m = polar(c, AR - 22, deg=zoom_deg(ZOOM - 1)) + (0, 26)
    s.fill(P().poly([m + (4, -7), m + (14, 0), m + (4, 7), m + (8, 0)], closed=True), UI_HI)

    # lock ring around the banjo, its distance beneath, the frequency below both
    lock = c + LOCK
    s.stroke(P().circle(lock, LOCK_R), ACCENT, 4)
    s.fill(P().circle(lock, 3), ACCENT_3)
    label(s, "RIEBECK: 2180m", MUTED, lock.x, lock.y + 104, px=3)
    label(s, "FREQUENCY:", MUTED, c.x, c.y + 260)
    label(
        s,
        "< OUTER WILDS VENTURES >",
        lambda col, row, ch: MUTED if ch in "<>" else ACCENT_1,
        c.x,
        c.y + 282,
    )

    # waveform box: end caps and one irregular wave pinned to mid-cap at both ends
    y = c.y + WAVE_Y
    caps = P().M(c.x - WAVE_HALF, y - 20).V(y + 20).M(c.x + WAVE_HALF, y - 20).V(y + 20)
    s.stroke(caps, UI_HI, 3, cap="round")
    noise = s.noise(22)
    k = np.arange(0, 2 * WAVE_HALF + 1, 3)
    v = 0.5 * noise(k / 150, 0.3) + 0.35 * noise(k / 42, 4.7) + 0.15 * noise(k / 15, 9.1)
    env = np.minimum(1, np.minimum(k, 2 * WAVE_HALF - k) / 20)
    wave = np.column_stack([c.x - WAVE_HALF + k, y - 95 * v * env])
    s.stroke(P().spline(wave), ACCENT, 2.4, cap="round", join="round")
