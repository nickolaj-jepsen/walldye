"""Anderssen and Kieseritzky's 1851 game replayed to mate on a flat board, the closing moves traced and the mating bishop picked out."""

from shapely import LineString, Polygon, box, union_all
from shapely.affinity import scale, translate
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from walldye import ACCENT, ACCENT_3, BG, BG_ALT, UI, UI_ALT, Canvas, P, Vec, by_regime, design
from walldye.geom import parts

# The full game in from-to squares; no castling, en passant or promotion was played.
RECORD = """
e2e4 e7e5 f2f4 e5f4 f1c4 d8h4 e1f1 b7b5 c4b5 g8f6 g1f3 h4h6 d2d3 f6h5 f3h4 h6g5 h4f5 c7c6
g2g4 h5f6 h1g1 c6b5 h2h4 g5g6 h4h5 g6g5 d1f3 f6g8 c1f4 g5f6 b1c3 f8c5 c3d5 f6b2 f4d6 c5g1
e4e5 b2a1 f1e2 b8a6 f5g7 e8d8 f3f6 g8f6 d6e7
"""
TRACED = 13  # half-moves traced, from 17.Nd5 to the mate
OLDER = 6  # of those, the ones through 19...Qxa1+, traced thinner
START = "RNBQKBNR"

SQ = 84  # square side
SPAN = 8 * SQ
GHOST_GAP = 84  # the taken pieces' offset from the board; they step one square apart
MARGIN = 160  # least gap between the board and the right edge in landscape

type Square = tuple[int, int]  # file, rank; a1 = (0, 0)


def sq(name: str) -> Square:
    return ord(name[0]) - 97, int(name[1]) - 1


type Piece = tuple[str, bool]  # letter, is the first player's
type Move = tuple[Square, Square, str]  # from, to, letter


def replay() -> tuple[dict[Square, Piece], list[Move], list[Piece]]:
    """The final position, every move, and the pieces taken in the order they fell."""
    board: dict[Square, Piece] = {}
    for f, p in enumerate(START):
        board[f, 0], board[f, 7] = (p, True), (p, False)
        board[f, 1], board[f, 6] = ("P", True), ("P", False)
    moves: list[Move] = []
    taken: list[Piece] = []
    for m in RECORD.split():
        a, b = sq(m[:2]), sq(m[2:])
        piece = board.pop(a)
        if b in board:
            taken.append(board[b])
        board[b] = piece
        moves.append((a, b, piece[0]))
    return board, moves, taken


