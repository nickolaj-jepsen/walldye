"""A wall of 24 two-handed clocks whose hand bars turn along the diagonals into one wave, while one clock breaks ranks to tell the time."""

import math
from typing import Literal

from walldye import ACCENT, BG_ALT, UI, UI_HI, Canvas, P, Params, Path, Vec, design, knob, polar


class Wall(Params):
    show: Literal["wave", "digits"] = knob(default="wave", doc="what the other 23 clocks draw")


VARIANTS = {"digits": Wall(show="digits")}

R, PITCH = 76, 172  # dial radius and clock spacing
HAND = 0.9 * R
TIME = (11, 22)  # hours, minutes
# Wall shapes: columns, rows, and the odd clock (row, col) in the wave and in the digits. The
# wave's odd clock sits where the bars run at 135 degrees, so its minute hand stays in line.
LANDSCAPE = (8, 3, (1, 5), (1, 2))
PORTRAIT = (4, 6, (4, 1), (1, 2))
N, E, S, W, PARK = 0, 90, 180, 270, 225  # bearings; PARK is where ClockClock rests unused hands
# Hand bearings of the six clocks of a 2 x 3 digit, row by row, left clock first.
DIGITS = {
    "1": ((PARK, PARK), (S, S), (PARK, PARK), (N, S), (PARK, PARK), (N, N)),
    "2": ((E, E), (W, S), (E, S), (N, W), (N, E), (W, W)),
}


def wave(i: int, j: int) -> float:
    """Bearing of the bar at column `i`, row `j`: constant along each i - j diagonal, so where it
    settles at 135 degrees the bars of one diagonal line up."""
    return 135 + 90 * math.exp(-(((i - j - 0.5) / 1.9) ** 2))


def hands(d: Path, c: Vec, a: float, b: float, reach: float = HAND) -> None:
    """Two hands from pivot `c` at bearings `a` (length `reach`) and `b`, as one stroke."""
    d.M(polar(c, reach, bearing=a)).L(c).L(polar(c, HAND, bearing=b))


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Wall]) -> None:
    cols, rows, odd_wave, odd_digits = LANDSCAPE if s.landscape else PORTRAIT
    digits = s.params.show == "digits"
    odd = odd_digits if digits else odd_wave
    # four digits in a row, or on a portrait screen the hours stacked over the minutes
    text = "".join(f"{v:02d}" for v in TIME)
    per_row = cols // 2
    # a little right of and above centre on a landscape screen, as in the 16:9 original
    c = s.pick(landscape=(25 / 48, 25 / 54), portrait=(0.5, 0.46))
    origin = c - ((cols - 1) * PITCH / 2, (rows - 1) * PITCH / 2)

    rims, ticks, bars, pins, odd_hands = P(), P(), P(), P(), P()
    for j in range(rows):
        for i in range(cols):
            o = origin + (i * PITCH, j * PITCH)
            rims.circle(o, R)
            for k in range(12):
                ticks.M(polar(o, R - 9, deg=k * 30)).L(polar(o, R - 5, deg=k * 30))
            if (j, i) == odd:
                h, m = TIME
                # the minute hand stays with its neighbours, the hour hand kinks off them
                hands(odd_hands, o, (h + m / 60) * 30, m * 6, 0.62 * R)
                continue
            pins.circle(o, 2.5)
            if digits:
                glyph = DIGITS[text[(j // 3) * per_row + i // 2]]
                hands(bars, o, *glyph[(j % 3) * 2 + i % 2])
            else:
                hands(bars, o, wave(i, j), wave(i, j) + 180)
    s.stroke(rims, UI, 1.5)
    s.stroke(ticks, UI, 1.5)
    s.stroke(bars, UI_HI, 6, cap="round", join="round")
    s.fill(pins, BG_ALT)
    s.stroke(odd_hands, ACCENT, 6, cap="round", join="round")
