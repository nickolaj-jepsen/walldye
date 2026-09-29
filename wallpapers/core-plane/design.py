"""A magnetic core memory plane drawn as tilted ring outlines on a lattice of over-and-under wires, fading out from one byte being read."""

import math

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_7,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    P,
    Path,
    Vec,
    design,
    mix,
    polar,
)
from walldye.field import Noise, runs

PITCH = 40
RX, RY = 11, 5  # core semi-axes
BYTE = 0x2A  # the byte being read, most significant bit on the left
# where an X or Y wire crosses a ±45° core: polar radius of the ellipse at 45° off its axis
CROSS = 1 / math.sqrt(0.5 / RX**2 + 0.5 / RY**2)
GAP = 2.2  # wire clearance either side of the crossing (ring stroke 2px + ~1px air)
# core outlines: tiers 0..4 fading out from the read byte, then 5 for its unset bits
RINGS = (UI_ALT, UI, mix(BG_ALT, UI, 0.5), BG_ALT, mix(BG, BG_ALT, 0.6), ACCENT_3)
SET = 6  # a set bit of the read byte, drawn on its own at a heavier weight
LEADS = (mix(BG, BG_ALT, 0.55), BG_ALT)  # bare wire; wire lifted where the plane is populated
READ = (ACCENT_7, ACCENT_3)  # the read row's X wire outside and across the byte
INHIBIT = mix(BG, BG_ALT, 0.35)


def core(d: Path, c: Vec, rot: float) -> None:
    """Append a core's outline to `d`: an ellipse centered on `c`, its long axis turned `rot`
    degrees, as two half arcs."""
    a, b = polar(c, RX, deg=rot + 180), polar(c, RX, deg=rot)
    d.M(a).A(RX, RY, rot, 0, 1, b).A(RX, RY, rot, 0, 1, a).Z()


def tier(p: Vec, focus: Vec, n: Noise, reach: float) -> int | None:
    """Tier 0..4 of the core at `p` from its noise-softened distance to `focus`, measured
    in units of `reach`, or None past the plane's fade (about 910 units)."""
    r = abs(p - focus) / reach + 70 * n.fbm(p.x / 400, p.y / 400, 2)
    k = int((r - 260) / 130)
    return None if k > 4 else max(0, k)


@design(aspects="any")
def draw(s: Canvas) -> None:
    cols, rows = s.w // PITCH, s.h // PITCH
    o = Vec(s.w % PITCH + PITCH, s.h % PITCH + PITCH) / 2  # first core; the lattice sits centered

    def at(i: float, j: float) -> Vec:
        return o + Vec(i, j) * PITCH

    # the byte sits right of center on a landscape screen, a little below center on a portrait one
    c = s.pick(landscape=(0.645, 0.57), portrait=(0.5, 0.56))
    row = round((c.y - o.y) / PITCH)
    # the byte's first core, on an even i + j so its set bits lean the same way on every screen
    col = 2 * round(((c.x - o.x) / PITCH - 3.5 + row) / 2) - row
    focus = at(col + 3.5, row - 0.5)
    # the plane's fade grows with the long side past 16:9, so ultrawide screens stay covered
    reach = max(1.0, max(s.w, s.h) / 1920)
    n = s.noise(4)

    cores: dict[tuple[int, int], int] = {}  # (i, j) -> index into RINGS, or SET
    for j in range(rows):
        for i in range(cols):
            if j == row and col <= i < col + 8:
                cores[i, j] = SET if BYTE >> (col + 7 - i) & 1 else 5
            elif (t := tier(at(i, j), focus, n, reach)) is not None:
                cores[i, j] = t

    def lead(i: int, j: int) -> int:
        """The LEADS index of a wire running into (i, j): 1, lifted, for a core of the two
        brightest tiers, else 0."""
        t = cores.get((i, j))
        return int(t is not None and t < 2)

    inhibit = P()
    for i in range(cols):
        inhibit.M(at(i, 0).x + 3, 0).V(s.h)
    s.stroke(inhibit, INHIBIT, 1)

    byte = at(col - 0.5, row).x, at(col + 7.5, row).x
    with (
        s.buckets(LEADS, "stroke", stroke_width=1.2) as wires,
        s.buckets(READ, "stroke", stroke_width=1.6) as read,
    ):

        def x_wire(j: int, x0: float, x1: float, k: int) -> None:
            y = at(0, j).y
            if j != row:
                wires[k].M(x0, y).H(x1)
                return
            for a, b, part in ((0, byte[0], 0), (byte[0], byte[1], 1), (byte[1], s.w, 0)):
                if min(x1, b) > max(x0, a):
                    read[part].M(max(x0, a), y).H(min(x1, b))

        # a gap where X/Y wires meet a core's right/bottom side reads as passing under it;
        # flush on the left/top reads as over
        for j in range(rows):
            x = 0.0
            for i in range(cols):
                if (i, j) in cores:
                    cx = at(i, j).x
                    x_wire(j, x, cx + CROSS - GAP, lead(i, j))
                    x = cx + CROSS + GAP
            x_wire(j, x, s.w, 0)
        for i in range(cols):
            x, y = at(i, 0).x, 0.0
            for j in range(rows):
                if (i, j) in cores:
                    cy = at(i, j).y
                    wires[lead(i, j)].M(x, y).V(cy + CROSS - GAP)
                    y = cy + CROSS + GAP
            wires[0].M(x, y).V(s.h)
        # sense wires: rising diagonals through the cores on odd i + j, which lean across them,
        # lifted only where the plane is populated; segment m runs from at(k + 1 - m, m - 1)
        # to at(k - m, m)
        for k in range(1, cols + rows, 2):
            tiers = [tier(at(k - m, m), focus, n, reach) for m in range(rows + 2)]
            lifted = np.array([t is not None and t < 4 for t in tiers])
            for mask, w in ((~lifted, 0), (lifted, 1)):
                for a, b in runs(mask):
                    wires[w].M(at(k + 1 - a, a - 1)).L(at(k + 1 - b, b - 1))

    lit = P()
    with s.buckets(RINGS, "stroke", stroke_width=2) as rings:
        for (i, j), t in cores.items():
            core(lit if t == SET else rings[t], at(i, j), 45 if (i + j) % 2 else -45)
    s.stroke(lit, ACCENT, 2.4)
