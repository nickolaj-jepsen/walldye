"""Spelunky Classic's first Mines level drafted as a plan: Derek Yu's 4x4 room walk and 10x8 tile templates build it, and the cheapest route joins its two doors."""

import heapq
from collections.abc import Sequence
from itertools import pairwise

from shapely.geometry import box
from shapely.ops import unary_union

from walldye import ACCENT, BG, BG_ALT, BLACK, MUTED, UI, UI_ALT, UI_HI, Canvas, P, Rng, Vec, design
from walldye.pixel import glyphs

type Cell = tuple[int, int]  # (column, row), in tiles or in rooms
type Rooms = list[list[int]]  # room type by [column][row]: 0 off the walk, 1 to 3 on it
# [row][column]: "1" solid, "L" ladder, "P" ladder top, "E" entrance, "X" exit, "0" air
type Grid = list[list[str]]

T = 24  # canvas units per tile
RW, RH = 10, 8  # room size in tiles
COLS, ROWS = 4, 4
GW, GH = COLS * RW, ROWS * RH
X0, Y0 = 480, 156  # top-left corner of the tile grid
PW, PH = RW * T, RH * T
RAD = 10  # corner radius of the route

# Mines templates from scrRoomGen (idol and altar side rooms left out).
START = [
    "60000600000000000000000000000000000000000008000000000000000000000000001111111111",
    "11111111112222222222000000000000000000000008000000000000000000000000001111111111",
    "00000000000008000000000000000000L000000000P111111000L111111000L00111111111111111",
    "0000000000008000000000000000000000000L000111111P000111111L001111100L001111111111",
    "60000600000000000000000000000000000000000008000000000000000000000000002021111120",
    "11111111112222222222000000000000000000000008000000000000000000000000002021111120",
    "00000000000008000000000000000000L000000000P111111000L111111000L00011111111101111",
    "0000000000008000000000000000000000000L000111111P000111111L001111000L001111011111",
]
END = [
    "00000000006000060000000000000000000000000008000000000000000000000000001111111111",
    "00000000000000000000000000000000000000000008000000000000000000000000001111111111",
    "00000000000010021110001001111000110111129012000000111111111021111111201111111111",
    "00000000000111200100011110010021111011000000002109011111111102111111121111111111",
    "60000600000000000000000000000000000000000008000000000000000000000000001111111111",
    "11111111112222222222000000000000000000000008000000000000000000000000001111111111",
]
SIDE = [
    "00000000000010111100000000000000011010000050000000000000000000000000001111111111",
    "110000000040L600000011P000000011L000000011L5000000110000000011000000001111111111",
    "00000000110060000L040000000P110000000L110050000L11000000001100000000111111111111",
    "110000000040L600000011P000000011L000000011L0000000110000000011000000001112222111",
    "00000000110060000L040000000P110000000L110000000L11000000001100000000111112222111",
    "11111111110221111220002111120000022220000002222000002111120002211112201111111111",
    "11111111111112222111112000021111102201111120000211111022011111200002111112222111",
    "11111111110000000000110000001111222222111111111111112222221122000000221100000011",
    "121111112100L2112L0011P1111P1111L2112L1111L1111L1111L1221L1100L0000L001111221111",
]
MAIN1 = [
    "60000600000000000000000000000000000000000050000000000000000000000000001111111111",
    "60000600000000000000000000000000000000005000050000000000000000000000001111111111",
    "60000600000000000000000000000000050000000000000000000000000011111111111111111111",
    "60000600000000000000000600000000000000000000000000000222220000111111001111111111",
    "11111111112222222222000000000000000000000050000000000000000000000000001111111111",
    "11111111112111111112022222222000000000000050000000000000000000000000001111111111",
    "11111111112111111112211111111221111111120111111110022222222000000000001111111111",
    (
        "1111111111000000000L111111111P000000000L5000050000000000000000000000001111111111",
        "1111111111L000000000P111111111L0000000005000050000000000000000000000001111111111",
    ),
    "000000000000L0000L0000P1111P0000L0000L0000P1111P0000L1111L0000L1111L001111111111",
    "00000000000111111110001111110000000000005000050000000000000000000000001111111111",
    "00000000000000000000000000000000000000000021111200021111112021111111121111111111",
    (
        "2222222222000000000000000000L001111111P001050000L011000000L010000000L01111111111",
        "222222222200000000000L000000000P111111100L500000100L000000110L000000011111111111",
    ),
]
MAIN3 = [
    "00000000000000000000000000000000000000000050000000000000000000000000001111111111",
    "00000000000000000000000000000000000000005000050000000000000000000000001111111111",
    "00000000000000000000000000000050000500000000000000000000000011111111111111111111",
    "00000000000000000000000600000000000000000000000000000111110000111111001111111111",
    "00000000000111111110001111110000000000005000050000000000000000000000001111111111",
    "00000000000000000000000000000000000000000021111200021111112021111111121111111111",
    "10000000011112002111111200211100000000000022222000111111111111111111111111111111",
    (
        "0000000000000000000000000000L001111111P001050000L011000000L010000000L01111111111",
        "000000000000000000000L000000000P111111100L500000100L000000110L000000011111111111",
    ),
]
DROP = [
    "00000000006000060000000000000000000000006000060000000000000000000000000000000000",
    "00000000006000060000000000000000000000000000050000000000000000000000001202111111",
    "00000000006000060000000000000000000000050000000000000000000000000000001111112021",
    "00000000006000060000000000000000000000000000000000000000000002200002201112002111",
    "00000000000000220000000000000000200002000112002110011100111012000000211111001111",
    "00000000000060000000000000000000000000000000000000001112220002100000001110111111",
    "00000000000060000000000000000000000000000000000000002221110000000001201111110111",
    "00000000000060000000000000000000000000000000000000002022020000100001001111001111",
    "11111111112222222222000000000000000000000000000000000000000000000000001120000211",
    "11111111112222111111000002211100000002110000000000200000000000000000211120000211",
    "11111111111111112222111220000011200000000000000000000000000012000000001120000211",
    "11111111112111111112021111112000211112000002112000000022000002200002201111001111",
]
# 5x3 obstacle chunks: '8' door pedestals, '5' ground, '6' air.
OBS = {
    "8": [
        "009000111011111",
        "009000212002120",
        "000000000092222",
        "000000000022229",
        "000001100119001",
        "000001001110091",
        "111111000140094",
        "000001202112921",
    ],
    "5": [
        "111110000000000",
        "000001111000000",
        "000000111100000",
        "000000000011111",
        "000002020017177",
        "000000202071717",
        "000000020277171",
        "000002220011100",
        "000000222001110",
        "000000022200111",
        "111002220000000",
        "011100222000000",
        "001110022200000",
        "000000222021112",
        "000002010077117",
        "000000010271177",
    ],
    "6": [
        "111110000000000",
        "222220000000000",
        "111002220000000",
        "011100222000000",
        "001110022200000",
        "000000111000000",
        "000000111002220",
        "000000222001110",
        "000000022001111",
        "000002220011100",
    ],
}


