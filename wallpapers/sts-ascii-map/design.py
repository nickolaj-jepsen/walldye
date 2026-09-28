"""A Slay the Spire act-one map in bitmap text, exactly as the game's map generator logs it, with one route lit up to the treasure floor."""

from walldye import ACCENT, ACCENT_2, ACCENT_4, UI, UI_ALT, UI_HI, Canvas, Rng, design, mix, ramp
from walldye.pixel import Pixels, glyph, glyphs

W_, H_, DENSITY = 7, 15, 6  # map columns, floors, paths
SEED = 24
ASCENSION = 1  # A1+ elite share (8% * 1.6)
CURRENT = 8  # the treasure floor, where the lit route ends
M, EV, E, R, S, T = "M", "?", "E", "R", "$", "T"

PX = 2  # font pixel, so an 8x16 character is 16 by 32
PITCH = 14  # line pitch in font pixels: tighter than the 16-row cell, so edges meet the rooms
LINE = 6 + 3 * W_  # characters per line of the dump
MAP_W, MAP_H = LINE * 8 * PX, ((2 * H_ - 1) * PITCH + 16) * PX
HEAD = 40  # the log line sits this far above the dump
LEGEND = "? Unknown  $ Merchant  T Treasure  R Rest  M Enemy  E Elite"

NODE = mix(UI_ALT, UI_HI, 0.3)
LIT = ramp(ACCENT_4, ACCENT_2, 2 * CURRENT + 1)  # the route brightens floor by floor
# Pixels palette: 0 is empty, then labels and edges, rooms, the current room, the route.
PALETTE = (None, UI, NODE, ACCENT, *LIT)
I_UI, I_NODE, I_NOW, I_LIT = 1, 2, 3, 4

type Edges = list[list[list[int]]]


def generate(r: Rng) -> tuple[Edges, list[list[int]]]:
    """Port of MapGenerator.createPaths/_createPaths + filterRedundantEdgesFromRow (via sts_lightspeed).

    Returns (edges, paths): edges[y][x] is a sorted list of dst x (row 14 points at the boss, x=3).
    """
    edges: Edges = [[[] for _ in range(W_)] for _ in range(H_)]
    parents: Edges = [[[] for _ in range(W_)] for _ in range(H_)]
    rr = r.randint  # randRange(min, max), inclusive

    def common_ancestor(x1: int, x2: int, y: int) -> bool:
        # faithful to the game's `node1.x < node2.y` typo
        lo, hi = (x1, x2) if x1 < y else (x2, x1)
        if not parents[y][lo] or not parents[y][hi]:
            return False
        return max(parents[y][lo]) == min(parents[y][hi])

    def step(x: int, y: int) -> int:
        lo, hi = (0, 1) if x == 0 else (-1, 0) if x == W_ - 1 else (-1, 1)
        nx = x + rr(lo, hi)
        for px in list(parents[y + 1][nx]):
            if px == x or not common_ancestor(px, x, y):
                continue
            if nx > x:
                nx = x + rr(-1, 0)
                nx = x if nx < 0 else nx
            elif nx == x:
                nx = x + rr(-1, 1)
                nx = x - 1 if nx > W_ - 1 else x + 1 if nx < 0 else nx
            else:
                nx = x + rr(0, 1)
                nx = x if nx > W_ - 1 else nx
        if x > 0 and edges[y][x - 1]:
            nx = max(nx, max(edges[y][x - 1]))
        if x < W_ - 1 and edges[y][x + 1]:
            nx = min(nx, min(edges[y][x + 1]))
        return nx

    starts: list[int] = []
    paths: list[list[int]] = []
    for i in range(DENSITY):
        x = rr(0, W_ - 1)
        while i == 1 and x == starts[0]:
            x = rr(0, W_ - 1)
        starts.append(x)
        paths.append([x])
        for y in range(H_ - 1):
            nx = step(x, y)
            if nx not in edges[y][x]:
                edges[y][x].append(nx)
                edges[y][x].sort()
            parents[y + 1][nx].append(x)
            x = nx
            paths[-1].append(x)
        if 3 not in edges[H_ - 1][x]:
            edges[H_ - 1][x].append(3)
    seen: set[int] = set()
    for x in range(W_):
        keep: list[int] = []
        for d in edges[0][x]:
            if d not in seen:
                keep.append(d)
            seen.add(d)
        edges[0][x] = keep
    return edges, paths


