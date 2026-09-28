"""A teletext page in separated-graphics sixels: two hill ridges, a dashed sea and a half-sunk sun."""

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, ACCENT_3, BG_ALT, UI, UI_ALT, Canvas, design
from walldye.pixel import glyphs

SW, SH = 24, 15  # sixel pitch; 80x72 sixels = a 40x24 teletext page
GW, GH = 18, 11  # lit block inside the pitch, the rest is the separated-mode gutter
COLS, ROWS = 80, 72
HORIZON = 42  # first row of character row 14: the horizon gets a text row to itself
SUN = (52, 42, 4, 6.4)  # centre col/row, radius in cols/rows
HEADER = "P101  TELETEXT 101  Sun 27 Sep 19:04"
# sixel kinds in rising priority: the highest one in a 2x3 character cell recolours the rest
SEA, LINE, FAR, NEAR, REFL, DISC = range(1, 7)
TONES = (BG_ALT, UI, ACCENT_3, ACCENT)
# kind -> TONES index: the far ridge shares the horizon line's step, the near one the sea's
INK = (0, 0, 1, 1, 0, 2, 3)


def bumps(c: NDArray[np.floating], *hs: tuple[float, float, float]) -> NDArray[np.floating]:
    """Smooth ridge height in rows: a sum of (height, centre col, width) Gaussians over `c`."""
    return sum((h * np.exp(-(((c - m) / w) ** 2)) for h, m, w in hs), np.zeros_like(c))


@design()
def draw(s: Canvas) -> None:
    g = np.zeros((ROWS, COLS), int)
    rr, cc = np.mgrid[0:ROWS, 0:COLS]
    c = np.arange(COLS) + 0.5
    far = HORIZON - bumps(c, (16, 22, 12), (6, 36, 6))
    near = HORIZON - bumps(c, (7, 2, 10), (5.5, 20, 9), (2.5, 32, 5))
    g[(rr >= far) & (rr < HORIZON)] = FAR
    g[(rr >= near) & (rr < HORIZON)] = NEAR
    land_end = int(np.nonzero(HORIZON - far >= 1)[0].max())
    g[HORIZON, land_end - 2 :] = LINE  # tuck the horizon a little under the last slope

    # sea: dash rows in perspective, closer together toward the horizon, evenly jittered
    sc, sr, rx, ry = SUN
    r = s.np_rng(3)
    for k, row in enumerate([45, 47, 50, 54, 59, 65, 71]):
        period, n = 6 + 2 * k, 2 + k // 2
        for c0 in range(-int(r.integers(0, period)), COLS, period):
            c0 += int(r.integers(0, period - n))
            calm = row <= HORIZON + 12 and sc - rx - 3 < c0 + n and c0 < sc + rx + 3
            if not calm:  # a calm patch round the reflection
                g[row, max(c0, 0) : max(c0 + n, 0)] = SEA
    for row, half in [(45, 4), (48, 3), (51, 1)]:  # reflection bars shrinking toward the viewer
        g[row, sc - half : sc + half] = REFL
    disc = ((cc + 0.5 - sc) / rx) ** 2 + ((rr + 0.5 - sr) / ry) ** 2 <= 1
    g[disc & (rr < HORIZON)] = DISC

    # teletext allows one foreground colour per 2x3 character cell
    top = g.reshape(ROWS // 3, 3, COLS // 2, 2).max(axis=(1, 3))
    g = np.where(g > 0, top.repeat(3, axis=0).repeat(2, axis=1), 0)

    ink = np.array(INK)[g]
    with s.buckets(TONES, "fill") as b:
        for row, col in np.argwhere(g).tolist():
            x, y = col * SW + (SW - GW) // 2, row * SH + (SH - GH) // 2
            b[int(ink[row, col])].rect(x, y, GW, GH)
    glyphs(s, [HEADER], UI_ALT, at=(48, 10), font="5x8", px=3, gap=1)
