"""Edwards Island at night from the water, traced in outline from the in-game map, beside a ghosting triangular rift dithered over the sea."""

from collections.abc import Sequence
from itertools import pairwise

import numpy as np
import shapely
from shapely.geometry import Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_4,
    ACCENT_6,
    ACCENT_7,
    BG,
    BG_ALT,
    BG_DEEP,
    BLACK,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Style,
    Vec,
    design,
    ladder,
    mix,
)
from walldye.field import cells, gauss, noise_grid
from walldye.geom import Affine
from walldye.pixel import dither, grid_runs

type MapPoint = tuple[float, float]

CELL = 4
HORIZON = 690
# Island coordinates are in the in-game Edwards Island map's pixels (1500x842, waterline y=705).
K, OX, WATERLINE = 0.95, 640, 705
RX, RW, RH = 400, 230, 390  # rift base centre, width, height
RB = HORIZON - 4
TRI = [(RX, RB - RH), (RX + RW / 2, RB), (RX - RW / 2, RB)]
# Streaks bleeding out through both sides: (row y, half-gap from the axis, length, shift in cells).
STREAKS = [
    (420, 30, 150, 6),
    (436, 40, 110, 4),
    (468, 56, 170, 8),
    (492, 62, 90, 3),
    (540, 80, 120, 5),
]

EDGE = UI_HI
FAINT = UI_ALT
LAND_BACK = mix(BLACK, BG_DEEP, 0.5)  # the far tier, a half step up from the near one
LAND_FRONT = BLACK
LINE: Style = {"stroke": EDGE, "stroke_width": 1}
RIDGE: Style = {**LINE, "stroke_linejoin": "round"}  # land outlines, spiky with pines
# Dither palette: 1 glints on the sea, 2-4 the rift's halo up the accent ladder, 5-6 its reflection.
HALO = ladder((BG, ACCENT_4, ACCENT), 4)
PALETTE = (None, BG_ALT, HALO[1], HALO[2], HALO[3], ACCENT_7, ACCENT_6)

