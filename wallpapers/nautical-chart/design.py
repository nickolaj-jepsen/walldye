"""A corner of a sea chart: a noise-field coast with isobaths traced from its distance field, soundings, the marks and lights of one way in, and a compass rose."""

import math
from collections.abc import Callable
from itertools import pairwise
from typing import Literal

import numpy as np
import shapely
from numpy.typing import NDArray
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Params,
    Path,
    Rect,
    Vec,
    design,
    knob,
    mix,
    polar,
    smoothstep,
)
from walldye.field import gauss, iso_lines, noise_grid
from walldye.geom import Affine, Polyline, poisson_disk, spline_points

type Field = NDArray[np.float64]
type Mask = NDArray[np.bool_]


class Chart(Params):
    coast: Literal["headland", "estuary", "harbor", "skerries"] = knob(
        default="headland", doc="the coast charted, which sets the marks that lead in"
    )


VARIANTS = {
    "estuary": Chart(coast="estuary"),
    "harbor": Chart(coast="harbor"),
    "skerries": Chart(coast="skerries"),
}

CELL = 4
CHART = (1920 // CELL + 1, 1080 // CELL + 1)  # the 16:9 chart the coast was tuned on, in cells
ISLETS = ((640, 580, 24, 0.5), (694, 546, 12, 0.5), (606, 610, 8, 0.4))  # x, y, radius, height
LIGHT, HARBOR = Vec(960, 150), Vec(786, 250)  # chart positions
LIGHT_R, SPREAD = 260, 40  # the light's sector: arc radius, width in degrees
ROSE_R = 150
FADE = 480  # units over which the westward coast takes over from the 16:9 chart's noise
PAD = 5  # cells a region's field is held past the frame, so its outline closes off-screen
# depth in chart units, dash pattern: finer dashes inshore, as charts mark their isobaths
DEPTHS = ((28, (1.5, 5)), (80, (10, 6)), (170, (14, 5, 2, 5)), (320, (22, 6, 2, 6, 2, 6)))

# The other coasts are drawn in chart units on a 16:9 sheet, turned a quarter on portrait.
MARGIN = 48  # cells their fields reach past the canvas, so land off-screen still shapes depths
DRYING = mix(BG, BG_ALT, 0.6)  # banks and ledges that dry at low water
# the estuary's channel, from far up the river out to sea
CHANNEL = (
    (-1900, 470),
    (-1350, 630),
    (-800, 470),
    (-300, 610),
    (100, 530),
    (330, 550),
    (560, 625),
    (800, 640),
    (990, 555),
    (1140, 450),
    (1340, 425),
    (1560, 495),
    (1820, 560),
    (2200, 600),
)
BUOYED = (330, 1450)  # the channel's buoyed reach, as chart x
GATE, BEAM = 190, 56  # buoy pairs: spacing along the channel, offset either side of it
# the harbor: breakwaters from their roots ashore to their heads, the basin, the transit
MOLES = (((1560, 316), (1390, 395), (1318, 515)), ((1560, 810), (1430, 725), (1384, 652)))
BASIN = ((1400, 470), (1600, 470), (1600, 660), (1400, 660))
TRANSIT = 70  # the leading line's bearing on the 16:9 sheet
# the skerries: the track through the islets, in from the open sea
PASSAGE = ((560, 140), (905, 520), (1010, 700), (1400, 770))
DANGER = Vec(1010, 612)  # a rock in the narrows, marked by a lit beacon


def layer(
    s: Canvas[Chart],
    key: int,
    scale: int,
    octaves: int,
    gain: float,
    west: int,
    cols: int,
    rows: int,
) -> Field:
    """Noise layer `key` over `rows` by `cols` chart cells, the first `west` of them west of the
    16:9 chart.

    The 16:9 tile is drawn first, on a lattice rounded up to whole `scale` cells as the coast was
    tuned on, and mirrored past its edges; a second tile from the same stream carries on
    westward, faded in over FADE units so the seam never shows.
    """
    rng = s.np_rng(key)
    size = [math.ceil(n / scale) * scale for n in CHART]
    east = noise_grid(size[0], size[1], scale, rng, octaves=octaves, gain=gain)
    east = east[: CHART[1], : CHART[0]]
    near = mirror(east, west, cols - west - CHART[0], rows)
    if west == 0:
        return near
    far = noise_grid(size[0], size[1], scale, rng, octaves=octaves, gain=gain)
    far = mirror(far[: CHART[1], : CHART[0]], 0, cols - CHART[0], rows)[:, ::-1]
    w = smoothstep(-FADE, 0, (np.arange(cols) - west) * CELL)
    return w * near + (1 - w) * far


def mirror(a: Field, left: int, right: int, rows: int) -> Field:
    """`a` mirrored `left` columns out to the west, `right` to the east and down to `rows`."""
    pad = ((0, max(0, rows - a.shape[0])), (left, max(0, right)))
    return np.pad(a, pad, mode="reflect")[:rows, : left + a.shape[1] + right]


def rings(a: Field) -> list[Field]:
    """Closed outlines of `a > 0` on the canvas that `a` covers, densified off the frame."""
    rows, cols = a.shape
    frame = Rect(0, 0, (cols - 1) * CELL, (rows - 1) * CELL)
    padded = np.pad(np.pad(a, PAD, mode="edge"), 1, constant_values=-1)
    origin = (-(PAD + 1) * CELL, -(PAD + 1) * CELL)
    out: list[Field] = []
    for line in iso_lines(padded, 0, cell=CELL, origin=origin, simplify=0.5):
        if long(line, 30):
            out.append(densify_off_frame(line[:-1], frame))
    return out


def long(line: Field, least: float) -> bool:
    """Whether `line` runs further than `least`; a speck that simplifies to one point does not."""
    return bool(np.ptp(line, axis=0).max() > 0) and Polyline(line).length > least


def region(a: Field) -> Path:
    """Closed outlines of `a > 0` on the canvas that `a` covers."""
    d = P()
    for ring in rings(a):
        d.spline(ring, closed=True)
    return d


def densify_off_frame(ring: Field, frame: Rect) -> Field:
    """The closed `ring` with a point every 40 units along its segments wholly off `frame`.

    Simplifying leaves each off-screen closing run as one long segment, and a spline through it
    swings the coast wide where it leaves the frame; short segments keep the tangents local.
    """
    out: list[Field] = []
    for a, b in zip(ring, np.roll(ring, -1, axis=0), strict=True):
        out.append(a)
        if not frame.contains(Vec(*a)) and not frame.contains(Vec(*b)):
            n = int(np.hypot(*(b - a)) // 40)
            out += [a + (b - a) * k / (n + 1) for k in range(1, n + 1)]
    return np.array(out)


def isobaths(s: Canvas[Chart], depth: Field, trim: bool = False) -> None:
    """The depth contours of `depth`; with `trim`, not those that only graze the frame."""
    for level, dash in DEPTHS:
        d = P()
        for line in iso_lines(depth, level, cell=CELL, simplify=0.6):
            x, y = line[:, 0], line[:, 1]
            inset = np.minimum.reduce([x, s.w - x, y, s.h - y]).max()
            if long(line, 20) and not (trim and inset < 16):
                d.spline(line)
        s.stroke(d, UI, 1.4, dash=dash)


def anchor(s: Canvas[Chart], at: Vec) -> None:
    hx, hy = at
    shank = (
        P()
        .M(hx, hy - 16)
        .V(hy + 8)
        .M(hx - 6, hy - 9)
        .H(hx + 6)
        .M(hx - 10, hy - 1)
        .A(10, 10, 0, 0, 0, hx + 10, hy - 1)
    )
    s.stroke(shank, UI_HI, 1.6)
    s.stroke(P().circle((hx, hy - 19), 3), UI_HI, 1.4)


def compass_rose(s: Canvas[Chart], rose: Vec) -> None:
    ticks = P()
    for b in range(360):
        tick = 16 if b % 10 == 0 else 10 if b % 5 == 0 else 5
        ticks.M(polar(rose, ROSE_R, bearing=b)).L(polar(rose, ROSE_R - tick, bearing=b))
    s.stroke(ticks, UI, 1.2)
    s.stroke(P().circle(rose, ROSE_R), UI, 1.4)
    s.stroke(P().circle(rose, ROSE_R - 26), UI, 1.2)
    rx, ry = rose
    s.stroke(P().M(rx - 120, ry).H(rx + 120).M(rx, ry - 120).V(ry + 120), UI, 1.2)
    s.fill(P().arrowhead(polar(rose, 112, bearing=0), 112, bearing=0, width=7), ACCENT)
    s.fill(P().arrowhead(polar(rose, 112, bearing=180), 112, bearing=180, width=7), UI_ALT)


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Chart]) -> None:
    if s.params.coast == "estuary":
        estuary(s)
    elif s.params.coast == "harbor":
        harbor(s)
    elif s.params.coast == "skerries":
        skerries(s)
    else:
        headland(s)


