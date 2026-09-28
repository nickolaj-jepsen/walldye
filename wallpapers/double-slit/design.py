"""Young's double slit seen side on: crest arcs from two slits cross in beads along the bright directions, and a comb of lines on the screen traces the fringes under the single-slit envelope."""

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
    ACCENT_4,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Buckets,
    Canvas,
    P,
    by_regime,
    design,
    mix,
    smoothstep,
)
from walldye.geom import Affine, parts

WAVE = 24  # wavelength: the spacing of the crest arcs
SLIT = 104  # slit width
SEP = 4 * SLIT  # slit pitch; every fourth order falls on an envelope zero and goes missing
DROP = 820  # barrier to screen
SPAN = 426  # half the screen's length: it ends on the envelope's second zero
RINGS = int(math.hypot(DROP, SPAN + SEP) / WAVE)  # crests from each slit that reach the screen
HALF = 4  # half the width of a crest band where two crests overlap
ARCS = (BG_ALT, mix(BG_ALT, UI, 0.5))
# a step lower on paper, where UI_HI beads would outweigh the comb
BEADS = (
    by_regime(BG_ALT, mix(BG, BG_ALT, 0.6)),
    by_regime(UI, BG_ALT),
    by_regime(UI_ALT, UI),
    by_regime(UI_HI, UI_ALT),
)
COMB = (UI, ACCENT_4, ACCENT_1, ACCENT)
CUTS = (0.3, 0.6, 0.85)  # COMB thresholds on the square root of the intensity
PITCH, PEAK = 4, 190  # comb line pitch; the central fringe's length


def envelope(sin: NDArray[np.float64]) -> NDArray[np.float64]:
    """Single-slit intensity for the sine of the angle off the axis, 1 on it."""
    return np.sinc(SLIT * sin / WAVE) ** 2


def intensity(v: NDArray[np.float64]) -> NDArray[np.float64]:
    """Two-slit intensity at height `v` on the screen: the exact path difference sets the
    fringes, the single-slit envelope their brightness."""
    diff = np.hypot(DROP, v + SEP / 2) - np.hypot(DROP, v - SEP / 2)
    return np.cos(math.pi * diff / WAVE) ** 2 * envelope(v / np.hypot(DROP, v))


def graded(b: Buckets, pts: NDArray[np.floating], tones: Sequence[int | None]) -> None:
    """Draw a polyline as runs of equal tone index, each reaching the next run's first
    vertex; single-vertex runs and None runs are left out."""
    i = 0
    for tone, run in itertools.groupby(tones):
        n = len(list(run))
        if tone is not None and n > 1:
            b[tone].poly(pts[i : i + n + 1])
        i += n


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Local frame: u runs from the barrier toward the screen, v along the screen; landscape
    # screens send the light rightward, portrait ones downward. `o` is the screen's centre.
    o = s.pick(landscape=(0.66, 0.5), portrait=(0.5, 0.62))
    if s.landscape:
        m = Affine(1, 0, 0, 1, o.x - DROP, o.y)
    else:
        m = Affine(0, 1, 1, 0, o.x, o.y - DROP)
    slits = (-SEP / 2, SEP / 2)
    v0 = SEP / 2 + SLIT / 2 + 30
    lit = Polygon([(0, -v0), (DROP, -SPAN), (DROP, SPAN), (0, v0)])

    def inside(pts: NDArray[np.float64]) -> NDArray[np.float64]:
        """How far into the lit trapezoid each point sits, eased to 1 over 70 units."""
        u, v = pts[:, 0], np.abs(pts[:, 1])
        edge = v0 + (SPAN - v0) * u / DROP
        slope = math.hypot(1, (SPAN - v0) / DROP)
        ok = (u >= 0) & (u <= DROP)
        return np.where(ok, smoothstep(0, 70, (edge - v) / slope), 0.0)

    with s.group(transform=m):
        # plane wave arriving at the barrier, its crests fading at the ends and further back
        vs = np.linspace(-v0 - 40, v0 + 40, 60)
        with s.buckets(ARCS, "stroke", stroke_width=1.2) as waves:
            for n in range(1, 7):
                pts = np.column_stack([np.full_like(vs, -n * WAVE), vs])
                f = smoothstep(v0 + 40, v0 - 80, np.abs(vs)) * (1.15 - 0.15 * n)
                graded(waves, pts, [None if t < 0.2 else int(t > 0.6) for t in f])

        # crest arcs from each slit, clipped to the lit region
        with s.buckets(ARCS, "stroke", stroke_width=1.2, stroke_linecap="round") as arcs:
            for sv in slits:
                for n in range(1, RINGS + 1):
                    r = n * WAVE
                    a = np.linspace(-math.pi / 2, math.pi / 2, 24 + 4 * n)
                    pts = np.column_stack([r * np.cos(a), sv + r * np.sin(a)])
                    f = inside(pts)
                    graded(arcs, pts, [None if t < 0.05 else int(t > 0.5) for t in f])

        # where crests from both slits overlap: beads along the bright directions
        crests = []
        for sv in slits:
            o2 = Point(0, sv)
            rings = [
                o2.buffer(n * WAVE + HALF, 64).difference(o2.buffer(n * WAVE - HALF, 64))
                for n in range(1, RINGS + 1)
            ]
            crests.append(unary_union(rings).intersection(lit))
        beads = [g for g in parts(crests[0].intersection(crests[1])) if g.area > 2]
        c = np.array([g.centroid.coords[0] for g in beads])
        # far-field brightness in the bead's direction as seen from between the slits
        glow = envelope(c[:, 1] / np.hypot(c[:, 0], c[:, 1])) ** 0.5 * inside(c)
        with s.buckets(BEADS, "fill") as fills:
            for g, t in zip(beads, glow):
                if t > 0.08:
                    fills[min(3, int(t * 4))].shape(g)

        # the barrier, cut by two slits
        bar = P()
        edges = [-v0 - 60, *(sv + d for sv in slits for d in (-SLIT / 2, SLIT / 2)), v0 + 60]
        for a0, a1 in zip(edges[::2], edges[1::2]):
            bar.rect(-4, a0, 8, a1 - a0)
        s.fill(bar, UI_ALT)

        # the screen, and the fringes it records as a comb of lines whose length and tone
        # follow the intensity, under the dashed single-slit envelope
        s.fill(P().rect(DROP - 1.5, -SPAN - 10, 3, 2 * SPAN + 20), UI_ALT)
        n = int(SPAN // PITCH)
        v = PITCH * np.arange(-n, n + 1, dtype=float)
        i = intensity(v)
        with s.buckets(COMB, "stroke", stroke_width=PITCH / 2) as comb:
            for vv, ii in zip(v, i):
                ln = PEAK * ii
                if ln >= 2:
                    comb[int(np.searchsorted(CUTS, ii**0.5))].M(DROP + 6, vv).H(DROP + 6 + ln)
        v = np.linspace(-SPAN, SPAN, 900)
        env = envelope(v / np.hypot(DROP, v))
        s.stroke(P().poly(np.column_stack([DROP + 6 + PEAK * env, v])), UI, 1.2, dash=(4, 5))
