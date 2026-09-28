"""An 80-column punch card, Hollerith-punched with a nixos-rebuild command and one column lit under the read line: holes cut with even-odd fill."""

from walldye import (
    ACCENT,
    ACCENT_3,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    Canvas,
    P,
    Path,
    Vec,
    by_regime,
    design,
    mix,
)
from walldye.geom import Affine

TILT = -6.5  # card rotation in degrees; portrait turns it a further quarter turn clockwise
PPI = 1200 / 7.375  # the 7.375 x 3.25 in card, drawn 1200 wide
CW, CH = 7.375 * PPI, 3.25 * PPI
HW, HH = 0.055 * PPI, 0.125 * PPI  # one rectangular hole
TEXT = (" " * 9 + "NIXOS-REBUILD SWITCH --FLAKE .#DESKTOP --UPGRADE").ljust(72) + "00000010"
READ_COL = 68
PRINT = mix(BG_ALT, UI, 0.3)  # the faint pre-printed hole grid
SYMBOLS = {"-": (11,), "/": (0, 1), ".": (12, 3, 8), "#": (3, 8)}  # zone punches
SHADOW = Vec(14, 18)  # drop shadow offset at scale 1
# BG_DEEP is lighter than BG on light themes, so there the shadow steps towards FG
SHADE = by_regime(BG_DEEP, mix(BG, BG_ALT, 0.5))


def row(zone: int) -> int:
    """Slot row, 0 at the top, of an IBM 029 punch zone: 12, 11, 0, then 1 to 9."""
    return {12: 0, 11: 1}.get(zone, zone + 2)


def hollerith(ch: str) -> list[int]:
    """Slot rows punched for `ch`; none for a space or a character the code lacks."""
    if ch.isdigit():
        zones: tuple[int, ...] = (int(ch),)
    elif "A" <= ch <= "I":
        zones = (12, ord(ch) - 64)
    elif "J" <= ch <= "R":
        zones = (11, ord(ch) - 73)
    elif "S" <= ch <= "Z":
        zones = (0, ord(ch) - 81)
    else:
        zones = SYMBOLS.get(ch, ())
    return [row(z) for z in zones]


def hole(col: int, r: int) -> Vec:
    """Centre of the hole at column `col` and slot row `r`, in card units."""
    return Vec(0.2515 * PPI + col * 0.087 * PPI, 0.25 * PPI + r * 0.25 * PPI)


def slot(d: Path, col: int, r: int) -> None:
    x, y = hole(col, r)
    d.rrect(x - HW / 2, y - HH / 2, HW, HH, 2)


def outline(d: Path) -> Path:
    """The card edge: rounded corners and the clipped top-left corner."""
    c, r = 0.25 * PPI, 10
    d.M(c, 0).H(CW - r).Q(CW, 0, CW, r).V(CH - r).Q(CW, CH, CW - r, CH)
    return d.H(r).Q(0, CH, 0, CH - r).V(c * 1.6).Z()


@design(aspects="any")
def draw(s: Canvas) -> None:
    if s.landscape:
        at, deg, k = s.frac(880 / 1920, 580 / 1080), TILT, 1.0
    else:
        # stood on end, as large as the narrow side allows
        at, deg, k = s.frac(0.48, 0.54), 90 + TILT, min(0.59 * s.w / CH, 0.7 * s.h / CW)
    place = Affine.frame(at, deg=deg, scale=k) @ Affine.translate(-CW / 2, -CH / 2)

    punched = {(c, r) for c, ch in enumerate(TEXT) for r in hollerith(ch)}
    card, faint, lit = outline(P()), P(), P()
    for c in range(80):
        for r in range(12):
            if c == READ_COL:
                slot(lit, c, r)
            elif (c, r) in punched:
                slot(card, c, r)
            else:
                slot(faint, c, r)

    s.path(outline(P()), fill=SHADE, transform=Affine.translate(*(SHADOW * k)) @ place)
    with s.group(transform=place):
        s.fill(card, BG_ALT, rule="evenodd")  # punched holes show what lies under the card
        s.fill(faint, PRINT)
        x = hole(READ_COL, 0).x
        s.stroke(P().M(x, -90).L(x, CH + 90), ACCENT_3, 2)
        s.fill(lit, ACCENT)
