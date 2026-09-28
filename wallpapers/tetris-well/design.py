"""A Tetris well mid-game: a stack played by a noisy El-Tetris bot, one T piece hanging over its dashed landing ghost."""

import math
from typing import Literal

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_8,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    P,
    Params,
    Rng,
    Vec,
    design,
    knob,
)


class Well(Params):
    piece: Literal["T", "I"] = knob(
        default="T", doc="T over a ragged stack, or I over a four-row gap about to clear"
    )


VARIANTS = {"four-lines": Well(piece="I")}

COLS, ROWS, CELL = 10, 20, 36
GAP, RX = 3, 3  # gutter between cells, corner radius
SEED, DIG_SEED = 64, 6  # the ragged game; the game built around an open column
DIG_COL = 9  # the column kept open for the I
DEPTH = 4  # rows below the stack top that stay in the lighter tone
HANG = 7  # grid row of the falling piece's lowest cell

type Cells = tuple[tuple[int, int], ...]
type Board = list[list[str | None]]
type Move = tuple[float, Cells, int, int]  # score, cells, column, row

SHAPES: dict[str, Cells] = {
    "I": ((0, 0), (1, 0), (2, 0), (3, 0)),
    "O": ((0, 0), (1, 0), (0, 1), (1, 1)),
    "T": ((0, 0), (1, 0), (2, 0), (1, 1)),
    "S": ((1, 0), (2, 0), (0, 1), (1, 1)),
    "Z": ((0, 0), (1, 0), (1, 1), (2, 1)),
    "J": ((0, 0), (0, 1), (1, 1), (2, 1)),
    "L": ((2, 0), (0, 1), (1, 1), (2, 1)),
}
# Rows count down from 0 at the top. Stack cells sink from UI to BG_ALT with age (row depth).
GREYS = (BG_ALT, UI)
BEVEL = (UI, UI_ALT)


def rotations(cells: Cells) -> list[Cells]:
    """The distinct quarter turns of a piece, each shifted to touch x = 0 and y = 0."""
    out: list[Cells] = []
    cur = cells
    for _ in range(4):
        mx, my = min(x for x, _ in cur), min(y for _, y in cur)
        norm = tuple(sorted((x - mx, y - my) for x, y in cur))
        if norm not in out:
            out.append(norm)
        cur = tuple((-y, x) for x, y in cur)
    return out


def fits(board: Board, cells: Cells, ox: int, oy: int) -> bool:
    return all(
        0 <= ox + x < COLS and oy + y < ROWS and (oy + y < 0 or board[oy + y][ox + x] is None)
        for x, y in cells
    )


def drop(board: Board, cells: Cells, ox: int) -> int | None:
    """The row a piece dropped in column `ox` comes to rest on, or None if it cannot enter."""
    oy = -4
    if not fits(board, cells, ox, oy):
        return None
    while fits(board, cells, ox, oy + 1):
        oy += 1
    return oy


def place(board: Board, cells: Cells, ox: int, oy: int, tag: str) -> tuple[Board, int]:
    """A copy of `board` with the piece locked in and full rows cleared, and the rows cleared."""
    b = [row[:] for row in board]
    for x, y in cells:
        b[oy + y][ox + x] = tag
    full = [j for j in range(ROWS) if all(c is not None for c in b[j])]
    fresh: Board = [[None] * COLS for _ in full]
    return fresh + [row for j, row in enumerate(b) if j not in full], len(full)


def score(board: Board, cells: Cells, oy: int, cleared: int) -> float:
    """El-Tetris (Dellacherie) evaluation of a board after a move."""
    filled = [[c is not None for c in row] for row in board]
    lo, hi = min(y for _, y in cells), max(y for _, y in cells)
    land = ROWS - (oy + hi) + (hi - lo) / 2
    rt = sum(
        (not r[0]) + (not r[-1]) + sum(r[i] != r[i + 1] for i in range(COLS - 1)) for r in filled
    )
    ct = sum(
        filled[0][i]
        + sum(filled[j][i] != filled[j + 1][i] for j in range(ROWS - 1))
        + (not filled[-1][i])
        for i in range(COLS)
    )
    holes = 0
    for i in range(COLS):
        col = [filled[j][i] for j in range(ROWS)]
        if True in col:
            holes += col[col.index(True) :].count(False)
    wells = 0
    for i in range(COLS):
        depth = 0
        for j in range(ROWS):
            left = i == 0 or filled[j][i - 1]
            right = i == COLS - 1 or filled[j][i + 1]
            if not filled[j][i] and left and right:
                depth += 1
                wells += depth
            else:
                depth = 0
    return -4.50 * land + 3.42 * cleared - 3.22 * rt - 9.35 * ct - 7.90 * holes - 3.39 * wells


