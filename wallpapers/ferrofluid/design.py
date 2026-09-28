"""A ferrofluid crown under a magnet: tapered spikes on a hex lattice rise from a low dome, rim-lit from the right above a fading reflection."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_4,
    ACCENT_7,
    ACCENT_8,
    BG,
    BG_ALT,
    BG_DEEP,
    BLACK,
    UI,
    UI_ALT,
    Canvas,
    P,
    Rng,
    by_regime,
    clamp,
    design,
    ladder,
)
from walldye.field import falloff

type Pts = NDArray[np.float64]
type Spike = tuple[float, float, float, float]

R, A = 330, 64  # crown radius, lattice pitch
ROW = A * math.sqrt(3) / 2  # lattice row spacing
SQ = 0.14  # depth squash: how far we look down on the plate
DOME, SPIKE = 60, 240  # dome and tallest spike heights
TS = np.linspace(0, 1, 25)  # samples up a spike, base to tip
RIM = ladder((BG, ACCENT_4, ACCENT), 12)[5:]  # the upper accent ladder, for the lit right third
# Light themes turn BLACK paler than BG, so there the fluid sits a UI_ALT step towards FG
# instead, and its unlit rims step back towards BG to read as light catching an edge.
FLUID = by_regime(BLACK, UI_ALT)
MIRROR = by_regime(BG_DEEP, BG_ALT)
DIM = by_regime(BG_ALT, UI)  # the far flank of every spike, and right flanks turned away
HALF = by_regime(UI, BG_ALT)  # right flanks half turned to the light


def dome(r: Pts) -> Pts:
    """Height of the dome body at distances `r` from the crown's axis, 0 at the rim and beyond."""
    return DOME * falloff((r / R) ** 2, 1, 0.6)


def profile(t: Pts) -> Pts:
    """Half-width of a spike (in base half-widths) at height fraction `t`: a near-conical flank
    with a small fillet flaring into the saddle between spikes."""
    return (1 - t) ** 1.4 + 0.32 * falloff(t, 0.16, 2)


def lattice(rng: Rng) -> list[Spike]:
    """Spikes as (u, v, foot, height), back to front: the lattice point around the crown's axis,
    the dome's height there, and the spike's own height. The front shoulder stays low so the
    dome reads. Every lattice point draws its jitter, kept or not."""
    rows = int(R / ROW) + 1
    kept: list[Spike] = []
    for j in range(-rows, rows + 1):
        for i in range(-rows - 2, rows + 3):
            u, v = (i + (j % 2) / 2) * A, j * ROW
            r = math.hypot(u, v)
            h = (SPIKE * falloff((r / R) ** 2, 1, 1.6) + 16) * (1 + rng.uniform(-0.08, 0.08))
            if r < R * 0.8 and not (v > R * 0.3 and r > R * 0.5):
                kept.append((u, v, r, h))
    kept.sort(key=lambda p: p[1])
    feet = dome(np.array([r for _, _, r, _ in kept])).tolist()
    return [(u, v, foot, h) for (u, v, _, h), foot in zip(kept, feet, strict=True)]


def mound(flip: int) -> Pts:
    """Outline of the dome body around its foot at (0, 0): the crest as seen from above, then
    the front half of the rim. flip=-1 mirrors it into its reflection."""
    u = R * (np.arange(201) / 100 - 1)
    v = R * np.arange(-60, 61) / 60
    r = np.hypot(u[:, None], v[None, :])
    y = np.where(r <= R, v[None, :] * SQ - flip * dome(r), np.nan)
    crest = np.nanmin(y, axis=1) if flip > 0 else np.nanmax(y, axis=1)
    a = np.pi * np.arange(61) / 60
    rim = np.column_stack((R * np.cos(a), flip * R * SQ * np.sin(a)))
    return np.vstack((np.column_stack((u, crest)), rim[::-1]))


