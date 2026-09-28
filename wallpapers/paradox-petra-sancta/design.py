"""A heraldry treatise plate: the de Clare arms on a compass-built heater shield, tinctures in Petra Sancta hatching with a seven-swatch key."""

import math

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry

from walldye import ACCENT, ACCENT_3, BG_ALT, UI, UI_ALT, UI_HI, Canvas, P, Path, design
from walldye.geom import hatch

WID, HT = 440, 520  # shield width and height, top to tip
# classic heater: each base arc has radius = shield width, centred on the opposite flank
FLANK = HT - math.sqrt(WID**2 - (WID / 2) ** 2)  # below the top, where the base arcs begin
# chevronels measured off Commons' Clare_Blazon.svg: upper-edge apexes at 1%, 27% and 53% of
# the height, each ~13% tall at the pale, arms falling 0.85 per unit across
CHEV_APEXES, CHEV_DROP, CHEV_SLOPE = (6, 141, 276), 66, 0.85
MARGIN = 48  # plate border
SW, SW_PITCH = 34, 81  # key swatch size and spacing
KEY_W = 6 * SW_PITCH + SW
KEY_GAP = 180  # key's right end to the shield's dexter edge, landscape
# Petra Sancta's seven tinctures in canonical order (or, argent, gules, then the other four
# colours), each named here by its hatching
KEY = ("dots", "plain", "pale", "fess", "bend", "grid", "bend-sinister")


def stagger(region: BaseGeometry, step: float, ox: float, oy: float) -> NDArray[np.float64]:
    """Centres of a dot grid `step` apart inside `region`, anchored at (ox, oy), with every odd
    row shifted half a step; dots on the boundary are left out."""
    x0, y0, x1, y1 = region.bounds
    j = np.arange(math.floor((y0 - oy) / step), math.ceil((y1 - oy) / step) + 1)
    i = np.arange(math.floor((x0 - ox) / step) - 1, math.ceil((x1 - ox) / step) + 1)
    xs = ox + (i[None, :] + 0.5 * (j[:, None] % 2)) * step
    ys = np.broadcast_to(oy + j[:, None] * step, xs.shape)
    keep = shapely.contains_xy(region, xs, ys)
    return np.column_stack([xs[keep], ys[keep]])