def best(
    board: Board,
    kind: str,
    rots: list[Cells],
    rng: Rng | None = None,
    noise: float = 0.0,
    keep: int | None = None,
) -> Move | None:
    """The highest-scoring drop of piece `kind` in any of `rots`, each score jittered by up to
    `noise` from `rng`, never touching column `keep`; None when no drop fits."""
    moves: list[Move] = []
    for cells in rots:
        w = max(x for x, _ in cells) + 1
        for ox in range(COLS - w + 1):
            if keep is not None and any(ox + x == keep for x, _ in cells):
                continue
            oy = drop(board, cells, ox)
            if oy is None or oy + min(y for _, y in cells) < 0:
                continue
            nb, cl = place(board, cells, ox, oy, kind)
            jitter = rng.uniform(0, noise) if rng is not None else 0.0
            moves.append((score(nb, cells, oy, cl) + jitter, cells, ox, oy))
    return max(moves, key=lambda m: m[0]) if moves else None


def ready(board: Board, col: int) -> bool:
    """Whether the four bottom rows are full apart from column `col`."""
    return all(
        board[j][i] is not None for j in range(ROWS - 4, ROWS) for i in range(COLS) if i != col
    )


def play(rng: Rng, noise: float, keep: int | None = None) -> Board:
    """A 7-bag game. A free game stops once the stack holds 52 cells; one that keeps column
    `keep` open stops once the four rows at the foot of that column are ready to clear."""
    board: Board = [[None] * COLS for _ in range(ROWS)]
    bag: list[str] = []
    for _ in range(400):
        if not bag:
            bag = list(SHAPES)
            rng.shuffle(bag)
        kind = bag.pop()
        move = best(board, kind, rotations(SHAPES[kind]), rng, noise, keep)
        if move is None:
            break
        _, shape, ox, oy = move
        board, _ = place(board, shape, ox, oy, kind)
        if keep is None and sum(c is not None for row in board for c in row) >= 52:
            break
        if keep is not None and ready(board, keep):
            break
    return board


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Well]) -> None:
    kind = s.params.piece
    # The floor of the well, under its centre: right of centre on a landscape screen, low and a
    # little right on a portrait one. Whole units, so every cell edge lands on the same grid.
    floor = s.pick(landscape=(0.71875, 5 / 6), portrait=(0.56, 0.8), snap=6)
    o = floor - (COLS * CELL / 2, ROWS * CELL)

    def cell(i: int, j: int) -> Vec:
        return o + (i * CELL + GAP / 2, j * CELL + GAP / 2)

    w = CELL - GAP
    if kind == "T":
        # Noise makes a sloppy mid-game player, so the stack grows ragged with a few holes.
        board = play(s.rng(SEED), 30)
        # Only the flat rotations, so the hanging T reads at a glance.
        rots = [c for c in rotations(SHAPES["T"]) if max(y for _, y in c) == 1]
    else:
        board = play(s.rng(DIG_SEED), 0, keep=DIG_COL)
        rots = [c for c in rotations(SHAPES["I"]) if max(x for x, _ in c) == 0]
    move = best(board, kind, rots)
    assert move is not None
    _, cells, gx, gy = move
    lift = HANG - max(y for _, y in cells)

    top = min(j for j in range(ROWS) if any(board[j]))
    with (
        s.buckets(GREYS, "fill") as fills,
        s.buckets(BEVEL, "stroke", stroke_width=2.5, stroke_linecap="round") as bevels,
    ):
        for j in range(ROWS):
            for i in range(COLS):
                if board[j][i] is None:
                    continue
                t = int(j < top + DEPTH)
                x, y = cell(i, j)
                fills[t].rrect(x, y, w, w, RX)
                bevels[t].M(x + 2.5, y + w - 5).V(y + 2.5).H(x + w - 5)

    # Well: a shaft whose walls run off the top edge.
    m = 6
    s.stroke(P().M(o.x - m, 0).V(floor.y + m).H(o.x + COLS * CELL + m).V(0), UI, 2)

    ghost = P()
    for x, y in cells:
        cx, cy = cell(gx + x, gy + y)
        ghost.rrect(cx + 1, cy + 1, w - 2, w - 2, RX)
    # 3 dash periods per side, phased so a dash sits centred on every rounded corner.
    edge, arc = w - 2 - 2 * RX, math.pi * RX / 2
    per, dash = (edge + arc) / 3, (edge + arc) / 5
    off = (edge + arc / 2 - dash / 2) % per
    s.path(
        ghost,
        fill=ACCENT_8,
        stroke=ACCENT_1,
        stroke_width=1.5,
        stroke_dasharray=(dash, per - dash),
        stroke_dashoffset=-off,
    )

    face, shade = P(), P()
    for x, y in cells:
        cx, cy = cell(gx + x, lift + y)
        face.rrect(cx, cy, w, w, RX)
        shade.M(cx + w - 2, cy + RX).V(cy + w - 2).H(cx + RX)
    s.fill(face, ACCENT)
    s.stroke(shade, ACCENT_1, 2.5, cap="round")
