"""Civilization V's tech tree from Agriculture to the Classical boundary: medallion tiles with pixel icons and bitmap names on the game's grid, bus wiring, and The Wheel under research."""

from typing import Literal

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_8,
    BG,
    BG_ALT,
    BG_DEEP,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    P,
    Path,
    Vec,
    design,
)
from walldye.pixel import glyphs, sprite

# Civ V BNW geometry (tile 270x60, column pitch 366, row pitch 68) scaled by 0.9.
BW, BH = 244, 54
PITCH, ROW = 330, 61
GAP = PITCH - BW  # between columns; the bus trunk runs down its middle
TREE_W = 3 * PITCH + BW
Y0 = 268
LW = 2
R = 7  # wiring corner radius
ICON = Vec(16, 14)  # icon's top-left in its tile: 9 cells of 3 px, kept on whole pixels
MEDAL = ICON + (13.5, 13.5)  # the round portrait is centred on the icon

type State = Literal["done", "todo", "now"]

# name: (column, row, state, icon, unlock count), per the BNW tree
TECHS: dict[str, tuple[int, int, State, str, int]] = {
    "Agriculture": (0, 5, "done", "wheat", 1),
    "Pottery": (1, 1, "done", "amphora", 2),
    "Animal Husbandry": (1, 4, "done", "cow", 4),
    "Archery": (1, 6, "done", "target", 2),
    "Mining": (1, 8, "done", "pick", 2),
    "Sailing": (2, 0, "todo", "ship", 5),
    "Calendar": (2, 1, "todo", "stones", 3),
    "Writing": (2, 2, "done", "quill", 3),
    "Trapping": (2, 4, "todo", "fox", 2),
    "The Wheel": (2, 6, "now", "wheel", 3),
    "Masonry": (2, 8, "done", "bricks", 5),
    "Bronze Working": (2, 9, "todo", "anvil", 5),
    "Optics": (3, 0, "todo", "scope", 3),
    "Horseback Riding": (3, 4, "todo", "horse", 4),
    "Mathematics": (3, 6, "todo", "divider", 3),
    "Construction": (3, 8, "todo", "arch", 4),
}
(NOW,) = [t for t in TECHS if TECHS[t][2] == "now"]  # exactly one tech is under research
EDGES = (
    ("Agriculture", "Pottery"),
    ("Agriculture", "Animal Husbandry"),
    ("Agriculture", "Archery"),
    ("Agriculture", "Mining"),
    ("Pottery", "Sailing"),
    ("Pottery", "Calendar"),
    ("Pottery", "Writing"),
    ("Animal Husbandry", "Trapping"),
    ("Animal Husbandry", "The Wheel"),
    ("Archery", "The Wheel"),
    ("Mining", "Masonry"),
    ("Mining", "Bronze Working"),
    ("Sailing", "Optics"),
    ("Trapping", "Horseback Riding"),
    ("The Wheel", "Horseback Riding"),
    ("The Wheel", "Mathematics"),
    ("The Wheel", "Construction"),
    ("Masonry", "Construction"),
)
# techs whose lines leave the crop toward later columns
EXITS = (
    "Calendar",
    "Writing",
    "Bronze Working",
    "Optics",
    "Horseback Riding",
    "Mathematics",
    "Construction",
)
TURNS = "4 Turns"
PROGRESS = 0.6  # of the research bar under the tech in progress

ICONS = {
    "wheat": """
..#.#.#..
.#.#.#.#.
..#.#.#..
...###...
....#....
...###...
..#.#.#..
.#..#..#.
#...#...#""",
    "amphora": """
..#####..
...###...
.#.###.#.
#.#####.#
.#######.
.#######.
..#####..
...###...
..#####..""",
    "cow": """
#.......#
##.....##
.#######.
.##.#.##.
..#####..
..#####..
..##.##..
...###...
.........""",
    "target": """
..#####..
.#.....#.
#..###..#
#.#...#.#
#.#.#####
#.#...#.#
#..###..#
.#.....#.
..#####..""",
    "pick": """
..#####..
.##.#.##.
##..#..##
#...#...#
....#....
....#....
....#....
....#....
....#....""",
    "ship": """
....#....
...###...
..#.#.#..
.#..#..#.
#########
....#....
#########
.#######.
..#####..""",
    "stones": """
.........
#########
#########
.##...##.
.##...##.
.##...##.
.##...##.
.##...##.
#########""",
    "quill": """
.......##
......###
.....###.
....###..
...###...
..###....
..##.....
.#.......
#........""",
    "fox": """
#.......#
##.....##
###...###
#########
#.##.##.#
.#######.
..#####..
...#.#...
....#....""",
    "wheel": """
..#####..
.#..#..#.
#.#.#.#.#
#..###..#
#########
#..###..#
#.#.#.#.#
.#..#..#.
..#####..""",
    "bricks": """
.........
#########
#...#...#
#########
#.#...#.#
#########
#...#...#
#########
.........""",
    "anvil": """
..###....
..###....
...#.....
.........
#########
.#######.
...###...
...###...
.#######.""",
    "scope": """
.......##
.....####
...####..
.####....
##.#.....
...#.....
..#.#....
.#...#...
#.....#..""",
    "horse": """
.....#.#.
....#####
...######
..###.###
.#######.
####.###.
##...###.
.....###.
.....###.""",
    "divider": """
....#....
...###...
...#.#...
..#...#..
..#...#..
.#.....#.
.#######.
#.......#
#.......#""",
    "arch": """
..#####..
.#######.
###...###
##.....##
##.....##
##.....##
##.....##
###...###
.........""",
}

