"""Patent plan of a Minecraft redstone line on a block grid: lever, dust, repeater and lamp, the dust a step fainter per block."""

import math

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_4,
    ACCENT_6,
    BG_ALT,
    MUTED,
    UI,
    UI_HI,
    Canvas,
    P,
    Path,
    Vec,
    design,
    ladder,
    polar,
)
from walldye.pixel import glyphs

B = 44  # one block
COLS, ROWS = 36, 7
X0, Y0 = (1920 - COLS * B) // 2, (1080 - ROWS * B) // 2
WY = Y0 + ROWS * B // 2  # the wire's centre line
HEAVY = (1, 17, 33)  # 16-block rhythm: lever + 15 dust, repeater + 15 dust, then the dead block
LEVELS = ladder((ACCENT_6, ACCENT_4, ACCENT), 16)  # power 0 to 15; level-0 dust still shows in game
T = 38 / 16  # one texel of the vanilla 16 px models, drawn inside a 38 px block
GAP = 1  # hairline seam so each block's level stays legible while the dust reads continuous


def cx(k: int) -> float:
    """Centre x of block `k` of the line; the +1 centres the 34-block line on the 36-block plate."""
    return X0 + B * (k + 1) + B / 2


def leader(d: Path, x: float, top: float) -> None:
    """Adds to `d` a leader from just above the wire at `x` up to `top`, with a tick at each end."""
    d.M(x + 0.5, WY - 14).V(top).M(x - 5, top + 0.5).H(x + 6).M(x - 3, WY - 13.5).H(x + 4)


def lever(s: Canvas, x: float) -> None:
    # lever.json: 6x8-texel cobblestone base, 2x10 stick tilted 45 deg along the long axis (here the wire)
    s.stroke(P().rect(x - 4 * T, WY - 3 * T, 8 * T, 6 * T), UI_HI, 2, join="round")
    s.stroke(P().M(x, WY).H(x + 10 * T * math.cos(math.radians(45))), UI_HI, 2 * T)


def repeater(s: Canvas, x: float) -> None:
    # repeater_1tick.json, output facing +x: fixed torch 2-4 texels from the output edge, delay torch
    # at 6-8, the lit strip back to the input edge; powered, so torches and strip are all lit
    s.stroke(P().rrect(x - 8 * T, WY - 8 * T, 16 * T, 16 * T, 2), UI_HI, 2)
    out = x + 8 * T
    s.fill(P().rect(out - 14 * T, WY - T / 2, 8 * T, T), ACCENT_2)
    torches = P()
    for a in (2, 6):
        torches.rect(out - (a + 2) * T, WY - T, 2 * T, 2 * T)
    s.fill(torches, ACCENT)


def lamp(s: Canvas, x: float) -> None:
    # redstone_lamp.png, unlit: a frame, a diamond lattice meeting short spokes at the edge midpoints
    c = Vec(x, WY)
    h, v = 8 * T, 4.75 * T
    s.stroke(P().rect(x - h, WY - h, 2 * h, 2 * h), UI_HI, 2)
    lattice = P().ngon(c, v, 4, bearing=0)
    for b in range(0, 360, 90):
        lattice.M(polar(c, h, bearing=b)).L(polar(c, v, bearing=b))
    s.stroke(lattice, UI_HI, 1.5, join="miter")


@design()
def draw(s: Canvas) -> None:
    x1, y1 = X0 + COLS * B, Y0 + ROWS * B
    plate, heavy = P(), P()
    for c in range(COLS + 1):
        (heavy if c in HEAVY else plate).M(X0 + c * B + 0.5, Y0).V(y1)
    for r in range(ROWS + 1):
        plate.M(X0, Y0 + r * B + 0.5).H(x1)
    s.stroke(plate, BG_ALT, 1)
    s.stroke(heavy, UI, 1)

    # the lever powers blocks 1-15 from 15 down to 1; the repeater restarts 17-32 from 15 down to 0
    with s.buckets(LEVELS, "stroke", stroke_width=6, stroke_linecap="butt") as dust:
        for first, n in ((1, 15), (17, 16)):
            for i in range(n):
                x = cx(first + i)
                dust[15 - i].M(x - B / 2 + GAP / 2, WY).H(x + B / 2 - GAP / 2)

    lever(s, cx(0))
    repeater(s, cx(16))
    lamp(s, cx(33))

    leaders = P()
    for k, label in ((1, "15"), (32, "0")):
        leader(leaders, cx(k), WY - 64)
        glyphs(s, label, MUTED, at=(cx(k) + 1, WY - 88), font="5x8", px=2, anchor="middle")
    s.stroke(leaders, UI, 1)
