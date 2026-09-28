"""Spelunky Classic's idol room in pixel art: the idol on its altar under the giant tiki, a rope hung beside it and a room of ledges next door, traced from the game's sprites."""

from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_4,
    ACCENT_6,
    ACCENT_HI,
    BG_ALT,
    BG_DEEP,
    FG_ALT,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    by_regime,
    design,
    ladder,
)
from walldye.pixel import Pixels

PX = 5  # screen px per sprite px
T = 16  # sprite px per tile (80 screen px)
RX, RY = 11, 3  # idol room origin, in tiles

# The statue, altar and idol are shaded dark to light. Light themes run the stone steps and the
# accent ladder toward the text colour, which would print them as negatives, so there they take
# shades in the same dark-to-light order.
STONE = tuple(
    by_regime(dark, light)
    for dark, light in zip(
        (BG_DEEP, BG_ALT, UI, UI_ALT, UI_HI), ladder((UI_ALT, BG_DEEP), 5), strict=True
    )
)
IDOL_RAMP = (ACCENT_6, ACCENT_4, ACCENT_2, ACCENT_1, ACCENT, ACCENT_HI)
IDOL_SHADES = tuple(
    by_regime(dark, light) for dark, light in zip(IDOL_RAMP, IDOL_RAMP[::-1], strict=True)
)

# Index 0 is open cave, left undrawn; the rock and rope use the stone steps as they are.
PALETTE = (None, BG_DEEP, BG_ALT, UI, UI_ALT, UI_HI, MUTED, FG_ALT, *STONE, *IDOL_SHADES)


def key(shades: Mapping[str, Colour]) -> dict[str, int]:
    """Map each letter of a sprite to the PALETTE index of its shade."""
    return {ch: PALETTE.index(c) for ch, c in shades.items()}


# scrRoomGen side rooms (Spelunky Classic), '2' (50% block) rolled: the idol room is case 10
# (`2200000022/0000B00000/.../0000I00000/1111A01111`), its left neighbour the upper-plats case 1
# with its '5' ground obstacle expanded to case 9 (00000/02220/01110).
IDOL_ROOM = [
    "1100000001",
    "0000B00000",
    "0000000000",
    "0000000000",
    "0000000000",
    "0000000000",
    "0000I00000",
    "1111A01111",
]
UPPER_PLATS = [
    "0000000000",
    "0010111100",
    "0000000000",
    "0001101000",
    "0000000000",
    "0000100000",
    "0001110000",
    "1111111111",
]

# Sprites traced 1:1 from the Classic sources: sGoldIdol, sGiantTikiHead with bgTiki and
# bgTikiArms, sAltarL/R, sRope/sRopeTop/sRopeEnd, sBrick and sCaveTop.
IDOL = """
................
.....abbbba.....
....acddddca....
...acdeeeedca...
...adaaccaada...
...adbaddabda...
..bfeecddceefb..
..afddcbbcddfa..
..afbbaaaabbfa..
..abbacadacbba..
...agaaaaaaga...
...agacadacga...
...afgeeeegfa...
...aabcdbcbaa...
...acggccggca...
....accaacca....
"""

IDOL_KEY = key(
    {
        "a": IDOL_SHADES[0],
        "b": IDOL_SHADES[1],
        "c": IDOL_SHADES[2],
        "f": IDOL_SHADES[3],
        "d": IDOL_SHADES[4],
        "g": IDOL_SHADES[4],
        "e": IDOL_SHADES[5],
    }
)

