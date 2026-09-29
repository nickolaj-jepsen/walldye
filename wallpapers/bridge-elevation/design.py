"""The Great Belt's East Bridge drawn to scale as an engineering elevation, its main cable picked out."""

from dataclasses import dataclass
from itertools import pairwise

from walldye import ACCENT, ACCENT_3, BG, BG_ALT, UI, UI_ALT, UI_HI, Canvas, P, Vec, design

# Geometry in meters: x along the bridge from mid-span (east positive), z above sea level.
MAIN, SIDE = 1624.0, 535.0
PYLON_X = MAIN / 2
BENT_X = PYLON_X + SIDE  # where each cable meets its anchor block
PYLON_TOP = 254.0
SAG = MAIN / 9  # cable sag to span, f/L = 1/9
CABLE_LOW = 72.0
SADDLE = CABLE_LOW + SAG
BENT_Z = 60.0
SIDE_SAG = SAG * (SIDE / MAIN) ** 2  # the same horizontal pull over the shorter span
ROAD_TOP, GRADE, GIRDER = 70.0, 0.02, 4.0
HANGER, HANGER_GAP = 24.0, 28.0  # 56 m between the hangers either side of a pylon
APPROACH, PIERS = 193.0, (7, 12)  # pier count west and east of the anchor blocks
BEARING = BENT_X + 20  # the approach girder's first bearing, on the anchor block
LEG_BASE, LEG_TOP = 18.0, 9.0
BEAMS = ((125.0, 137.0), (232.0, 244.0))  # the two cross beams between the legs
WEDGE = ((-16.0, 0.0), (-4.0, 63.0), (6.0, 63.0), (66.0, 0.0))  # anchor block, from the bent
DASHDOT = (22, 6, 3, 6)


def road(x: float) -> float:
    """Road level: a crest curve over the main span, then 2% grades down both approaches."""
    a = abs(x)
    if a <= PYLON_X:
        return ROAD_TOP - GRADE * a * a / (2 * PYLON_X)
    return ROAD_TOP - GRADE * PYLON_X / 2 - GRADE * (a - PYLON_X)


def cable(x: float) -> float:
    """Main cable: a parabola across the main span, sagging chords to the anchor blocks."""
    a = abs(x)
    if a <= PYLON_X:
        return CABLE_LOW + SAG * (a / PYLON_X) ** 2
    t = (a - PYLON_X) / SIDE
    return SADDLE + (BENT_Z - SADDLE) * t - 4 * SIDE_SAG * t * (1 - t)


def depth(x: float) -> float:
    """Sea bed below the waterline: shoals under the approaches, the channel between pylons."""
    u = min(1.0, abs(x - 160) / 1600)
    return 12 + 22 * (1 - u * u) ** 2


def leg(z: float) -> float:
    """Half the pylon leg's width at height z; the legs taper upward."""
    return (LEG_BASE + (LEG_TOP - LEG_BASE) * z / PYLON_TOP) / 2


def hangers_at() -> list[float]:
    """Hanger stations: every 24 m out from the 56 m gap at each pylon, to either anchor block."""
    main = [PYLON_X - HANGER_GAP - HANGER * n for n in range(33)]
    side = [PYLON_X + HANGER_GAP + HANGER * n for n in range(21)]
    half = main + side
    return [-x for x in half] + half


def piers() -> list[float]:
    """Every approach pier, west then east."""
    west = [-(BEARING + APPROACH * n) for n in range(1, PIERS[0] + 1)]
    east = [BEARING + APPROACH * n for n in range(1, PIERS[1] + 1)]
    return west + east


@dataclass(frozen=True)
class Sheet:
    """Meters to canvas units: `k` units per meter, mid-span at `cx`, the waterline at `wy`."""

    k: float
    cx: float
    wy: float

    def p(self, x: float, z: float) -> Vec:
        return Vec(self.cx + x * self.k, self.wy - z * self.k)

    def x(self, x: float) -> float:
        return self.cx + x * self.k

    def y(self, z: float) -> float:
        return self.wy - z * self.k


