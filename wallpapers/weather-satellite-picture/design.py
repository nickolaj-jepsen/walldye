"""A weather-satellite picture of a cyclone arriving line by line over APT, Floyd-Steinberg dithered."""

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, BG_ALT, UI, UI_ALT, UI_HI, Canvas, P, Params, design, knob
from walldye.pixel import dither, glyphs, grid_runs


class Pass(Params):
    line: int = knob(default=177, lo=110, hi=255, doc="lines received, counted from the top")
    complete: bool = False  # the whole frame received and the scanline gone


VARIANTS = {"complete": Pass(complete=True)}

CELL = 3
SYNC, WEDGE = 16, 4  # sync strip and telemetry wedge widths in cells
EYE = 5  # eye radius in cells
PALETTE = (None, BG_ALT, UI, UI_ALT, UI_HI)
EYEWALL = 4
PULSE = [0, 0] + [2, 0] * 7  # APT sync A: seven pulses
SPECKS = 30 / (81 * 354)  # static specks per unreceived cell
DRIFT = (1.7, 5.9)  # noise offset, so the eye does not sit on a lattice zero


def snap(v: float) -> int:
    """`v` rounded to a whole number of cells, in canvas units."""
    return round(v / CELL) * CELL


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Pass]) -> None:
    # The eye sits 100 lines down in every frame; a portrait frame is narrower and runs longer.
    eye_row = 100
    if s.landscape:
        cols, rows, eye_col = 374, 260, 207
        y0 = snap(s.center.y - rows * CELL / 2)
    else:
        cols, rows = (s.w - 180) // CELL, max(260, int(s.h * 0.4) // CELL)
        eye_col = round(cols * 0.553)
        y0 = snap(s.h * 0.37) - eye_row * CELL  # the eye a little above the middle
    x0 = snap(s.center.x - cols * CELL / 2)
    play = rows if s.params.complete else min(s.params.line, rows)  # first unreceived line

    # Eye-relative canvas units at each image cell, so every screen shape gets the same storm.
    inner = cols - SYNC - WEDGE
    ys, xs = np.mgrid[0:rows, 0:inner]
    x = (xs + SYNC - eye_col) * CELL
    y = (ys - eye_row) * CELL
    r = np.hypot(x, y) + 1

    def fbm(key: int, scale: float) -> NDArray[np.float64]:
        u, v = x / (scale * CELL) + DRIFT[0], y / (scale * CELL) + DRIFT[1]
        return 1.25 * s.noise(key).fbm(u, v, octaves=3)

    a = np.arctan2(y, x) + 2.4 * np.log(r / 50)  # log-spiral twist
    arms = (0.5 + 0.5 * np.cos(2 * a + 1.2 * fbm(3, 40))) ** 1.7
    body = np.exp(-((r / 280) ** 2))
    core = np.exp(-((r / 100) ** 3))  # dense overcast around the eye
    rag = np.clip(0.75 + 1.2 * fbm(5, 24), 0, 1.3)
    field = 0.85 * core + arms * body * rag + 0.2 * fbm(7, 12)
    field += 0.5 * np.clip(fbm(9, 14) - 0.12, 0, 1) * (1 - body)  # fair-weather cumulus
    field *= np.clip((ys * CELL - 20) / 90, 0, 1)  # cloud-free under the frame's top edge
    tone = np.clip((field - 0.16) * 1.1, 0, 1)
    rng = s.np_rng(5)
    tone += (tone > 0.08) * rng.uniform(-0.06, 0.06, rows)[:, None]  # per-line reception banding

    grid = dither(tone, 3, method="fs", serpentine=True)
    rc = r / CELL
    grid[rc < EYE] = 0
    grid[(rc >= EYE) & (rc < EYE + 1.2)] = EYEWALL
    for j in rng.choice(np.arange(8, play - 4), 4, replace=False):  # dropout lines
        grid[j] = np.minimum(grid[j], 1) if j % 2 else 0
    grid[play:] = 0

    full = np.zeros((rows, cols), int)
    full[:, SYNC:-WEDGE] = grid
    live = np.arange(play)
    full[:play, :SYNC] = np.where((live % 4 != 3)[:, None], PULSE, 0)
    full[:play, -WEDGE + 1 :] = (1 + (live // 10) % 2)[:, None]  # stepped calibration wedge
    n = round(SPECKS * (rows - play - 2) * inner)
    if n > 0:  # radio static below the scanline
        full[rng.integers(play + 1, rows - 1, n), rng.integers(SYNC, cols - WEDGE, n)] = 1
    grid_runs(s, full, PALETTE, CELL, (x0, y0))

    w, h = cols * CELL, rows * CELL
    s.stroke(P().rect(x0 - 0.5, y0 - 0.5, w + 1, h + 1), UI_ALT, 1)
    ty = y0 - 24
    glyphs(s, ["NOAA-19  APT  137.100 MHz  CH2"], UI_HI, at=(x0, ty), font="5x8", px=2)
    label = f"LINE {play:04d}/{rows:04d}"
    glyphs(s, [label], UI_HI, at=(x0 + w + 2, ty), font="5x8", px=2, anchor="end")
    # The scanline and its write head on the sync strip; after the last line the head is parked.
    head = P()
    if play < rows:
        py = y0 + play * CELL
        head.rect(x0, py, w, 3).rect(x0 + 2 * CELL, py - 6, 13 * CELL, 15)
    else:
        head.rect(x0 + 2 * CELL, y0 + h - 15, 13 * CELL, 15)
    s.fill(head, ACCENT)
