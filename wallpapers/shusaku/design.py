"""Shusaku vs Gennan (1846) replayed to move 127 on a Go board, with that move picked out."""

from walldye import ACCENT, ACCENT_3, BG, BG_ALT, UI, UI_ALT, Canvas, P, Vec, design

# Moves 1-127 of the game record (SGF coordinates: column then row, "a" = top-left).
RECORD = """
qd dc pq oc cp cf ep qo pe np po pp op qp oq oo pn qq nq on pm om pl mp mq ol pk lq lr kr lp kq
qr rr rs mr nr pr ps qs no mo qr rm rl qs lo mn qr qm or ql qj rj ri rk ln mm qi rq jn ls ns gq
go ck kc ic pc nj ke og oh pb qb ng mi mj nd ph qg pg hq hr ir iq hp jr fc lc ld mc lb mb md qf
pf qh rg rh sh rf sg pj pi oi oj ni qk ok qe kb jb ka jc ob ja la db cc fe cn gr is fq io ji
"""

N, PITCH, STONE = 19, 44, 20  # board lines, line spacing, stone radius
SPAN = (N - 1) * PITCH
MARGIN = 144  # least gap between the board and the right edge in landscape
HOSHI = (3, 9, 15)  # star-point lines

type Cell = tuple[int, int]


def replay() -> tuple[dict[Cell, bool], Cell]:
    """The stones left after the last move, True for the first player's (Shusaku's), with
    captured groups removed; and the last move's point."""
    board: dict[Cell, bool] = {}

    def neighbors(p: Cell) -> list[Cell]:
        x, y = p
        adjacent = ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
        return [(i, j) for i, j in adjacent if 0 <= i < N and 0 <= j < N]

    def captured(p: Cell) -> set[Cell]:
        """The group at `p` when it has no liberty left, else an empty set."""
        group, stack = {p}, [p]
        while stack:
            for q in neighbors(stack.pop()):
                if q not in board:
                    return set()
                if board[q] == board[p] and q not in group:
                    group.add(q)
                    stack.append(q)
        return group

    last = (0, 0)
    for k, m in enumerate(RECORD.split()):
        last, black = (ord(m[0]) - 97, ord(m[1]) - 97), k % 2 == 0
        board[last] = black
        for q in neighbors(last):
            if q in board and board[q] != black:
                for r in captured(q):
                    del board[r]
    return board, last


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: on the right third, pulled in to keep MARGIN; portrait: centered, below the middle
    c = s.pick(landscape=(0.71875, 0.5), portrait=(0.5, 0.6), snap=2)
    if s.landscape:
        c = Vec(min(c.x, s.w - MARGIN - SPAN / 2), c.y)
    o = c - (SPAN / 2, SPAN / 2)

    def at(i: int, j: int) -> Vec:
        return o + (i * PITCH, j * PITCH)

    grid = P()
    for i in range(1, N - 1):
        grid.M(at(i, 0)).V(o.y + SPAN).M(at(0, i)).H(o.x + SPAN)
    s.stroke(grid, BG_ALT, 1.5)
    s.stroke(P().rect(o.x, o.y, SPAN, SPAN), UI, 1.5)
    s.fill(P().dots([at(i, j) for i in HOSHI for j in HOSHI], 5), UI)

    board, last = replay()
    black, white = P(), P()
    for p, is_black in board.items():
        if p != last:
            (black if is_black else white).circle(at(*p), STONE)
    s.fill(black, UI)
    s.path(white, fill=BG, stroke=UI_ALT, stroke_width=1.6)
    s.path(P().circle(at(*last), STONE + 1), fill=ACCENT, stroke=ACCENT_3, stroke_width=2)
