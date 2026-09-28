"""A Nomai conversation on a stone wall: log-spiral lines of jagged script branching off one another, and a translator's trace lighting one reply."""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import LineString

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    BG_ALT,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Rng,
    design,
    smoothstep,
)
from walldye.field import cells, noise_grid
from walldye.geom import Affine, Polyline
from walldye.pixel import dither, grid_runs

type Pts = NDArray[np.float64]

# Geometry follows Mobius' spiral generator as reimplemented by New Horizons
# (NomaiTextArcBuilder and NomaiTextArcArranger): adult-profile spirals r = a*e^(b*t), replies
# placed perpendicular on parent skeleton points 3..26 of 51, random mirror, the whole
# conversation kept inside the arranger's landscape bounds box.
SEED = 54
N_SPIRALS = 7
K = 190  # px per world unit
BOUNDS = (-2.4, 2.4, -1.2, 2.8)  # NomaiTextArcArranger min/max x, min/max y
START_S = 342.8796
N_SKEL = 51
PARENT_PTS = (3, 26)
GAP = 0.36
ROOT_SIZE = 2.0  # world units between neighbouring lines
CELL = 4  # stone grain cell; a dot fills its top-left quarter
TONES = (UI_HI, UI_ALT)  # the root, then every other reply
# Stroke widths of a line's four quarters, base to tip: the others, then the reply being read.
WIDTHS = (2.0, 1.8, 1.6, 1.4)
LIT_WIDTHS = (2.1, 1.9, 1.7, 1.5)
# The translator's trace along the parent up to the branch point: fractions and tones.
TRACE = ((0.0, 0.5), (0.5, 0.8), (0.8, 1.0))
TRACE_TONES = (ACCENT_3, ACCENT_2, ACCENT)


@dataclass(frozen=True)
class Line:
    """One line of the conversation, in world units with y up."""

    local: Pts  # skeleton in its own frame, base at the origin heading +y
    ang: float  # radians counter-clockwise, local to world
    mirror: int  # -1 flips the curl
    world: Pts
    depth: int
    parent: int  # index of the line it replies to; -1 for the root
    at: int  # skeleton point on the parent it branches from
    size: float


def skeleton(r: Rng, size: float) -> Pts:
    """Adult-profile log spiral r = a*e^(b*t), 51 points uniform in t from the uncurled base to
    the tip, base at 0 heading +y.

    endS is chosen so the tip winds 1.1-1.35 turns from the base (the tight coil seen on real
    walls); the skeleton is then scaled so the base-to-coil span is `size` world units.
    """
    a, b = 0.5, r.uniform(0.2, 0.3)
    c = (a / b) * math.sqrt(1 + b * b)
    t0 = math.log(1 + START_S / c) / b
    t1 = t0 - 2 * math.pi * r.uniform(1.1, 1.35)
    ts = np.linspace(t0, t1, N_SKEL)
    rr = a * np.exp(b * ts)
    pts = np.stack([rr * np.cos(ts), rr * np.sin(ts)], 1)
    pts -= pts[0]
    d = pts[1] - pts[0]
    pts = Affine.rotate(rad=math.pi / 2 - math.atan2(d[1], d[0])).apply(pts)
    return pts * size / np.ptp(pts, 0).max()


def placement(origin: Pts | tuple[float, float], ang: float, mirror: int) -> Affine:
    """Mirror the local x axis, turn by `ang` radians counter-clockwise, move to `origin`."""
    turn = Affine.rotate(rad=ang) @ Affine.scale(mirror, 1)
    return Affine.translate(origin[0], origin[1]) @ turn


def inside(pts: Pts) -> bool:
    x0, x1, y0, y1 = BOUNDS
    lo, hi = pts.min(0), pts.max(0)
    return bool(lo[0] > x0 and hi[0] < x1 and lo[1] > y0 and hi[1] < y1)


def clashes(pts: Pts, lines: list[Line], parent: int) -> bool:
    """The new line, less its base where it meets the parent, runs too close to another line."""
    line = LineString(pts[4:])
    near = any(line.distance(LineString(n.world)) < GAP for k, n in enumerate(lines) if k != parent)
    return near or bool(line.distance(LineString(lines[parent].world)) < GAP * 0.7)


def conversation(r: Rng) -> list[Line]:
    """The root line and up to N_SPIRALS - 1 replies, two levels deep, placed by rejection."""
    local = skeleton(r, ROOT_SIZE)
    ang, mirror = math.radians(r.uniform(-60, 60)), r.choice([-1, 1])
    world = placement((0.0, 0.0), ang, mirror).apply(local)
    lines = [Line(local, ang, mirror, world, 0, -1, -1, float(np.ptp(local, 0).max()))]
    tries = 0
    while len(lines) < N_SPIRALS and tries < 400:
        tries += 1
        pi = r.choice([k for k, n in enumerate(lines) if n.depth < 2])
        parent = lines[pi]
        taken = {n.at for n in lines if n.parent == pi}
        i = r.randint(*PARENT_PTS)
        if any(abs(i - j) < 4 for j in taken):
            continue
        # PlaceOnParentPoint: the reply's 'up' is the parent's tangent turned +90deg in the
        # parent's own frame, which is always the convex side of the parent's curl
        tl = parent.local[min(i + 1, N_SKEL - 1)] - parent.local[i - 1]
        up_local = np.array([[-tl[1], tl[0]]]) / math.hypot(tl[0], tl[1])
        up = placement((0.0, 0.0), parent.ang, parent.mirror).apply(up_local)[0]
        ang = math.atan2(up[1], up[0]) - math.pi / 2
        local = skeleton(r, parent.size * r.uniform(0.55, 0.75))
        mirror = r.choice([-1, 1])
        world = placement(parent.world[i], ang, mirror).apply(local)
        if not inside(world) or clashes(world, lines, pi):
            continue
        size = float(np.ptp(local, 0).max())
        lines.append(Line(local, ang, mirror, world, parent.depth + 1, pi, i, size))
    return lines


