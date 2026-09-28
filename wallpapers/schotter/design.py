"""A band of square outlines whose random jitter and tilt grow column by column, until one escapes."""

from walldye import ACCENT, ACCENT_6, UI, UI_ALT, Canvas, P, Vec, design

COLS, ROWS, PITCH, SIDE = 29, 9, 50, 46
ORIGIN = Vec(190, 285)  # top-left corner of the band
ESCAPED = Vec(1775, 845)  # centre of the filled square
# The three strays leave holes at the band's corner and trail towards the escaped square with
# widening gaps: their direction, then gaps and tilts (deg), nearest the square first.
STRAY_DIR, STRAY_GAPS, STRAY_TILT = Vec(0.55, 0.835), (58, 72, 90), (20, 28, 35)
CORNERS = (Vec(-1, -1), Vec(1, -1), Vec(1, 1), Vec(-1, 1))


def square(c: Vec, tilt: float, side: float = SIDE) -> list[Vec]:
    """The corners of a square of `side` around `c`, turned `tilt` degrees clockwise."""
    return [c + (k * (side / 2)).rotate(deg=tilt) for k in CORNERS]


@design()
def draw(s: Canvas) -> None:
    rng = s.rng(1968)
    crisp, faded = P(), P()
    placed: list[Vec] = []
    dist = 0
    for gap, tilt in zip(reversed(STRAY_GAPS), reversed(STRAY_TILT), strict=True):
        dist += gap
        placed.append(ESCAPED - STRAY_DIR * dist)
        faded.poly(square(placed[-1], tilt), closed=True)
    for i in range(COLS):
        t = max(0.0, (i - 6) / (COLS - 7)) ** 1.6
        for j in range(ROWS):
            if (COLS - 1 - i) + (ROWS - 1 - j) < 2:
                continue
            home = ORIGIN + (i * PITCH + SIDE / 2, j * PITCH + SIDE / 2)
            # resample jitter that would stack a square on a neighbour, or crowd the three strays
            while True:
                c = home + (rng.gauss(0, t * 18), rng.gauss(0, t * 18))
                if all(abs(c - p) > (24 if k >= 3 else 44) for k, p in enumerate(placed)):
                    break
            placed.append(c)
            tilt = rng.uniform(-1, 1) * t * 50
            (faded if t > 0.6 else crisp).poly(square(c, tilt), closed=True)
    s.stroke(crisp, UI_ALT, 2, join="round")
    s.stroke(faded, UI, 2, join="round")
    s.path(
        P().poly(square(ESCAPED, 40), closed=True),
        fill=ACCENT_6,
        stroke=ACCENT,
        stroke_width=3,
        stroke_linejoin="round",
    )