# Camp Grounds shelf, Edwards Woods up to Relay Point, the Harden Tower saddle, Fort Milner's cliff.
BACK = [
    (300, 520),
    (305, 470),
    (298, 420),
    (292, 380),
    (287, 350),
    (300, 336),
    (330, 332),
    (352, 318),
    (366, 290),
    (378, 262),
    (392, 256),
    (408, 262),
    (420, 276),
    (440, 262),
    (462, 252),
    (482, 240),
    (500, 222),
    (512, 198),
    (530, 196),
    (548, 188),
    (560, 172),
    (590, 172),
    (604, 168),
    (642, 172),
    (668, 182),
    (700, 196),
    (716, 208),
    (722, 226),
    (726, 262),
    (748, 300),
    (775, 340),
    (792, 372),
    (852, 378),
    (862, 360),
    (875, 325),
    (905, 300),
    (948, 283),
    (1285, 272),
    (1283, 300),
    (1272, 340),
    (1258, 375),
    (1240, 410),
    (1180, 450),
    (1040, 470),
    (840, 440),
    (620, 470),
    (430, 500),
]
# Fort Milner skyline blocks (x0, x1, top), left to right.
FORT = [
    (948, 972, 190),
    (972, 1000, 184),
    (1006, 1053, 130),
    (1060, 1115, 162),
    (1125, 1192, 212),
    (1208, 1278, 202),
]
# Faint cliff-face strokes on the back tier: Camp Grounds, Fort Milner, the Harden saddle.
CRACKS_BACK = [
    [(302, 390), (318, 430), (330, 470)],
    [(360, 362), (380, 420), (372, 480)],
    [(1000, 300), (1050, 350), (1090, 420)],
    [(1140, 300), (1170, 350), (1180, 410)],
    [(1235, 290), (1245, 345)],
    [(760, 290), (800, 330)],
]
# And on the Discovery Cliffs below.
CRACKS_FRONT = [
    [(560, 560), (600, 620), (592, 690)],
    [(650, 556), (690, 640), (700, 690)],
]
# Conifer spikes (x, top, half-width) along the woods, fort and Epiphany Field.
PINES = [
    (340, 312, 7),
    (356, 300, 8),
    (372, 250, 9),
    (396, 244, 8),
    (416, 262, 7),
    (432, 248, 9),
    (452, 236, 9),
    (470, 226, 9),
    (492, 212, 8),
    (512, 180, 10),
    (538, 180, 8),
    (554, 158, 9),
    (575, 140, 10),
    (596, 156, 9),
    (620, 146, 10),
    (646, 160, 9),
    (672, 170, 8),
    (694, 182, 8),
    (1003, 162, 7),
    (1157, 160, 8),
    (858, 440, 8),
    (878, 412, 9),
    (900, 400, 9),
    (922, 396, 10),
    (944, 392, 9),
    (966, 388, 10),
    (988, 400, 9),
    (1010, 422, 8),
]
# Main Street's upper row of gabled houses (x0, x1, eave, ridge) and the Epiphany Field farmhouse.
HOUSES = [
    (300, 326, 516, 503),
    (328, 352, 516, 505),
    (354, 382, 512, 498),
    (386, 410, 516, 505),
    (414, 440, 520, 509),
    (590, 630, 506, 492),
]
# Main Street's lower town stepping down to the dock (x, eave, width).
TOWN = [
    (262, 680, 22),
    (290, 672, 24),
    (318, 678, 20),
    (345, 666, 26),
    (378, 676, 22),
    (404, 682, 22),
    (280, 628, 22),
    (322, 624, 44),
    (296, 590, 20),
    (372, 640, 20),
]
# Lower tier: Main Street mound, Discovery Cliffs, Epiphany Field under the boardwalk.
FRONT = [
    (250, 705),
    (256, 690),
    (262, 660),
    (270, 628),
    (278, 598),
    (286, 562),
    (292, 527),
    (452, 526),
    (500, 524),
    (640, 520),
    (655, 522),
    (700, 536),
    (1000, 536),
    (1030, 540),
    (1010, 552),
    (960, 562),
    (880, 576),
    (800, 586),
    (736, 590),
    (722, 622),
    (726, 670),
    (740, 705),
]
BEACON = [
    (736, 705),
    (760, 680),
    (790, 652),
    (830, 626),
    (860, 611),
    (879, 606),
    (902, 616),
    (926, 640),
    (946, 672),
    (956, 705),
]
ADLER = [(880, 606), (1060, 600), (1076, 614), (1080, 634), (1066, 648), (990, 652), (900, 648)]
# Epiphany Field's wooded knoll behind the boardwalk.
KNOLL = [
    (842, 540),
    (848, 470),
    (866, 440),
    (900, 420),
    (1000, 420),
    (1020, 450),
    (1033, 490),
    (1030, 540),
]
# Plank boardwalk along Epiphany Field: down from the cliff, flat, then over the trestle bridge.
BOARDWALK = [
    (640, 520),
    (700, 537),
    (790, 537),
    (800, 518),
    (842, 518),
    (848, 534),
    (982, 534),
    (996, 546),
]
# Scalloped cloud banks from the map (x0, x1, base, puff radius); the last one sits in front.
CLOUDS = [
    (1030, 1300, 470, 26),
    (140, 300, 500, 16),
    (430, 640, 505, 20),
    (740, 860, 470, 18),
]
CLOUD_FRONT = (960, 1110, 690, 22)


def m(x: float, y: float) -> Vec:
    """Map pixel to canvas: scaled by K with the map's waterline on the horizon."""
    return Vec(OX + x * K, HORIZON - (WATERLINE - y) * K)


def mp(points: Sequence[MapPoint]) -> Polygon:
    """The polygon through map-pixel points."""
    return Polygon([m(x, y) for x, y in points])


def arch(x0: float, top: float, x1: float, bottom: float) -> BaseGeometry:
    """A round-headed opening between map-pixel columns x0 and x1, from its crown down."""
    (a, b), (c, d) = m(x0, top), m(x1, bottom)
    r = (c - a) / 2
    return Point(a + r, b + r).buffer(r, quad_segs=16).union(box(a, b + r, c, d))


