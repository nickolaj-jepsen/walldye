"""A sunspot in solar granulation, in Voronoi cells and penumbral filaments."""

import math

import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import Polygon

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    BG,
    BG_ALT,
    BG_DEEP,
    BLACK,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Rect,
    Vec,
    by_regime,
    design,
    ladder,
    mix,
    polar,
    smoothstep,
)
from walldye.geom import Affine, poisson_disk, ribbon

type Ellipse = tuple[float, float, float]

# The drawing is laid out in a landscape frame with the limb towards +x; portrait screens turn it
# a quarter so the limb sits at the top.
PEN: Ellipse = (265, 200, math.radians(-22))  # penumbra: semi-axes and rotation
UMB: Ellipse = (108, 82, math.radians(-30))  # umbra
PORE = Vec(242, -152)  # a lone pore, from the spot center
PORE_R = 13
STRETCH, FALLOFF = 0.35, 0.45  # radial elongation of the granules just outside the penumbra
LIMB_GAP, LIMB_MARGIN = 920, 400  # limb at least this far past the spot and in from the edge
LIMB_R = 760  # foreshortening follows a sphere of this radius, starting LIMB_R before the limb
FADE = (520, 20)  # granulation dims into the lanes between these distances before the limb
# Light themes draw on the paper: the lanes and the sky past the limb are the page, the granules a
# shade darker, the spot the darkest.
LANE = by_regime(BG_DEEP, BG)  # the design's bg: lanes and the sky past the limb
TOP = mix(BG_ALT, UI, 0.2)  # the granule furthest from the lanes' tone
GRAN = ladder((mix(LANE, TOP, 0.1), TOP), 10)  # granule tones, lanes to TOP
# the penumbra between the filaments; the lanes' tone in dark themes, so it only shows in light
FLOOR = by_regime(BG_DEEP, mix(UI_ALT, UI_HI, 0.5))
CORE = by_regime(BLACK, MUTED)  # umbra and pore
FIL = (ACCENT_5, ACCENT_3, ACCENT_2, ACCENT_1)  # penumbral filament tones
FIL_WEIGHTS = (2, 4, 4, 1)
FILAMENTS = 170
BRIDGE = 62  # light bridge direction, degrees
RING = np.linspace(0, math.tau, 90, endpoint=False)
# a penumbral grain: a small ellipse, long axis along the filament
GRAIN = np.array(
    [(4.5 * math.cos(u), 1.7 * math.sin(u)) for u in np.linspace(0, math.tau, 8, endpoint=False)]
)


def ellipse_r(e: Ellipse, a: float) -> float:
    """Radius of the rotated ellipse `e` in direction `a` (screen radians) from its center."""
    ax, ay, rot = e
    return ax * ay / math.hypot(ay * math.cos(a - rot), ax * math.sin(a - rot))