def spike(u: float, v: float, foot: float, h: float, flip: int) -> tuple[Pts, Pts, Pts]:
    """One spike standing `foot` up the dome at lattice point (u, v): its left and right flanks,
    base to tip, and its outline closed round the front of its base. flip=-1 hangs it into the
    reflection."""
    bx, by = u, v * SQ - flip * foot
    rb = A * 0.5
    lean = 0.15 * h * u / R  # spikes stand normal to the mound, so outer ones splay a little
    x, y, half = bx + lean * TS, by - flip * h * TS, rb * profile(TS)
    left, right = np.column_stack((x - half, y)), np.column_stack((x + half, y))
    a = np.pi * np.arange(17) / 16
    front = np.column_stack((bx + 1.32 * rb * np.cos(a), by + 1.32 * rb * SQ * np.sin(a)))
    return left, right, np.vstack((left, right[::-1], front))


def shifted(pts: Pts, dx: Pts | float) -> Pts:
    """`pts` moved right by `dx` (one value per point, or one for all)."""
    return pts + np.column_stack((np.broadcast_to(dx, len(pts)), np.zeros(len(pts))))


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of centre on a landscape screen, leaving the left for windows; centred and a little
    # low on a portrait one, under the clock
    c = s.pick(landscape=(1180 / 1920, 730 / 1080), portrait=(0.5, 0.62))
    spikes = lattice(s.rng(4))

    # reflection: only the mound and the tallest central spikes, fading out quickly
    s.fill(P().poly(c + mound(-1), closed=True), MIRROR)
    tall = sorted(spikes, key=lambda p: -p[3])[:7]
    for u, v, foot, h in sorted(tall, key=lambda p: p[1]):
        _, right, body = spike(u, v, foot, h * 0.45, -1)
        s.fill(P().poly(c + body, closed=True), MIRROR)
        rim = np.vstack((right, shifted(right, -2.5)[::-1]))
        s.fill(P().poly(c + rim, closed=True), ACCENT_7 if u > 0 else ACCENT_8)
    lip_y = c.y + R * SQ
    fade = s.linear_gradient([(0, BG, 0.4), (1, BG, 1)], (0, lip_y), (0, lip_y + 130))
    s.fill(P().rect(0, c.y, s.w, s.h - c.y), fade)
    # the surface line fades out at both ends, stopping short of the canvas edges
    x0, x1 = max(c.x - 760, 40), min(c.x + 700, s.w - 40)
    line = s.linear_gradient([(0, BG), (0.3, UI), (0.7, UI), (1, BG)], (x0, 0), (x1, 0))
    s.stroke(P().M(x0, c.y).H(x1), line, 1.4)

    # dome body with a soft specular band on its upper right, glimpsed between the spikes
    body = P().poly(c + mound(1), closed=True)
    s.fill(body, FLUID)
    with s.clip() as dome_clip:
        dome_clip.add(body)
    spec = s.radial_gradient(
        [(0, BG_ALT, 0.9), (0.6, BG, 0.4), (1, BG, 0)], (0.5, 0.5), 0.5, units="bbox"
    )
    band = P().ellipse(c + (0.42 * R, -0.3 * DOME), 0.34 * R, 0.1 * R)
    s.path(band, fill=spec, clip_path=dome_clip.ref)

    for u, v, foot, h in spikes:
        left, right, outline = spike(u, v, foot, h, 1)
        s.fill(P().poly(c + outline, closed=True), FLUID)
        lit = clamp(0.5 + 0.8 * u / R + 0.4 * h / SPIKE - 0.35)
        w = (1.5 + 2.7 * lit) * np.sin(np.pi * np.minimum(1, TS * 1.15)) ** 0.7
        rim = np.vstack((right, shifted(right, -w * (0.4 + 0.6 * (1 - TS)))[::-1]))
        # the accent ladder is reserved for the lit right third; the rest of the crown catches
        # only HALF or DIM
        if lit > 0.45:
            tone = RIM[round((lit - 0.45) / 0.55 * (len(RIM) - 1))]
        else:
            tone = HALF if lit > 0.25 else DIM
        s.fill(P().poly(c + rim, closed=True), tone)
        s.fill(P().poly(c + np.vstack((left, shifted(left, 0.6 * w)[::-1])), closed=True), DIM)

    # glossy lip along the lit right third of the puddle edge
    a = np.radians(-12 + 72 * np.arange(41) / 40)
    lip = c + np.column_stack((R * np.cos(a), R * SQ * np.sin(a)))
    s.stroke(P().poly(lip), UI, 1.5, cap="round")