def glyph_line(r: Rng, px: Pts, w0: float = 13.0, w1: float = 4.0) -> tuple[Pts, Pts]:
    """Lightning-like crinkle along a spiral: irregular steps whose amplitude drifts along the
    stroke, with rare larger kinks, in a band tapering from w0 at the base to w1 at the tip.

    Returns the points and each one's fraction of the way along.
    """
    spine = Polyline(px)
    total = spine.length
    # three draws, two used: keeps the stream the piece was tuned on
    phases = [r.uniform(0, 2 * math.pi) for _ in range(3)]
    ds, offs = [0.0], [0.0]
    d = off = 0.0
    while d < total:
        f = d / total
        half = (w0 + (w1 - w0) * f) / 2
        env = 0.55 + 0.25 * math.sin(d / 23 + phases[0]) + 0.2 * math.sin(d / 9.5 + phases[1])
        d += r.uniform(1.0, 3.2) * (1 - 0.4 * f)
        # random walk with pull back to the baseline, occasionally flipping hard for a kink
        off = 0.3 * off + r.gauss(0, 0.8) * half * env
        if r.random() < 0.035:
            off = math.copysign(half * r.uniform(1.1, 1.5), -off or 1)
        off = max(-2 * half, min(2 * half, off))
        ds.append(d)
        offs.append(off)
    u = np.minimum(np.array(ds), total)
    # the normal of a 2 px chord, smoother than the segment direction at skeleton joints
    t = spine.at(np.minimum(u + 1, total)) - spine.at(np.maximum(u - 1, 0))
    n = np.hypot(t[:, 0], t[:, 1])
    n[n == 0] = 1
    normal = np.stack([-t[:, 1], t[:, 0]], 1) / n[:, None]
    return spine.at(u) + np.array(offs)[:, None] * normal, u / total


def quarters(pts: Pts, fr: Pts) -> list[Pts]:
    """A glyph line cut into four slightly overlapping pieces, base first."""
    return [pts[(fr >= k / 4 - 0.003) & (fr <= (k + 1) / 4 + 0.003)] for k in range(4)]


def stone(s: Canvas, c: tuple[float, float], rx: float, ry: float) -> None:
    """Dithered pitting in an elliptical patch of wall around `c`, rougher where the grain is."""
    xs, ys = cells(s.inset(0), CELL)
    rows, cols = xs.shape
    grain = noise_grid(cols, rows, 30, s.np_rng(7), octaves=3)
    fade = smoothstep(1, 0, np.hypot((xs - c[0]) / rx, (ys - c[1]) / ry))
    grid = dither(0.14 * fade * (1 + 0.8 * grain), 2, method="bluenoise", rng=s.np_rng(3))
    # 2 px dots on the 4 px grid: stone pitting rather than solid blocks
    dots = np.zeros((2 * rows, 2 * cols), dtype=np.int64)
    dots[::2, ::2] = grid
    grid_runs(s, dots, [None, BG_ALT], CELL // 2)


@design(aspects="any")
def draw(s: Canvas) -> None:
    lines = conversation(s.rng(SEED))
    world = np.concatenate([n.world for n in lines])
    lo, hi = world.min(0), world.max(0)
    # the conversation's box centred a little right of centre, or centred on a portrait screen
    c = s.pick(landscape=(0.53125, 14 / 27), portrait=(0.5, 0.5))
    mid = (lo + hi) / 2
    to_px = Affine.translate(c.x, c.y) @ Affine.scale(K, -K) @ Affine.translate(-mid[0], -mid[1])
    px = [to_px.apply(n.world) for n in lines]
    span = (hi - lo) * K
    stone(s, c, span[0] * 0.72, span[1] * 0.8)

    # the reply being read: the leaf whose tip sits highest
    leaves = [k for k, n in enumerate(lines) if n.depth == 2] or [
        k for k, n in enumerate(lines) if n.depth == 1
    ]
    lit = max(leaves, key=lambda k: float(lines[k].world[-1, 1]))
    r = s.rng(SEED + 1)
    glyphs = [glyph_line(r, p) for p in px]

    rest = [[P() for _ in WIDTHS] for _ in TONES]
    for k, n in enumerate(lines):
        if k != lit:
            for d, seg in zip(rest[min(n.depth, 1)], quarters(*glyphs[k]), strict=True):
                d.poly(seg)
    for tone, paths in zip(TONES, rest, strict=True):
        for d, w in zip(paths, WIDTHS, strict=True):
            s.stroke(d, tone, w, join="round", cap="round")

    # the translator traces the parent up to the branch point, then the reply being read
    parent, at = lines[lit].parent, lines[lit].at
    frac = Polyline(px[parent][: at + 1]).length / Polyline(px[parent]).length
    pts, fr = glyphs[parent]
    for (a, b), tone in zip(TRACE, TRACE_TONES, strict=True):
        seg = pts[(fr >= a * frac) & (fr <= b * frac + 0.004)]
        s.stroke(P().poly(seg), tone, 2.0, join="round", cap="round")
    for seg, w in zip(quarters(*glyphs[lit]), LIT_WIDTHS, strict=True):
        s.stroke(P().poly(seg), ACCENT, w, join="round", cap="round")