@design(aspects="any", bg=LANE)
def draw(s: Canvas) -> None:
    r = s.rng(4)
    n = s.noise(9)
    place = Affine.identity() if s.landscape else Affine.frame((0, s.h), deg=-90)
    w, h = max(s.w, s.h), min(s.w, s.h)  # the frame's size
    c = place.inverse()(s.pick(landscape=(0.3125, 0.574), portrait=(0.55, 0.62)))
    limb = max(c.x + LIMB_GAP, w - LIMB_MARGIN)
    fade0, fade1 = limb - FADE[0], limb - FADE[1]

    def edge(e: Ellipse, amp: float, a: float, z: float) -> float:
        """Lobed boundary: an ellipse with fBm wobble, periodic in angle."""
        return ellipse_r(e, a) * (1 + amp * n.fbm(math.cos(a) * 1.1 + z, math.sin(a) * 1.1 + z, 2))

    def pen(a: float) -> float:
        return edge(PEN, 0.5, a, 5)

    def umb(a: float) -> float:
        return edge(UMB, 0.3, a, 0)

    # Granulation: Poisson seeds in warped space, mapped back to the frame through the spot's radial
    # stretch (in units of the penumbra ellipse) and then the limb's foreshortening.
    seeds = poisson_disk(Rect(-80, -80, w + 160, h + 160), 21, r)
    vor = Voronoi(seeds)
    d = vor.vertices - c
    base = np.array([ellipse_r(PEN, a) for a in np.arctan2(d[:, 1], d[:, 0])])
    table = np.linspace(0, 30, 6000)
    warp = table * (1 + STRETCH * np.exp(-np.maximum(table - 1, 0) / FALLOFF))
    rho = np.hypot(d[:, 0], d[:, 1]) / base
    d *= (np.interp(rho, warp, table) / np.maximum(rho, 1e-9))[:, None]
    verts = d + c
    x0 = limb - LIMB_R
    past = np.maximum(verts[:, 0] - x0, 0)
    verts[:, 0] = np.where(
        past > 0, x0 + LIMB_R * np.sin(np.minimum(past / LIMB_R, math.pi / 2)), verts[:, 0]
    )

    pore_c = c + PORE
    with s.group(transform=place):
        # granules are clipped to the penumbra outline so they hug it without a gap
        rim = [polar(c, pen(a), rad=a) for a in np.linspace(0, math.tau, 240, endpoint=False)]
        moat = Polygon(rim).buffer(3)
        # whole-unit vertices keep the texture small; the rounding stroke hides the half unit
        gran = [P(0) for _ in GRAN]
        for reg in vor.point_region:
            region = vor.regions[reg]
            if not region or -1 in region:
                continue
            poly = verts[region]
            cx, cy = poly.mean(0)
            if not (-40 < cx < fade1 + 60 and -40 < cy < h + 40):
                continue
            a = math.atan2(cy - c.y, cx - c.x)
            if math.hypot(cx - c.x, cy - c.y) < pen(a) - 6:
                continue
            if math.hypot(cx - pore_c.x, cy - pore_c.y) < PORE_R + 12:
                continue
            fade = 1 - smoothstep(fade0, fade1, cx + 40 * n.fbm(cy / 260, 3.1, 2))
            cell = Polygon(poly)
            if math.hypot(cx - c.x, cy - c.y) < pen(a) + 60:
                cell = cell.difference(moat)
            cell = cell.buffer(-2.4, join_style="mitre")
            if cell.is_empty or cell.geom_type != "Polygon" or cell.area < 12:
                continue
            v = (0.5 + 0.2 * n.fbm(cx / 300, cy / 300, 2) + r.gauss(0, 0.12)) * fade
            if v < 0.03:
                continue
            gran[GRAN.rung(v)].shape(cell)
        for tone, path in zip(GRAN, gran, strict=True):
            # a round-joined stroke of the fill color rounds the corners without extra vertices
            s.path(path, fill=tone, stroke=tone, stroke_width=2.2, stroke_linejoin="round")

        # Penumbra: straight radial filaments with dark gaps, all ending on the same lobed
        # boundary. Secondary filaments start part-way out to fill the widening ring.
        s.fill(P().poly(rim, closed=True), FLOOR)
        grains = P()
        t = np.linspace(0, 1, 11)
        with s.buckets(FIL, "fill") as fil:
            for k in range(FILAMENTS):
                a = (k + r.uniform(-0.3, 0.3)) / FILAMENTS * math.tau
                r_in, r_out = umb(a) - 4, pen(a) + r.uniform(-2, 2)
                primary = k % 5 < 3
                start = r_in if primary else r_in + (r_out - r_in) * r.uniform(0.3, 0.55)
                w0 = r.uniform(2.2, 3.0)
                spine = c + np.outer(start + (r_out - start) * t, (math.cos(a), math.sin(a)))
                width = w0 * (1 - smoothstep(0.75, 1.0, t) * 0.45) * np.minimum(1, 0.45 + t * 6)
                fil[r.choices(range(len(FIL)), FIL_WEIGHTS)[0]].poly(
                    ribbon(spine, width), closed=True
                )
                if primary and r.random() < 0.3:
                    # a bright penumbral grain at the filament's inner head
                    head = Affine.frame(polar(c, r_in + 8, rad=a), rad=a)
                    grains.spline(head.apply(GRAIN), closed=True)
        s.fill(grains, ACCENT)

        s.fill(P().spline([polar(c, umb(a), rad=a) for a in RING], closed=True), CORE)

        # Light bridge: a thin, slightly bowed tongue across the umbra, widening where it meets
        # the penumbra.
        rb = math.radians(BRIDGE)
        e0, e1 = umb(rb + math.pi) + 6, umb(rb) + 6
        u = np.linspace(0, 1, 25)
        spine = Affine.frame(c, deg=BRIDGE).apply(
            np.column_stack([-e0 + (e0 + e1) * u, 5 * np.sin(math.pi * u)])
        )
        width = 2 * (2.6 + 4 * np.abs(2 * u - 1) ** 3)
        s.fill(P().spline(ribbon(spine, width), closed=True), ACCENT_6)

        wobble = [1 + 0.2 * n(math.cos(a) + 9, math.sin(a)) for a in RING[::4]]
        pore = [polar(pore_c, PORE_R * k, rad=a) for a, k in zip(RING[::4], wobble, strict=True)]
        s.fill(P().spline(pore, closed=True), CORE)
