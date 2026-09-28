"""Header diagrams from early RFCs in Spleen pixel type, with one field lit and a short note beside it."""

from dataclasses import dataclass
from typing import Literal

from walldye import (
    ACCENT,
    ACCENT_3,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    Params,
    design,
    knob,
    mix,
)
from walldye.pixel import glyphs

# The diagrams are copied character for character from the RFC text, less their indent.
SEP = "+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+"
BITS = [
    " 0                   1                   2                   3",
    " 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1",
]
IP = [  # RFC 791, Figure 4
    *BITS,
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
TCP = [  # RFC 793, Figure 3
    *BITS,
    SEP,
    "|          Source Port          |       Destination Port        |",
    SEP,
    "|                        Sequence Number                        |",
    SEP,
    "|                    Acknowledgment Number                      |",
    SEP,
    "|  Data |           |U|A|P|R|S|F|                               |",
    "| Offset| Reserved  |R|C|S|S|Y|I|            Window             |",
    "|       |           |G|K|H|T|N|N|                               |",
    SEP,
    "|           Checksum            |         Urgent Pointer        |",
    SEP,
    "|                    Options                    |    Padding    |",
    SEP,
    "|                             data                              |",
    SEP,
]
OCTETS = "+--------+--------+--------+--------+"
UDP = [  # RFC 768
    " 0      7 8     15 16    23 24    31",
    OCTETS,
    "|     Source      |   Destination   |",
    "|      Port       |      Port       |",
    OCTETS,
    "|                 |                 |",
    "|     Length      |    Checksum     |",
    OCTETS,
    "|",
    "|          data octets ...",
    "+---------------- ...",
]
SEP16 = "+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+"
DNS = [  # RFC 1035, 4.1.1
    "                                1  1  1  1  1  1",
    "  0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5",
    SEP16,
    "|                      ID                       |",
    SEP16,
    "|QR|   Opcode  |AA|TC|RD|RA|   Z    |   RCODE   |",
    SEP16,
    "|                    QDCOUNT                    |",
    SEP16,
    "|                    ANCOUNT                    |",
    SEP16,
    "|                    NSCOUNT                    |",
    SEP16,
    "|                    ARCOUNT                    |",
    SEP16,
]
PX = 2
CW, CH = 8 * PX, 16 * PX  # one 8x16 character cell
DIM, RULE = mix(BG_ALT, UI, 0.5), mix(BG_ALT, UI, 0.75)
TEXT = mix(UI_ALT, UI_HI, 0.3)

Name = Literal["ip", "tcp", "udp", "dns"]


class Header(Params):
    figure: Name = knob(default="ip", doc="which RFC diagram")


VARIANTS = {"tcp": Header(figure="tcp"), "udp": Header(figure="udp"), "dns": Header(figure="dns")}


@dataclass(frozen=True)
class Figure:
    title: str  # "" for none
    lines: list[str]
    caption: str  # "" for none
    ruler: int  # rows of bit numbers above the first rule
    rows: range  # the lit field, its rules included
    cols: range
    note: str
    lit: range  # the lit characters of the note
    fx: float  # the figure's left edge on a landscape screen, as a fraction of the width
    right: bool = False  # the note sits right of the figure on a landscape screen


def figure(name: Name) -> Figure:
    """The diagram `name`, the field it lights and the note beside that field."""
    match name:
        case "ip":  # a router lowers the Time to Live by one: one hop
            return Figure(
                title="3.1.  Internet Header Format",
                lines=IP,
                caption="Figure 4.",
                ruler=2,
                rows=range(6, 9),
                cols=range(17),
                note="64 -> 63",
                lit=range(6, 8),
                fx=0.3125,
            )
        case "tcp":  # SYN on the first segment of the RFC's handshake example, its Figure 7
            return Figure(
                title="TCP Header Format",
                lines=TCP,
                caption="Figure 3.",
                ruler=2,
                rows=range(8, 13),
                cols=range(28, 31),
                note="<SEQ=100><CTL=SYN>",
                lit=range(14, 17),
                fx=0.3125,
            )
        case "udp":  # port 53, where RFC 1035 puts name servers
            return Figure(
                title="",
                lines=UDP,
                caption="User Datagram Header Format",
                ruler=1,
                rows=range(1, 5),
                cols=range(18, 37),
                note="53",
                lit=range(2),
                fx=0.5,
                right=True,
            )
        case "dns":  # QR is 0 in a query and 1 in its response
            return Figure(
                title="4.1.1. Header section format",
                lines=DNS,
                caption="",
                ruler=2,
                rows=range(4, 7),
                cols=range(4),
                note="0 -> 1",
                lit=range(5, 6),
                fx=0.36,
            )


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Header]) -> None:
    f = figure(s.params.figure)
    width = max(len(line) for line in f.lines)
    # Rows run from the title to past the caption.
    top = -2 if f.title else 0
    bottom = len(f.lines) + 2 if f.caption else len(f.lines)
    detail = bottom + 1
    mid = len(f.rows) // 2  # the field's middle row, where the note sits
    left = 0 if f.right else len(f.note) + 1  # note columns left of the figure
    beside = (width + len(f.note) + 1) * CW  # the figure with the note in its margin
    # The note sits in the margin beside the lit row. The 32-bit rows leave only 40 px on a
    # portrait screen, so there the figure is centred and the lit field is repeated under it
    # (from row `detail`), with the note beside that.
    zoom = not s.landscape and beside > s.w - 160
    at = s.pick(landscape=(f.fx, 0.5), portrait=(0.5, 0.46), snap=PX)
    if s.landscape:
        reserve = width + len(f.note) + 1 - left
        x0 = min(at.x, s.w - reserve * CW - 240)  # 16:10 would leave too little on the right
    elif zoom:
        x0 = at.x - width * CW / 2
    else:
        x0 = at.x - beside / 2 + left * CW
    if zoom:
        y0 = at.y - (top + detail + len(f.rows) + 1) / 2 * CH
        note = (x0 + (f.cols.stop + 1) * CW, y0 + (detail + mid) * CH)
    else:
        y0 = at.y - (top + bottom) / 2 * CH
        nx = x0 + (width + 1) * CW if f.right else x0 - left * CW
        note = (nx, y0 + (f.rows.start + mid) * CH)

    def colour(c: int, r: int, ch: str) -> Colour:
        lit = c in f.cols and r in f.rows
        if r < f.ruler:
            return RULE
        if ch in "+-|":
            return ACCENT_3 if lit else RULE
        return ACCENT if lit else TEXT

    glyphs(s, f.lines, colour, at=(x0, y0), px=PX)
    if zoom:
        field = [row[f.cols.start : f.cols.stop] for row in f.lines[f.rows.start : f.rows.stop]]
        at_field = (x0 + f.cols.start * CW, y0 + detail * CH)
        glyphs(
            s,
            field,
            lambda c, r, ch: colour(c + f.cols.start, r + f.rows.start, ch),
            at=at_field,
            px=PX,
        )
    if f.title:
        glyphs(s, f.title, DIM, at=(x0, y0 - 2 * CH), px=PX)
    if f.caption:
        glyphs(s, f.caption, DIM, at=(x0, y0 + (bottom - 1) * CH), px=PX)
    glyphs(s, f.note, lambda c, r, ch: ACCENT if c in f.lit else DIM, at=note, px=PX)