HEAD = """
.aaaaaaaaaaaaaaaaaaaaaaaaaaaaa..
aabaabbccddbddddddddbddccbabbaa.
abbabbbbbbbdbbbbbbbbdbbbbbaabba.
aaabcccccdbdbdbddbdbdbdccccaaaa.
.abbbbbbbbbbbbddddbbbbbbbbbbba..
.abbbbbccdddebddddbedddccbbbbaaa
.abbbbcccddddbcddcbddddcccbbabba
aaabbcccbbbbddbccbddbbbbcccbabba
abbaccccddddbddbbddbddddccccbaaa
abbacccbbbbcdbdeedbdcbbbbcccbba.
abbaccbcdddbcdbddbdcbdddcbccbba.
abbacbcaaaadbdbddbdbdaaaacbcbba.
aaaadbcabbbdbdbddbdbdbbbacbcbba.
aaabdbcbbdddbdccccdbdddbbcbdbba.
aabbcbcccbbdbbccccbbdbbcccbcbba.
aabbccbbbddbdddeedddbddbbbccbba.
aabbdddccddbdaaddaadbddccdddbba.
aaabbddccddbdbaddabdbddccddbbba.
baabbcccbddcbdbddbdbcddbcccbbba.
bbabbccbdbdccbbbbbbccdbdbccbbba.
bbabccbbdbddccccccccddbdbbccbaaa
bbabccabddbabbabbabbabddbaccbaab
ababccabdddbddbddbddbdddbaccaabb
aaabcccabddbddbddbddbddbacccabbb
.abbbcccabbabbabbabbabbacccbabba
.abbbbcccddddddddddddddcccbbbaaa
.abbcbbccdddddbbbbdddddccbbcbba.
.abbccbbbbcccccddcccccbbbbccbba.
.aabccbbaaabbbbbbbbbbbbbbaaabaaa
..abccbabbaabbbbbbbbbbbaaabababb
..aabcbabbbaabbddbbbbbaabbbaaabb
...aaaaaaaaaaaaaaaaaaaaabbaaaabb
"""
HEAD_KEY = key({"a": STONE[0], "b": STONE[1], "c": STONE[2], "d": STONE[3], "e": STONE[4]})

BODY = """
aabaaaaabaccdcbbbbcdccabaaaaabaa
dabaaaddabcaadcddcdaacbaddaaabad
dabaaadddabcaabaabaacbadddaaabad
aabcaaadddaabbbbbbbbaadddaaacbaa
aabcaaaabdddaaaccaaaddddaaaacbaa
aacbcaabddddddaccadddddaaaacbcaa
accbccbdcaadddaccadddaaaaaccbcca
cccbccbaccaaaaaccaaaaaaaccccbccc
ccbbccaccccaaaccccaaaacccccbbbcc
bbbcbccccccccccbbccccccccccbcbbb
bbbcccccccbbbbbbbbbbbbcccccccbbb
bbbccaaacccbbbaaaabbbcccaaaccbbb
bbbcaaaccaacbaddddabcaaccaaacbbb
bbbccabcadcbaaddddaabcdacbaccbb.
.bbbcbcadacaaaaddaaaacadacbcbb..
.babccaaaacaaaaaaaaaacaaaaccb...
bacbccaaacaccaaccaaccacaaaccb...
bccbccaaacaacccbbcccaacaaaccb...
bcbccaaaacaaaccaaccaaacaaaaccb..
bbbccaaacaaaaddaaddaaaacaaabbb..
.bbccaaacaaaddddddddaaacabbdbb..
.bbcaaaacaaaddddddddaaacaddaab..
..dbaaaacaaaadaaaadaaaacaaaabd..
..cdbaaacaaaaaaaaaaaaaacaaabdc..
..cadbaaccaaaaaccaaaaaccaabdac..
..caadbbbbcaaaccccaaacbbbbdaac..
..bcaaddddbbbbbbbbbbbbddddaacb..
...bcaaaaaddddddddddddaaaaacb...
..bcbbcaaaaaaaaaaaaaaaaaacbbcb..
..bcacbbbbccaaaaaaaaccbbbbcacb..
..bcaaaacbbbbbbccbbbbbbcaaaacb..
..baddaaaabcaaccccaacbaaaaddab..
..baddaaaabbaaaaaaaabbaaaaddab..
.bcdddaaaacbcaaaaaacbcaaaadddcb.
.bcdddaaaacbcccaacccbcaaaadddcb.
.baddaaaaacbccccccccbcaaaaaddab.
.baddaaaaaccbccccccbccaaaaaddab.
bcadbaaaaaccbccccccbccaaaaaddacb
bcdadbbbaccbbbccccbbbccaaaadddcb
bcdabdddbbcbbbbbbbbbbccaaaaaddcb
badbdaaadbbbbbbbbbbbbbcaaaaaddab
baddaaaaccbb.bbbbbbbbbbcaaaaddab
badaaaaacbb.b.b.b.b.b.bbaaaaadab
baaaaaacbb.b.b.b.b.b.b.bcaaaaaab
baaaaaabb.b.b.b.b.b.b.bbbaaaaaab
baaaaaab.....b.b.b...bacbaaaaaab
bcaaaaabb.............bbbaaaaacb
bccccaacb..............bcaaccccb
bccccaaab..............baaaccccb
.bcccaaacb............bcaaacccb.
.bcccaaacb............bcaaacccb.
.bcccaaabb............bbaaacccb.
.bbcaabbcb............bcbbaacbb.
.bdbbbaacb............bcaabbbdb.
..bddaccbb............bbccaddb..
..baacccbb............bbcccaab..
..baacccbb............bbcccaab..
..baaaccbab..........babccaaab..
...baaccbcb..........bcbccaab...
...baacabbb..........bbbacaab...
...baaabbbb..........bbbbaaab...
..babbbcbb............bbcbbbab..
.baddaacb..............bcaaddab.
.baaaaccb..............bccaaaab.
"""
BODY_KEY = key({"a": STONE[2], "b": STONE[0], "c": STONE[1], "d": STONE[3]})

