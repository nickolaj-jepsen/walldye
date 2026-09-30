"""A `git log --graph` at transit-map scale: ringed commits on lanes that fork and merge."""

import math
from typing import NamedTuple

from walldye import ACCENT, BG, UI_ALT, Canvas, P, design, mix, smoothstep

LANE, PITCH, R = 62, 48, 7  # lane spacing, row pitch, commit ring radius
FEATURE = 1  # the lane drawn in ACCENT; no other branch uses it
FADE = 0.34 * 1080  # lane strokes fade in over this distance from the top and bottom edges
# One row per commit, top to bottom: o commit, | lane passing through, then an optional fork/merge
# "a>b" down to the next row. Every lane gets a commit, fork or merge at least every six rows.
# Rows 14-38 are the 16:9 sheet and fill every landscape screen; portrait screens show more of
# the history above and below, always centered on row CENTER, the middle of the feature branch.
HISTORY = """
o.|.|.
|.|.o. 4>5
|.o.||
o.|.||
|.|.|o 5>4
|.|.o.
|.o.|. 2>3
o.|||.
|.||o.
|.o||.
|.||o. 4>3
|.|o..
o.||..
|.o|..
o.||..
|.|o..
|.o|..
o.||..
|.|o.. 3>2
|.o...
o.|...
|.o... 2>3
o.||.. 0>1
|o||..
|||o.. 3>4
|o|||.
||||o.
|o|||. 3>2
||o.|.
|o|.|. 1>0
o.|.|.
|.|.o. 4>5
|.o.|| 2>0
o...||
|...o|
|...|o
o...||
|...o|
|...|o
o...|| 0>2
|.o.||
|.|.|o 5>4
o.|.|.
|.|.o.
|.o.|. 2>3
o.|||.
|.|o|.
|.||o. 4>5
|.o|||
|.|o|| 3>2
o.|.||
|.|.o|
|.o.||
"""
CENTER = 26


class Row(NamedTuple):
    commit: int  # lane of this row's commit
    lanes: frozenset[int]  # lanes present in this row
    move: tuple[int, int] | None  # fork or merge from lane a here to lane b in the next row


def parse(text: str) -> tuple[Row, ...]:
    """The rows of `text`, one per non-blank line in the HISTORY format."""
    rows = []
    for line in text.strip().splitlines():
        cells, *moves = line.split()
        lanes = frozenset(i for i, ch in enumerate(cells) if ch in "o|")
        move = None
        if moves:
            a, b = moves[0].split(">")
            move = (int(a), int(b))
        rows.append(Row(cells.index("o"), lanes, move))
    return tuple(rows)


ROWS = parse(HISTORY)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the lane group's center: right of center on landscape screens, centered on portrait ones
    x0 = s.pick(landscape=(81 / 128, 0.5), portrait=(0.5, 0.5), snap=1).x - 2.5 * LANE
    # enough rows to run past both edges, where the fade hides where the history starts and stops
    half = min(CENTER, len(ROWS) - 1 - CENTER, math.ceil(s.h / PITCH / 2 + 0.75))

    # one vertical fade shared by every lane stroke and ring: BG at the edges, UI_ALT mid-sheet
    # stops every 108 px across each edge ramp (the 16:9 sheet's ten stops); flat in between
    ds = (*range(0, 540, 108), *range(s.h - 432, s.h + 1, 108))
    fade = s.linear_gradient(
        [(d / s.h, mix(BG, UI_ALT, smoothstep(0, FADE, min(d, s.h - d)) ** 0.8)) for d in ds],
        (0, 0),
        (0, s.h),
    )

    def x(lane: int) -> float:
        return x0 + lane * LANE

    lines, dots, feature, feature_dots = P(), P(), P(), P()
    for i in range(CENTER - half, CENTER + half + 1):
        row = ROWS[i]
        y = s.h / 2 + (i - CENTER) * PITCH
        below = ROWS[i + 1].lanes if i + 1 < len(ROWS) else row.lanes
        move = row.move
        # a lane merging into one that is already here stops at this row
        merging = move[0] if move and move[1] in row.lanes else None
        edges = [(k, k) for k in sorted(row.lanes & below) if k != merging]
        if move:
            edges.append(move)
        for a, b in edges:
            d = feature if FEATURE in (a, b) else lines
            if a == b:
                d.M(x(a), y).V(y + PITCH)
            else:
                d.M(x(a), y).C(x(a), y + PITCH / 2, x(b), y + PITCH / 2, x(b), y + PITCH)
        # the feature branch's commits, and the merge commit that brings it back
        merged = i > 0 and ROWS[i - 1].move == (FEATURE, row.commit)
        (feature_dots if row.commit == FEATURE or merged else dots).circle((x(row.commit), y), R)

    s.stroke(lines, fade, 3)
    s.stroke(feature, ACCENT, 3)
    s.path(dots, fill=BG, stroke=fade, stroke_width=3)
    s.path(feature_dots, fill=BG, stroke=ACCENT, stroke_width=3)
