"""A PICO-8-style sprite editor: a campfire sprite zoomed on the edit grid beside the half-filled sheet it was picked from, in pixel runs and bitmap labels."""

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_5,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Rng,
    design,
)
from walldye.pixel import Pixels, glyphs

COLS, ROWS = 16, 7
SP = 5  # sheet pixel; each cell is 9 pixels: a 1-pixel gutter plus the 8x8 sprite
CELL = 9 * SP
SW, SH = COLS * CELL + SP, ROWS * CELL + SP
EP = 40  # editor zoom; 8 * EP == SH so both panels share top and bottom edges
GAP = 80  # between the panels: side by side on landscape screens, stacked on portrait ones
BAR = 34  # palette strip and status bar height
LABEL = 36  # label row above each panel
SEL = (5, 2)

# '1' UI, '2' UI_ALT, '3' UI_HI (see calm()); flame: 'a' dark, 'b' body, 'c' heart, 'd' core.
ART = {
    (0, 0): "........|........|.1....1.|.1.1..1.|11.1.1.1|2222222|1111111|.1..1..1",  # grass
    (1, 0): "11111111|1....1..|1....1..|11111111|..1....1|..1....1|11111111|1....1..",  # brick
    (2, 0): "........|..2222..|.2331121|.2311111|.2111111|..11111.|........|........",  # boulder
    (3, 0): "........|..1..1..|.1.11.1.|........|........|.1..1...|1.11.11.|........",  # water
    (4, 0): "1......1|12222221|1......1|1......1|12222221|1......1|1......1|12222221",  # ladder
    (5, 0): ".222222.|2......2|2......2|2......2|2....3.2|2......2|2......2|2......2",  # door
    (6, 0): "..222...|.22222..|2223222.|2222222.|.22222..|...1....|...1....|..111...",  # tree
    (7, 0): "22222222|21....12|2.1..1.2|2..11..2|2..11..2|2.1..1.2|21....12|22222222",  # crate
    (0, 1): "........|.33.....|3..3....|3..3333.|.33..3.3|.....3..|........|........",  # key
    (1, 1): "........|.33.33..|3332333.|3222223.|.32223..|..323...|...3....|........",  # heart
    (2, 1): "........|..222...|.23332..|.23.32..|.23.32..|.23332..|..222...|........",  # coin
    (3, 1): "...22...|...11...|..2..2..|.2....2.|.233332.|.233332.|..2222..|........",  # potion
    (4, 1): "......3.|.....3..|....3...|.1.3....|..1.....|.2.1....|2.......|........",  # sword
    (5, 1): ".222222.|.233332.|.232232.|.233332.|.232232.|..2332..|...22...|........",  # shield
    (6, 1): "........|.222222.|21111112|22222222|21133112|21111112|22222222|........",  # chest
    (7, 1): "...3....|...3....|..333...|3333333.|.33333..|.3...3..|3.....3.|........",  # star
    (6, 2): "...3....|..3.3...|..3.3...|...3....|..222...|...2....|...2....|...2....",  # torch
    (7, 2): "........|..222...|.2...2..|..222...|...2....|.......|........|........",  # ring
    (0, 3): "..222...|.23332..|.3.3.3..|.33333..|..333...|..2.2...|........|........",  # skull
    (1, 3): "..222...|.22222..|.2.2.2..|.22222..|.22222..|.22222..|.2.2.2..|........",  # ghost
    (2, 3): "........|1..2..1.|12222221|12.22.21|.2.22.2.|...22...|........|........",  # bat
    (3, 3): "........|........|..222...|.22222..|.2.2.22.|2222222.|2222222.|........",  # slime
    (4, 3): "..222...|.23232..|2322232.|.......|...2....|...2....|..222...|........",  # mushroom
    (0, 4): "...3....|..333...|.3.3.3..|...3....|...3....|...3....|........|........",  # up
    (1, 4): "...3....|...3....|...3....|.3.3.3..|..333...|...3....|........|........",  # down
    (2, 4): "........|..3.....|.3......|3333333.|.3......|..3.....|........|........",  # left
    (3, 4): "........|....3...|.....3..|3333333.|.....3..|....3...|........|........",  # right
}

