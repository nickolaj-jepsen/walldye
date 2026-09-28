"""A nautical chart corner: a noise-field coast with isobaths traced from its distance field, soundings, a light sector, an approach track and a compass rose."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from shapely.geometry import LineString, Point

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
    Path,
    Rect,
    Vec,
    design,
    mix,
    polar,
    smoothstep,
)
from walldye.field import iso_lines, noise_grid
from walldye.geom import Polyline, poisson_disk

type Field = NDArray[np.float64]

CELL = 4
CHART = (1920 // CELL + 1, 1080 // CELL + 1)  # the 16:9 chart the coast was tuned on, in cells
ISLETS = ((640, 580, 24, 0.5), (694, 546, 12, 0.5), (606, 610, 8, 0.4))  # x, y, radius, height
LIGHT, HARBOUR = Vec(960, 150), Vec(786, 250)  # chart positions
LIGHT_R, SPREAD = 260, 40  # the light's sector: arc radius, width in degrees
ROSE_R = 150
FADE = 480  # units over which the westward coast takes over from the 16:9 chart's noise
PAD = 5  # cells a region's field is held past the frame, so its outline closes off-screen
# depth in chart units, dash pattern: finer dashes inshore, as charts mark their isobaths
DEPTHS = ((28, (1.5, 5)), (80, (10, 6)), (170, (14, 5, 2, 5)), (320, (22, 6, 2, 6, 2, 6)))


def layer(
    s: Canvas, key: int, scale: int, octaves: int, gain: float, west: int, cols: int, rows: int
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


def region(a: Field) -> Path:
    """Closed outlines of `a > 0` on the canvas that `a` covers."""
    rows, cols = a.shape
    frame = Rect(0, 0, (cols - 1) * CELL, (rows - 1) * CELL)
    padded = np.pad(np.pad(a, PAD, mode="edge"), 1, constant_values=-1)
    origin = (-(PAD + 1) * CELL, -(PAD + 1) * CELL)
    d = P()
    for line in iso_lines(padded, 0, cell=CELL, origin=origin, simplify=0.5):
        if Polyline(line).length > 30:
            d.spline(densify_off_frame(line[:-1], frame), closed=True)
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


@design(aspects="any")
def draw(s: Canvas) -> None:
    # dx: where the canvas's left edge falls on the chart
    if s.landscape:
        # the rose keeps its place from the right edge; the chart is cut or carried on westward
        dx = 1920 - s.w
        rose = Vec(s.w - 280, s.h - 220)
    else:
        dx = 120
        # low on the screen, but on a tall phone no further from the chart than it needs
        rose = Vec(s.w - 280, min(s.h * 0.78, 1560))
    light, harbour = LIGHT - (dx, 0), HARBOUR - (dx, 0)
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
    # the harbour: a bay pushed north-west into the land
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
    for level, dash in DEPTHS:
        d = P()
        for line in iso_lines(depth, level, cell=CELL, simplify=0.6):
            if Polyline(line).length > 20:
                d.spline(line)
        s.stroke(d, UI, 1.4, dash=dash)

    # The light's sector bisects the approach, which the track follows in to the anchorage. The
    # track starts level with the rose, so the two read as a pair and the open water stays open.
    if s.landscape:
        sector = 152.5  # compass bearing of the sector's centre line, seaward from the light
        ahead = polar((0, 0), 1, bearing=sector)
        entry = light + ahead * ((rose.y - light.y) / ahead.y)
    else:
        # too narrow to run out on that bearing: aim the sector at an entry left of the rose
        entry = rose - (310, 0)
        ahead = (entry - light).unit()
        sector = math.degrees(math.atan2(ahead.x, -ahead.y))
    turn = light + ahead * 200
    path = [entry, turn, harbour + (26, 4)]
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
    hx, hy = harbour
    anchor = (
        P()
        .M(hx, hy - 16)
        .V(hy + 8)
        .M(hx - 6, hy - 9)
        .H(hx + 6)
        .M(hx - 10, hy - 1)
        .A(10, 10, 0, 0, 0, hx + 10, hy - 1)
    )
    s.stroke(anchor, UI_HI, 1.6)
    s.stroke(P().circle((hx, hy - 19), 3), UI_HI, 1.4)
    s.stroke(P().circle(light, 8), UI_HI, 1.6)
    s.fill(P().circle(light, 3.5), ACCENT)

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