def pine(x: float, top: float, hw: float, base: float) -> Polygon:
    """Three-tier conifer silhouette in map pixels."""
    h = base - top
    left = [
        (x - hw, base),
        (x - hw * 0.35, top + h * 0.66),
        (x - hw * 0.75, top + h * 0.66),
        (x - hw * 0.25, top + h * 0.33),
        (x - hw * 0.5, top + h * 0.33),
    ]
    right = [(2 * x - a, b) for a, b in reversed(left)]
    return mp([*left, (x, top), *right])


def cloud(x0: float, x1: float, base: float, r: float) -> BaseGeometry:
    """Scalloped cumulus: a row of puffs over a flat base, taller in the middle."""
    n = max(3, round((x1 - x0) / (r * 1.3)))
    puffs = []
    for i in range(n):
        t = (i + 0.5) / n
        rr = r * (0.75 + 0.5 * np.sin(np.pi * t))
        puffs.append(Point(m(x0 + (x1 - x0) * t, base - rr * 0.5)).buffer(rr * K, quad_segs=12))
    bx0, by = m(x0, base)
    return unary_union(puffs).intersection(box(bx0 - 40, 0, m(x1, 0).x + 40, by))


def harden(s: Canvas, foot: Vec) -> None:
    """Harden Tower: flared four-leg lattice, banded central shaft, railed cabin, dish and beacon."""
    bx, by = round(foot.x), round(foot.y)
    h = 70
    top = by - h
    lattice = P()
    for sx in (-1, 1):
        lattice.M(bx + sx * 23, by).L(bx + sx * 8, top)
    rings = [0, 0.28, 0.54, 0.78, 1]
    for f in rings[1:-1]:
        w = 23 - 15 * f
        lattice.M(bx - w, by - h * f).H(bx + w)
    for f0, f1 in pairwise(rings):
        w0, w1 = 23 - 15 * f0, 23 - 15 * f1
        lattice.M(bx - w0, by - h * f0).L(bx + w1, by - h * f1)
        lattice.M(bx + w0, by - h * f0).L(bx - w1, by - h * f1)
    s.stroke(lattice, EDGE, 1)
    # Banded shaft: alternating dark and light rings, as painted on the tower.
    with s.buckets((BG_DEEP, UI_HI), "fill") as bands:
        for i, yy in enumerate(range(by, top, -8)):
            bands[i % 2].rect(bx - 5, max(top, yy - 8), 10, min(8, yy - top))
    s.stroke(P().rect(bx - 5, top, 10, h), EDGE, 1)
    # Gallery deck with railing, cabin, roof cap, then the dish and antenna ball.
    s.path(P().rect(bx - 13, top - 2, 26, 2), fill=BG_DEEP, **LINE)
    rail = P().M(bx - 13, top - 7).H(bx + 13)
    for xx in range(-13, 14, 6):
        rail.M(bx + xx, top - 2).V(top - 7)
    s.stroke(rail, EDGE, 1)
    s.path(P().rect(bx - 7, top - 16, 14, 14), fill=BG_DEEP, **LINE)
    s.fill(P().rect(bx - 5, top - 13, 10, 4), UI_ALT)
    s.path(P().rect(bx - 9, top - 19, 18, 3), fill=BG_DEEP, **LINE)
    s.stroke(P().M(bx - 5, top - 19).V(top - 27).M(bx + 3, top - 19).L(bx + 6, top - 25), EDGE, 1)
    s.path(P().circle((bx + 8, top - 28), 5), fill=BG_DEEP, **LINE)
    s.stroke(P().M(bx + 5, top - 31).L(bx + 11, top - 25), EDGE, 1)
    s.fill(P().rect(bx - 6.5, top - 30.5, 3, 3), ACCENT)