# Walk cycle, frames 0..3 on row 2: body fixed, legs vary.
BODY = "..222...|..222...|..222...|.22222..|2.222.2.|..222..."
LEGS = ["..2.2...|.2...2..", "..2.2...|..2.2...", "..2.2...|.2...2..", "...22...|...22..."]

FIRE = """
....a...
...ab...
..abb.a.
..bcbab.
.abcdbb.
.bcddba.
..3223..
.32..23.
"""

# Chunky 2-pixel-stroke letters, like a font drawn into the sheet by hand.
LETTERS = [
    ".111111.|.111111.|.11..11.|.111111.|.111111.|.11.....|.11.....|........",
    ".111111.|.111111.|...11...|...11...|...11...|.111111.|.111111.|........",
    "..11111.|.111111.|.11.....|.11.....|.11.....|.111111.|..11111.|........",
    "..1111..|.111111.|.11..11.|.11..11.|.11..11.|.111111.|..1111..|........",
    "..1111..|.11..11.|.111111.|..1111..|.11..11.|.111111.|..1111..|........",
]

# The sheet at full strength; the flame's heart and core share the accent itself.
SHEET = (None, UI, UI_ALT, UI_HI, ACCENT_3, ACCENT_1, ACCENT)
SHEET_KEY = {"1": 1, "2": 2, "3": 3, "a": 4, "b": 5, "c": 6, "d": 6}
# The editor one step dimmer than the sheet, so the selection frame stays the event.
ZOOM = (UI, UI_ALT, ACCENT_5, ACCENT_3, ACCENT_1, ACCENT)
ZOOM_KEY = {"1": 0, "2": 0, "3": 1, "a": 2, "b": 3, "c": 4, "d": 5}
SWATCHES = (BG_DEEP, BG_ALT, UI, UI_ALT, UI_HI, ACCENT)  # the last one is selected
FLAGS = (0, 1, 0, 0, 1, 0, 0, 0)  # sprite flags, as the eight toggles in PICO-8's editor


def calm(art: str) -> str:
    """Keep the sheet even and quiet: at most two UI_HI highlight pixels per sprite."""
    if art.count("3") <= 2:
        return art
    if "2" in art:
        return art.replace("2", "1").replace("3", "2")
    return art.replace("3", "2")


def invader(r: Rng) -> str:
    """Mirrored random 5-wide body padded to 8x8."""
    h = r.randint(4, 6)
    half: list[list[bool]] = []
    while sum(map(sum, half)) < 8:  # reject sparse fragments
        half = [[r.random() < 0.6 for _ in range(3)] for _ in range(h)]
    out = ["........"] * 8
    top = (8 - h) // 2
    for j, row in enumerate(half):
        bits = row + row[1::-1]
        tone = "2" if r.random() < 0.8 else "1"
        out[top + j] = "." + "".join(tone if b else "." for b in bits) + ".."
    return "|".join(out)


