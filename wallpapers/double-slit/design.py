"""Young's double-slit experiment: crossing wavelets bead along the antinodal lines above a strip of stepped fringe bars, brightest at the centre."""

import itertools
import math
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    ACCENT_6,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    Buckets,
    Canvas,
    P,
    design,
    mix,
    polar,
    smoothstep,
)
from walldye.geom import parts

SPACING = 52  # fringe pitch on the strip
RATIO = 4.6  # slit pitch / slit width: how fast the sinc envelope kills the orders
SEP = 140  # slit pitch
DROP = 410  # barrier to strip
# wavelength that makes the far-field nodal lines land on the strip's dark gaps
WAVE = SPACING * SEP / DROP
SHARP = 4  # fringe profile cos^SHARP: sharper than cos^2 so dark bands read as gaps
REL = (0.1, 0.35, 0.62, 0.86)  # tier cut levels as a fraction of each fringe's own peak
LOBES = (4, 8, 12, 16)  # outermost visible order of each envelope lobe
FAN = 58  # degrees either side of straight down that each slit's wavelets span
REACH = DROP - 60  # how far below the barrier the wavelets run
BAR, GAP = 250, 5  # barrier half-length; slit width as drawn
# Fringe tiers from dim to bright, so a fringe's narrower, taller tiers land on top.
FRINGE = (BG_ALT, UI, UI_ALT, ACCENT_6, ACCENT_5, ACCENT_4, ACCENT_3, ACCENT_1, ACCENT)
CENTRE, SIDE = (4, 6, 7, 8), (3, 4, 5, 6)  # FRINGE index per tier: order 0, orders ±1
RIPPLE = (mix(BG, BG_ALT, 0.5), BG_ALT, mix(BG_ALT, UI, 0.5), UI)


def envelope(x: float) -> float:
    """Single-slit intensity at `x` from the strip's centre, 1 at the centre."""
    v = math.pi * x / SPACING / RATIO
    return 1.0 if v == 0 else (math.sin(v) / v) ** 2


def ripple(v: float, floor: float, lift: float) -> int | None:
    """RIPPLE index for a fade value `v` in [0, 1]; None at or below `floor`."""
    return min(len(RIPPLE) - 1, int(v * len(RIPPLE) - lift)) if v > floor else None


def graded(b: Buckets, pts: NDArray[np.floating], tones: Sequence[int | None]) -> None:
    """Draw a polyline as runs of equal RIPPLE index, each reaching the next run's first
    vertex; single-vertex runs and None runs are left out."""
    i = 0
    for tone, run in itertools.groupby(tones):
        n = len(list(run))
        if tone is not None and n > 1:
            b[tone].poly(pts[i : i + n + 1])
        i += n


@design(aspects="any")
def draw(s: Canvas) -> None:
    cx, cy = s.pick(landscape=(0.5, 710 / 1080), portrait=(0.5, 0.56))  # the strip's centre
    top = cy - DROP  # the barrier
    slits = (cx - SEP / 2, cx + SEP / 2)
    fan = math.radians(FAN)

    def fade(
        pts: NDArray[np.float64], sources: Sequence[float], soft: float
    ) -> NDArray[np.float64]:
        """1 near the slits, easing to 0 at the fan's edges and at REACH below the barrier."""
        dx = np.subtract.outer(pts[:, 0], np.asarray(sources))
        a = np.abs(np.arctan2(dx, (pts[:, 1] - top)[:, None])).max(axis=1)
        return smoothstep(fan, fan * soft, a) * smoothstep(REACH, REACH * soft, pts[:, 1] - top)

    with s.buckets(RIPPLE, "stroke", stroke_width=1.3, stroke_linecap="round") as lines:
        # plane wave above the barrier, fading toward its ends
        xs = cx - 240 + 8 * np.arange(61)
        for i in range(1, 5):
            pts = np.column_stack([xs, np.full_like(xs, top - WAVE * i)])
            v = (1 - i * 0.12) * smoothstep(240, 120, np.abs(xs - cx))
            graded(lines, pts, [ripple(t, 0.1, 0.4) for t in v])
        # faint wavelet arcs in a fan below each slit
        for sx in slits:
            for n in range(1, int(REACH / WAVE) + 1):
                a = np.linspace(-fan, fan, 13 + n * 6)
                pts = np.column_stack([sx + n * WAVE * np.sin(a), top + n * WAVE * np.cos(a)])
                graded(lines, pts, [ripple(t, 0.1, 0.4) for t in 0.45 * fade(pts, [sx], 0.3)])

    # Where both slits' crests overlap, beads chain along the antinodal lines toward the
    # bright fringes.
    crests = []
    for sx in slits:
        o = Point(sx, top)
        wedge = Polygon(
            [(sx, top), *(polar((sx, top), 2 * REACH, bearing=180 - d) for d in (-FAN, 0, FAN))]
        )
        rings = [
            o.buffer(n * WAVE + 2.6, 64).difference(o.buffer(n * WAVE - 2.6, 64))
            for n in range(1, int(REACH / WAVE) + 1)
        ]
        crests.append(unary_union(rings).intersection(wedge))
    beads = [g for g in parts(crests[0].intersection(crests[1])) if g.area > 2]
    v = fade(np.array([g.centroid.coords[0] for g in beads]), slits, 0.4)
    with s.buckets(RIPPLE, "fill") as fills:
        for g, t in zip(beads, v):
            if (tone := ripple(t, 0.12, 0.2)) is not None:
                fills[tone].shape(g)

    edges = [cx - BAR, *(x + d for x in slits for d in (-GAP / 2, GAP / 2)), cx + BAR]
    bar = P()
    for x0, x1 in zip(edges[::2], edges[1::2]):
        bar.rect(x0, top - 3, x1 - x0, 6)
    s.fill(bar, UI_ALT)

    # The strip ends on the last lobe that fits, so each edge closes on an envelope zero.
    last = max(k for k in LOBES if k * SPACING <= 0.4 * s.w)
    with s.buckets(FRINGE, "fill") as fringes:
        for k in range(-last, last + 1):
            peak = envelope(k * SPACING) ** 0.4  # display gamma so the faint orders survive
            if peak < 0.12:
                continue
            x, h = cx + k * SPACING, 40 + 110 * peak
            # every fringe keeps at least two tiers; brighter ones gain more
            for j in range(min(4, 2 + int(peak / 0.4))):
                w = 2 * SPACING / math.pi * math.acos(REL[j] ** (1 / SHARP)) * (0.4 + 0.6 * peak)
                hj = h * (0.7 + 0.1 * j)
                if k == 0:
                    t = CENTRE[j]
                elif abs(k) == 1:
                    t = SIDE[j]
                else:  # the UI ramp tops out at UI_ALT, so only the middle glows
                    t = min(j, 1 + int(peak * 2.5))
                fringes[t].rect(x - w / 2, cy - hj / 2, w, hj)
