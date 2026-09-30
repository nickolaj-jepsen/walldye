"""A NetHack-style level in bitmap glyphs: BSP rooms, cheapest-path corridors and an @ carrying a torch."""

import heapq
import math
from bisect import bisect

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    UI,
    UI_ALT,
    Canvas,
    Color,
    Rng,
    Vec,
    design,
)
from walldye.pixel import glyphs

COLS, ROWS = 80, 17  # NetHack-proportioned map
PX = 2  # the 8x16 font doubled, so a cell is 16 by 32
CW, CH = 8 * PX, 16 * PX
SEED = 8
KNOWN_X = 0.36  # rooms left of this fraction of the map stay unexplored and undrawn
KNOWN_X_TALL = 0.45  # a portrait screen leaves one more column of rooms unexplored
TORCH = 6.4  # radius in cell widths; cells are 1:2, so distance counts 2 * dy
# The torch pool steps down the accent ladder at these fractions of its radius.
TORCH_EDGES = (0.3, 0.55, 0.8)
TORCH_TONES = (ACCENT, ACCENT_1, ACCENT_3, ACCENT_5)
ITEMS = "!$)?%["
STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))

type Room = tuple[int, int, int, int]  # floor x, y, w, h in cells
type Tree = int | tuple[Tree, Tree]  # BSP split; leaves index the room list
type Cell = tuple[int, int]


