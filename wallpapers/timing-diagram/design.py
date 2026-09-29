"""A datasheet SPI read timing diagram: slanted edges, hatched buses, one setup time picked out."""

from typing import Literal

from shapely.geometry import Polygon

from walldye import ACCENT, BG_ALT, UI, UI_ALT, Canvas, P, Paint, Path, design
from walldye.geom import hatch
from walldye.pixel import glyphs

type Pts = list[tuple[float, float]]
type Seg = tuple[float, float, str | None]
type Anchor = Literal["start", "middle", "end"]

# Lane baselines; a high level sits HW above its baseline, hi-Z halfway.
LANES = (260, 370, 480, 590, 700, 810)
NAMES = ("CS#", "SCLK", "MOSI", "MISO", "ADDR[7:0]", "DATA[7:0]")
# The figure's box, label column included, is centered on the canvas: the labels weight the left.
X0, X1, LABEL_X, HW, SLANT = 372, 1692, 332, 44, 4
CLK0, PER, NCLK = 572, 64, 16
CS_LO, CS_HI = 492, 1636
TX, RX = 0x3A, 0xBE


def rise(k: int) -> int:
    """The rising SCLK edge of cycle k, where SPI mode 0 samples."""
    return CLK0 + k * PER


def shift(k: int) -> int:
    """The falling SCLK edge of cycle k, where the data lines change."""
    return rise(k) + PER // 2


def bits(byte: int) -> list[int]:
    """The eight bits of `byte`, most significant first."""
    return [(byte >> (7 - i)) & 1 for i in range(8)]


def wave(y: float, events: list[tuple[int, float]], level: float) -> Pts:
    """Polyline of a digital lane on baseline `y` starting at `level` (0, 1, or 0.5 for hi-Z);
    each event (x, level) slants to the new level across x ± SLANT, and repeats are ignored."""
    pts, cur = [(X0, y - level * HW)], level
    for x, lv in events:
        if lv == cur:
            continue
        pts += [(x - SLANT, y - cur * HW), (x + SLANT, y - lv * HW)]
        cur = lv
    return [*pts, (X1, y - cur * HW)]


def text(s: Canvas, x: float, y: float, msg: str, paint: Paint, anchor: Anchor = "start") -> None:
    """One line of 5x8 bitmap text centered vertically on `y` and placed at `x` by `anchor`."""
    glyphs(s, msg, paint, at=(round(x), round(y - 8)), font="5x8", px=2, gap=1, anchor=anchor)


def bus(s: Canvas, outline: Path, rules: Path, y: float, segs: list[Seg]) -> None:
    """A bus lane on baseline `y`, appended to `outline`: each (x0, x1, label) is a window drawn
    as a long hexagon, labeled, or for a None label ruled into `rules` as don't-care."""
    top, bot, mid = y - HW, y, y - HW / 2
    pos = X0
    for x0, x1, label in segs:
        if x0 - SLANT > pos:
            outline.M(pos, mid).H(x0 - SLANT)
        hexa = [
            (x0 - SLANT, mid),
            (x0 + SLANT, top),
            (x1 - SLANT, top),
            (x1 + SLANT, mid),
            (x1 - SLANT, bot),
            (x0 + SLANT, bot),
        ]
        outline.poly(hexa, closed=True)
        if label:
            text(s, (x0 + x1) / 2, mid, label, UI_ALT, "middle")
        else:
            for seg in hatch(Polygon(hexa).buffer(-3), 12 / 2**0.5, deg=-45):
                rules.poly(seg)
        pos = x1 + SLANT
    outline.M(pos, mid).H(X1)


def dim(s: Canvas, xa: float, xb: float, y: float, label: str, paint: Paint, left: bool) -> None:
    """Datasheet dimension: a double arrow between two extension lines, labeled on the left
    when `left`, else on the right."""
    xa, xb = xa + 1.5, xb - 1.5  # tips stop short of the extension lines so neighbors never touch
    s.stroke(P().M(xa, y).H(xb), paint, 1.4)
    s.fill(P().arrowhead((xa, y), 9, deg=180, width=4).arrowhead((xb, y), 9, deg=0, width=4), paint)
    if left:
        text(s, xa - 12, y, label, paint, "end")
    else:
        text(s, xb + 12, y, label, paint)


@design()
def draw(s: Canvas) -> None:
    refs = P()
    for k in range(NCLK):
        refs.M(rise(k), 196).V(826)
    s.stroke(refs, BG_ALT, 1.2, dash=(3, 5))

    for y, name in zip(LANES, NAMES, strict=True):
        text(s, LABEL_X, y - HW / 2, name, UI_ALT, "end")

    cs, clk, mosi, miso, addr, data = LANES
    tx, rx = bits(TX), bits(RX)
    lanes = P()
    lanes.poly(wave(cs, [(CS_LO, 0), (CS_HI, 1)], 1))
    lanes.poly(wave(clk, [e for k in range(NCLK) for e in ((rise(k), 1), (shift(k), 0))], 0))
    # The controller sends the address byte once CS# falls, the device answers with the data
    # byte over the next eight cycles, and each line floats at hi-Z while it is not driven.
    mosi_ev = [(CS_LO + 20, tx[0]), *((shift(k - 1), tx[k]) for k in range(1, 8)), (shift(7), 0.5)]
    lanes.poly(wave(mosi, mosi_ev, 0.5))
    lanes.poly(wave(miso, [*((shift(7 + k), rx[k]) for k in range(8)), (shift(15), 0.5)], 0.5))
    s.stroke(lanes, UI_ALT, 2, join="round")

    buses, rules = P(), P()
    bus(s, buses, rules, addr, [(CS_LO + 20, shift(7), f"0x{TX:02X}"), (shift(7), CS_HI, None)])
    bus(s, buses, rules, data, [(CS_LO + 20, shift(7), None), (shift(7), shift(15), f"0x{RX:02X}")])
    s.stroke(rules, UI, 1.2)
    s.stroke(buses, UI_ALT, 2, join="round")

    # Setup and hold straddle the 6th rising edge, where MOSI falls from 1 to 0 just before it.
    edge, before, after = rise(5), shift(4), shift(5)
    yd = (clk + mosi - HW) / 2
    s.stroke(P().M(after, mosi - HW - 4).V(yd - 10), UI_ALT, 1.2)
    dim(s, edge, after, yd, "tH  8 ns", UI_ALT, left=False)
    s.stroke(P().M(before, mosi - HW - 4).V(yd - 10).M(edge, clk + 6).V(yd + 10), ACCENT, 1.4)
    dim(s, before, edge, yd, "tSU  5 ns", ACCENT, left=True)

    text(s, (X0 + X1) / 2, 870, "Figure 7. Read Timing", UI_ALT, "middle")