def level_path(r: Rng) -> tuple[Rooms, Cell, Cell]:
    """scrLevelGen's walk, dangling elses included: the room types and the start and end rooms.

    Type 1 is open left and right, 2 also below, 3 also above; 0 is a side room off the walk.
    """
    rp = [[0] * ROWS for _ in range(COLS)]
    x, y = r.randint(0, 3), 0
    start = end = (x, 0)
    rp[x][0] = 1
    px, py = x, 0
    while y < ROWS:
        dropped = False
        n = r.randint(3, 5) if x == 0 else r.randint(5, 7) if x == 3 else r.randint(1, 5)
        if n < 3 or n > 5:
            if x > 0:
                if rp[x - 1][y] == 0:
                    x -= 1
                elif x < 3:
                    if rp[x + 1][y] == 0:
                        x += 1
                    else:
                        n = 5
        elif n in (3, 4) and x < 3:
            if rp[x + 1][y] == 0:
                x += 1
            elif x > 0:
                if rp[x - 1][y] == 0:
                    x -= 1
                else:
                    n = 5
        if n == 5:
            y += 1
            dropped = True
            if y < ROWS:
                rp[px][py] = 2
                rp[x][y] = 3
            else:
                end = (x, y - 1)
        if not dropped:
            rp[x][y] = 1
        px, py = x, y
    return rp, start, end


def pick(r: Rng, rooms: Sequence[str | tuple[str, str]]) -> str:
    """A template from `rooms`; a pair is one template and its mirror image."""
    t = r.choice(rooms)
    return r.choice(t) if isinstance(t, tuple) else t


def room_template(r: Rng, rp: Rooms, c: int, row: int, start: Cell, end: Cell) -> str:
    """scrRoomGen's choice of template for room (c, row) of the Mines."""
    t = rp[c][row]
    above = rp[c][row - 1] if row else -1
    if (c, row) == start:
        return pick(r, START[4:8] if t == 2 else START[:4])
    if (c, row) == end:
        return pick(r, END[1:4] if above == 2 else END[2:6])
    if t == 0:
        return pick(r, SIDE)
    if t == 1:
        return pick(r, MAIN1)
    if t == 3:
        return pick(r, MAIN3)
    return pick(r, DROP[:8] if above == 2 else DROP)