def headland(s: Canvas[Chart]) -> None:
    """A headland with a sector light over the approach to an anchorage in its bay."""
    # dx: where the canvas's left edge falls on the chart
    if s.landscape:
        # the rose keeps its place from the right edge; the chart is cut or carried on westward
        dx = 1920 - s.w
        rose = Vec(s.w - 280, s.h - 220)
    else:
        dx = 120
        # low on the screen, but on a tall phone no further from the chart than it needs
        rose = Vec(s.w - 280, min(s.h * 0.78, 1560))
    light, harbor = LIGHT - (dx, 0), HARBOR - (dx, 0)
    cols, rows = s.w // CELL + 1, s.h // CELL + 1
    x0 = dx // CELL
    west = max(0, -x0)  # chart cells west of the 16:9 chart
    # the chart from its west end, so land cut off the canvas still shapes the depths
    span = west + max(CHART[0], x0 + cols)

    y, x = np.mgrid[0:rows, 0:span] * CELL
    x -= west * CELL

    def noise(key: int, scale: int, octaves: int, gain: float = 0.5) -> Field:
        return layer(s, key, scale, octaves, gain, west, span, rows)

    # land rises towards the top-left corner, edged by fBm headlands and bays; west of the 16:9
    # chart the coast climbs back to the top edge, so a wide screen shows a broad headland
    reach = np.where(x < 0, 1700, 1000)
    base = 1 - ((np.abs(x) / reach) ** 1.6 + (y / 620) ** 1.6) ** (1 / 1.6)
    big = noise(4, 240, 2)
    fine = noise(5, 60, 4, 0.55)
    # the harbor: a bay pushed north-west into the land
    u, v = (x - 640) * 0.8 + (y - 250) * 0.6, -(x - 640) * 0.6 + (y - 250) * 0.8
    bay = 0.4 * np.exp(-(u**2 / (2 * 70**2) + v**2 / (2 * 90**2)))
    rough = noise(6, 16, 2)
    islets = (1 + 0.9 * rough) * sum(
        a * np.exp(-((x - ix) ** 2 + (y - iy) ** 2) / (2 * r**2)) for ix, iy, r, a in ISLETS
    )
    land = base + 0.25 * big + 0.1 * fine - bay + islets

    wet = land <= 0
    dist = ndimage.distance_transform_edt(wet) * CELL
    shoal = noise(9, 320, 2)
    depth = ndimage.gaussian_filter(dist * (1 + 0.5 * shoal) + 70 * noise(10, 160, 2), 4)
    depth = np.where(wet, depth, 0)
    # from here on the arrays are on the canvas
    view = slice(west + x0, west + x0 + cols)
    land, wet, depth = land[:, view], wet[:, view], depth[:, view]

    def at(p: Vec) -> float:
        return float(depth[min(rows - 1, int(p.y / CELL)), min(cols - 1, int(p.x / CELL))])

    # shallows get a faint tint, as charts wash the inshore water
    s.fill(region(np.where(wet, DEPTHS[1][0] - depth, 1)), mix(BG, BG_ALT, 0.3), rule="evenodd")
    s.path(region(land), fill=BG_ALT, fill_rule="evenodd", stroke=UI_ALT, stroke_width=1.6)
    isobaths(s, depth)

    # The light's sector bisects the approach, which the track follows in to the anchorage. The
    # track starts level with the rose, so the two read as a pair and the open water stays open.
    if s.landscape:
        sector = 152.5  # compass bearing of the sector's center line, seaward from the light
        ahead = polar((0, 0), 1, bearing=sector)
        entry = light + ahead * ((rose.y - light.y) / ahead.y)
    else:
        # too narrow to run out on that bearing: aim the sector at an entry left of the rose
        entry = rose - (310, 0)
        ahead = (entry - light).unit()
        sector = math.degrees(math.atan2(ahead.x, -ahead.y))
    turn = light + ahead * 200
    path = [entry, turn, harbor + (26, 4)]
    track = LineString(path)

    soundings: list[Vec] = []
    r = s.rng(3)
    for p in poisson_disk(Rect(20, 20, s.w - 40, s.h - 40), 52, r):
        q = Vec(*p)
        dv = at(q)
        # soundings thin out offshore, where charts sound less densely
        if (
            dv < 8
            or r.random() > 1.25 * math.exp(-((dv / 300) ** 1.6))
            or any(abs(dv - level) < 12 for level, _ in DEPTHS)
        ):
            continue
        if abs(q - rose) < ROSE_R + 40 or track.distance(Point(q)) < 22 or abs(q - light) < 30:
            continue
        n = 1 if dv < 60 else 2 if dv < 220 else 3
        soundings += [q + ((k - (n - 1) / 2) * 5, 0) for k in range(n)]
    s.fill(P().dots(soundings, 1.5), UI_ALT)

    arc = (sector - SPREAD / 2, sector + SPREAD / 2)
    edges = P()
    for b in arc:
        edges.M(polar(light, 40, bearing=b)).L(polar(light, LIGHT_R - 30, bearing=b))
    s.stroke(edges, UI_ALT, 1.2, dash=(4, 5))
    s.stroke(P().arc(light, LIGHT_R, bearing=arc), ACCENT, 2)
    s.stroke(P().poly(path), ACCENT_3, 2, dash=(14, 8))
    across = ahead.perp() * 9
    s.stroke(P().M(entry + across).L(entry - across), UI_HI, 1.6)
    s.path(P().circle(turn, 7), fill=BG, stroke=UI_HI, stroke_width=1.6)
    s.fill(P().circle(turn, 3), ACCENT_1)
    anchor(s, harbor)
    s.stroke(P().circle(light, 8), UI_HI, 1.6)
    s.fill(P().circle(light, 3.5), ACCENT)
    compass_rose(s, rose)