def bsp(r: Rng, x: int, y: int, w: int, h: int, out: list[Room]) -> Tree:
    """Split the box x, y, w, h until it is small, append one room per leaf to `out` with at
    least one blank cell between neighbors, and return the split tree."""
    if w >= 28 and (w > 2.2 * h or r.random() < 0.6):
        k = r.randint(w * 2 // 5, w * 3 // 5)
        return bsp(r, x, y, k, h, out), bsp(r, x + k, y, w - k, h, out)
    if h >= 12:
        k = r.randint(h * 2 // 5, h * 3 // 5)
        return bsp(r, x, y, w, k, out), bsp(r, x, y + k, w, h - k, out)
    rw = r.randint(min(w - 4, max(4, w // 2)), w - 4)
    rh = r.randint(min(h - 4, max(2, h // 2)), h - 4)
    out.append((x + r.randint(2, w - rw - 1), y + r.randint(2, h - rh - 1), rw, rh))
    return len(out) - 1


def leaves(t: Tree) -> list[int]:
    """The room indices under `t`, left to right."""
    return [t] if isinstance(t, int) else leaves(t[0]) + leaves(t[1])


def center(room: Room) -> Cell:
    """The cell at the middle of a room's floor."""
    x, y, w, h = room
    return x + w // 2, y + h // 2


@design(aspects="any")
def draw(s: Canvas) -> None:
    r = s.rng(SEED)
    rooms: list[Room] = []
    tree = bsp(r, 0, 0, COLS, ROWS, rooms)
    m = [[" "] * COLS for _ in range(ROWS)]
    owner: list[list[int | None]] = [[None] * COLS for _ in range(ROWS)]
    for k, (x, y, w, h) in enumerate(rooms):
        for j in range(y - 1, y + h + 1):
            for i in range(x - 1, x + w + 1):
                m[j][i] = "-" if j in (y - 1, y + h) else "|" if i in (x - 1, x + w) else "."
                owner[j][i] = k

    def cost(i: int, j: int) -> float:
        """What stepping onto cell i, j costs a corridor."""
        ch = m[j][i]
        if ch in "-|":
            vert = 0 < j < ROWS - 1 and m[j - 1][i] in "-|+" and m[j + 1][i] in "-|+"
            horiz = 0 < i < COLS - 1 and m[j][i - 1] in "-|+" and m[j][i + 1] in "-|+"
            return 40 if vert != horiz else math.inf  # doors in wall runs, never in corners
        if ch == " " and any(
            m[j + dj][i + di] in "-|"
            for di, dj in STEPS
            if 0 <= i + di < COLS and 0 <= j + dj < ROWS
        ):
            return 8  # keep corridors off room walls
        return {" ": 3, "#": 1, "+": 1}.get(ch, 2)  # reuse corridors and doors

    edges: list[tuple[int, int, list[Cell]]] = []  # room a, room b, corridor cells

    def join(t: Tree) -> None:
        """Connect both halves of every split, bottom up, by a Dijkstra path between a random
        room on each side, carving # through rock and + through walls."""
        if isinstance(t, int):
            return
        join(t[0])
        join(t[1])
        a, b = r.choice(leaves(t[0])), r.choice(leaves(t[1]))
        src, dst = center(rooms[a]), center(rooms[b])
        dist: dict[Cell, float] = {src: 0}
        prev: dict[Cell, Cell] = {}
        heap: list[tuple[float, Cell]] = [(0, src)]
        while heap:
            d, (i, j) = heapq.heappop(heap)
            if (i, j) == dst:
                break
            for di, dj in STEPS:
                n = (i + di, j + dj)
                if 0 <= n[0] < COLS and 0 <= n[1] < ROWS and d + cost(*n) < dist.get(n, math.inf):
                    dist[n], prev[n] = d + cost(*n), (i, j)
                    heapq.heappush(heap, (dist[n], n))
        cells: list[Cell] = []
        c = dst
        while c != src:
            i, j = c
            if m[j][i] == " ":
                m[j][i] = "#"
            elif m[j][i] in "-|":
                m[j][i] = "+"
            if m[j][i] in "#+":
                cells.append(c)
            c = prev[c]
        edges.append((a, b, cells))

    join(tree)

    edge = COLS * (KNOWN_X if s.landscape else KNOWN_X_TALL)
    seen = {k for k in range(len(rooms)) if center(rooms[k])[0] >= edge}
    here = max(seen, key=lambda k: rooms[k][2] * rooms[k][3])
    for k, (x, y, w, h) in enumerate(rooms):
        if k == here:
            continue
        for _ in range(r.randint(0, 1)):
            i, j = r.randint(x, x + w - 1), r.randint(y, y + h - 1)
            m[j][i] = r.choice(ITEMS)
    wx, wy, ww, wh = rooms[(here + 2) % len(rooms)]  # a pool in a room two along
    for j in range(wy, wy + wh):
        for i in range(wx, wx + ww):
            if (
                math.hypot((i - wx - ww * 0.65) / (ww * 0.3), (j - wy - wh * 0.55) / (wh * 0.35))
                < 1
            ):
                m[j][i] = "~"
    x, y, w, h = rooms[-1 if here != len(rooms) - 1 else 0]
    m[y + h - 1][x + 1] = ">"

    # The @ stands in the big dark room: only its walls and the torch disc are known there.
    x, y, w, h = rooms[here]
    px, py = x + w // 2 - 1, y + h // 2
    m[py + 1][px + 3] = "d"
    known = {c for a, b, cells in edges if a in seen and b in seen for c in cells}
    known |= {
        (i, j)
        for j in range(ROWS)
        for i in range(COLS)
        if owner[j][i] in seen and (owner[j][i] != here or m[j][i] in "-|+")
    }
    lit: dict[Cell, float] = {}  # the room is convex, so the torch pool is a clipped disc
    for j in range(y - 1, y + h + 1):
        for i in range(x - 1, x + w + 1):
            f = math.hypot(i - px, 2 * (j - py)) / TORCH
            if f <= 1:
                lit[(i, j)] = f
    m[py][px] = "@"

    def color(i: int, j: int, ch: str) -> Color | None:
        """The @ at ACCENT, lit cells down the torch ladder, remembered cells in UI or UI_ALT,
        and nothing for the unknown."""
        if ch == "@":
            return ACCENT
        if (i, j) in lit:
            if ch in "-|+":
                return ACCENT_4  # light hitting the walls
            if ch == "d":
                return ACCENT_3  # the pet stays below the @
            return TORCH_TONES[bisect(TORCH_EDGES, lit[(i, j)])]
        if (i, j) in known and ch != "d":
            return UI if ch in ".#~-" else UI_ALT
        return None

    # Center what is drawn, not the whole map: the unexplored west is blank.
    drawn = known | lit.keys()
    i0, i1 = min(i for i, _ in drawn), max(i for i, _ in drawn) + 1
    j0, j1 = min(j for _, j in drawn), max(j for _, j in drawn) + 1
    c = s.pick(landscape=(0.619, 0.515), portrait=(0.5, 0.42), snap=PX)
    at = c - Vec((i0 + i1) * CW // 2, (j0 + j1) * CH // 2)
    glyphs(s, ["".join(row) for row in m], color, at=at, font="8x16", px=PX)
