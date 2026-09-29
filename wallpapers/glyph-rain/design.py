"""Sparse digital rain of hex digits in 5x8 pixel glyphs; one lit stream falls behind an inverse head."""

from walldye import (
    ACCENT,
    ACCENT_6,
    ACCENT_7,
    ACCENT_HI,
    BG,
    BG_ALT,
    UI,
    Canvas,
    Color,
    design,
    ladder,
    mix,
)
from walldye.pixel import glyphs, grid_runs

PX, GAP = 3, 1  # font pixel; gap between glyph cells, in font pixels
CW, CH = (5 + GAP) * PX, (8 + GAP) * PX  # glyph cell
CHARS = "0123456789ABCDEF"
MIRRORED = 0.12  # share of glyphs drawn back to front
HERO_LEN = 16
TONES = ladder((BG_ALT, UI), 8)  # rain, from a faded tail to a bright head
# The lit stream from its head up: the digit knocked out of the head block, a glint, a fast
# fall from ACCENT to ACCENT_7, then a long tail from ACCENT_6 to ACCENT_7.
HERO_TONES = (
    BG,
    ACCENT_HI,
    *[mix(ACCENT_7, ACCENT, (1 - k / 5) ** 1.4) for k in range(5)],
    *ladder((ACCENT_6, ACCENT_7), HERO_LEN - 7),
)


@design(aspects="any")
def draw(s: Canvas) -> None:
    cols, rows = s.w // CW, s.h // CH + 1
    # the lit stream: right of center, its head a little below the middle
    focus = s.pick(landscape=(0.6875, 0.625), portrait=(0.62, 0.6))
    hero_col, hero_head = int(focus.x // CW), int(focus.y // CH)

    r = s.rng(7)
    cand = [c + r.randint(0, 1) for c in range(3, cols - 4, 3) if abs(c - hero_col) > 5]
    lanes = [c for c in cand if r.random() < 0.55 + 0.2 * c / cols]
    streams: list[tuple[int, int, int, float]] = []  # column, head row, length, brightness
    for c in lanes:
        head = top = bottom = r.randrange(5, rows - 3)
        streams.append((c, head, r.randint(7, 18), 0.7 + 0.3 * r.random()))
        if r.random() < 0.4 and head > 22:  # an older drop further up the same column
            top = head - r.randint(20, 26)
            streams.append((c, top, r.randint(4, 9), 0.5 + 0.2 * r.random()))
        # A tall screen stacks more drops above and below; a 1080-high one has room for neither.
        while top > 40:
            top -= r.randint(18, 34)
            streams.append((c, top, r.randint(5, 16), 0.5 + 0.4 * r.random()))
        while bottom < rows - 40:
            bottom += r.randint(18, 34)
            streams.append((c, bottom, r.randint(5, 16), 0.5 + 0.4 * r.random()))

    # Drops in one column never overlap, so each cell lands in exactly one of the paint maps.
    chars: dict[tuple[int, int], str] = {}
    upright: dict[tuple[int, int], Color] = {}
    mirrored: dict[tuple[int, int], Color] = {}
    for c, head, length, lum in streams:
        for k in range(length):
            if 0 <= head - k < rows:
                chars[c, head - k] = r.choice(CHARS)
                paints = mirrored if r.random() < MIRRORED else upright
                paints[c, head - k] = TONES.at(lum * (1 - k / length) ** 1.6)
    for k in range(HERO_LEN):
        chars[hero_col, hero_head - k] = r.choice(CHARS)
        paints = mirrored if r.random() < MIRRORED else upright
        paints[hero_col, hero_head - k] = HERO_TONES[k]

    # inverse head: a lit block over the head's cell, its digit drawn over it in BG
    block = [[1] * (CW // PX)] * (CH // PX)
    grid_runs(s, block, [None, ACCENT_HI], PX, (hero_col * CW - PX, hero_head * CH - PX))
    grid = [[" "] * cols for _ in range(-(-s.h // CH))]  # the rows that reach the canvas
    for (c, row), ch in chars.items():
        if row < len(grid):
            grid[row][c] = ch
    lines = ["".join(row) for row in grid]
    glyphs(s, lines, lambda i, j, _: upright.get((i, j)), at=(0, 0), font="5x8", px=PX, gap=GAP)
    glyphs(
        s,
        lines,
        lambda i, j, _: mirrored.get((i, j)),
        at=(0, 0),
        font="5x8",
        px=PX,
        gap=GAP,
        flip=True,
    )