def view(s: Canvas[Chart], focus: Vec) -> Affine:
    """Chart units to canvas: a landscape canvas keeps the sheet's east edge on its right edge,
    as the headland does; a portrait one turns the sheet a quarter clockwise, `focus` centered."""
    if s.landscape:
        return Affine.translate(s.w - 1920, 0)
    return (
        Affine.translate(s.w / 2, s.h / 2)
        @ Affine.rotate(deg=90)
        @ Affine.translate(-focus.x, -focus.y)
    )


def sheet(s: Canvas[Chart], frame: Affine) -> tuple[Field, Field]:
    """Chart coordinates (u, v) of the canvas's cells, MARGIN cells past each edge."""
    rows, cols = s.h // CELL + 1, s.w // CELL + 1
    gy, gx = np.mgrid[-MARGIN : rows + MARGIN, -MARGIN : cols + MARGIN] * CELL
    uv = frame.inverse().apply(np.stack([gx.ravel(), gy.ravel()], axis=1))
    return uv[:, 0].reshape(gx.shape), uv[:, 1].reshape(gx.shape)


def fbm(
    s: Canvas[Chart], key: str, u: Field, v: Field, scale: float, octaves: int, step: int = 4
) -> Field:
    """Noise `key` at chart coordinates (u, v), features `scale` units across and `octaves` deep,
    sampled every `step` cells and interpolated between: plenty for noise this broad."""
    coarse = s.noise(key).fbm(u[::step, ::step] / scale, v[::step, ::step] / scale, octaves)
    rows, cols = u.shape
    return ndimage.map_coordinates(coarse, np.mgrid[0:rows, 0:cols] / step, order=1, mode="nearest")


