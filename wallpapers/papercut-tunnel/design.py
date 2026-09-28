"""A tunnel book: flat paper sheets with hand-cut holes stepping back to a lit backing, each casting an offset shadow on the sheet behind."""

import math
from collections.abc import Callable
from itertools import pairwise

import numpy as np
import shapely
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_2,
    ACCENT_HI,
    BG_DEEP,
    BLACK,
    MUTED,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Rng,
    Vec,
    by_regime,
    clamp,
    design,
    mix,
    ramp,
    smoothstep,
)
from walldye.geom import Affine, parts

type Arr = NDArray[np.float64]
type Radius = Callable[[Arr], Arr]

DRIFT = Vec(-0.8, 0.6)  # direction from the focus back out towards the front sheet
CORE = (880, 610, 420, 290, 195, 128, 82)  # hole radii, front sheet first, as s.rng(8) cuts them
EXTRA = (1270, 1830)  # sheets added in front, from s.rng(9), while a corner is left uncovered
REACH = 1.45  # a corner is uncovered when it lies more than this many radii from the front hole
FLAT = 0.06  # a long rim run bowing out by less than this share of its chord reads as a seam
# shifts of the focus tried, nearest first, until every rim meets the frame as a deliberate crop
NUDGES = sorted(
    ((dx, dy) for dx in range(-120, 121, 20) for dy in range(-120, 121, 20)),
    key=lambda d: math.hypot(*d),
)
LIGHT = math.pi / 4  # the cut edges facing the light sit on the lower right of each hole
AROUND = np.linspace(0, math.tau, 180, endpoint=False)
EDGE = np.linspace(LIGHT - math.pi / 2, LIGHT + math.pi / 2, 241)  # the lit half of a rim
EDGE_W = 2.2 * smoothstep(0, 0.45, np.cos(EDGE - LIGHT))  # constant, tapering only at the ends


def blob(r: Rng, big: float) -> Radius:
    """Polar radius function of a hole of mean radius `big`: broad lobes that fade out on small
    holes, plus a faint hand-cut waver."""
    lobe = clamp((big - 82) / 500)
    harm = [(k, big * lobe * r.uniform(0.03, 0.08), r.uniform(0, math.tau)) for k in (2, 3, 4)]
    harm += [(k, big * r.uniform(0.001, 0.004), r.uniform(0, math.tau)) for k in range(7, 14)]
    return lambda a: big + sum((amp * np.sin(k * a + ph) for k, amp, ph in harm), np.zeros_like(a))


def rim(c: Vec, rad: Radius, a: Arr, inset: float | Arr = 0.0) -> Arr:
    """The (N, 2) points of a hole's outline at angles `a`, pulled `inset` towards its centre."""
    r = rad(a) - inset
    return np.column_stack((c.x + r * np.cos(a), c.y + r * np.sin(a)))


def even_gaps(holes: list[Arr]) -> bool:
    """Every rim gap is at least 60% of that pair's mean gap, so no two rims crowd together.
    `holes` run front sheet first."""
    for outer, inner in pairwise(holes):
        d = shapely.distance(shapely.LinearRing(outer), shapely.points(inner[::2]))
        if d.min() < 0.6 * d.mean():
            return False
    return True


def cut(r: Rng, radii: list[float], centres: list[Vec], behind: list[Arr]) -> list[Radius]:
    """Radius functions for holes of `radii` around `centres` (front sheet first), in front of
    the `behind` outlines, redrawn up to 200 times until every gap is even; the last try stands
    otherwise."""
    for _ in range(199):
        rads = [blob(r, big) for big in radii]
        holes = [rim(c, rad, AROUND) for c, rad in zip(centres, rads, strict=True)]
        if even_gaps(holes + behind):
            return rads
    return [blob(r, big) for big in radii]


def straight(outline: Arr, w: float, h: float) -> bool:
    """Whether the outline crosses the w x h frame in a run that reads as a straight panel edge
    rather than a cut curve: a chord over 3/4 of the short side, bowing out by under FLAT of it.
    A hole far wider than the frame's short side cuts it that way."""
    seen = shapely.line_merge(shapely.LinearRing(outline).intersection(shapely.box(0, 0, w, h)))
    for run in parts(seen):
        pts = np.asarray(run.coords)
        chord = shapely.LineString(pts[[0, -1]])
        bow = shapely.distance(chord, shapely.points(pts)).max()
        if chord.length > 0.75 * min(w, h) and bow < FLAT * chord.length:
            return True
    return False


