"""A mostly empty aquarium in coarse pixel art: sand, weed, bubbles and one fish against a school."""

import math

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_1,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    design,
    mix,
)
from walldye.pixel import Pixels

PX = 6  # one art pixel
# The sand rim shares the far weed's paint under its own index, so weed never mistakes it for a
# blade.
PALETTE = (None, BG_ALT, mix(BG_ALT, UI, 0.5), UI, UI_ALT, ACCENT_1, ACCENT, mix(BG_ALT, UI, 0.5))
FAR, MID, NEAR, BRIGHT, FIN, BODY, RIM = range(1, 8)

# Facing right; "f" marks the fins and tail, a step off the body on the lit fish.
FISH = """
......ff.....
f...#######..
ff.#######.##
.f###########
ff.#########.
f...######...
......f......
"""

SAND = 18  # sand depth in cells below its mean surface
# The school as offsets of each fish's top-left from the lead's, in cells: a chevron pointing
# left, its rows a little uneven.
SCHOOL = ((0, 0), (13, -6), (13, 7), (26, -11), (26, 1), (26, 13), (39, -7), (39, 7))
PEBBLE = [".h#.", "####"]


def blade(px: Pixels, x0: int, y0: int, height: int, lean: float, phase: float, tone: int) -> None:
    """A ribbon of weed rising `height` cells from (x0, y0), tapering from three cells wide
    to one by dropping cells on its left, its tip leaning `lean` cells right with the current
    plus a sway of up to 5 that only speeds or slows the lean. It steps at most one column per
    row and stops short of any weed of its tone already on the grid, a clear cell between."""
    taken = px.grid == tone
    x = x0
    for t in range(height):
        f = t / height
        want = x0 + round(lean * f * f + 5 * f * math.sin(phase + t / 13))
        x += int(want > x)  # only ever toward the lean, so the edges have no ledges or spurs
        w = 3 if f < 0.35 else 2 if f < 0.8 else 1
        y = y0 - t
        if np.any(taken[y - 1 : y + 2, max(x - 1, 0) : x + 4]):
            return
        px.grid[y, x + 3 - w : x + 3] = tone


BUBBLES = {1: ["b"], 2: ["bb", "bb"], 3: ["hbb", "b.b", "bbb"]}


def bubble(px: Pixels, x: int, y: int, size: int, body: int, hi: int) -> None:
    """A bubble with its top-left cell at (x, y), clipped to the grid: one cell, a 2x2 block,
    or a 3x3 ring with an open centre and a highlight cell on its upper left."""
    px.stamp(BUBBLES[size], x, y, {"b": body, "h": hi})


def fish(px: Pixels, x: int, y: int, *, left: bool, body: int, fin: int) -> None:
    px.stamp(FISH.strip().split("\n"), x, y, {"#": body, "f": fin}, flip=left)


@design(aspects="any")
def draw(s: Canvas) -> None:
    cols, rows = -(-s.w // PX), -(-s.h // PX)
    px = Pixels(cols, rows, PALETTE)
    ys = np.arange(rows)[:, None]
    xc = np.arange(cols)

    # Sand: a low rolling surface with a lit rim over solid grain that thickens with depth.
    n = s.noise(1)
    roll = n.fbm(xc / 90, 0.5, octaves=2)
    top = rows - SAND + np.round(3 * roll / np.abs(roll).max()).astype(int)
    below = ys > top[None, :]
    depth = np.clip((ys - top[None, :] - 1) / SAND, 0, 1)
    px.dither(0.35 + 0.65 * depth, (0, FAR), method="bayer", matrix=4, where=below)
    px.grid[top, xc] = RIM

    # Weed clumps bending with one current: tall at the left, short beside it, one on the right.
    # A clump's blades share one sway, so they run side by side; the tall clump has one blade
    # standing forward a step.
    clumps = (
        ((0.08, 4, 0.5, 1), (0.17, 3, 0.24, None), (0.9, 4, 0.34, None))
        if s.landscape
        else ((0.12, 4, 0.3, 1), (0.84, 3, 0.2, None))
    )
    r = s.rng(2)
    for fx, count, tall, front in clumps:
        x0 = round(fx * cols)
        lean, phase = r.uniform(4, 8), r.uniform(0, 6.3)
        for k in range(count):
            bx = x0 + round((k - count / 2) * 7)
            h = round(tall * rows * r.uniform(0.6, 1.0))
            tone = NEAR if k == front else MID
            # stand the base on the highest of its three rim cells, filling down to the others
            y0 = int(top[bx : bx + 3].min())
            for c in range(bx, bx + 3):
                px.grid[y0 : top[c], c] = tone
            blade(px, bx, y0, h, lean + k * 0.5, phase + k * 0.15, tone)

    # Bubbles: a column rising off a pebble on the sand, each gap a fifth wider than the one
    # below and the bubbles growing with it, fading a step over the upper third; the gaps are
    # scaled so the last bubble sits on the top edge, cut in half by the frame.
    bx = round(cols * (0.32 if s.landscape else 0.6))
    rest = int(top[bx - 2 : bx + 2].min()) - 1  # the pebble's lower row, on the highest rim cell
    for c in range(bx - 2, bx + 2):
        px.grid[rest : top[c], c] = NEAR
    px.stamp(PEBBLE, bx - 2, rest - 1, {"#": NEAR, "h": BRIGHT})
    base = rest - 4
    gaps = [4 * 1.2**i for i in range(40)]
    ends = np.cumsum(gaps)
    n = int(np.searchsorted(ends, base)) + 1
    scale = base / ends[n - 1]
    jitter = s.rng(3)
    for k in range(n + 1):
        y = base - (ends[k - 1] * scale if k else 0)
        gap = gaps[max(k - 1, 0)] * scale
        size = 3 if gap > 9 else 2
        x = bx + round(3 * math.sin(k * 0.9)) + jitter.randint(-1, 1) - size // 2
        high = y < base / 3
        bubble(px, x, round(y) - size // 2, size, MID if high else NEAR, NEAR if high else BRIGHT)

    # Fish: a chevron heading left behind its lead fish, and one lit fish passing over its
    # back half the other way, nose into the open water.
    lit = s.pick(landscape=(0.61, 0.3), portrait=(0.35, 0.33))
    lx, ly = round(lit.x / PX), round(lit.y / PX)
    fish(px, lx, ly, left=False, body=BODY, fin=FIN)
    for dx, dy in SCHOOL:
        fish(px, lx - 30 + dx, ly + 23 + dy, left=True, body=NEAR, fin=MID)

    px.draw(s, PX)
