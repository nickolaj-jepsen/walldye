"""Alex's radio dial from Oxenfree tuned to 98.0: ticks and monoline numerals fanned along radii from a pivot below the screen, with a fixed hairline over a soft glow."""

import math

from walldye import (
    ACCENT,
    ACCENT_4,
    BG,
    MUTED,
    UI_HI,
    Canvas,
    P,
    Path,
    Vec,
    design,
    ladder,
    mix,
    polar,
)
from walldye.geom import Affine

TICK = mix(UI_HI, MUTED, 0.2)
NUM = mix(UI_HI, MUTED, 0.5)
GLOW = ladder((BG, ACCENT_4, ACCENT), 8)  # the accent ladder; rungs 3 and 5 light the lock

# Fan geometry measured from in-game frames: brackets are radii ±14.5° from a pivot ~2 dial-widths
# below, top/bottom width ≈ 1.35, about 3.4 MHz visible, three ticks per MHz.
R_BOT, R_TOP = 1120, 1490
R_MID = (R_BOT + R_TOP) / 2  # centre of the glow, which the layout places
HALF = 14.5  # bracket bearing, degrees
DEG_PER_MHZ = 8.5
LOCK = 98.0
R_LABEL = 1400
DH = 58  # numeral height
DW = DH * 0.56
GAP = DW * 0.35  # between the numerals of one label


def digit(p: Path, ch: str, x: float, y: float) -> None:
    """Add the thin monoline numeral `ch` (the game's dial font) to `p`, top-left at (x, y).

    Only 0, 1, 6, 7, 8 and 9 are drawn; any other character adds nothing.
    """
    w, h = DW, DH
    if ch == "0":
        p.ellipse((x + w / 2, y + h / 2), w / 2, h / 2)
    elif ch == "1":
        p.M(x + w * 0.2, y + h * 0.16).L(x + w * 0.55, y).V(y + h)
    elif ch == "7":
        p.M(x, y).H(x + w).L(x + w * 0.3, y + h)
    elif ch == "8":
        p.ellipse((x + w / 2, y + h * 0.24), w * 0.42, h * 0.24)
        p.ellipse((x + w / 2, y + h * 0.73), w / 2, h * 0.27)
    elif ch == "9":
        p.ellipse((x + w / 2, y + h * 0.3), w / 2, h * 0.3)
        p.M(x + w, y + h * 0.3).Q(x + w, y + h * 0.7, x + w * 0.45, y + h)
    elif ch == "6":
        p.ellipse((x + w / 2, y + h * 0.7), w / 2, h * 0.3)
        p.M(x, y + h * 0.7).Q(x, y + h * 0.3, x + w * 0.55, y)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape keeps the 16:9 original's placement; portrait lifts the dial a little
    glow = s.pick(landscape=(0.5, 545 / 1080), portrait=(0.5, 0.45))
    c = glow + (0, R_MID)  # pivot of the fan, far below the screen
    h = R_TOP - R_BOT

    def at(r: float, b: float) -> Vec:
        return polar(c, r, bearing=b)

    # lock glow: a flat horizontal wash behind numerals and ticks, the only accent event
    wash = s.radial_gradient(
        [(0, GLOW[5], 0.5), (0.5, GLOW[3], 0.22), (1, GLOW[3], 0)], (0.5, 0.5), 0.5, units="bbox"
    )
    s.fill(P().ellipse(glow, 560, 230), wash)

    # labels are set upright above the pivot, then turned onto their radius
    for f in range(math.floor(LOCK - 2.5), math.ceil(LOCK + 2.5)):
        b = (f - LOCK) * DEG_PER_MHZ
        if abs(b) > HALF - 2:
            continue
        label = str(f)
        w = len(label) * DW + (len(label) - 1) * GAP
        glyphs = P()
        for i, ch in enumerate(label):
            digit(glyphs, ch, c.x - w / 2 + i * (DW + GAP), c.y - R_LABEL - DH)
        with s.group(transform=Affine.rotate(deg=b, about=c)):
            s.stroke(glyphs, NUM, 11, cap="round", opacity=0.08)
            s.stroke(glyphs, NUM, 4.5, cap="round", join="round")

    rnd = s.rng(979)
    ticks = P()
    for k in range(math.floor((LOCK - 2) * 3), math.ceil((LOCK + 2) * 3) + 1):
        b = (k / 3 - LOCK) * DEG_PER_MHZ
        if abs(b) > HALF - 1.2:
            continue
        ln = 0.42 * h if k % 3 == 0 else 0.26 * h * rnd.uniform(0.85, 1.25)
        ln *= 1 - 0.25 * (abs(b) / HALF) ** 2  # ticks shorten toward the brackets
        ticks.M(at(R_BOT + 12, b)).L(at(R_BOT + 12 + ln, b))

    brackets = P()
    for b in (-HALF, HALF):
        brackets.M(at(R_BOT - 12, b)).L(at(R_TOP, b))

    # soft bloom under the brighter neon strokes
    s.stroke(brackets, TICK, 16, cap="round", opacity=0.12)
    s.stroke(ticks, TICK, 14, cap="round", opacity=0.1)
    s.stroke(brackets, TICK, 6, cap="round")
    s.stroke(ticks, TICK, 5, cap="round")

    # fixed hairline: from just above the bracket tops down to the tick baseline
    needle = P().M(at(R_TOP - 25, 0)).L(at(R_BOT + 12, 0))
    s.stroke(needle, GLOW[5], 12, cap="round", opacity=0.45)
    s.stroke(needle, ACCENT, 3.5)