def build(r: Rng) -> tuple[Rooms, Cell, Cell, Grid]:
    """One generated level: the room walk, its start and end rooms, and the GW x GH tile grid."""
    rp, start, end = level_path(r)
    grid = [["0"] * GW for _ in range(GH)]
    for row in range(ROWS):
        for c in range(COLS):
            room = list(room_template(r, rp, c, row, start, end))
            for i in range(80):
                if room[i] in OBS:
                    o = r.choice(OBS[room[i]])
                    for k in range(3):
                        room[i + 10 * k : i + 10 * k + 5] = list(o[5 * k : 5 * k + 5])
            for j in range(RH):
                for i in range(RW):
                    ch = room[j * 10 + i]
                    gx, gy = c * RW + i, row * RH + j
                    if (
                        ch == "1"
                        or (ch == "2" and r.random() < 0.5)
                        or (ch == "4" and r.random() < 0.25)
                    ):
                        if grid[gy][gx] == "0":
                            grid[gy][gx] = "1"
                    elif ch in "LP":
                        grid[gy][gx] = ch
                    elif ch == "9":
                        grid[gy][gx] = "E" if (c, row) == start else "X"
                        if gy + 1 < GH:
                            grid[gy + 1][gx] = "1"  # a door always stands on a brick
    return rp, start, end, grid


def find(grid: Grid, ch: str) -> Cell:
    """The first tile holding `ch`, in reading order."""
    return next((x, y) for y in range(GH) for x in range(GW) if grid[y][x] == ch)


def route(grid: Grid) -> list[Cell] | None:
    """Cheapest walk entrance -> exit: walk, fall, climb ladders, hop up to 2 tiles onto a ledge."""

    def solid(x: int, y: int) -> bool:
        return not (0 <= x < GW and 0 <= y < GH) or grid[y][x] == "1"

    def ladder(x: int, y: int) -> bool:
        return 0 <= x < GW and 0 <= y < GH and grid[y][x] in "LP"

    def rest(x: int, y: int) -> int | None:
        # fall until supported or caught by a ladder; None if the fall leaves the map
        while not solid(x, y + 1) and not ladder(x, y):
            y += 1
            if y >= GH:
                return None
        return y

    s, e = find(grid, "E"), find(grid, "X")
    dist: dict[Cell, float] = {s: 0}
    prev: dict[Cell, Cell] = {}
    q: list[tuple[float, Cell]] = [(0, s)]
    while q:
        d, (x, y) = heapq.heappop(q)
        if (x, y) == e:
            break
        if d > dist[(x, y)]:
            continue
        nxt: list[tuple[Cell, float]] = []
        for dx in (-1, 1):
            if not solid(x + dx, y):
                yy = rest(x + dx, y)
                if yy is not None:
                    nxt.append(((x + dx, yy), 1 + 0.2 * (yy - y)))
            for h in (1, 2):
                if (
                    all(not solid(x, y - k) for k in range(1, h + 1))
                    and not solid(x + dx, y - h)
                    and solid(x + dx, y - h + 1)
                ):
                    nxt.append(((x + dx, y - h), 2 + 2 * h))
        if not solid(x, y - 1) and (ladder(x, y) or ladder(x, y - 1)):
            nxt.append(((x, y - 1), 1.2))
        if ladder(x, y + 1) or (ladder(x, y) and not solid(x, y + 1)):
            nxt.append(((x, y + 1), 1.2))
        for n, w in nxt:
            if dist.get(n, 1e9) > d + w:
                dist[n] = d + w
                prev[n] = (x, y)
                heapq.heappush(q, (d + w, n))
    if e not in prev:
        return None
    cells = [e]
    while cells[-1] != s:
        cells.append(prev[cells[-1]])
    return cells[::-1]


def find_level(s: Canvas) -> tuple[Rooms, Grid, list[Cell]]:
    """The first level whose walk starts in column 2, takes 8 to 10 rooms, drops through two
    rooms in a row and ends in another column, and whose doors a route joins."""
    for sd in range(20000):
        rp, start, end, grid = build(s.rng(sd))
        path = [(c, rw) for c in range(COLS) for rw in range(ROWS) if rp[c][rw]]
        two_over_two = any(
            rp[c][rw] == 2 and rp[c][rw - 1] == 2 for c in range(COLS) for rw in range(1, ROWS)
        )
        if not (start[0] == 2 and 8 <= len(path) <= 10 and two_over_two and end[0] != start[0]):
            continue
        cells = route(grid)
        if cells:
            return rp, grid, cells
    raise RuntimeError("no level meets the brief")