def chart(
    s: Canvas[Chart],
    u: Field,
    v: Field,
    land: Field,
    dry: Field,
    edge: Literal["sand", "rock"] = "sand",
    coast: Path | None = None,
) -> tuple[Field, Mask]:
    """Draw the tinted shallows, the drying ground, the land and the isobaths from `land` (above
    0 ashore) and `dry` (above 0 where the bottom dries), both over the sheet from `sheet`, with
    `coast` in place of the land's outline when given. Drying sand is edged with a dotted line,
    drying rock with a ragged fringe. Returns the depth over the canvas's cells and where they
    dry."""
    wet = dry <= 0
    dist = ndimage.distance_transform_edt(wet) * CELL
    swell = fbm(s, "swell", u, v, 640, 2)
    depth = ndimage.gaussian_filter(
        dist * (1 + 0.5 * fbm(s, "shoal", u, v, 1280, 2)) + 70 * swell, 4
    )
    depth = np.where(wet, depth, 0)
    rows, cols = s.h // CELL + 1, s.w // CELL + 1
    on = (slice(MARGIN, MARGIN + rows), slice(MARGIN, MARGIN + cols))
    land, dry, wet, depth = land[on], dry[on], wet[on], depth[on]
    s.fill(region(np.where(wet, DEPTHS[1][0] - depth, 1)), mix(BG, BG_ALT, 0.3), rule="evenodd")
    drying = (dry > 0) & (land <= 0)
    if drying.any():
        edges = rings(dry)
        outline = P()
        for ring in edges:
            outline.spline(ring, closed=True)
        s.fill(outline, DRYING, rule="evenodd")
        if edge == "sand":
            s.stroke(outline, UI_ALT, 1.8, cap="round", dash=(0.1, 4.4))
        else:
            s.stroke(fringe(s, dry, edges), UI, 1.2)
    s.path(
        region(land) if coast is None else coast,
        fill=BG_ALT,
        fill_rule="evenodd",
        stroke=UI_ALT,
        stroke_width=1.6,
    )
    isobaths(s, depth, trim=True)
    return depth, drying


