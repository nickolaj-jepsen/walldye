"""A suspension bridge as an engineering elevation in line work, its main cable picked out."""

from itertools import pairwise

from walldye import ACCENT, ACCENT_3, BG, BG_ALT, UI, UI_ALT, UI_HI, Canvas, P, Vec, design

CX = 960  # the drawing is symmetric about the canvas centre line
DECK, CHORD = 640, 26  # top chord y, truss depth
TOWERS, TOP = (560, 1360), 244
SAG_Y = 610  # main cable low point
ANCHORS = (170, 1750)  # where the cable enters each anchorage face
ANCHOR_Y = 600
WATER, BANK = 830, 230
PANEL = 24
DASHDOT = (22, 6, 3, 6)


def cable_y(x: float) -> float:
    """Main cable: parabola across the main span, shallow sagging chords to the anchorages."""
    a, b = TOWERS
    if a <= x <= b:
        t = (x - (a + b) / 2) / ((b - a) / 2)
        return SAG_Y + (TOP - SAG_Y) * t * t
    x0, x1 = (ANCHORS[0], a) if x < a else (b, ANCHORS[1])
    y0, y1 = (ANCHOR_Y, TOP) if x < a else (TOP, ANCHOR_Y)
    t = (x - x0) / (x1 - x0)
    return y0 + (y1 - y0) * t + 26 * 4 * t * (1 - t)


def ground_y(x: float) -> float:
    """Banks and river bed as one bump: a flat bed, steepening banks, level at the shore."""
    u = min(1.0, abs(x - CX) / (CX - BANK))
    return 790 + 195 * (1 - u**4) ** 2


@design()
def draw(s: Canvas) -> None:
    # water, truss web and extension lines share one stroke
    fine = P()

    # water: waterline plus the drafting convention of staggered equal dashes, sparser with depth
    wet = [x for x in range(s.w) if ground_y(x) > WATER]
    fine.M(wet[0], WATER).H(wet[-1])
    dash = 22
    for k, (period, depth) in enumerate([(66, 14), (132, 28), (264, 42)]):
        y = WATER + depth
        for i in range(-30, 30):
            x = CX + i * period + (period / 2 if k % 2 == 0 else 0) - dash / 2
            clear = all(x + dash < tx - 64 or x > tx + 64 for tx in TOWERS)
            if clear and ground_y(x) > y + 24 and ground_y(x + dash) > y + 24:
                fine.M(x, y).H(x + dash)

    # ground line with earth hatching under it
    ground = P().poly([(x, ground_y(x)) for x in range(0, s.w + 1, 8)])
    earth = P()
    for x in range(4, s.w, 14):
        y = ground_y(x)
        earth.M(x, y + 4).L(x - 8, y + 12)
    s.stroke(earth, BG_ALT, 1.2)
    s.stroke(ground, UI_ALT, 1.4)

    # foundations: caissons below the piers, dashed as hidden lines
    hidden = P()
    for tx in TOWERS:
        foot = ground_y(tx) + 60
        hidden.poly([(tx - 56, WATER), (tx - 56, foot), (tx + 56, foot), (tx + 56, WATER)])
    for ax in ANCHORS:
        sign = 1 if ax < CX else -1
        outer, inner = ax - 105 * sign, ax + 45 * sign
        hidden.poly([(outer, 790), (outer, 900), (inner, 900), (inner, 790)])
    s.stroke(hidden, UI_ALT, 1.2, dash=(8, 6))

    hangers = P()
    for k in range(-40, 41):
        x = CX + k * PANEL
        if all(abs(x - tx) > 30 for tx in TOWERS) and ANCHORS[0] + 80 < x < ANCHORS[1] - 80:
            hangers.M(x, cable_y(x) + 2).V(DECK)
    s.stroke(hangers, UI_ALT, 1)

    # deck: a Warren truss whose chords run to each anchorage's outer face, hidden inside it
    x0 = ANCHORS[0] - 105
    chords = P().M(x0, DECK).H(s.w - x0).M(x0, DECK + CHORD).H(s.w - x0)
    for k in range(-37, 37):
        x = CX + k * PANEL
        fine.M(x, DECK).L(x + PANEL / 2, DECK + CHORD).L(x + PANEL, DECK)

    # dimension chain across anchorages and towers, plus navigation clearance at midspan
    yd = 150
    stops = [ANCHORS[0], *TOWERS, ANCHORS[1]]
    for x in stops:
        fine.M(x, yd - 12).V(yd + 14 if x in TOWERS else ANCHOR_Y - 10)
    dims = P().M(stops[0], yd).H(stops[-1]).M(CX, DECK + CHORD).V(WATER)
    heads = P()
    for a, b in pairwise(stops):
        heads.arrowhead((a, yd), 12, deg=180).arrowhead((b, yd), 12, deg=0)
    heads.arrowhead((CX, DECK + CHORD), 12, deg=-90).arrowhead((CX, WATER), 12, deg=90)

    s.stroke(fine, UI, 1.2)
    s.stroke(chords, UI_HI, 1.6)

    # piers, towers and anchorages, filled so they hide the deck behind them
    solid = P()
    for tx in TOWERS:
        pier_top = DECK + CHORD + 24
        solid.poly(
            [(tx - 46, WATER), (tx - 36, pier_top), (tx + 36, pier_top), (tx + 46, WATER)],
            closed=True,
        )
        steps = [(pier_top, 24), (470, 20), (350, 17), (TOP + 12, 15)]
        left = [(tx - w, y) for y, w in steps]
        right = [(tx + w, y) for y, w in reversed(steps)]
        cap = [(tx - 22, TOP + 12), (tx - 22, TOP - 2), (tx + 22, TOP - 2), (tx + 22, TOP + 12)]
        solid.poly(left + cap + right, closed=True)
        for y, w in steps[1:3]:
            solid.M(tx - w, y).H(tx + w)
    for ax in ANCHORS:
        sign = 1 if ax < CX else -1
        outer = ax - 105 * sign
        solid.poly(
            [(outer, 790), (outer, 580), (ax - 5 * sign, 580), (ax + 45 * sign, 790)],
            closed=True,
        )
    s.path(solid, fill=BG, stroke=UI_HI, stroke_width=1.6, stroke_linejoin="round")

    centres = P()
    for tx in TOWERS:
        centres.M(tx, TOP - 70).V(ground_y(tx) + 80)
    s.stroke(centres, UI, 1.2, dash=DASHDOT)
    s.stroke(dims, UI_ALT, 1.2)
    s.fill(heads, UI_ALT)

    # main cable, splaying to an anchor plate hidden inside each anchorage
    splay, plates = P(), P()
    for ax in ANCHORS:
        sign = 1 if ax < CX else -1
        entry, plate = Vec(ax, ANCHOR_Y), Vec(ax - 60 * sign, 740)
        splay.M(entry).L(plate)
        half = (plate - entry).unit().perp() * 14
        plates.M(plate + half).L(plate - half)
    s.stroke(splay, ACCENT_3, 1.6, dash=(8, 5))
    s.stroke(plates, ACCENT_3, 3)
    xs = sorted({*range(ANCHORS[0], ANCHORS[1], 4), *TOWERS, ANCHORS[1]})
    s.stroke(P().poly([(x, cable_y(x)) for x in xs]), ACCENT, 3, join="round", cap="round")
