"""Riley's Movement in Squares as a three-row checker frieze whose columns narrow by a power law
towards a fold, where the thinnest are lit."""

from itertools import pairwise

from walldye import ACCENT, ACCENT_1, ACCENT_3, UI, Canvas, design

X0, X1, FOLD = 160, 1760, 1220  # band ends, and the fold where the columns are thinnest
Y0, ROWS, CELL = 605, 3, 90
WMIN, POW = 3.0, 1.35  # column width at the fold; how steeply widths fall towards it
# Plain squares, slivers, the columns nearest the fold, and the core: indices 0 to 3.
TONES = (UI, ACCENT_3, ACCENT_1, ACCENT)
HEAT = 6.5  # columns narrower than this are slivers
CORE, HOT = 4, 12  # columns nearest the fold, by rank, that take the core, then the next tone


def edges(start: float, end: float) -> list[float]:
    """Column edges from `start` to `end`: the first column is CELL wide, and widths shrink
    with distance to `end` down to WMIN, the last one clipped so the list ends at `end`."""
    d, out, x = abs(end - start), [start], start
    step = 1 if end > start else -1
    while abs(end - x) > WMIN:
        w = (CELL - WMIN) * (abs(end - x) / d) ** POW + WMIN
        x += step * min(w, abs(end - x))
        out.append(x)
    out[-1] = end
    return out


@design()
def draw(s: Canvas) -> None:
    xs = edges(X0, FOLD) + edges(X1, FOLD)[::-1][1:]
    # half-pixel edges land on whole device pixels at 4K, so slivers don't shimmer
    cols = list(pairwise(round(x * 2) / 2 for x in xs))
    near = sorted(range(len(cols)), key=lambda c: abs(sum(cols[c]) / 2 - FOLD))
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