def lighthouse(s: Canvas, foot: Vec) -> None:
    """Epiphany Field light: tapered tower, dark top band, lit lamp room under a dome; the
    flat-roofed keeper's house beside it."""
    bx, by = round(foot.x), round(foot.y)
    g = by - 38
    tower = P().poly([(bx - 8, by), (bx - 6, g), (bx + 6, g), (bx + 8, by)], closed=True)
    s.path(tower, fill=UI, **LINE)
    s.path(P().rect(bx - 6, g - 3, 12, 3), fill=BG_DEEP, **LINE)
    s.path(P().rect(bx - 4, g - 9, 8, 6), fill=ACCENT_6, **LINE)
    s.path(P().M(bx - 5, g - 9).A(5, 4, 0, 0, 1, bx + 5, g - 9).Z(), fill=BG_DEEP, **LINE)
    # Keeper's house: box with an overhanging flat roof, window strip, door, round window.
    hx = bx + 18
    s.path(P().rect(hx - 8, by - 26, 38, 26), fill=BG_DEEP, **LINE)
    s.path(P().rect(hx - 10, by - 29, 42, 3), fill=BG_DEEP, **LINE)
    openings = P().rect(hx - 3, by - 16, 14, 4).rect(hx + 16, by - 12, 6, 12)
    s.fill(openings.circle((hx + 21, by - 20), 2.5), UI_ALT)


