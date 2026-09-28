"""The Spire from Slay the Spire in void-and-cluster dither: a tapering tower cut by cloud wedges, lit windows near its base, and the Corrupt Heart as pixel art above its lit summit."""

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    ACCENT_8,
    ACCENT_HI,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    by_regime,
    design,
)
from walldye.field import cells, falloff, gauss, noise_grid
from walldye.pixel import Pixels, dither, grid_runs

type Field = NDArray[np.float64]
type Mask = NDArray[np.bool_]

CELL = 4
# Feature positions are units below the summit on the 16:9 tower, REF long; a longer portrait
# tower spreads them out and grows them by the square root of its extra length.
REF = 728
HW_TOP, TAPER, LEAN = 34, 34 / REF, 4  # summit half-width, its growth per unit down, base offset

# Fins off the flanks (side, base top, base height, reach, rise), placed from the main-menu tower.
FINS = (
    (1, 118, 28, 20, 14),
    (1, 208, 22, 14, 10),
    (1, 288, 30, 18, 20),
    (1, 438, 40, 52, 36),
    (-1, 78, 18, 12, 10),
    (-1, 258, 26, 14, 12),
    (-1, 548, 22, 18, 12),
)
# Bites out of the flanks (side, y, depth, height): the ragged mid-section.
NOTCHES = ((1, 168, 8, 30), (1, 348, 10, 44), (-1, 168, 7, 36), (-1, 388, 9, 28))
# Cloud wedges (y, x from and to the tower's axis, max thickness, slope, thick end: +1 right).
BANDS = (
    (208, -360, 340, 56, -34, -1),
    (418, -200, 520, 64, 26, 1),
    (613, -500, 260, 60, -22, -1),
)
WINDOWS, LOW = 368, 588  # lit windows start this far down, and crowd below the second depth

# Index grid: 0 sky (undrawn), 1-3 stone from dim to lit, 4 cloud, 5 its rim, then the accent
# ladder from 6 (ACCENT_8, nearly the sky) to 13 (ACCENT).
CLOUD, RIM, LIT = 4, 5, 6
PALETTE = (
    None,
    by_regime(BG_ALT, UI),
    by_regime(UI, UI_ALT),
    by_regime(UI_ALT, UI_HI),
    by_regime(BG_DEEP, BG_ALT),
    by_regime(BG_ALT, BG_DEEP),
    ACCENT_8,
    ACCENT_7,
    ACCENT_6,
    ACCENT_5,
    ACCENT_4,
    ACCENT_3,
    ACCENT_2,
    ACCENT,
)

# Corrupt Heart traced from the wiki sprite (14 px per cell): d rear vessels, a..e body and front
# vessels from shadow to light, r the glowing veins.
HEART = """
...........................aa
.............ddd.aaa......aaa......d..dd
aaaa.........ddd.aaaadddd.aaa......d..dd
aaaa..........dd..aaaaddd.aaa......d.ddd
aaaa..........ddd..aaaadd.aaa......ddddd
aaa............ddd.aaaaaaaaaa......dddd
bba.............ddddaaaaaaaaa.....adddd
bba..............dddddaaaaaaa.....dddd
ccba..............dddddaaabba...dddddd
ccba..............ddddddabbba.dddddd
.ccba..............dddddabbbadddddd
.ccba.a............dddddbbbbadddd
.cecbba..aa........dddddbbbbad
..cccba.cba........dddddbbbba
...ccbbccba........dddabbbbba
...ccbbcba.........dddabbbbba
....bbbbba........dddddbbbcb
.....bbbbba......ddddddbbbcb
......bbbba.....dddddddbccba
.......bbbaa...dddddddbbccba
........bbabeecdddddddbbbbba
........aaceeeeerddddabbbbaa
........abceeeerrdaaaaabbaaa
.......ccbbceeerebbbbaaabbaa
......ccbbbceeerrrbbbbabbbb
.....rccbbbccerrerbbbcbbbbb
....rrccbbbccrreeerbbccbbbcb
...crrbcbbbccreeeebrbcccbbbb
..ccrbcbbbbcbrceecbbrcccbbbb
..cbrbbbbbbccrccccbbrcccbbbb
..cbrrbbbbbccbbberrbbbccbbbb
..bbrrbbbbbccbbbrrbbbbccbaba
.ebbrrbbbbcccbbrrcbbbbbbbaaa
.ebbrbrbbbccbbrccbbbbbbbbaaa
.ebbrbbbbcccbbrccbbbbbbbbaadd
.cbbrbbabeccbrrecbbbbbbbbaadddd
..brraaabccccrrrbcbbbbbbbadddddd
..brraaacccccbercbbbbbbbbd.ddd
..baaaaaccccbcerrrbbbbbrbddddd
..aaaaabecccbcerrbbbbbrrbddddd
...aaaabeecccerbcbbbbbcbaddddd
...aaarbcccccecccbbbbccb.ddddd
....aarccccceebccbbbbcba...ddd
....aarcccccecbcbbabbba
....aaabccccecccbaaaa
.....aabcccceeecbaaa
......abcccceecbaa
.......accccecbaa
........bcccbba
.........bbbaa
""".strip("\n").split("\n")
HEART_KEY = {"d": 1, "a": 2, "b": 3, "c": 4, "e": 5, "r": 6}
HALO = 7
HEART_PALETTE = (None, ACCENT_6, ACCENT_4, ACCENT_3, ACCENT_2, ACCENT_1, ACCENT_HI, BG)
HEART_COL, HEART_GAP = 14, 10  # sprite column over the tower's axis; cells between it and summit