def fringe(s: Canvas[Chart], dry: Field, edges: list[Field]) -> Path:
    """Short ticks from `edges`, the outlines of `dry`, out into the water: rock that covers and
    uncovers."""
    rows, cols = dry.shape
    r = s.rng("fringe")
    d = P()
    for ring in edges:
        edge = Polyline(spline_points(ring, 4, closed=True), closed=True)
        for k in np.arange(0, edge.length, 4.5):
            p, t = edge.at(k), edge.tangent(k)
            if not s.inset(-8).contains(p):
                continue
            out = t.perp()
            i, j = int((p.y + out.y * 4) / CELL), int((p.x + out.x * 4) / CELL)
            if 0 <= i < rows and 0 <= j < cols and dry[i, j] > 0:
                out = -out
            d.M(p).L(p + out * r.uniform(2.5, 7))
    return d


def sound(s: Canvas[Chart], depth: Field, drying: Mask, clear: Callable[[Vec], bool]) -> None:
    """Soundings over the water, thinning offshore, and on drying ground the drying heights,
    underlined as charts print them; only at points where `clear` holds."""
    rows, cols = depth.shape
    dots: list[Vec] = []
    bars = P()
    r = s.rng("soundings")
    for p in poisson_disk(Rect(20, 20, s.w - 40, s.h - 40), 52, r):
        q = Vec(*p)
        i, j = min(rows - 1, int(q.y / CELL)), min(cols - 1, int(q.x / CELL))
        dv = float(depth[i, j])
        if drying[i, j]:
            n = 1 + int(r.random() < 0.4)
        elif (
            dv < 8
            or r.random() > 1.25 * math.exp(-((dv / 300) ** 1.6))
            or any(abs(dv - level) < 12 for level, _ in DEPTHS)
        ):
            continue
        else:
            n = 1 if dv < 60 else 2 if dv < 220 else 3
        if not clear(q):
            continue
        dots += [q + ((k - (n - 1) / 2) * 5, 0) for k in range(n)]
        if drying[i, j]:
            bars.M(q.x - 2.5 * n - 1, q.y + 5).H(q.x + 2.5 * n + 1)
    s.fill(P().dots(dots, 1.5), UI_ALT)
    s.stroke(bars, UI_ALT, 1.2)


def flare(d: Path, light: Vec, bearing: float = 315) -> None:
    """A light's flare: a teardrop pointing from the light, as charts print it."""
    tip, length, r = polar(light, 5, bearing=bearing), 22, 5.5
    c = polar(tip, length, bearing=bearing)
    turn = math.degrees(math.acos(r / length))
    back = bearing + 180
    pts = [tip] + [polar(c, r, bearing=back + turn + k * (360 - 2 * turn) / 16) for k in range(17)]
    d.poly(pts, closed=True)


