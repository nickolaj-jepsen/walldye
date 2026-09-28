"""A btop-style CPU panel: per-core load history as braille-dot area plots, one core spiking."""

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import convolve1d

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_3,
    ACCENT_4,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    NpRng,
    Vec,
    design,
)
from walldye.pixel import glyphs

type Series = NDArray[np.float64]

FW, FH = 8, 16  # glyph cell at px=1
COLS, ROWS = 100, 27  # panel size in cells
PLOT_H, GAP = 5, 1  # rows per core plot, rows between plots
BASE = (0.22, 0.3, 0.18, 0.26)  # mean load per core
SPIKE = 2  # the core that spikes
PL, PR = 6, COLS - 8  # plot columns: core label on the left, percentage on the right
# Braille bit per (dot row, dot column); a cell's character is U+2800 plus its raised bits.
DOT = np.array([[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]])
# Plot rows from the top, dimming towards the floor: the UI ramp for idle load, the accent
# ladder for the spike.
IDLE = (UI_HI, UI_HI, UI_HI, UI_ALT, UI)
HOT = (ACCENT, ACCENT_1, ACCENT_2, ACCENT_3, ACCENT_4)


def smooth(v: Series, k: int) -> Series:
    """`v` convolved with a normalised Hann window of width 2k + 1, edges held."""
    win = np.hanning(2 * k + 1)
    return convolve1d(v, win / win.sum(), mode="nearest")


def series(rng: NpRng, n: int, base: float, burst: tuple[int, int] | None) -> tuple[Series, Series]:
    """`n` samples of load wandering around `base`, clipped to [0.04, 0.98], and the burst
    envelope in [0, 1]: a fast rise from `burst[0]`, a plateau near 0.85, a decay after
    `burst[1]` (all zeros without a burst)."""
    v = smooth(rng.normal(0, 1, n), 5)
    v = base * (1 + 0.55 * v / v.std())
    env = np.zeros(n)
    if burst:
        x = np.arange(n)
        a, b = burst
        env = np.clip((x - a) / 6, 0, 1) * np.exp(-np.clip(x - b, 0, None) / 10)
        v = v * (1 - env) + env * (0.84 + 0.05 * smooth(rng.normal(0, 1, n), 3))
    return np.clip(v, 0.04, 0.98), env


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: right of centre, leaving the left for windows; portrait: centred, low
    c = s.pick(landscape=(0.698, 0.5), portrait=(0.5, 0.62), snap=4)
    rng = s.np_rng(42)
    grid = [[" "] * COLS for _ in range(ROWS)]
    tone: list[list[Colour]] = [[UI] * COLS for _ in range(ROWS)]

    def put(col: int, row: int, text: str, colour: Colour) -> None:
        for i, ch in enumerate(text):
            grid[row][col + i] = ch
            tone[row][col + i] = colour

    w = PR - PL
    n = 2 * w  # two dot columns per cell
    # height above the plot floor, 1-based, of each (plot row, dot row)
    level = (PLOT_H - np.arange(PLOT_H))[:, None] * 4 - np.arange(4)
    for k, base in enumerate(BASE):
        v, env = series(rng, n, base, (int(n * 0.7), int(n * 0.8)) if k == SPIKE else None)
        top = 2 + k * (PLOT_H + GAP)
        h = np.round(v * PLOT_H * 4).astype(int).reshape(w, 2)  # filled dots per dot column
        raised = level[:, None, :, None] <= h[None, :, None, :]  # (plot row, cell, dot row, col)
        bits = (raised * DOT).sum(axis=(2, 3))
        hot = env[::2] > 0.3
        for cy in range(PLOT_H):
            for cx in np.flatnonzero(bits[cy]).tolist():
                put(
                    PL + cx,
                    top + cy,
                    chr(0x2800 + int(bits[cy, cx])),
                    (HOT if hot[cx] else IDLE)[cy],
                )
        put(2, top + PLOT_H - 1, f"C{k}", UI_HI if k == SPIKE else UI_ALT)
        put(COLS - 6, top + PLOT_H - 1, f"{round(v[-1] * 100):>3}%", UI_ALT)
        if k < len(BASE) - 1:
            put(PL, top + PLOT_H, "┈" * w, UI)

    # rounded frame with btop-style title notches
    put(0, 0, "╭" + "─" * (COLS - 2) + "╮", UI_ALT)
    put(0, ROWS - 1, "╰" + "─" * (COLS - 2) + "╯", UI_ALT)
    for j in range(1, ROWS - 1):
        put(0, j, "│", UI_ALT)
        put(COLS - 1, j, "│", UI_ALT)
    for x, label, colour in ((2, "cpu", UI_HI), (COLS - 12, "2000ms", UI_ALT)):
        put(x, 0, "┤", UI_ALT)
        put(x + 1, 0, label, colour)
        put(x + 1 + len(label), 0, "├", UI_ALT)

    glyphs(
        s,
        ["".join(r) for r in grid],
        lambda col, row, ch: tone[row][col],
        at=c - Vec(COLS * FW, ROWS * FH) / 2,
        font="8x16",
        px=1,
    )
