"""A dither specimen plate: one tone ramp in 1-bit through eight algorithms, crossed by a probe."""

from typing import Literal

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, ACCENT_2, UI_ALT, UI_HI, Canvas, P, Paint, Point, design
from walldye.geom import Affine
from walldye.pixel import DitherMethod, dither, glyphs, grid_runs

CELL, COLS, ROWS = 3, 400, 12  # dither cell in units; each ribbon is COLS x ROWS cells
GAP = 7  # cells between ribbons, so every ribbon starts on the cell grid
LO, HI = 0.18, 0.6  # floor makes every ribbon ink from x=0; cap sits under Bayer-2's 0.625 step
PROBE = 0.55
APERTURE = 4  # cells either side of the probe whose inked cells read out in ACCENT_2
METHODS: tuple[tuple[str, DitherMethod | None, int], ...] = (
    ("BAYER-2", "bayer", 2),
    ("BAYER-8", "bayer", 8),
    ("CLUSTER", None, 4),
    ("BLUENOISE", "bluenoise", 64),
    ("FLOYD-ST", "fs", 4),
    ("ATKINSON", "atkinson", 4),
    ("JARVIS", "jarvis", 4),
    ("RIEMERSMA", "riemersma", 4),
)
BLOCK_W, BLOCK_H = COLS * CELL, (len(METHODS) * (ROWS + GAP) - GAP) * CELL  # the ribbons
MID = (BLOCK_W // 2, BLOCK_H // CELL // 2 * CELL)  # middle of the ribbons, on the cell grid
RIGHT = 819  # least room right of MID in landscape: 16:9's 204-unit margin plus 615 of plate
type Anchor = Literal["start", "middle", "end"]
# 45° 4x4 clustered-dot screen: the library's 8x8 one grows blobs that outshout the other ribbons.
CLUSTER4 = (np.array([[0, 2, 14, 6], [4, 10, 5, 12], [15, 3, 1, 7], [8, 13, 9, 11]]) + 0.5) / 16


def ribbon(s: Canvas, method: DitherMethod | None, matrix: int) -> NDArray[np.int64]:
    """The ramp from LO to HI as a (ROWS, COLS) grid of 0/1 cells; method None is CLUSTER4."""
    tone = np.tile(LO + (HI - LO) * (np.arange(COLS) + 0.5) / COLS, (ROWS, 1))
    if method is None:
        screen = CLUSTER4[np.arange(ROWS)[:, None] % 4, np.arange(COLS) % 4]
        return (tone > screen).astype(np.int64)
    return dither(tone, 2, method=method, matrix=matrix, rng=s.np_rng(3), serpentine=True)


def label(s: Canvas, text: str, paint: Paint, at: Point, anchor: Anchor = "start") -> None:
    """One line of the plate's 5x8 lettering, `anchor` saying which edge sits at at[0]."""
    glyphs(s, text, paint, at=at, font="5x8", px=2, anchor=anchor)


def plate(s: Canvas) -> None:
    """The whole plate in its own frame: the ribbons span (0, 0) to (BLOCK_W, BLOCK_H), with
    names to the left, the scale above and the caption and probe reading below."""
    c = int(PROBE * COLS)
    sheet = np.zeros((BLOCK_H // CELL, COLS), dtype=np.int64)
    for k, (name, method, matrix) in enumerate(METHODS):
        j = k * (ROWS + GAP)
        sheet[j : j + ROWS] = ribbon(s, method, matrix)
        label(s, name, UI_HI, (-20, j * CELL + (ROWS * CELL - 16) // 2), "end")
    sheet[:, c - APERTURE : c + APERTURE] *= 2  # the aperture's inked cells take index 2
    grid_runs(s, sheet, [None, UI_HI, ACCENT_2], CELL)

    top, bot = -24, BLOCK_H
    ticks = P()
    for t in range(11):
        x = t * BLOCK_W / 10
        ticks.M(x, top - (8 if t % 2 == 0 else 4)).V(top)
        if t % 2 == 0:
            label(s, str(t * 10), UI_ALT, (x, top - 30), "middle")
    ticks.M(0, top).H(BLOCK_W).M(0, bot + 24).H(BLOCK_W)
    s.stroke(ticks, UI_ALT, 1.5)
    label(s, "FIG. 1   1-BIT, 3 PX CELL, 400 x 12", UI_ALT, (0, bot + 36))

    # The probe runs only through the gaps so the aperture cells stay whole.
    px = c * CELL
    probe = P().M(px, top - 4).V(-6)
    for k in range(1, len(METHODS)):
        g = (k * (ROWS + GAP) - GAP) * CELL
        probe.M(px, g + 6).V(g + GAP * CELL - 6)
    probe.M(px, bot + 6).V(bot + 24)
    s.stroke(probe, ACCENT, 1.5)
    label(s, f"{PROBE:.2f}", ACCENT, (px, bot + 36), "middle")


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Landscape: right of center, but never nearer the right edge than on 16:9, which centers
    # it on 16:10. Portrait: the plate turned a quarter anticlockwise, like a wide figure
    # printed sideways, so the ramp rises up the screen.
    mid = s.pick(landscape=(0.573, 0.515), portrait=(0.5, 0.5), snap=CELL)
    if s.landscape:
        x = min(mid.x, (s.w - RIGHT) // CELL * CELL)
        frame = Affine.translate(x - MID[0], mid.y - MID[1])
    else:
        frame = Affine.frame((mid.x - MID[1], mid.y + MID[0]), deg=-90)
    with s.group(transform=frame):
        plate(s)