def buoy(line: Path, body: Path, at: Vec, shape: Literal["can", "cone", "sphere"]) -> None:
    """A buoy standing at `at` in chart symbols: a small circle at its foot on a waterline,
    under a leaning can, cone or sphere. The outline goes on `line`, a knock-out on `body`."""
    x, y = at
    if shape == "can":
        outline = [(x - 9, y), (x - 7.3, y - 13), (x + 12, y - 8.2), (x + 9, y)]
        body.poly(outline, closed=True)
        line.poly(outline)
    elif shape == "cone":
        body.M(x - 8.3, y).C((x - 6, y - 10), (x, y - 17), (x + 5.3, y - 20)).C(
            (x + 8, y - 15), (x + 8.5, y - 8), (x + 8.5, y)
        ).Z()
        line.M(x - 8.3, y).C((x - 6, y - 10), (x, y - 17), (x + 5.3, y - 20)).C(
            (x + 8, y - 15), (x + 8.5, y - 8), (x + 8.5, y)
        )
    else:
        body.M(x - 10, y).A(10, 10, 0, 1, 1, x + 10, y).Z()
        line.M(x - 10, y).A(10, 10, 0, 1, 1, x + 10, y).M(x, y - 3).L(x + 3.6, y - 9.4)
    line.M(x - 14, y).H(x - 3).M(x + 3, y).H(x + 14).circle(at, 3)


def estuary(s: Canvas[Chart]) -> None:
    """A river mouth half filled by sandbanks, a buoyed channel winding out between them."""
    frame = view(s, Vec(1080, 560))
    u, v = sheet(s, frame)
    big, fine = fbm(s, "big", u, v, 900, 2), fbm(s, "fine", u, v, 220, 4, 2)
    center = spline_points(CHANNEL, 24)
    # the river winds with its channel; at the mouth the north shore swings up and away and the
    # south shore down and away
    river = 545 + (np.interp(u, center[:, 0], center[:, 1]) - 545) * smoothstep(400, 0, u)
    north = river - 145 - 560 * smoothstep(250, 1200, u)
    south = river + 145 + 560 * smoothstep(100, 850, u)
    land = np.maximum(north - v, v - south) / 140 + 0.5 * big + 0.12 * fine
    reach, _ = cKDTree(center).query(np.stack([u.ravel(), v.ravel()], axis=1))
    reach = reach.reshape(u.shape)
    # banks lie along the ebb, so their noise is stretched along the river
    banks = (
        gauss(u - 880, 560) * gauss(v - 560, 300) * (0.6 + 2.4 * fbm(s, "sand", u / 3, v, 150, 2))
    )
    banks = np.minimum(banks - 0.3, (reach - 72) / 60)
    dry = np.maximum(land + 0.3, banks)
    depth, drying = chart(s, u, v, land, dry)

    # the buoyed reach, traveled inward: cans to port, cones to starboard
    inward = center[(center[:, 0] > BUOYED[0]) & (center[:, 0] < BUOYED[1])][::-1]
    way = Polyline(frame.apply(inward))
    stations = np.arange(40, way.length - 20, GATE)
    gates = [way.at(d) for d in stations]
    line, body = P(), P()
    for k, d in enumerate(stations):
        p, side = way.at(d), way.tangent(d).perp()
        buoy(line, body, p + side * BEAM, "cone")
        buoy(line, body, p - side * BEAM + way.tangent(d) * (22 if k % 2 else -22), "can")
    fairway = frame(Vec(1560, 495))
    buoy(line, body, fairway, "sphere")
    berth = frame(Vec(330, 590))
    legs = LineString([fairway, *gates, berth + (26, 4)]).simplify(10)
    track = [Vec(*q) for q in legs.coords]
    # on a portrait screen the river runs down from the top and the rose sits off the fairway
    rose = Vec(s.w - 280, s.h - 220) if s.landscape else Vec(s.w - 260, s.h - 230)

    def clear(q: Vec) -> bool:
        return abs(q - rose) > ROSE_R + 40 and legs.distance(Point(q)) > 22

    sound(s, depth, drying, clear)
    s.fill(body, BG)
    s.stroke(line, UI_HI, 1.4)
    s.stroke(P().poly(track), ACCENT, 1.8)
    glow = P()
    flare(glow, fairway, 45)
    s.fill(glow, ACCENT)
    anchor(s, berth)
    compass_rose(s, rose)