def boardwalk(s: Canvas) -> None:
    """The boardwalk as a thick rail with posts under it, and the trestle bridge's rails."""
    pts = [m(x, y) for x, y in BOARDWALK]
    s.stroke(P().poly(pts), EDGE, 2.5, join="round")
    posts = P()
    for (x0, y0), (x1, y1) in pairwise(pts):
        n = int(abs(x1 - x0) // 9)
        for i in range(1, n + 1):
            t = i / (n + 1)
            px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            posts.M(round(px), py + 1).V(py + 7)
    (bx0, by0), (bx1, _) = m(800, 518), m(842, 518)
    posts.M(bx0, by0 - 8).H(bx1)
    for xx in np.linspace(bx0, bx1, 5):
        posts.M(xx, by0).V(by0 - 8)
    s.stroke(posts, FAINT, 1)


def rift_field(s: Canvas) -> None:
    """The dithered layer: the rift's halo and streaks in the sky, glints and a broken
    reflection on the sea."""
    xs, ys = cells(s.inset(0), CELL)
    rows, cols = xs.shape
    sky = ys < HORIZON
    rift = Polygon(TRI)

    td = shapely.distance(rift, shapely.points(xs, ys))
    # Inside: a faint fill with a brighter vertical slit, as in the key art.
    slit = (
        gauss(xs - RX, 12)
        * np.clip((ys - (RB - RH * 0.78)) / (RH * 0.4), 0, 1)
        * np.clip((RB - 24 - ys) / 70, 0, 1)
    )
    halo = np.where(td > 0, 0.18 * np.exp(-((td / 40) ** 1.5)), 0.08 + 0.45 * slit)
    halo = np.where(sky, halo, 0)

    # Time-loop streaks: short runs slide outward on both sides, leaving a faint ghost.
    for sy, gap, length, k in STREAKS:
        j = sy // CELL
        for side in (-1, 1):
            a0 = RX + side * gap
            i0, i1 = sorted((int(a0 // CELL), int((a0 + side * length) // CELL)))
            row = halo[j, i0:i1].copy()
            fall = np.linspace(0.32, 0.06, i1 - i0)
            halo[j, i0:i1] = np.maximum.reduce(
                [np.roll(row, side * k), 0.5 * row, fall if side > 0 else fall[::-1]]
            )

    # Glints on the swell: noise stretched four to one, whose crests near the rift and the
    # horizon just cross the line screen's first threshold (1/6) as short single-row dashes.
    rip = noise_grid(cols, rows * 4, 36, s.np_rng(7), octaves=3)[::4]
    depth = np.clip((ys - HORIZON) / 220, 0, 1)
    sea = 1.8 * np.clip(rip - 0.05, 0, 1) * gauss(xs - RX, 300) * (1 - depth)

    # Reflection: the triangle mirrored and broken into rows, fading fast.
    rng = s.np_rng(11)
    off = np.clip(rng.normal(0, 8, rows), -18, 18)
    gap = rng.random(rows) < 0.4
    mirror = shapely.distance(rift, shapely.points(xs - off[:, None], 2 * RB - ys))
    fade = np.clip(1 - (ys - HORIZON) / 170, 0, 1) ** 1.5
    refl = np.where(~sky & ~gap[:, None], 0.55 * gauss(mirror, 18) * fade, 0)

    g_sea = dither(sea, 2, method="lines", matrix=3)
    g_halo = dither(halo, 4, method="atkinson")
    g_refl = dither(refl, 3, method="bayer", matrix=4)
    sky_idx = np.where(g_halo > 0, 1 + g_halo, 0)
    sea_idx = np.where(g_refl > 0, 4 + g_refl, g_sea)
    grid_runs(s, np.where(sky, sky_idx, sea_idx), PALETTE, CELL)


def rift_lines(s: Canvas) -> None:
    """The rift itself: a ghosted triple outline, hollow inverted vertex markers and dashed
    streaks running out through both sides."""
    centre = (RX, RB - RH / 3)
    for sc, dx, dy, c in ((1.04, -7, 5, ACCENT_4), (1.02, 6, -3, ACCENT_2), (1, 0, 0, ACCENT)):
        ghost = (Affine.translate(dx, dy) @ Affine.scale(sc, about=centre)).apply(TRI)
        s.stroke(P().poly(ghost, closed=True), c, 1.5)
    marks = P()
    for vx, vy in TRI:
        apex = vy < RB
        cx = vx if apex else vx + (8 if vx > RX else -8)
        cy = vy - 11 if apex else vy + 9
        marks.poly([(cx - 7, cy - 5), (cx + 7, cy - 5), (cx, cy + 6)], closed=True)
    s.stroke(marks, ACCENT, 1)
    dashes = P()
    for sy, gap, length, _ in STREAKS:
        for side in (-1, 1):
            a0 = RX + side * (gap + 14)
            dashes.M(a0, sy + 1.5).H(a0 + side * length * 0.8)
    s.stroke(dashes, ACCENT_6, 1, dash=(18, 6, 40, 10))


@design()
def draw(s: Canvas) -> None:
    rift_field(s)

    # Sparse stars, kept away from the rift.
    r = s.np_rng(5)
    stars = P()
    for _ in range(90):
        sx, sy = r.uniform(0, s.w), r.uniform(0, 520)
        if abs(sx - RX) < 200 and sy > RB - RH - 60:
            continue
        stars.M(round(sx), round(sy)).H(round(sx) + 2)
    s.stroke(stars, UI, 2)

    # Rope bridge off Relay Point, then Fort Milner's viaduct: deck, piers, round-headed arches.
    s.stroke(P().M(m(716, 212)).Q(m(770, 232), m(822, 216)), EDGE, 1)
    arches = unary_union([arch(ax, 230, ax + 13, 290) for ax in range(832, 940, 21)])
    via = box(*m(822, 206), *m(948, 282)).difference(arches)
    s.path(P().shape(via), fill=LAND_BACK, **LINE)
    s.stroke(P().M(m(822, 212)).H(m(948, 0).x), FAINT, 1)

    # The back tier: woods, the saddle and Fort Milner's blocks, the Relay Point cabin and the
    # fort's domed hall, with pines standing proud of the ridge.
    back = [mp(BACK)]
    back += [mp([(x0, 285), (x0, top), (x1, top), (x1, 285)]) for x0, x1, top in FORT]
    back.append(mp([(590, 190), (590, 170), (624, 170), (624, 190)]))
    x0, x1, eave = m(1125, 0).x, m(1192, 0).x, m(0, 212).y
    t = np.linspace(0, np.pi, 15)
    dome = np.column_stack([x0 + (x1 - x0) * (0.5 - 0.5 * np.cos(t)), eave - 14 * np.sin(t)])
    back.append(Polygon(dome))
    back += [pine(px, top, hw * 1.4, top + 50) for px, top, hw in PINES if px < 1020 and top < 300]
    s.path(P().shape(unary_union(back)), fill=LAND_BACK, **RIDGE)
    win = P()
    for fx0, fx1, top in FORT:
        for wy in range(top + 10, 270, 13):
            for wx in range(fx0 + 6, fx1 - 8, 11):
                wx0, wy0 = m(wx, wy)
                win.rect(round(wx0), round(wy0), 4, 3)
    s.fill(win, UI_ALT)
    # The Camp Grounds shelf edge and the cliff faces.
    cracks = P().poly([m(287, 350), m(330, 358), m(420, 354), m(470, 352)])
    for c in CRACKS_BACK:
        cracks.poly([m(x, y) for x, y in c])
    s.stroke(cracks, FAINT, 1)
    harden(s, m(818, 376))

    clouds = P()
    for c in CLOUDS:
        clouds.shape(cloud(*c))
    s.path(clouds, fill=BG_ALT, stroke=UI_ALT, stroke_width=1)

    knoll = [mp(KNOLL)]
    knoll += [pine(px, top, hw * 1.4, top + 46) for px, top, hw in PINES if px > 850 and top > 300]
    s.path(P().shape(unary_union(knoll)), fill=LAND_BACK, **RIDGE)
    # Lower tier with the Discovery Cliffs arch cut through, plus Main Street's gables.
    front = [mp(FRONT)]
    front += [
        mp([(a, e + 6), (a, e), ((a + b) / 2, rr), (b, e), (b, e + 6)]) for a, b, e, rr in HOUSES
    ]
    lower = unary_union(front).difference(arch(450, 656, 500, 706))
    s.path(P().shape(lower), fill=LAND_FRONT, **RIDGE)
    # The path up to the upper row, the lower town, and the Discovery Cliffs faces.
    s.stroke(P().poly([m(440, 700), m(470, 640), m(500, 590), m(520, 548), m(540, 530)]), FAINT, 1)
    town = P()
    lit = P()
    for hx, hy, w in TOWN:
        (tx, ty), tw = m(hx, hy), w * K
        town.poly(
            [(tx, ty + 18), (tx, ty), (tx + tw / 2, ty - 9), (tx + tw, ty), (tx + tw, ty + 18)],
            closed=True,
        )
        lit.rect(round(tx + tw / 2 - 2), round(ty + 4), 4, 4)
    cracks = P()
    for c in CRACKS_FRONT:
        cracks.poly([m(x, y) for x, y in c])
    s.stroke(cracks, FAINT, 1)
    s.path(town, fill=BG_DEEP, stroke=FAINT, stroke_width=1)
    s.fill(lit, UI_ALT)
    boardwalk(s)
    lighthouse(s, m(688, 525))

    # The house on the eastern shelf, with a cloud bank drifting in front of it.
    s.path(P().shape(mp(ADLER)), fill=LAND_BACK, **LINE)
    hx, hy = m(995, 606)
    house = P().poly([(hx, hy), (hx, hy - 48), (hx + 58, hy - 32), (hx + 58, hy)], closed=True)
    s.path(house, fill=BG_DEEP, **LINE)
    s.fill(P().rect(hx + 8, hy - 26, 38, 6), UI_ALT)
    trim = P().M(hx - 8, hy - 16).H(hx + 58).M(hx + 44, hy - 36).V(hy - 48).H(hx + 49).V(hy - 34)
    s.stroke(trim, EDGE, 1)
    s.path(P().shape(cloud(*CLOUD_FRONT)), fill=BG_ALT, stroke=UI_ALT, stroke_width=1)

    # The eastern headland with its sea cave, and the steps cut up its face.
    s.path(P().shape(mp(BEACON).difference(arch(800, 663, 860, 706))), fill=LAND_FRONT, **LINE)
    steps = P()
    for i in range(9):
        sx, sy = m(752 + i * 12, 684 - i * 8.6)
        steps.M(sx, sy).H(sx + 8).V(sy - 8)
    s.stroke(steps, FAINT, 1)

    # Ferry at the Main Street dock, then the waterline.
    s.stroke(P().poly([m(180, 702), m(250, 702)]), EDGE, 2)
    hull = P().poly([m(156, 688), m(224, 688), m(216, 708), m(162, 708)], closed=True)
    s.path(hull, fill=BG_DEEP, **LINE)
    s.path(P().rect(*m(164, 668), 36 * K, 20 * K), fill=BG_DEEP, **LINE)
    s.fill(P().rect(*m(168, 673), 26 * K, 6 * K), UI_ALT)
    s.stroke(P().poly([m(182, 668), m(182, 655)]), EDGE, 1)
    s.stroke(P().M(m(150, 0).x, HORIZON + 0.5).H(m(1090, 0).x), UI_ALT, 1)

    rift_lines(s)