def rule(d: Path, region: BaseGeometry, pitch: float, deg: float, shortest: float = 0.0) -> None:
    """Hatching across `region` at `deg` into `d`, dropping pieces shorter than `shortest` (the
    corner slivers a diagonal leaves in a square)."""
    for seg in hatch(region, pitch, deg=deg):
        if math.dist(seg[0], seg[1]) >= shortest:
            d.poly(seg)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the shield's centre: on the right third in landscape, above the middle on a phone
    c = s.pick(landscape=(1180 / 1920, 520 / 1080), portrait=(0.5, 0.44), snap=1)
    k = 1.0 if s.landscape else 1.2  # a phone is width-bound, so the shield grows a little
    wid, ht = WID * k, HT * k
    # narrow landscapes (16:10) keep the key 200 units inside the plate
    cx = max(c.x, MARGIN + 200 + KEY_W + KEY_GAP + wid / 2) if s.landscape else c.x
    top = c.y - ht / 2
    x0, x1, flank, fess, tip = cx - wid / 2, cx + wid / 2, top + FLANK * k, top + ht / 2, top + ht

    # --- geometry ------------------------------------------------------
    base = box(x0, flank, x1, tip + 1)
    for ox in (x0, x1):
        base = base.intersection(shapely.Point(ox, flank).buffer(wid, quad_segs=256))
    shield = box(x0, top, x1, flank).union(base)

    def under(apex_y: float) -> Polygon:
        """Everything below a chevron line with its apex on the pale at `apex_y`."""
        return Polygon(
            [
                (cx, apex_y),
                (cx + wid, apex_y + wid * CHEV_SLOPE),
                (cx + wid, tip + ht),
                (cx - wid, tip + ht),
                (cx - wid, apex_y + wid * CHEV_SLOPE),
            ]
        )

    chev = shapely.unary_union(
        [under(top + a * k).difference(under(top + (a + CHEV_DROP) * k)) for a in CHEV_APEXES]
    ).intersection(shield)
    field = shield.difference(chev)

    # --- plate border and registration ticks ---------------------------
    m = MARGIN
    s.stroke(P().rect(m, m, s.w - 2 * m, s.h - 2 * m), UI, 0.75)
    ticks = P()
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        x, y = m if sx > 0 else s.w - m, m if sy > 0 else s.h - m
        ticks.M(x - sx * 14, y).H(x - sx * 4).M(x, y - sy * 14).V(y - sy * 4)
    s.stroke(ticks, UI_ALT, 0.75)

    # --- construction layer --------------------------------------------
    # each base arc carried well past the shield: centred on one flank, from above the other
    # flank on past the tip
    s.stroke(
        P().arc((x1, flank), wid, deg=(196, 104)).arc((x0, flank), wid, deg=(-16, 76)), UI, 0.75
    )
    datums = P()
    for y in (top, fess, flank, tip):
        datums.M(x0 - 110, y).H(x1 + 110)
    s.stroke(datums, BG_ALT, 0.75)
    cross = P()
    for ox in (x0, x1):
        cross.M(ox - 14, flank).H(ox - 4).M(ox + 4, flank).H(ox + 14)
        cross.M(ox, flank - 14).V(flank - 4).M(ox, flank + 4).V(flank + 14)
        cross.circle((ox, flank), 4)

    if s.landscape:
        # the key rides the base datum, which is carried dotted across to it
        kx, ky, pitch = x0 - KEY_GAP - KEY_W, tip - SW / 2, SW_PITCH
        pale_end = s.h - m - 40
    else:
        # spread across the shield's width under it, with the pale axis pointing down to it
        kx, ky, pitch = x0, tip + 160, (wid - SW) / 6
        pale_end = ky - 28
    # pale axis stops at the shield so it isn't read as a partition line
    pale = P().M(cx, max(m + 40, top - 172)).V(top - 8).M(cx, tip + 8).V(pale_end)
    s.stroke(pale, UI, 0.75, dash=(14, 4, 2, 4))
    s.stroke(cross, UI_HI, 1)

    # --- dimensions ----------------------------------------------------
    dim, heads = P(), P()
    dx = x1 + 70
    dim.M(x1 + 12, top).H(dx + 12).M(cx + 12, tip).H(dx + 12).M(dx, top).V(tip)
    heads.arrowhead((dx, top), 9, deg=-90, width=2.6).arrowhead((dx, tip), 9, deg=90, width=2.6)
    dim.M(dx - 5, flank).H(dx + 5)
    dy = tip + 50
    dim.M(x0, flank + 12).V(dy + 12).M(x1, flank + 12).V(dy + 12).M(x0, dy).H(x1)
    heads.arrowhead((x0, dy), 9, deg=180, width=2.6).arrowhead((x1, dy), 9, deg=0, width=2.6)
    s.stroke(dim, UI, 0.75)
    s.fill(heads, UI)

    # --- tinctures: a dotted field, chevronels ruled upright -------------
    s.fill(P().dots(stagger(field, 8, cx, top), 1.0), UI_ALT)
    ruled = P()
    rule(ruled, chev, 5, 90)
    s.stroke(ruled, ACCENT, 1)

    # --- outlines ------------------------------------------------------
    outline = P().M(x0, top).H(x1).V(flank).A(wid, wid, 0, 0, 1, cx, tip)
    s.stroke(outline.A(wid, wid, 0, 0, 1, x0, flank).Z(), UI_HI, 1.5, join="miter")
    s.stroke(P().shape(chev), ACCENT, 1.5, join="miter")

    # --- tincture key --------------------------------------------------
    frames, dots, upright, lines = P(), P(), P(), P()
    for i, name in enumerate(KEY):
        x = kx + i * pitch
        frames.rect(x, ky, SW, SW)
        inner = box(x, ky, x + SW, ky + SW).buffer(-3.5, join_style="mitre")
        if name == "dots":
            dots.dots(stagger(inner, 6, x + SW / 2, ky + SW / 2), 0.9)
        elif name == "pale":
            rule(upright, inner, 4, 90)
        elif name == "fess":
            rule(lines, inner, 4, 0)
        elif name == "bend":
            rule(lines, inner, 4.5, 45, shortest=4)
        elif name == "bend-sinister":
            rule(lines, inner, 4.5, -45, shortest=4)
        elif name == "grid":
            # closed grid: each line set stops exactly on the outermost line of the other
            g0, g1, gy0, gy1 = x + 5, x + SW - 5, ky + 5, ky + SW - 5
            for n in range(7):
                lines.M(g0 + n * 4, gy0).V(gy1).M(g0, gy0 + n * 4).H(g1)
    s.fill(dots, UI_HI)
    s.stroke(upright, ACCENT_3, 0.75)  # the chevronels' tincture, keyed
    s.stroke(lines, UI_HI, 0.75)
    s.stroke(frames, UI_ALT, 0.75)
    if s.landscape:
        s.stroke(P().M(kx + KEY_W + 16, tip).H(x0 - 118), BG_ALT, 0.75, dash=(2, 6))