@design(aspects="any")
def draw(s: Canvas) -> None:
    if s.landscape:
        # the whole suspension bridge, cut mid-span on the approaches: wider screens show
        # more of them, stopping short of the west landfall
        spans = min(7.5, round((s.w / 1.06 - BEARING) / APPROACH - 0.5) + 0.5)
        k = s.w / (2 * (BEARING + APPROACH * max(1.5, spans)))
        sh = Sheet(k, s.w / 2, round(s.h * 0.7))
    else:
        # one pylon and its cable, the east one, with the main span to the left
        k = 0.64 * s.h / (PYLON_TOP + 30)
        sh = Sheet(k, s.w * 0.44 - PYLON_X * k, round(s.h * 0.84))
    big = k > 2
    x0, x1 = -sh.cx / k - 40, (s.w - sh.cx) / k + 40  # the visible stretch, in meters
    pylons = [x for x in (-PYLON_X, PYLON_X) if x0 - 60 < x < x1 + 60]
    anchors = [x for x in (-BENT_X, BENT_X) if x0 - 100 < x < x1 + 100]
    stations = [x for x in piers() if x0 - 20 < x < x1 + 20]

    # water: waterline plus the drafting convention of staggered dashes, sparser with depth
    fine = P().M(0, sh.wy).H(s.w)
    dash = 22
    rows = [(66, 12), (132, 24), (264, 36)] if big else [(66, 6)]
    for row, (period, below) in enumerate(rows):
        y = sh.wy + below
        for i in range(-2, s.w // period + 3):
            x = i * period + (period / 2 if row % 2 == 0 else 0)
            m, m1 = (x - sh.cx) / k, (x + dash - sh.cx) / k
            clear = all(abs(m - px) * k > 50 for px in pylons + stations)
            deep = min(depth(m), depth(m1)) * k > below + 6
            if clear and deep and all(abs(m - ax) * k > 90 for ax in anchors):
                fine.M(x, y).H(x + dash)
    s.stroke(fine, UI, 1.2)

    # sea bed with earth hatching under it
    def bed_y(px: float) -> float:
        return sh.y(-depth((px - sh.cx) / k))

    bed = P().poly([(px, bed_y(px)) for px in range(0, s.w + 9, 8)])
    earth = P()
    for px in range(4, s.w, 14):
        earth.M(px, bed_y(px) + 4).L(px - 8, bed_y(px) + 12)
    s.stroke(earth, BG_ALT, 1.2)
    s.stroke(bed, UI_ALT, 1.4)

    # foundations let into the bed, dashed as hidden lines
    hidden = P()
    caisson_top = {px: -depth(px) + 14 for px in pylons}
    for px in pylons:
        z0, z1 = caisson_top[px] - 20, caisson_top[px]
        box = [(-17.5, z0), (17.5, z0), (17.5, z1), (-17.5, z1)]
        hidden.poly([sh.p(px + u, z) for u, z in box], closed=True)
    for ax in anchors:
        sign = 1 if ax > 0 else -1
        z0 = -depth(ax) - 4
        box = [(-24, 0), (-24, z0), (86, z0), (86, 0)]
        hidden.poly([sh.p(ax + u * sign, z) for u, z in box])
    for px in stations:
        z0 = -depth(px) - 3
        box = [(-14, 0), (-14, z0), (14, z0), (14, 0)]
        hidden.poly([sh.p(px + u, z) for u, z in box])
    s.stroke(hidden, UI_ALT, 1.2, dash=(8, 6))

    # hangers every 24 m, 56 m apart across each pylon
    hangers = P()
    for x in hangers_at():
        top, foot = sh.y(cable(x)) + 1.5, sh.y(road(x))
        if foot - top > 3 and x0 < x < x1:
            hangers.M(sh.x(x), top).V(foot)
    s.stroke(hangers, UI_ALT, 1.4 if big else 1)

    # deck: road and girder soffit, one line when the scale is too small to part them
    xs = [x0 + i * (x1 - x0) / 400 for i in range(401)]
    deck = P().poly([sh.p(x, road(x)) for x in xs])
    if big:
        deck.poly([sh.p(x, road(x) - GIRDER) for x in xs])
    s.stroke(deck, UI_HI, 1.6 if big else 2)

    # main cable, its ends closed over by the saddle housings and anchor blocks
    lo, hi = max(x0, -BENT_X), min(x1, BENT_X)
    cxs = sorted({*[lo + i * (hi - lo) / 600 for i in range(601)], *pylons})
    path = P().poly([sh.p(x, cable(x)) for x in cxs if lo <= x <= hi])
    s.stroke(path, ACCENT, 4 if big else 2.6, join="round", cap="round")

    # piers, anchor blocks and pylons, filled so they hide what passes behind them
    solid = P()
    for px in stations:
        top = road(px) - GIRDER
        shaft = [(-7, 0), (-4.5, top), (4.5, top), (7, 0)]
        solid.poly([sh.p(px + u, z) for u, z in shaft], closed=True)
    for ax in anchors:
        sign = 1 if ax > 0 else -1
        solid.poly([sh.p(ax + u * sign, z) for u, z in WEDGE], closed=True)
    for px in pylons:
        foot, shoulder = caisson_top[px], PYLON_TOP - 8
        cap = LEG_TOP / 2 + 1.5
        pts = [(-leg(foot), foot), (-leg(shoulder), shoulder), (-cap, shoulder), (-cap, PYLON_TOP)]
        pts += [(-u, z) for u, z in reversed(pts)]
        solid.poly([sh.p(px + u, z) for u, z in pts], closed=True)
    s.path(solid, fill=BG, stroke=UI_HI, stroke_width=1.6, stroke_linejoin="round")

    if big:
        # cross beams between the legs, behind the near one
        beams = P()
        for px in pylons:
            for z0, z1 in BEAMS:
                w = leg(z1) - 2
                box = [(-w, z0), (w, z0), (w, z1), (-w, z1)]
                beams.poly([sh.p(px + u, z) for u, z in box], closed=True)
        s.stroke(beams, UI_ALT, 1.2, dash=(8, 6))

    centers = P()
    for px in pylons:
        centers.M(sh.p(px, PYLON_TOP + 30)).L(sh.p(px, caisson_top[px] - 28))
    s.stroke(centers, UI, 1.2, dash=DASHDOT)

    # dimensions
    dims, heads, ext = P(), P(), P()
    head = 12 if big else 9
    if s.landscape:
        # span chain from bent to pylon to pylon to bent, and the sag at mid-span
        yd = sh.y(PYLON_TOP + 70)
        stops = [-BENT_X, -PYLON_X, PYLON_X, BENT_X]
        dims.M(sh.x(stops[0]), yd).H(sh.x(stops[-1]))
        for x in stops:
            reach = PYLON_TOP + 14 if abs(x) == PYLON_X else 74
            ext.M(sh.x(x), yd - 12).V(sh.y(reach))
        for a, b in pairwise(stops):
            heads.arrowhead((sh.x(a), yd), head, deg=180).arrowhead((sh.x(b), yd), head, deg=0)
        # the sag below the chord between saddles, and the shipping clearance under the deck
        chord = sh.y(SADDLE)
        ext.M(sh.x(-PYLON_X) + 24, chord).H(sh.x(PYLON_X) - 24)
        for top, foot in ((chord, sh.y(CABLE_LOW)), (sh.y(ROAD_TOP - GIRDER), sh.wy)):
            dims.M(sh.x(0), top).V(foot)
            heads.arrowhead((sh.x(0), top), head, deg=-90)
            heads.arrowhead((sh.x(0), foot), head, deg=90)
    else:
        # pylon height beside the pylon, and the hanger gap across it
        px = PYLON_X
        xd = sh.x(px + 72)
        ext.M(sh.x(px + LEG_TOP / 2 + 6), sh.y(PYLON_TOP)).H(xd + 14)
        dims.M(xd, sh.y(PYLON_TOP)).V(sh.wy)
        heads.arrowhead((xd, sh.y(PYLON_TOP)), head, deg=-90).arrowhead((xd, sh.wy), head, deg=90)
        yd = sh.y(road(px) + 12)
        a, b = sh.x(px - HANGER_GAP), sh.x(px + HANGER_GAP)
        dims.M(a, yd).H(b)
        heads.arrowhead((a, yd), head, deg=180).arrowhead((b, yd), head, deg=0)
    s.stroke(ext, UI, 1.2)
    s.stroke(dims, UI_ALT, 1.2)
    s.fill(heads, UI_ALT)

    # the cable splaying down inside each anchor block to its anchor plate
    splay, plates = P(), P()
    for ax in anchors:
        sign = 1 if ax > 0 else -1
        entry, plate = sh.p(ax, BENT_Z), sh.p(ax + 44 * sign, 10)
        splay.M(entry).L(plate)
        half = (plate - entry).unit().perp() * max(4.0, 8 * k)
        plates.M(plate + half).L(plate - half)
    s.stroke(splay, ACCENT_3, 1.6, dash=(8, 5))
    s.stroke(plates, ACCENT_3, 3)