def framed(holes: list[Arr], w: float, h: float) -> bool:
    """Whether the hole outlines (back sheet first) meet the frame as deliberate crops: no rim
    comes within 60 units of an edge without crossing it, or crosses one by less than 25, or
    crosses the frame as a straight edge, and no sheet shows only as a sliver under about 40
    units wide, such as a corner cut off by a hole."""
    for outline in holes:
        if straight(outline, w, h):
            return False
        x, y = outline[:, 0], outline[:, 1]
        across = (y >= 0) & (y <= h), (x >= 0) & (x <= w)
        for d, span in ((x, across[0]), (w - x, across[0]), (y, across[1]), (h - y, across[1])):
            if span.any() and -25 < d[span].min() < 60:
                return False
    frame = shapely.box(0, 0, w, h)
    cover = [shapely.Polygon(p) for p in holes] + [frame]
    for inner, outer in pairwise(cover):
        seen = outer.intersection(frame).difference(inner)
        if any(part.buffer(-20).is_empty for part in parts(seen)):
            return False
    return True


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Hole shapes and their centres relative to the focus, back sheet first, the same on every
    # screen. Centres step out from the focus in proportion to each ring's width, so the drift
    # never pinches one side.
    radii = (*CORE[::-1], *EXTRA)
    offsets = [Vec(0, 0)]
    for inner, outer in pairwise(radii):
        offsets.append(offsets[-1] + DRIFT * (0.3 * (outer - inner)))
    core = len(CORE)
    shapes = cut(s.rng(8), list(CORE), offsets[core - 1 :: -1], [])[::-1]
    extra = s.rng(9)
    for o, big in zip(offsets[core:], EXTRA, strict=True):
        shapes += cut(extra, [big], [o], [rim(offsets[len(shapes) - 1], shapes[-1], AROUND)])

    def outlines(focus: Vec, drop: int) -> list[Arr]:
        """Hole outlines around `focus`, back sheet first: the core sheets, then as many extra
        ones in front as it takes to cover the canvas corners, less the `drop` frontmost extras."""
        n = core
        while n < len(radii):
            front = focus + offsets[n - 1]
            if max(abs(front - (x, y)) for x in (0, s.w) for y in (0, s.h)) <= REACH * radii[n - 1]:
                break
            n += 1
        n = max(core, n - drop)
        return [rim(focus + o, f, AROUND) for o, f in zip(offsets[:n], shapes[:n], strict=True)]

    # Every nudge with all the sheets the corners ask for, then without the front one: on
    # ultra-wide screens a hole wide enough to reach the far side cuts it as a straight edge.
    base = s.pick(landscape=(0.65625, 0.435), portrait=(0.58, 0.42))
    tries = ((base + d, drop) for drop in (0, 1) for d in NUDGES)
    focus, drop = next((t for t in tries if framed(outlines(*t), s.w, s.h)), (base, 0))
    holes = outlines(focus, drop)
    n = len(holes)

    tones = ramp(BG_DEEP, UI_ALT, n)[::-1]  # UI_ALT at the back, BG_DEEP at the front
    glow = s.radial_gradient([(0, ACCENT), (0.6, ACCENT), (1, ACCENT_1)], focus, CORE[-1] * 1.3)
    s.fill(P().rect(0, 0, s.w, s.h), glow)
    for i in range(n):
        c, shape, tone = focus + offsets[i], shapes[i], tones[i]
        sheet = P().rect(*s.inset(-40)).spline(holes[i], closed=True)
        # The shadow falls on the sheet behind, or on the backing behind the last one. Shadows
        # and lit edges pick their colour per regime, so they keep their sense on light themes.
        if i == 0:
            shade = by_regime(ACCENT_2, ACCENT_HI)
        else:
            shade = by_regime(mix(tones[i - 1], BLACK, 0.47), mix(tones[i - 1], MUTED, 0.3))
        depth = 1 - i / (n - 1)
        s.path(
            sheet,
            fill=shade,
            fill_rule="evenodd",
            transform=Affine.translate(10 - 6 * depth, 13 - 8 * depth),
        )
        s.fill(sheet, tone, rule="evenodd")
        # lit cut edge: a sliver on the side of the hole facing the light
        edge = np.vstack((rim(c, shape, EDGE), rim(c, shape, EDGE, EDGE_W)[::-1]))
        s.fill(P().poly(edge, closed=True), by_regime(mix(tone, UI_HI, 0.5), mix(tone, BLACK, 0.6)))