# tile fill, border, ink (name and icon), unlock ring
STYLE: dict[State, tuple[Colour, Colour, Colour, Colour]] = {
    "done": (BG_ALT, UI_HI, MUTED, UI_HI),
    "todo": (BG, UI_ALT, UI_HI, UI_ALT),
    "now": (ACCENT_8, ACCENT, ACCENT, ACCENT_2),
}


@design()
def draw(s: Canvas) -> None:
    o = Vec((s.w - TREE_W) // 2, Y0)  # the tree's top-left, centred across the width

    def tile(t: str) -> Vec:
        c, r, *_ = TECHS[t]
        return o + (c * PITCH, r * ROW)

    def route(d: Path, a: str, b: str) -> None:
        """Append the bus route from a's right edge to b's left edge to `d`: a stub to the
        trunk halfway across the gap, down or up the trunk, then the feed into b."""
        p0 = tile(a) + (BW, BH / 2)
        p1 = tile(b) + (0, BH / 2)
        if p0.y == p1.y:
            d.M(p0).H(p1.x)
            return
        tx = p1.x - GAP / 2
        k = 1 if p1.y > p0.y else -1
        d.M(p0).H(tx - R).Q(tx, p0.y, tx, p0.y + k * R)
        d.V(p1.y - k * R).Q(tx, p1.y, tx + R, p1.y).H(p1.x)

    # era banners bleeding off both edges, and the divider just past the last trunk
    era_x = o.x + 3 * PITCH - GAP // 2 + 20
    top = Y0 - 46
    s.fill(P().rect(era_x, top + 22, LW, 10 * ROW + 40), BG_ALT)
    banners = P().rect(-LW, top, era_x + LW, 22).rect(era_x, top, s.w - era_x + LW, 22)
    s.path(banners, fill=BG_DEEP, stroke=UI_ALT, stroke_width=LW)
    for x0, x1, name in ((0, era_x, "Ancient Era"), (era_x, s.w, "Classical Era")):
        glyphs(s, name, UI_HI, at=((x0 + x1) // 2, top + 3), font="5x8", px=2, anchor="middle")

    grey, hot = P(), P()
    for a, b in EDGES:
        route(hot if b == NOW else grey, a, b)
    for t in EXITS:  # off the edge, as in a scrolled tree view
        grey.M(tile(t) + (BW, BH / 2)).H(s.w)
    s.stroke(grey, UI_ALT, LW)
    s.stroke(hot, ACCENT_3, LW)

    for state, (fill, border, ink, ring) in STYLE.items():
        techs = [(t, tile(t), v[3], v[4]) for t, v in TECHS.items() if v[2] == state]
        plates, medals, rings = P(), P(), P()
        for _, p, _, unlocks in techs:
            plates.rrect(p.x + 1, p.y + 1, BW - LW, BH - LW, 4)
            medals.circle(p + MEDAL, 22)
            for u in range(unlocks):
                rings.circle(p + (76 + u * 32, 35), 10)
        s.path(plates, fill=fill, stroke=border, stroke_width=LW)
        if state == "now":  # the research bar runs under the portrait
            p = tile(NOW)
            s.fill(P().rect(p.x + 3, p.y + BH - 7, round((BW - 6) * PROGRESS), 4), ACCENT_3)
            glyphs(s, TURNS, ACCENT_2, at=p + (BW - 10, 6), font="5x8", px=2, anchor="end")
        s.path(medals, fill=BG_DEEP, stroke=border, stroke_width=LW)
        s.path(rings, fill=UI if state == "done" else "none", stroke=ring, stroke_width=LW)
        for t, p, icon, _ in techs:
            sprite(s, ICONS[icon], {"#": ink}, 3, p + ICON)
            glyphs(s, t, ink, at=p + (60, 6), font="5x8", px=2)
