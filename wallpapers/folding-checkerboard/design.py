"""A four-row checker frieze whose columns narrow toward two folds."""

from itertools import pairwise

from walldye import ACCENT, ACCENT_1, ACCENT_3, UI, Canvas, design

X0, X1 = 120, 1800  # band ends
SHALLOW, DEEP = (640, 12.0), (1330, 3.0)  # each fold's x and the column width at it
Y0, ROWS, CELL = 540, 4, 90
POW = 1.35  # how steeply widths fall towards a fold
# Plain squares, slivers, the columns nearest the deep fold, and the core: indices 0 to 3.
TONES = (UI, ACCENT_3, ACCENT_1, ACCENT)
HEAT = 6.5  # columns narrower than this are slivers
CORE, HOT = 4, 12  # columns nearest the deep fold, by rank, that take the core, then the next tone


def edges(start: float, end: float, wmin: float) -> list[float]:
    """Column edges from `start` to `end`: the first column is CELL wide, and widths shrink
    with distance to `end` down to `wmin`, the last one clipped so the list ends at `end`."""
    d, out, x = abs(end - start), [start], start
    step = 1 if end > start else -1
    while abs(end - x) > wmin:
        w = (CELL - wmin) * (abs(end - x) / d) ** POW + wmin
        x += step * min(w, abs(end - x))
        out.append(x)
    out[-1] = end
    return out


@design()
def draw(s: Canvas) -> None:
    (f1, w1), (f2, w2) = SHALLOW, DEEP
    mid = (f1 + f2) / 2  # between the folds the columns widen again, to full squares at mid
    xs = (
        edges(X0, f1, w1)
        + edges(mid, f1, w1)[::-1][1:]
        + edges(mid, f2, w2)[1:]
        + edges(X1, f2, w2)[::-1][1:]
    )
    # half-pixel edges land on whole device pixels at 4K, so slivers don't shimmer
    cols = list(pairwise(round(x * 2) / 2 for x in xs))
    near = sorted(range(len(cols)), key=lambda c: abs(sum(cols[c]) / 2 - f2))
    rank = {c: k for k, c in enumerate(near)}

    def tone(c: int) -> int:
        a, b = cols[c]
        if rank[c] < CORE:
            return 3
        if rank[c] < HOT:
            return 2
        return 1 if b - a < HEAT else 0

    with s.buckets(TONES, "fill") as squares:
        for c, (a, b) in enumerate(cols):
            for r in range(ROWS):
                if (c + r) % 2 == 0:
                    squares[tone(c)].rect(a, Y0 + r * CELL, b - a, CELL)