def tower_mask(
    px: Field, py: Field, x: float, top: float, length: float
) -> tuple[Mask, Mask, Field, Field]:
    """The tower (fins included), its fins alone, and the axis and half-width at each cell."""
    t = np.clip((py - top) / length, 0, 1)
    cx = x + LEAN * t
    hw = HW_TOP + TAPER * length * t
    k = length / REF
    # Jagged summit: the top edge steps between a few teeth, highest at the two corners like the
    # menu tower.
    teeth = top + 22 - 26 * gauss(np.abs(px - cx) - hw + 9, 8) - 8 * gauss(px - cx + 6, 5)
    body = (np.abs(px - cx) < hw) & (py > teeth)
    g = np.sqrt(k)  # features grow more slowly than the spacing between them
    for side, dy, d0, h0 in NOTCHES:
        y0, d, h = top + dy * k, d0 * g, h0 * g
        near = np.abs(py - y0) < h / 2
        body &= ~(near & (side * (px - cx) > hw - d * (1 - np.abs(py - y0) / (h / 2))))
    fin = np.zeros_like(body)
    for side, dy, h0, reach0, rise0 in FINS:
        y0, h, reach, rise = top + dy * k, h0 * g, reach0 * g, rise0 * g
        u = (px - (cx + side * hw)) * side  # outward distance from the flank
        # Triangle (0, y0) (0, y0 + h) (reach, y0 - rise): between the two slanted sides.
        lo = y0 - rise * u / reach
        hi = y0 + h - (h + rise) * u / reach
        fin |= (u > 0) & (u < reach) & (py > lo) & (py < hi)
    return body | fin, fin, cx, hw