ARM_R = """
ab..............
dcbb............
dddcbb..........
cdddccbb........
ccccccccbb......
cccdddcddcb.....
ccdabacbbadb....
aaabcbaccbadb...
aabbbbbacbbdb...
abbbbabbbbbcb...
bbbbbbbbabcbb...
bbbbbbcbbbbb....
bb..bbabbbb.....
......bbbb......
"""
ARM_L = """
...............b
.............bbd
...........bbddd
.........bbcdddc
.......bbccccccc
.....bbccccccccc
....bcccccaabccc
...bcccbaaaccbaa
..bcccaddccacaaa
.bcccaccaaabbbaa
.bcccbcddcccbbbb
.bcccbccbaabbbbb
.bacbccddcccb...
.bbabcccaaabb...
..bbbccccccab...
...bbbaaaabb....
"""
ARM_KEY = key({"a": STONE[1], "b": STONE[0], "c": STONE[2], "d": STONE[3]})

ALTAR_L = """
aaaabcaaaaaaaaaa
dddcbcdddedddddd
eddbcddddddddddd
fffcgffgfffgffff
eeegeeefeeffeeee
eeeedddafdefegge
defeddddafggaffa
dddfdddddaafeade
dddedddddddefegg
dddeddddddddefga
dddedddddddddefd
dddfeeeefeeeeefe
dddaaaafaaaaaaaf
ddddddfaddddddda
edddddfedddddddd
feeeeeffeeeeeeef
"""
ALTAR_R = """
aaaaaaaaaaaaabca
dddddddddddddebd
ddddddddddddddef
eeeegeeeeeeeeeee
ffffefffffffefff
fggfefddddddefff
aeeaedddddddggfd
fdafeddddddgfage
ggfefdddddgefdaa
agefdddhddgaiddf
defdddcccbeihddd
feffbcbebccceddd
eaaaaaabihebcedd
addddddihddebced
dddddddfdddecbcf
effffffeffecbgbe
"""
# The halves use different letters for the same shades (dump order), hence two keys.
ALTAR_L_KEY = key(
    {
        "a": STONE[4],
        "d": STONE[3],
        "e": STONE[2],
        "f": STONE[1],
        "g": STONE[0],
        "b": STONE[2],
        "c": STONE[1],
    }
)
ALTAR_R_KEY = key(
    {
        "a": STONE[4],
        "d": STONE[3],
        "f": STONE[2],
        "e": STONE[1],
        "g": STONE[0],
        "c": STONE[2],
        "b": STONE[1],
        "h": STONE[0],
        "i": STONE[1],
    }
)

ROPE_SEG = ["abba", "acda"]
ROPE_TOP = """
...aa...
..abba..
.abaaca.
acadeaca
afaggafa
aaffafa.
.aaafa..
...aca..
"""
ROPE_END = """
..aaba..
.acabaa.
acaadada
cadbacba
abaacaba
adcaabda
.adbbda.
..aaaa..
"""
ROPE_KEY = key({"a": BG_DEEP, "b": UI_HI, "c": UI, "d": MUTED})
TOP_KEY = key({"a": BG_DEEP, "b": UI_HI, "c": UI_ALT, "d": FG_ALT, "e": MUTED, "f": UI, "g": UI})
END_KEY = key({"a": BG_DEEP, "b": UI_HI, "c": UI, "d": UI_ALT})