@design()
def draw(s: Canvas) -> None:
    rp, grid, cells = find_level(s)

    def tx(i: float) -> float:
        return X0 + i * T

    def ty(j: float) -> float:
        return Y0 + j * T

    # faint tile lattice over the plate
    lat = P()
    for i in range(1, GW):
        lat.M(tx(i), Y0).V(ty(GH))
    for j in range(1, GH):
        lat.M(X0, ty(j)).H(tx(GW))
    s.stroke(lat, BG_ALT, 1)

    # terrain: hatched bricks inside, a cross-hatched bedrock ring, one outline round both
    with s.pattern(8, 8) as hatch:
        hatch.stroke(P().M(-2, 2).L(2, -2).M(0, 8).L(8, 0).M(6, 10).L(10, 6), UI, 1.2)
    with s.pattern(8, 8) as cross:
        cross.stroke(
            P()
            .M(-2, 2)
            .L(2, -2)
            .M(0, 8)
            .L(8, 0)
            .M(6, 10)
            .L(10, 6)
            # the other diagonal
            .M(-2, 6)
            .L(2, 10)
            .M(0, 0)
            .L(8, 8)
            .M(6, -2)
            .L(10, 2),
            UI,
            1.2,
        )
    bricks = unary_union(
        [
            box(tx(i), ty(j), tx(i + 1), ty(j + 1))
            for j in range(GH)
            for i in range(GW)
            if grid[j][i] == "1"
        ]
    ).simplify(0)
    plate = box(X0, Y0, tx(GW), ty(GH))
    ring = box(X0 - T, Y0 - T, tx(GW) + T, ty(GH) + T).difference(plate)
    s.fill(P().shape(ring), cross.ref)
    s.fill(P().shape(bricks), hatch.ref)
    s.stroke(P().shape(unary_union([bricks, ring]).simplify(0)), UI_ALT, 1.2)

    # ladders: rails and rungs, the 'P' top rung flush with the tile top
    lad = P()
    for j in range(GH):
        for i in range(GW):
            if grid[j][i] in "LP":
                x, y = tx(i), ty(j)
                lad.M(x + 6, y).V(y + T).M(x + T - 6, y).V(y + T)
                for k in (4, 12, 20) if grid[j][i] == "L" else (1, 8, 16):
                    lad.M(x + 6, y + k).H(x + T - 6)
    s.stroke(lad, UI_HI, 1.5)

    # knockout chips for the room type numerals
    chips = P()
    for rw in range(ROWS):
        for c in range(COLS):
            chips.rect(tx(c * RW) + 5, ty(rw * RH) + 5, 18, 24)
    s.fill(chips, BG)

    # room generator grid as a construction overlay (no walls between rooms in-game)
    rg = P()
    for c in range(COLS + 1):
        rg.M(tx(c * RW), Y0).V(ty(GH))
    for rw in range(ROWS + 1):
        rg.M(X0, ty(rw * RH)).H(tx(GW))
    s.stroke(rg, UI_HI, 1.2, dash=(6, 6))

    for rw in range(ROWS):
        for c in range(COLS):
            glyphs(
                s, [str(rp[c][rw])], MUTED, at=(tx(c * RW) + 9, ty(rw * RH) + 9), font="5x8", px=2
            )

    # doors: square stone frames round the opening, the entrance dim and the exit a deep hole
    frames = P()
    for ch, opening in (("E", UI), ("X", BLACK)):
        i, j = find(grid, ch)
        x, y = tx(i), ty(j)
        s.fill(P().rect(x + 1, y + 1, T - 2, T - 2), opening)
        frames.M(x + 1.5, y + T).V(y + 1.5).H(x + T - 1.5).V(y + T)
        frames.M(x + 5, y + T).V(y + 5).H(x + T - 5).V(y + T)
    s.stroke(frames, UI_HI, 1.5)

    # the route through the real tiles: hops turn up then across, falls across then down,
    # and straight runs merge into one leg
    pts: list[Cell] = []
    for a, b in pairwise(cells):
        pts.append(a)
        if a[0] != b[0] and a[1] != b[1]:
            pts.append((a[0], b[1]) if b[1] < a[1] else (b[0], a[1]))
    pts.append(cells[-1])
    turns = [pts[0]]
    for b, c in pairwise(pts[1:]):
        a = turns[-1]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) != 0:
            turns.append(b)
    turns.append(pts[-1])
    xy = [Vec(tx(i) + T / 2, ty(j) + T / 2) for i, j in turns]

    walk = P().M(xy[0])
    for a, b, c in zip(xy, xy[1:], xy[2:]):
        u, v = b - a, c - b
        r = min(RAD, abs(u) / 2, abs(v) / 2)
        walk.L(b - u.unit() * r).A(r, r, 0, 0, u.x * v.y - u.y * v.x > 0, b + v.unit() * r)
    walk.L(xy[-1])
    s.stroke(walk, ACCENT, 2.5, cap="round", join="round")

    # chevrons where the route falls through a room boundary
    arr = P()
    for a, b in pairwise(cells):
        if b[1] // RH > a[1] // RH:
            x, y = tx(b[0]) + T / 2, ty(b[1] // RH * RH) + T / 2
            arr.M(x - 6, y - 6).L(x, y).L(x + 6, y - 6)
    s.stroke(arr, ACCENT, 2.5, cap="round", join="round")

    s.fill(P().circle(xy[0], 4.5), ACCENT)
    s.path(P().circle(xy[-1], 4.5), fill=BLACK, stroke=ACCENT, stroke_width=2)

    # dimension lines outside the bedrock ring
    dim = P()
    dy = Y0 - T - 30
    dim.M(X0, dy).H(tx(GW))
    for c in range(COLS + 1):
        dim.M(tx(c * RW), dy - 8).V(dy + 8)
    for i in range(GW):
        if i % RW:
            dim.M(tx(i), dy - 3).V(dy + 3)
    dx = X0 - T - 30
    dim.M(dx, Y0).V(ty(GH))
    for rw in range(ROWS + 1):
        dim.M(dx - 8, ty(rw * RH)).H(dx + 8)
    for j in range(GH):
        if j % RH:
            dim.M(dx - 3, ty(j)).H(dx + 3)
    s.stroke(dim, UI_ALT, 1.2)
    for c in range(COLS):
        glyphs(s, ["10"], MUTED, at=(tx(c * RW) + PW / 2, dy - 26), font="5x8", anchor="middle")
    for rw in range(ROWS):
        glyphs(s, ["8"], MUTED, at=(dx - 28, ty(rw * RH) + PH / 2 - 8), font="5x8")

    # legend: type numeral + exit schematic; type 2 twice (plain, and under another 2)
    lx, ly = 1540, 250
    leg, tick = P(), P()
    bw, bh, g = 78, 62, 26
    rows = [("0", 0, 0, 0), ("1", 1, 0, 0), ("2", 1, 0, 1), ("2", 1, 1, 1), ("3", 1, 1, 0)]
    for k, (num, sides, top, bot) in enumerate(rows):
        y = ly + k * 100
        glyphs(s, [num], MUTED, at=(lx, y + bh / 2 - 8), font="5x8")
        bx = lx + 30
        for yy, open_ in ((y, top), (y + bh, bot)):
            m = bx + bw / 2
            if open_:
                leg.M(bx, yy).H(m - g / 2).M(m + g / 2, yy).H(bx + bw)
                tick.M(m - g / 2, yy - 5).V(yy + 5).M(m + g / 2, yy - 5).V(yy + 5)
            else:
                leg.M(bx, yy).H(bx + bw)
        for sx in (bx, bx + bw):
            if sides:
                b = y + bh - 10
                leg.M(sx, y).V(b - g).M(sx, b).V(y + bh)
                tick.M(sx - 5, b - g).H(sx + 5).M(sx - 5, b).H(sx + 5)
            else:
                leg.M(sx, y).V(y + bh)
    s.stroke(leg, UI_HI, 1.2)
    s.stroke(tick, MUTED, 1)

    # title block: level number, the room grid and how many rooms the walk takes
    tb = P()
    tx0, ty0, tx1, ty1 = 1540, 960, 1840, 1030
    tb.M(tx0, ty0).H(tx1).V(ty1).H(tx0).Z()
    tb.M(tx0 + 110, ty0).V(ty1)
    tb.M(tx0 + 110, (ty0 + ty1) / 2).H(tx1)
    s.stroke(tb, UI_ALT, 1.2)
    npath = sum(1 for c in range(COLS) for rw in range(ROWS) if rp[c][rw])
    glyphs(s, ["1-1"], MUTED, at=(tx0 + 55 - 22, ty0 + 35 - 12), font="5x8", px=3)
    glyphs(s, ["4x4"], UI_HI, at=(tx0 + 126, ty0 + 10), font="5x8")
    glyphs(s, [f"{npath:02d}"], UI_HI, at=(tx0 + 126, ty0 + 45), font="5x8")