def rows(art: str) -> list[str]:
    """The pixel rows of `art`, written one per line or separated by '|'."""
    return art.strip("\n").replace("\n", "|").split("|")


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Panel origins: editor (ex, ey) and sheet (sx, sy). Landscape puts them side by side on
    # one baseline; portrait stacks the editor over the sheet, as PICO-8 itself does.
    if s.landscape:
        ex = (s.w - 8 * EP - GAP - SW) // 2
        sx = ex + 8 * EP + GAP
        ey = sy = (s.h - SH - 24 - BAR) // 2 + 12
    else:
        ex, sx = (s.w - 8 * EP) // 2, (s.w - SW) // 2
        drop = 8 * EP + 24 + BAR + GAP + LABEL  # editor top to sheet top
        span = LABEL + drop + SH + 24 + BAR
        ey = round(s.h * 0.46 - span / 2) + LABEL
        sy = ey + drop

    r = s.rng(8)
    art = {k: calm(a) for k, a in ART.items()}
    for f, legs in enumerate(LEGS):
        art[(f, 2)] = BODY + "|" + legs
    for k, a in enumerate(LETTERS):
        art[(4 + k, 4)] = a
    art[SEL] = FIRE
    # The sheet fills from the top left and trails off, like work in progress.
    for j in range(ROWS):
        for i in range(COLS):
            if (i, j) not in art and r.random() < 1.4 - i / 14 - j / 9:
                art[(i, j)] = invader(r)

    # Sheet: one index grid at sheet-pixel resolution, a 1-pixel gutter before each sprite.
    sheet = Pixels(COLS * 9 + 1, ROWS * 9 + 1, SHEET)
    for (i, j), a in art.items():
        sheet.stamp(rows(a), i * 9 + 1, j * 9 + 1, SHEET_KEY)
    s.fill(P().rect(sx, sy, SW, SH), BG_DEEP)
    sheet.draw(s, SP, (sx, sy))
    seps = P()
    for i in range(COLS + 1):
        seps.M(sx + i * CELL + SP / 2, sy).V(sy + SH)
    for j in range(ROWS + 1):
        seps.M(sx, sy + j * CELL + SP / 2).H(sx + SW)
    s.stroke(seps, BG_ALT, 1.5)
    ci, cj = SEL
    s.stroke(P().rect(sx + ci * CELL + SP / 2, sy + cj * CELL + SP / 2, CELL, CELL), ACCENT, 3)

    # Labels: sprite number over the editor, bank tabs over the sheet's right edge.
    glyphs(s, [f"{cj * COLS + ci:03d}"], UI_ALT, at=(ex - 6, ey - LABEL), font="5x8", px=3)
    glyphs(
        s,
        ["0 1 2 3"],
        lambda _c, _r, ch: UI_HI if ch == "0" else UI_ALT,
        at=(sx + SW + 3, sy - LABEL),
        font="5x8",
        px=3,
        anchor="end",
    )

    # Editor: the selected sprite at zoom.
    s.fill(P().rect(ex, ey, 8 * EP, 8 * EP), BG_DEEP)
    lines = P()
    for k in range(1, 8):
        lines.M(ex + k * EP, ey).V(ey + 8 * EP).M(ex, ey + k * EP).H(ex + 8 * EP)
    s.stroke(lines, BG_ALT, 1)
    with s.buckets(ZOOM, "fill") as b:
        for y, row in enumerate(rows(FIRE)):
            for x, ch in enumerate(row):
                if ch in ZOOM_KEY:
                    b[ZOOM_KEY[ch]].rect(ex + x * EP + 3, ey + y * EP + 3, EP - 6, EP - 6)
    s.stroke(P().rect(ex - 6, ey - 6, 8 * EP + 12, 8 * EP + 12), UI_ALT, 2)

    # Palette strip under the editor, spanning its frame; the first swatch matches the
    # editor ground, so it gets an outline.
    by = ey + 8 * EP + 24
    step = (8 * EP + 16) // 6
    for k, c in enumerate(SWATCHES):
        box = P().rect(ex - 6 + k * step, by, step - 4, BAR)
        if k == 0:
            s.path(box, fill=c, stroke=UI, stroke_width=1)
        else:
            s.fill(box, c)
    s.stroke(P().rect(ex - 6 + 5 * step - 5, by - 5, step + 6, BAR + 10), UI_HI, 2)

    # Status bar under the sheet: position, size and the flag toggles.
    ty = sy + SH + 24
    s.path(P().rect(sx, ty, SW, BAR), fill=BG_DEEP, stroke=BG_ALT, stroke_width=1.5)
    glyphs(s, [f"X{ci} Y{cj}   8X8"], UI_ALT, at=(sx + 16, ty + 9), font="5x8", px=2)
    on, off = P(), P()
    for k, flag in enumerate(FLAGS):
        (on if flag else off).rect(sx + SW - 16 - (8 - k) * 22 + 6, ty + 10, 14, 14)
    s.path(on, fill=UI_ALT, stroke=UI, stroke_width=1.5)
    s.stroke(off, UI, 1.5)