def assign(r: Rng, edges: Edges) -> dict[tuple[int, int], str]:
    """Port of RoomTypeAssigner: fixed rows, rounded-share pool, shuffle, parent/sibling rules."""
    room: dict[tuple[int, int], str] = {}
    total = unassigned = 0
    for y in range(H_):
        for x in range(W_):
            if not edges[y][x]:
                continue
            if y in (0, 8, H_ - 1):
                room[(x, y)] = {0: M, 8: T}.get(y, R)
                total += 1
            else:
                unassigned += 1
                total += y != H_ - 2  # the game's row-13 counting quirk
    elite = 0.08 * (1.6 if ASCENSION else 1)
    pool: list[str] = []
    for k, share in ((S, 0.05), (R, 0.12), (E, elite), (EV, 0.22)):
        pool += [k] * round(total * share + 1e-9)
    pool += [M] * (unassigned - len(pool))
    r.shuffle(pool)

    par: dict[tuple[int, int], list[int]] = {(x, y): [] for y in range(H_) for x in range(W_)}
    for y in range(H_ - 1):
        for x in range(W_):
            for d in edges[y][x]:
                par[(d, y + 1)].append(x)

    def siblings(x: int, y: int) -> set[str | None]:
        return {room.get((s, y)) for p in par[(x, y)] for s in edges[y - 1][p] if s != x}

    def parent_rooms(x: int, y: int) -> set[str | None]:
        return {room.get((p, y - 1)) for p in par[(x, y)]}

    for y in range(1, H_ - 1):
        if y == 8:
            continue
        for x in range(W_):
            if not edges[y][x]:
                continue
            tried: set[str] = set()
            pick = M
            for i, k in enumerate(pool):
                if k in tried:
                    continue
                tried.add(k)
                if (k in (E, R) and y <= 4) or (k == R and y >= 13):
                    continue
                if k in siblings(x, y):
                    continue
                if k in (S, E, R, T) and k in parent_rooms(x, y):
                    continue
                pick = pool.pop(i)
                break
            room[(x, y)] = pick
    return room


def dump(edges: Edges, room: dict[tuple[int, int], str]) -> list[str]:
    """The exact MapGenerator.toString(map, true) text, top line first."""
    out: list[str] = []
    for y in range(H_ - 1, -1, -1):
        line = " " * 6
        for x in range(W_):
            ds = edges[y][x]
            line += (
                ("\\" if any(d < x for d in ds) else " ")
                + ("|" if x in ds else " ")
                + ("/" if any(d > x for d in ds) else " ")
            )
        out.append(line)
        line = f"{y} " + " " * (5 - len(str(y)))
        for x in range(W_):
            shown = (
                any(x in edges[y - 1][p] for p in range(W_)) if y == H_ - 1 else bool(edges[y][x])
            )
            line += f" {room[(x, y)] if shown else ' '} "
        out.append(line)
    return out


def lit_path(edges: Edges, paths: list[list[int]]) -> list[tuple[int, int]]:
    """First generated path that survived the row-0 filter, up to CURRENT, as [(x, y)]."""
    p = next(p for p in paths if all(p[y + 1] in edges[y][p[y]] for y in range(CURRENT)))
    return [(p[y], y) for y in range(CURRENT + 1)]


@design(aspects="any")
def draw(s: Canvas) -> None:
    r = s.rng(SEED)
    edges, paths = generate(r)
    lines = dump(edges, assign(r, edges))
    route = lit_path(edges, paths)

    def line_of(y: int, edge: bool) -> int:
        return 2 * (H_ - 1 - y) + (0 if edge else 1)

    # (line, column) -> palette index for the lit route, its current room and floor number
    hot: dict[tuple[int, int], int] = {(line_of(CURRENT, False), 0): I_LIT + len(LIT) - 1}
    for i, (x, y) in enumerate(route):
        hot[(line_of(y, False), 7 + 3 * x)] = I_NOW if y == CURRENT else I_LIT + 2 * i
        if y < CURRENT:
            nx = route[i + 1][0]
            hot[(line_of(y, True), 6 + 3 * x + (1 + (nx > x) - (nx < x)))] = I_LIT + 2 * i + 1

    # Lines overlap by two font rows; glyph ink spans rows 1-12, so no two lines touch.
    px = Pixels(LINE * 8, (len(lines) - 1) * PITCH + 16, PALETTE)
    for row, line in enumerate(lines):
        for c, ch in enumerate(line):
            if ch == " ":
                continue
            index = hot.get((row, c), I_NODE if c >= 6 and row % 2 else I_UI)
            px.grid[row * PITCH : row * PITCH + 16, c * 8 : c * 8 + 8][glyph(ch)] = index

    # The dump's centre: on the right third when landscape; a little low when portrait, where
    # x centres the block with the wider key under it.
    mid = s.pick(landscape=(0.804, 0.511), portrait=(0.4315, 0.55), snap=PX)
    x0, y0 = mid.x - MAP_W / 2, mid.y - (MAP_H + HEAD) / 2 + HEAD
    px.draw(s, PX, (x0, y0))
    glyphs(s, "Generated the following dungeon map:", UI, at=(x0, y0 - HEAD), font="5x8")
    # the key sits on the dump's bottom line: in the corner when landscape, under it when portrait
    glyphs(s, LEGEND, UI, at=(64 if s.landscape else x0, y0 + MAP_H + 16), font="5x8")