BRICK_ART = """
abaaaabbbbabaaaa
aaacbaabbaaaabba
aacbbaaaaaaabbbb
babbaaccbbaabbbb
baabacbbbbaaaabb
aaaaabbbbaacbaaa
aabbaabbaacbbbaa
abbbbaaaabbbbbab
abbbbabbabbbbaaa
aaabbabbbaaaabba
aaaaaaabbaaabbba
accabbaaaaaabbaa
cbbabbbaabbaaaab
bbbaabaaabbaabbb
bbaaaaacbaaaaabb
aaabaacbbbabbaaa
"""
# sBrick's two rock shades ('a', 'b') share one step; only its specks ('c') stand out.
BRICK_KEY = key({"a": BG_ALT, "b": BG_ALT, "c": UI})
BRICK = np.array([[BRICK_KEY[ch] for ch in row] for row in BRICK_ART.split()])
# sCaveTop rows 13-15: the lumpy lip drawn over every exposed tile top.
CAVE_TOP = ["........aa......", ".aa....abba.aa..", "accaaaabcccaccaa"]
LIP_KEY = key({"a": UI_ALT, "b": UI, "c": UI})


def level_tiles(tc: int, tr: int) -> NDArray[np.bool_]:
    """The (tr, tc) tile mask, True for solid rock, with the idol room and its left neighbour
    carved out."""
    m = np.ones((tr, tc), bool)
    for ox, room in ((RX - 10, UPPER_PLATS), (RX, IDOL_ROOM)):
        for j, row in enumerate(room):
            m[RY + j, ox : ox + len(row)] = [ch == "1" for ch in row]
    m[RY + 7, RX + 4 : RX + 6] = False  # the altar replaces the floor under the idol
    return m


# 16:9 only: the two rooms sit side by side at the game's scale.
@design()
def draw(s: Canvas) -> None:
    cols, rows = s.w // PX, s.h // PX
    tiles = level_tiles(-(-cols // T), -(-rows // T))
    px = Pixels(cols, rows, PALETTE)
    g = px.grid

    # Rock: sBrick in every solid tile, mirrored at random on each axis.
    rng = s.rng(4)
    for ty, tx in np.argwhere(tiles):
        b = BRICK[:, ::-1] if rng.random() < 0.5 else BRICK
        b = b[::-1] if rng.random() < 0.5 else b
        ys, xs = ty * T, tx * T
        g[ys : ys + T, xs : xs + T] = b[: rows - ys, : cols - xs]

    solid = tiles.repeat(T, 0).repeat(T, 1)[:rows, :cols]
    pad = np.pad(solid, 1, constant_values=True)
    up, down, left, right = (
        pad[1 + dy : 1 + dy + rows, 1 + dx : 1 + dx + cols]
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
    )
    # An edge line where rock meets open cave below or beside it; exposed tops get the sCaveTop lip.
    g[solid & ~(down & left & right)] = PALETTE.index(UI_ALT)
    g[solid & (~up | ~down) & (~left | ~right)] = 0  # round the convex corners

    for ty, tx in np.argwhere(tiles[1:] & ~tiles[:-1]):
        px.stamp(CAVE_TOP, int(tx) * T, int(ty + 1) * T - 3, LIP_KEY)

    # The statue: bgTiki body and arms behind, the giant head at (xpos, ypos - 4) of the 'B' tile.
    hx, hy = (RX + 4) * T, (RY + 1) * T
    px.stamp(BODY, hx, hy + 32, BODY_KEY)
    px.stamp(ARM_R, hx + 32, hy + 32, ARM_KEY)
    px.stamp(ARM_L, hx - 16, hy + 32, ARM_KEY)
    px.stamp(HEAD, hx, hy - 4, HEAD_KEY)

    ax, ay = (RX + 4) * T, (RY + 7) * T
    px.stamp(ALTAR_L, ax, ay, ALTAR_L_KEY)
    px.stamp(ALTAR_R, ax + T, ay, ALTAR_R_KEY)
    px.stamp(IDOL, ax + 8, ay - T, IDOL_KEY)

    # The rope, anchored under the ceiling beside the ledge, runs in 8px segments to the floor.
    rx, ry = (RX + 2) * T + 6, RY * T
    floor = (RY + 7) * T
    px.stamp(ROPE_TOP, rx - 2, ry, TOP_KEY)
    px.stamp([ROPE_SEG[y % 2] for y in range(ry + 8, floor - 8)], rx, ry + 8, ROPE_KEY)
    px.stamp(ROPE_END, rx - 2, floor - 8, END_KEY)

    px.draw(s, PX)
