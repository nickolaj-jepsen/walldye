"""A PDP-11/70 front panel: octal-grouped lamp rows over paddle switches, one data word lit."""

from typing import Literal

from walldye import ACCENT, ACCENT_3, BG_ALT, UI, UI_ALT, UI_HI, Canvas, P, Vec, design
from walldye.pixel import glyphs, text_width

BITS = 22  # bits run leftwards from bit 0 in octal groups of three
ADDR, DATA = 0o17777707, 0o012700  # DATA is MOV #n, R0; the switches hold ADDR too
STATUS = ["RUN", "PAUSE", "MASTER", "USER", "SUPER", "KERNEL", "DATA", "16", "18", "22"]
LIT, DIM = ("RUN",), ("MASTER", "KERNEL", "22")
ROWS = ("ADDRESS", "DATA", "SWR")
FONT, PX = "5x8", 2
# Full-size panel geometry: lamp pitch, extra gap between octal groups, lamp radius, and the
# rows' offsets from the panel centre.
PITCH, GAP, R = 60, 15, 9
Y_STATUS, Y_ADDR, Y_DATA, Y_SW = -195, -85, 15, 155
LABEL_GAP = 40  # row labels end this far left of the top bit
# Width from the row labels' right edge to the last pivot.
SPAN = LABEL_GAP + (BITS - 1) * PITCH + (BITS - 1) // 3 * GAP + 16


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Full size on every landscape screen. A portrait screen narrows the pitch by u to fit its
    # width and shrinks lamps, switches and row spacing by the gentler k; text and line widths
    # stay put.
    label_w = text_width(ROWS[0], font=FONT, px=PX, gap=1) + 2
    u = min(1.0, (s.w - 2 * 72 - label_w) / SPAN)
    k = u**0.5
    # landscape: a touch left of the middle, bit 0 at x 1680 on 16:9; portrait: below the clock
    c = s.pick(landscape=(943.5 / 1920, 575 / 1080), portrait=(0.5, 0.56))
    right = c.x + (label_w + SPAN * u) / 2 - 16 * u  # x of bit 0

    def bx(b: int) -> float:
        """x of bit b."""
        return right - (b * PITCH + b // 3 * GAP) * u

    def row(y: float) -> float:
        return c.y + y * k

    def label(t: str, x: float, y: float, anchor: Literal["middle", "end"]) -> None:
        glyphs(s, t, UI_ALT, at=(round(x), round(y)), font=FONT, px=PX, gap=1, anchor=anchor)

    r = R * k
    brackets = P()
    for y in (row(Y_ADDR) + r + 13, row(Y_DATA) + r + 13):
        for g in range(0, BITS - 2, 3):  # full octal groups only; the lone top bit goes bare
            brackets.M(bx(g + 2) - 13 * u, y - 6).V(y).H(bx(g) + 13 * u).V(y - 6)
    s.stroke(brackets, UI_ALT, 1.2)

    lamps: dict[str, list[Vec]] = {"off": [], "ghost": [], "dim": [], "lit": []}
    # Status lamps spread evenly over the full grid width.
    step = (bx(0) - bx(BITS - 1)) / (len(STATUS) - 1)
    for i, name in enumerate(STATUS):
        at = Vec(bx(BITS - 1) + i * step, row(Y_STATUS))
        lamps["lit" if name in LIT else "dim" if name in DIM else "off"].append(at)
        label(name, at.x, at.y + r + 13, "middle")
    for b in range(BITS):
        lamps["dim" if ADDR >> b & 1 else "off"].append(Vec(bx(b), row(Y_ADDR)))
        # The data word is 16 bits; the unused high positions stay as ghosted sockets.
        kind = "ghost" if b >= 16 else "lit" if DATA >> b & 1 else "off"
        lamps[kind].append(Vec(bx(b), row(Y_DATA)))
    s.stroke(P().dots(lamps["lit"], r + 6 * k), ACCENT_3, 2.4)
    s.stroke(P().dots(lamps["ghost"], r), BG_ALT, 1.5)
    s.stroke(P().dots(lamps["off"], r), UI_ALT, 1.5)
    s.fill(P().dots(lamps["dim"], r), UI_HI)
    s.fill(P().dots(lamps["lit"], r), ACCENT)

    # Paddles pivot on one line, up for 1 and down for 0; the tone alternates per octal group.
    tones, pivot = (P(), P()), P()
    axis = row(Y_SW)
    for b in range(BITS):
        x = bx(b) - 11 * u
        pivot.M(x - 5 * u, axis).H(x + 27 * u)
        top = axis - (50 if ADDR >> b & 1 else 5) * k
        tones[b // 3 % 2].rrect(x, top, 22 * u, 55 * k, 4 * u)
    s.stroke(pivot, UI_ALT, 1.2)
    s.fill(tones[0], UI_ALT)
    s.fill(tones[1], UI)

    for name, y in zip(ROWS, (Y_ADDR, Y_DATA, Y_SW), strict=True):
        label(name, bx(BITS - 1) - LABEL_GAP * u - 2, row(y) - 8, "end")
