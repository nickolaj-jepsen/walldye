"""RFC 791's IPv4 header diagram in Spleen pixel type, with the Time to Live field lit as one hop."""

from walldye import ACCENT, ACCENT_3, BG_ALT, UI, UI_ALT, UI_HI, Canvas, Colour, design, mix
from walldye.pixel import glyphs

SEP = "+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+"
DIAGRAM = [
    " 0                   1                   2                   3",
    " 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1",
    SEP,
    "|Version|  IHL  |Type of Service|          Total Length         |",
    SEP,
    "|         Identification        |Flags|      Fragment Offset    |",
    SEP,
    "|  Time to Live |    Protocol   |         Header Checksum       |",
    SEP,
    "|                       Source Address                          |",
    SEP,
    "|                    Destination Address                        |",
    SEP,
    "|                    Options                    |    Padding    |",
    SEP,
]
TTL_ROW, TTL_COLS = 7, range(17)
NOTE = "64 -> 63"
PX = 2
CW, CH = 8 * PX, 16 * PX  # one 8x16 character cell
DIM, RULE = mix(BG_ALT, UI, 0.5), mix(BG_ALT, UI, 0.75)
TEXT = mix(UI_ALT, UI_HI, 0.3)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Landscape: the diagram's left edge at the figure's vertical centre, the note in the margin
    # beside the TTL row. Portrait leaves only 40 px around the 32-bit rows, so they are centred
    # and the note moves under the caption.
    at = s.pick(landscape=(0.3125, 0.5), portrait=(0.5, 0.46), snap=PX)
    last = len(DIAGRAM) + 1  # the "Figure 4." row
    if s.landscape:
        x0 = min(at.x, s.w - len(SEP) * CW - 240)  # 16:10 would leave too little on the right
        y0 = at.y - 7.5 * CH  # the figure runs from y0 - 2 * CH to y0 + 17 * CH
        note = (x0 - (len(NOTE) + 1) * CW, y0 + TTL_ROW * CH)
    else:
        x0 = at.x - len(SEP) * CW / 2
        y0 = at.y - 8.5 * CH  # the figure runs from y0 - 2 * CH to y0 + 19 * CH
        note = (x0, y0 + (last + 2) * CH)

    def colour(c: int, r: int, ch: str) -> Colour:
        in_ttl = c in TTL_COLS and abs(r - TTL_ROW) <= 1
        if r < 2:
            return RULE
        if ch in "+-|":
            return ACCENT_3 if in_ttl else RULE
        return ACCENT if in_ttl else TEXT

    glyphs(s, DIAGRAM, colour, at=(x0, y0), px=PX)
    glyphs(s, "3.1.  Internet Header Format", DIM, at=(x0, y0 - 2 * CH), px=PX)
    glyphs(s, "Figure 4.", DIM, at=(x0, y0 + last * CH), px=PX)
    glyphs(s, NOTE, lambda c, r, ch: ACCENT if c > 5 else DIM, at=note, px=PX)  # lit: the new value
