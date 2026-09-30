"""A sort drawn as wires: each number is a line at its place in the list, crossing the wire it swaps with."""

from typing import Literal

from walldye import ACCENT, BG, UI, UI_ALT, UI_HI, Canvas, P, Params, design, knob, ladder

type Column = list[tuple[int, int]]

TONES = ladder((UI, UI_ALT, UI_HI), 4)  # by value, low to high
WIRES = (2.0, 2.75, 3.5, 4.0)  # stroke width per tone rung
GAP = 3.5  # the BG casing each side of a wire, which makes every crossing an over-under
HERO = 5.5
SPAN = 1.6 * 0.88 * 1920  # the longest run of swaps, so ultrawide swaps keep their S
SHUFFLE = 15  # the starting order: its long climb starts low, right of center
LEAD = 3.0  # straight run at each end of a swap


class Sort(Params):
    algo: Literal["insertion", "bitonic"] = knob(default="insertion", doc="sorting algorithm")
    n: int = knob(default=32, choices=(16, 32, 64), doc="elements")


def insertion(a: list[int]) -> list[Column]:
    """Insertion sort's swaps on `a`, sorting it in place, each put one column after the last
    swap that touched either of its positions, so independent swaps share a column."""
    last = [-1] * len(a)
    cols: list[Column] = []
    for i in range(1, len(a)):
        j = i
        while j > 0 and a[j - 1] > a[j]:
            a[j - 1], a[j] = a[j], a[j - 1]
            k = max(last[j - 1], last[j]) + 1
            if k == len(cols):
                cols.append([])
            cols[k].append((j - 1, j))
            last[j - 1] = last[j] = k
            j -= 1
    return cols


def bitonic(a: list[int]) -> list[Column]:
    """The swaps of a bitonic sorting network on `a` (length a power of two), sorting it in
    place, one column per network stage that swaps anything."""
    n, cols, k = len(a), [], 2
    while k <= n:
        j = k // 2
        while j:
            col: Column = []
            for i in range(n):
                p = i ^ j
                if p > i:
                    lo, hi = (i, p) if i & k == 0 else (p, i)
                    if a[lo] > a[hi]:
                        a[lo], a[hi] = a[hi], a[lo]
                        col.append((lo, hi))
            if col:
                cols.append(col)
            j //= 2
        k *= 2
    return cols


@design(aspects="any", variants={"network": Sort(algo="bitonic")})
def draw(s: Canvas[Sort]) -> None:
    p = s.params
    n = p.n
    arr = list(range(n))
    s.rng(SHUFFLE).shuffle(arr)
    at = list(arr)  # the wire at each index
    cols = insertion(list(arr)) if p.algo == "insertion" else bitonic(list(arr))

    # t runs along the sort (left to right, or down on portrait screens), u across the wires
    length = s.w if s.landscape else s.h
    run = min(0.88 * length, SPAN)
    t0 = (length - run) / 2 if s.landscape else 0.08 * length
    t1 = t0 + run
    u0, u1 = (0.34 * s.h, 0.82 * s.h) if s.landscape else (0.14 * s.w, 0.72 * s.w)
    du = (u1 - u0) / (n - 1)
    # a column is wider the further its longest swap reaches, so long swaps don't turn vertical
    spans = [1 + max(j - i for i, j in col) / 2.5 for col in cols]
    step = (t1 - t0) / sum(spans)

    def pt(t: float, i: float) -> tuple[float, float]:
        u = u0 + i * du
        return (t, u) if s.landscape else (u, t)

    # each wire's swaps as (wire, start, end, from index, to index)
    pos = [0] * n
    for i, v in enumerate(arr):
        pos[v] = i
    start = list(pos)
    swaps: list[tuple[int, float, float, int, int]] = []
    t = t0
    for col, span in zip(cols, spans, strict=True):
        ta, tb = t + 0.15 * span * step, t + 0.85 * span * step
        t += span * step
        for i, j in col:
            at[i], at[j] = at[j], at[i]
            swaps += [(at[i], ta, tb, j, i), (at[j], ta, tb, i, j)]
    travel = [0] * n
    for v, _, _, a, b in swaps:
        travel[v] += abs(b - a)
    hero = max(range(n), key=lambda v: travel[v])

    # Flat runs go under every swap, and heavier swaps over lighter ones, so a crossing bundle
    # stays whole instead of cutting into dashes.
    rung = [TONES.rung(v / (n - 1)) for v in range(n)]
    flat = [P() for _ in TONES]
    # per direction, the wires and their casings, which stop short of each end so no casing
    # edge falls where a flat meets its swap
    moves = {d: ([P() for _ in TONES], [P() for _ in TONES]) for d in ("down", "up")}
    path = P().M(pt(-10, start[hero]))
    held = [-10.0] * n
    pos = list(start)
    for v, ta, tb, a, b in swaps:
        tm = (ta + tb) / 2
        k = 0.2 * (tb - ta)  # control points past the middle: flat shoulders, a steep crossing
        curve = (pt(tm + k, a), pt(tm - k, b), pt(tb - LEAD, b))
        if v == hero:
            path.L(pt(ta + LEAD, a)).C(*curve)
        else:
            r = rung[v]
            wires, casings = moves["up" if b < a else "down"]
            if ta - held[v] < 3 * (WIRES[r] + 2 * GAP) and held[v] > t0:
                # a short hold between two swaps goes on with them, cased, not as a stub
                wires[r].M(pt(held[v], a)).L(pt(ta + LEAD, a))
                casings[r].M(pt(held[v] + LEAD / 2, a)).L(pt(ta + LEAD, a))
            else:
                flat[r].M(pt(held[v], a)).L(pt(ta + LEAD, a))
                wires[r].M(pt(ta, a)).L(pt(ta + LEAD, a))
                casings[r].M(pt(ta + LEAD, a))
            wires[r].C(*curve).L(pt(tb, b))
            casings[r].C(*curve)
        held[v], pos[v] = tb - LEAD, b
    for v in range(n):
        if v != hero:
            flat[rung[v]].M(pt(held[v], pos[v])).L(pt(length + 10, pos[v]))
    path.L(pt(length + 10, pos[hero]))

    for r, d in enumerate(flat):
        s.stroke(d, TONES[r], WIRES[r])
    for r in range(len(TONES)):
        for wires, casings in moves.values():
            s.stroke(casings[r], BG, WIRES[r] + 2 * GAP)
            s.stroke(wires[r], TONES[r], WIRES[r])
    s.stroke(path, BG, HERO + 2 * GAP)
    s.stroke(path, ACCENT, HERO)