def harbor(s: Canvas[Chart]) -> None:
    """A walled harbor under a headland, led into on a pair of leading lights."""
    # on a portrait screen the coast runs along the bottom, the entrance 620 units above it
    frame = view(s, Vec(1970 - s.h / 2, 600))
    u, v = sheet(s, frame)
    big, fine = fbm(s, "big", u, v, 900, 2), fbm(s, "fine", u, v, 220, 4, 2)
    # the coast runs north and south, out to a headland north of the town, whose waterfront is
    # kept straight
    coastline = 1440 - 170 * gauss(v - 60, 240) + 90 * gauss(v - 1020, 280)
    calm = 1 - 0.8 * gauss(v - 560, 260)
    land = (u - coastline) / 160 + calm * (1.1 * big + 0.15 * fine)
    moles = shapely.union_all([LineString(m).buffer(9, quad_segs=12) for m in MOLES])
    basin = Polygon(BASIN)
    works = shapely.contains_xy(moles, u, v)
    solid = np.where(works, 1.0, np.where(shapely.contains_xy(basin, u, v), -1.0, land))
    rows, cols = s.h // CELL + 1, s.w // CELL + 1
    ashore = land[MARGIN : MARGIN + rows, MARGIN : MARGIN + cols]
    to_canvas = [frame.a, frame.c, frame.b, frame.d, frame.e, frame.f]
    coast: BaseGeometry = Polygon()
    for ring in rings(ashore):
        coast = coast.symmetric_difference(Polygon(spline_points(ring, 4, closed=True)).buffer(0))
    coast = coast.union(affinity.affine_transform(moles, to_canvas))
    coast = coast.difference(affinity.affine_transform(basin, to_canvas))
    depth, drying = chart(s, u, v, solid, solid, coast=P().shape(coast))

    heads = [Vec(*m[-1]) for m in MOLES]
    entrance = frame((heads[0] + heads[1]) / 2)
    ahead = (frame(polar((0, 0), 1, bearing=TRANSIT)) - frame(Vec(0, 0))).unit()
    front = entrance + ahead * 320
    rear = front + ahead * 170
    # offshore it starts well inside the frame: 1050 units out, or on a portrait screen as far
    # as the top and left margins allow
    run = 1050 if s.landscape else min((entrance.y - 260) / ahead.y, (entrance.x - 150) / ahead.x)
    start = entrance - ahead * run
    rose = Vec(max(300, s.w - 1620), 280) if s.landscape else Vec(s.w - 280, 330)
    line = LineString([start, rear])

    def clear(q: Vec) -> bool:
        return abs(q - rose) > ROSE_R + 40 and line.distance(Point(q)) > 22

    sound(s, depth, drying, clear)
    # the leading line: firm where it is steered, dashed on to the lights
    inside = entrance + ahead * 60
    s.stroke(P().M(start).L(inside), ACCENT, 2)
    s.stroke(P().M(inside).L(rear), ACCENT_3, 1.6, dash=(10, 6))
    across = ahead.perp() * 9
    s.stroke(P().M(start + across).L(start - across), UI_HI, 1.6)
    glow = P()
    for light in (front, rear):
        flare(glow, light)
    s.fill(glow, ACCENT)
    s.fill(P().dots([front, rear], 3), UI_HI)
    compass_rose(s, rose)


def rock(cross: Path, dots: Path, at: Vec, kind: int) -> None:
    """A rock in chart symbols: an asterisk where it dries (kind 0), a cross with a dot in each
    quarter where it is awash (1), a bare cross where it lies just under (2)."""
    x, y = at
    if kind == 0:
        for b in (0, 60, 120):
            cross.M(polar(at, 6, bearing=b)).L(polar(at, 6, bearing=b + 180))
        return
    cross.M(x - 6, y).H(x + 6).M(x, y - 6).V(y + 6)
    if kind == 1:
        dots.dots(
            [(x - 3.2, y - 3.2), (x + 3.2, y - 3.2), (x - 3.2, y + 3.2), (x + 3.2, y + 3.2)], 1.1
        )