def silhouette(kind: str) -> BaseGeometry:
    """A piece in a 100-unit box centered on the origin, base down, knights facing left."""

    def disc(x: float, y: float, r: float) -> BaseGeometry:
        return Point(x, y).buffer(r, quad_segs=24)

    base = box(-30, 29, 30, 40).buffer(2, join_style="mitre")
    if kind == "P":
        body = [Polygon([(-21, 30), (21, 30), (10, -3), (-10, -3)]), box(-16, -8, 16, -2)]
        body += [disc(0, -19, 14)]
    elif kind == "R":
        top = box(-23, -36, 23, -16)
        for x in (-10, 10):
            top = top.difference(box(x - 4, -40, x + 4, -27))
        body = [Polygon([(-21, 30), (21, 30), (16, -16), (-16, -16)]), top]
    elif kind == "B":
        mitre = scale(disc(0, -22, 10), 1.3, 1.8)
        mitre = mitre.difference(Polygon([(1, -30), (5, -33), (15, -18), (11, -15)]))
        body = [Polygon([(-18, 30), (18, 30), (7, -2), (-7, -2)]), box(-15, -7, 15, -2)]
        body += [mitre, disc(0, -44, 5)]
    elif kind == "N":
        head = Polygon(
            [
                (-24, 30), (24, 30), (25, 8), (21, -14), (12, -30), (2, -40), (-3, -46),
                (-6, -36), (-14, -32), (-26, -20), (-33, -8), (-30, -1), (-20, -1),
                (-10, -6), (-4, 0), (-16, 14),
            ]
        )  # fmt: skip
        body = [head.difference(disc(-7, -22, 3))]
    elif kind == "Q":
        tips = [(-22, -32), (-11, -37), (0, -40), (11, -37), (22, -32)]
        crown = [(-15, -10), (15, -10)] + [tips[4], (8, -20), tips[3], (3, -22), tips[2]]
        crown += [(-3, -22), tips[1], (-8, -20), tips[0]]
        body = [Polygon([(-22, 30), (22, 30), (10, -10), (-10, -10)]), Polygon(crown)]
        body += [box(-17, -12, 17, -6)] + [disc(x, y - 2, 4) for x, y in tips]
    else:
        body = [Polygon([(-22, 30), (22, 30), (11, -10), (-11, -10)]), box(-17, -15, 17, -9)]
        body += [Polygon([(-17, -14), (17, -14), (21, -30), (-21, -30)])]
        body += [box(-3, -50, 3, -30), box(-10, -45, 10, -39)]
    return union_all([base, *body])


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(0.65, 0.5), portrait=(0.5, 0.58), snap=2)
    if s.landscape:
        c = Vec(min(c.x, s.w - MARGIN - SPAN / 2), c.y)
    o = c - (SPAN / 2, SPAN / 2)

    def at(p: Square) -> Vec:
        return o + ((p[0] + 0.5) * SQ, (7.5 - p[1]) * SQ)

    squares = (P(), P())  # dark, light
    for f in range(8):
        for r in range(8):
            squares[(f + r) % 2].rect(o.x + f * SQ, o.y + (7 - r) * SQ, SQ, SQ)
    # the lighter squares take the step off the ground, so h1 reads light in both regimes
    s.fill(squares[0], by_regime(BG, BG_ALT))
    s.fill(squares[1], by_regime(BG_ALT, BG))
    s.stroke(P().rect(o.x, o.y, SPAN, SPAN), UI, 1.5)
    s.stroke(P().rect(o.x - 14, o.y - 14, SPAN + 28, SPAN + 28), UI, 1)

    board, moves, taken = replay()
    *traced, mate = moves[-TRACED:]
    trails, starts = (P(), P()), []
    for i, (a, b, kind) in enumerate(traced):
        pa, pb = at(a), at(b)
        pts = [pa, pb]
        if kind == "N":  # the long leg first
            long_first = abs(b[0] - a[0]) > abs(b[1] - a[1])
            pts.insert(1, Vec(pb.x, pa.y) if long_first else Vec(pa.x, pb.y))
        # break round pieces the move passes by, so no line runs through a figure
        passed = [Point(*at(q)).buffer(SQ * 0.42) for q in board if q not in (a, b)]
        line = LineString([tuple(q) for q in pts]).difference(union_all(passed))
        for part in parts(line):
            trails[i >= OLDER].poly(list(part.coords))
        starts.append(pa)
    s.stroke(trails[0], UI, 1.0)
    s.stroke(trails[1], UI, 1.5)
    s.path(P().dots(starts, 4), fill=BG, stroke=UI, stroke_width=1.5)

    k = SQ * 0.84 / 100
    shapes = {kind: scale(silhouette(kind), k, k, origin=(0, 0)) for kind in "PRNBQK"}
    white, black, ghosts = P(), P(), P()
    for p, (kind, is_white) in board.items():
        if p != mate[1]:
            ctr = at(p)
            (white if is_white else black).shape(translate(shapes[kind], ctr.x, ctr.y))
    # the first player's losses, stood off the board: up its left edge, or under it in portrait
    lost = sorted((kind for kind, first in taken if first), key="QRBNP".index)
    small = {kind: scale(shapes[kind], 0.9, 0.9, origin=(0, 0)) for kind in set(lost)}
    for i, kind in enumerate(lost):
        if s.landscape:
            ctr = Vec(o.x - GHOST_GAP, o.y + SPAN - SQ / 2 - i * SQ)
        else:
            ctr = Vec(o.x + SQ / 2 + i * SQ, o.y + SPAN + GHOST_GAP)
        ghosts.shape(translate(small[kind], ctr.x, ctr.y))
    # solid and dim in dark, hollow on paper: the first player's own style, a step quieter
    s.path(ghosts, fill=by_regime(UI, BG), stroke=UI, stroke_width=1.6)
    s.path(white, fill=by_regime(UI_ALT, BG), stroke=UI_ALT, stroke_width=1.5)
    s.path(black, fill=by_regime(BG, UI_ALT), stroke=UI_ALT, stroke_width=1.9)

    pa, pb = at(mate[0]), at(mate[1])
    s.stroke(P().M(pa).L(pb), ACCENT, 2.5)
    s.path(P().circle(pa, 4), fill=BG, stroke=ACCENT, stroke_width=2)
    bishop = translate(shapes["B"], pb.x, pb.y)
    s.path(P().shape(bishop), fill=ACCENT, stroke=ACCENT_3, stroke_width=1.5)
