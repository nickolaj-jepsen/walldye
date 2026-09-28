"""A 2/2 twill tartan woven from a mirrored threadcount, its one thin overcheck picked out."""

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT_2, ACCENT_5, BG, BG_ALT, BG_DEEP, UI, Canvas, P, design, mix
from walldye.field import runs

T = 4  # thread width
TWILL = 4  # a 2/2 twill repeats every four threads
TONES = (BG, BG_DEEP, BG_ALT, mix(BG_ALT, UI, 0.6), ACCENT_5, ACCENT_2)
# Threadcount from the dark pivot to the accent pivot as (TONES index, threads); pivots are not
# repeated when mirrored. The dark pivot's count is a minimum that draw widens to fit the screen.
HALF = ((0, 190), (1, 6), (0, 6), (1, 6), (0, 22), (2, 36), (3, 3), (2, 17), (1, 5), (4, 1), (5, 3))
BAND = sum(k for _, k in HALF[1:-1])  # threads between the two pivots
PIVOT = HALF[-1][1]  # accent pivot threads


def threads(n: int, at: int, dark: int) -> NDArray[np.int64]:
    """TONES indices of `n` threads of the sett with a `dark`-thread dark pivot, phased so the
    accent pivot starts at thread `at`."""
    order = ((0, dark), *HALF[1:], *HALF[-2:0:-1])
    sett = np.repeat([t for t, _ in order], [k for _, k in order])
    return sett[(np.arange(n) - at + dark + BAND) % len(sett)]


def reach(n: int, at: int) -> int:
    """The fewest dark pivot threads that keep the neighbouring repeats' bands off an
    `n`-thread axis whose accent pivot starts at thread `at`."""
    return max(at - BAND, n - at - PIVOT - BAND)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the accent pivots cross high and right of centre, on a whole thread
    cross = s.pick(landscape=(0.6042, 0.2148), portrait=(0.6, 0.3), snap=T)
    ax, ay = round(cross.x / T), round(cross.y / T)
    nx, ny = s.w // T, s.h // T
    # a longer screen widens the dark ground rather than showing a second overcheck
    dark = max(HALF[0][1], reach(nx, ax), reach(ny, ay))
    warp, weft = threads(nx, ax, dark), threads(ny, ay, dark)

    # warp: full-height stripes; index 0 is the ground itself
    with s.buckets(TONES, "fill") as stripes:
        for k in range(1, len(TONES)):
            for a, b in runs(warp == k):
                stripes[k].rect(a * T, 0, (b - a) * T, s.h)

    # 2/2 twill: the weft floats over two warp threads, stepping one thread per row
    cells = P()
    for r in range(TWILL):
        for q in range(TWILL):
            if (q + r) % TWILL >= 2:
                cells.rect(q * T, r * T, T, T)
    floats = []
    for tone in TONES:
        with s.pattern(TWILL * T, TWILL * T) as pat:
            pat.fill(cells, tone)
        floats.append(pat.ref)
    with s.buckets(floats, "fill") as bands:
        for k in range(len(TONES)):
            for a, b in runs(weft == k):
                bands[k].rect(0, a * T, s.w, (b - a) * T)