def skerries(s: Canvas[Chart]) -> None:
    """A mainland behind a cluster of islets and rocks, a track threading the gap between them."""
    frame = view(s, Vec(980, 560))
    u, v = sheet(s, frame)
    big, fine = fbm(s, "big", u, v, 700, 2), fbm(s, "fine", u, v, 200, 4, 2)
    main = (v - 930 + 120 * gauss(u - 1500, 320)) / 140 + 2 * big + 0.3 * fine
    lane = np.concatenate([np.linspace(a, b, 64) for a, b in pairwise(np.array(PASSAGE, float))])
    reach = cKDTree(lane).query(np.stack([u.ravel(), v.ravel()], axis=1))[0].reshape(u.shape)
    # islands crowd the middle of the group and thin out to its edges; the track's lane is clear
    group = np.exp(-(((u - 1000) / 760) ** 2 + ((v - 580) / 260) ** 2))
    isles = 1.6 * fbm(s, "isles", u, v, 170, 4, 2) + 0.9 * group - 0.95
    land = np.maximum(main, np.minimum(isles, (reach - 60) / 80))
    # the rock in the narrows dries, a ledge too small to show above high water
    dry = np.maximum(land + 0.14, 0.5 * gauss(np.hypot(u - DANGER.x, v - DANGER.y), 20) - 0.2)
    depth, drying = chart(s, u, v, land, dry, "rock")

    track = [frame(Vec(*q)) for q in PASSAGE]
    legs = LineString(track)
    rose = Vec(s.w - 280, 250) if s.landscape else Vec(s.w - 260, s.h - 280)

    def clear(q: Vec) -> bool:
        return abs(q - rose) > ROSE_R + 40 and legs.distance(Point(q)) > 22

    cross, dots, danger = P(), P(), P()
    beacon = frame(DANGER)
    hazards: list[Vec] = [beacon, beacon + (0, -24)]
    rr = s.rng("rocks")
    for p in poisson_disk(s.inset(40), 50, rr):
        q = Vec(*p)
        i, j = int(q.y / CELL), int(q.x / CELL)
        if (
            not clear(q)
            or legs.distance(Point(q)) < 50
            or abs(q - beacon) < 50
            or group[MARGIN + i, MARGIN + j] < 0.33
        ):
            continue
        dv, roll = float(depth[i, j]), rr.random()
        if drying[i, j] and roll < 0.3:
            rock(cross, dots, q, 0)
        elif 8 < dv < 50 and roll < 0.3:
            rock(cross, dots, q, 1 if dv < 22 else 2)
            if dv > 28:
                danger.circle(q, 13)
        else:
            continue
        hazards.append(q)
    sound(s, depth, drying, lambda q: clear(q) and all(abs(q - h) > 20 for h in hazards))
    s.stroke(cross, UI_HI, 1.3)
    s.fill(dots, UI_HI)
    s.stroke(danger, UI_ALT, 1.6, cap="round", dash=(0.1, 4.1))
    # a recommended track not laid on fixed marks: dashed, a two-way arrow midway along each leg
    route, arrows = P(), P()
    for a, b in pairwise(track):
        mid, t = (a + b) / 2, (b - a).unit()
        route.M(a).L(mid - t * 26).M(mid + t * 26).L(b)
        arrows.M(mid - t * 18).L(mid + t * 18)
        for tip in (mid - t * 18, mid + t * 18):
            back = (mid - tip).unit() * 7
            arrows.M(tip + back + t.perp() * 5).L(tip).L(tip + back - t.perp() * 5)
    s.stroke(route, ACCENT, 1.8, dash=(12, 7))
    s.stroke(arrows, ACCENT, 1.6)
    across = (track[1] - track[0]).unit().perp() * 9
    s.stroke(P().M(track[0] + across).L(track[0] - across), UI_HI, 1.6)
    # the beacon: a leaning spar on the rock under a topmark of two balls, and its light's flare
    bx, by = beacon
    spar = P().M(bx - 12, by).H(bx - 3).M(bx + 3, by).H(bx + 12).circle(beacon, 3)
    spar.M(bx + 0.8, by - 2.9).L(bx + 4.5, by - 22)
    spar.circle((bx + 5.4, by - 26.5), 2.6).circle((bx + 6.6, by - 33), 2.6)
    s.stroke(spar, UI_HI, 1.4)
    glow = P()
    flare(glow, beacon, 300)
    s.fill(glow, ACCENT)
    anchor(s, track[-1] - (26, 4))
    compass_rose(s, rose)