def bands(s: Canvas, px: Field, py: Field, x: float, top: float, k: float) -> tuple[Field, Mask]:
    """Each band is a bundle of wispy streaks; returns density in [0, 1] and the lit upper rim."""
    lx = px - x
    val = np.zeros_like(px)
    rim = np.zeros_like(px, dtype=bool)
    for n, (dy, x0, x1, th0, slope, end) in enumerate(BANDS):
        r = s.np_rng(n + 1)
        yc, th = top + dy * k, th0 * np.sqrt(k)
        for m in range(7):
            sx0 = x0 + r.uniform(0, 0.35) * (x1 - x0)
            sx1 = x1 - r.uniform(0, 0.35) * (x1 - x0)
            u = (lx - sx0) / (sx1 - sx0)
            w = np.clip(u if end > 0 else 1 - u, 0, 1)
            # wedge: swells toward the thick end, snaps off past it
            taper = np.sin(np.pi * w**1.8) ** 0.6
            ph = r.uniform(0, 6, 2)
            wave = 5 * np.sin(lx / 71 + ph[0]) + 3 * np.sin(lx / 23 + ph[1])
            cy = yc + (m - 3) * th * 0.16 + slope * (u - 0.5) + wave
            thick = th * r.uniform(0.12, 0.3) * taper
            half = thick * (1 + 0.35 * np.sin(lx / r.uniform(17, 41) + ph[1]))
            d = 1 - np.abs(py - cy) / np.maximum(half, 1e-3)
            on = (u > 0) & (u < 1) & (d > 0)
            val = np.maximum(
                val, np.where(on, np.clip(d * 2.2, 0, 1) * np.clip(taper * 2, 0, 1), 0)
            )
            if m == 0:
                rim |= on & (py < cy - half + CELL * 1.5) & (taper > 0.3)
    return val, rim


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right third on a landscape screen, the base on the bottom edge; on a portrait one a taller
    # tower just right of centre, the Heart below the clock
    x, top = s.pick(landscape=(1400 / 1920, 352 / 1080), portrait=(0.56, 0.36), snap=CELL)
    length = s.h - top
    k = length / REF
    px, py = cells(s.inset(0), CELL)
    tower, fin, cx, hw = tower_mask(px, py, x, top, length)

    # Stone: lit from the left edge, with vertical masonry courses from a noise field stretched
    # 16 cells tall, sampled in the tower's own frame.
    u = np.clip((px - (cx - hw)) / (2 * hw), 0, 1)  # 0 at the lit left edge
    tone = 0.7 - 0.6 * u**0.9 + 0.22 * ((px - (cx - hw)) < 8)
    half = int(HW_TOP + TAPER * length) + 8
    rows = int(length) // (16 * CELL) + 1
    course = noise_grid(2 * half // CELL + 1, rows, 2, s.np_rng(7), octaves=2)
    ci = np.clip(((px - x + half) // CELL).astype(int), 0, course.shape[1] - 1)
    cj = np.clip(((py - top) // (16 * CELL)).astype(int), 0, rows - 1)
    tone -= 0.3 * np.clip(course[cj, ci] - 0.1, 0, 1)
    tone = np.where(fin, 0.62, tone)
    stone = np.where(tower, np.clip(tone, 0.3, 1), 0.0)
    idx = dither(stone, 4, method="bluenoise", rng=s.np_rng(11))

    # Summit light: a wide glow from the jagged top, rising softly around the Heart above it.
    glow = falloff(np.hypot((px - x) / 340, (py - top) / 130), 1, 1.8)
    glow = np.maximum(glow, 0.55 * falloff(np.hypot(px - x, (py - top + 130) * 1.1), 190, 2))
    gd = dither(glow * 0.7, 4, method="bluenoise", rng=s.np_rng(12))
    idx = np.where(~tower & (gd > 0), LIT - 1 + gd, idx)  # ACCENT_8 to ACCENT_6
    lit = falloff(py - top, 190, 1.3) * tower * (0.55 + 0.45 * (u < 0.5))
    ld = dither(lit, 2, method="bluenoise", rng=s.np_rng(13))
    idx = np.where(ld == 1, np.where(py < top + 50, LIT + 3, LIT + 2), idx)
    # The summit's teeth catch the light, horn tips brightest, over two lit rows.
    lip = tower & ~np.roll(tower, 1, axis=0) & (py < top + 30)
    below = np.roll(lip, 1, axis=0) | np.roll(lip, 2, axis=0)
    idx = np.where(tower & below & (py < top + 30), LIT + 4, idx)
    idx = np.where(lip, np.where(py < top, LIT + 7, LIT + 6), idx)

    # Lit windows: specks dense near the base, thinning upward; two-cell slits low down.
    rng = s.np_rng(21)
    win, low = top + WINDOWS * k, top + LOW * k
    cand = np.argwhere(tower & (py > win) & (np.abs(px - cx) < hw - 4))
    p = (((cand[:, 0] + 0.5) * CELL - win) / (s.h - win)) ** 1.8
    for j, i in cand[rng.random(len(cand)) < p * 0.3]:
        deep = j * CELL > low
        idx[j, i] = rng.choice(
            [LIT + 4, LIT + 5, LIT + 6, LIT + 7],
            p=[0.25, 0.3, 0.25, 0.2] if deep else [0.5, 0.3, 0.15, 0.05],
        )
        if deep and rng.random() < 0.35 and j + 1 < len(idx) and tower[j + 1, i]:
            idx[j + 1, i] = LIT + 5

    # Cloud wedges in front of everything: a solid body and a sparse lit upper rim.
    bv, rim = bands(s, px, py, x, top, k)
    bd = dither(bv, 2, method="bluenoise", rng=s.np_rng(14))
    rd = dither(np.where(rim, 0.45, 0.0), 2, method="bluenoise", rng=s.np_rng(15))
    idx = np.where(rd == 1, RIM, idx)
    idx = np.where(bd == 1, CLOUD, idx)
    grid_runs(s, idx, PALETTE, CELL)

    # The Heart, with a one-cell halo that keeps its silhouette clean against the glow.
    heart = Pixels(max(len(r) for r in HEART) + 2, len(HEART) + 2, HEART_PALETTE)
    heart.stamp(HEART, 1, 1, HEART_KEY)
    m = np.pad(heart.grid > 0, 1)
    halo = m[:-2, 1:-1] | m[2:, 1:-1] | m[1:-1, :-2] | m[1:-1, 2:]
    heart.grid[(heart.grid == 0) & halo] = HALO
    origin = (x - (HEART_COL + 1) * CELL, top - (HEART_GAP + heart.rows - 1) * CELL)
    heart.draw(s, CELL, origin)
