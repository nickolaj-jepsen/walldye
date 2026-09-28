"""An unlabelled op-amp filter stage in schematic symbols on a dotted drafting grid, with the signal path picked out."""

import math

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_8,
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
)
from walldye.geom import Affine

# Everything below is in schematic units on a PITCH grid; draw() scales it onto the canvas.
PITCH = 40
BOX = Rect(640, 240, 1000, 576)  # the module outline; its pins sit on the left and right edges
SCALE = 1.15  # schematic to canvas units on a landscape screen
EDGE = 140  # least gap in canvas units between the module and the right edge of a landscape screen
SIDE = 80  # canvas margin either side of the module on a portrait screen
IN_Y, OUT_Y = 580, 540
GND_Y = 740
RAIL_HI, RAIL_LO = 412, 668
DOT, TERM = 4.5, 7
GRID = mix(BG, BG_ALT, 0.75)


def resistor(body: Path, wire: Path, a: Vec, b: Vec, size: float = 64, amp: float = 9) -> None:
    """Zigzag of six half-waves `amp` either side of a to b, `size` long and centred on the span;
    the zigzag goes into `body`, the two leads into `wire`."""
    u = (b - a).unit()
    t0 = (abs(b - a) - size) / 2
    zig = [a + u * (t0 + size * (2 * k + 1) / 12) + u.perp() * amp * (-1) ** k for k in range(6)]
    body.poly([a + u * t0, *zig, a + u * (t0 + size)])
    wire.poly([a, a + u * t0]).poly([a + u * (t0 + size), b])


def capacitor(body: Path, wire: Path, a: Vec, b: Vec, gap: float = 10, plate: float = 36) -> None:
    """Two plates `gap` apart across the middle of a to b, with their leads."""
    u = (b - a).unit()
    t0, t1 = (abs(b - a) - gap) / 2, (abs(b - a) + gap) / 2
    wire.poly([a, a + u * t0]).poly([a + u * t1, b])
    for t in (t0, t1):
        c = a + u * t
        body.poly([c - u.perp() * (plate / 2), c + u.perp() * (plate / 2)])


def diode(body: Path, wire: Path, a: Vec, b: Vec, size: float = 16) -> None:
    """Diode pointing from its anode at a to its cathode at b, with its leads."""
    u = (b - a).unit()
    n = u.perp() * size * 0.6
    c0 = a + u * (abs(b - a) - size) / 2
    c1 = c0 + u * size
    wire.poly([a, c0]).poly([c1, b])
    body.poly([c0 - n, c0 + n, c1], closed=True)
    body.poly([c1 - n, c1 + n])


def ground(body: Path, wire: Path, x: float, y: float, lead: float = 22) -> None:
    """Ground symbol: a lead down from (x, y), then three shrinking bars."""
    wire.M(x, y).V(y + lead)
    for k, half in enumerate((16, 10, 4)):
        body.M(x - half, y + lead + 7 * k).H(x + half)


def rail(body: Path, wire: Path, x: float, y: float, end: float) -> None:
    """Supply pin from y to a short bar at `end`."""
    wire.M(x, y).V(end)
    body.M(x - 12, end).H(x + 12)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: right of centre, pulled in to keep EDGE clear on narrow screens; portrait:
    # scaled down to the width and set in the upper half, above the dock
    scale = SCALE if s.landscape else (s.w - 2 * SIDE) / BOX.w
    c = s.pick(landscape=(0.6276, 0.5), portrait=(0.5, 0.42))
    if s.landscape:
        c = Vec(min(c.x, s.w - EDGE - BOX.w * scale / 2), c.y)
    m = Affine.translate(*(c - BOX.center * scale)) @ Affine.scale(scale)

    # the grid lies on the schematic's own lattice, so every part sits on a dot
    inv = m.inverse()
    lo, hi = inv((0, 0)), inv((s.w, s.h))
    xs = np.arange(math.floor(lo.x / PITCH) * PITCH, hi.x + PITCH, PITCH)
    ys = np.arange(math.floor(lo.y / PITCH) * PITCH, hi.y + PITCH, PITCH)
    gx, gy = np.meshgrid(xs, ys)
    grid = P().dots(np.column_stack([gx.ravel(), gy.ravel()]), 1.6)

    wires, parts, sig = P(), P(), P()
    junctions: list[tuple[float, float]] = []
    sig_junctions: list[tuple[float, float]] = []

    # input RC ladder: IN, R1, C1 to ground, R2, C2 to ground, then the + input
    sig.M(BOX.x + TERM, IN_Y).H(680)
    resistor(sig, sig, Vec(680, IN_Y), Vec(800, IN_Y))
    sig.M(800, IN_Y).H(840)
    resistor(sig, sig, Vec(840, IN_Y), Vec(960, IN_Y))
    sig.M(960, IN_Y).H(1080)
    for x in (820, 1000):
        capacitor(parts, wires, Vec(x, IN_Y), Vec(x, GND_Y))
        ground(parts, wires, x, GND_Y)
        sig_junctions.append((x, IN_Y))

    # op-amp: - at 500, + at 580, output at (1220, OUT_Y); supply pins end at the clamp's rails
    amp = P().poly([(1080, 460), (1080, 620), (1220, OUT_Y)], closed=True)
    amp.M(1094, 500).H(1108).M(1094, 580).H(1108).M(1101, 573).V(587)
    rail(parts, wires, 1140, 494, RAIL_HI)
    rail(parts, wires, 1140, 586, RAIL_LO)

    # feedback: Rf parallel to Cf from the output back to -, Rg to ground
    wires.M(1080, 500).H(1040).V(290).H(1120)
    capacitor(parts, wires, Vec(1120, 290), Vec(1240, 290))
    wires.M(1240, 290).H(1300).V(OUT_Y)
    wires.M(1040, 360).H(1120)
    resistor(parts, wires, Vec(1120, 360), Vec(1240, 360))
    wires.M(1240, 360).H(1300)
    resistor(parts, wires, Vec(1040, 360), Vec(920, 360))
    wires.M(920, 360).H(880)
    ground(parts, wires, 880, 360)
    junctions += [(1040, 360), (1300, 360)]

    # output: a Zobel network and a pair of clamp diodes
    sig.M(1220, OUT_Y).H(BOX.x1 - TERM)
    resistor(parts, wires, Vec(1440, OUT_Y), Vec(1440, 650))
    capacitor(parts, wires, Vec(1440, 650), Vec(1440, GND_Y))
    ground(parts, wires, 1440, GND_Y)
    diode(parts, wires, Vec(1580, OUT_Y), Vec(1580, 440))
    diode(parts, wires, Vec(1580, 640), Vec(1580, OUT_Y))
    rail(parts, wires, 1580, 440, RAIL_HI)
    rail(parts, wires, 1580, 640, RAIL_LO)
    sig_junctions += [(1300, OUT_Y), (1440, OUT_Y), (1580, OUT_Y)]

    # widths are in canvas units, so they stay put when the schematic scales
    thin, hot = 1.8 / scale, 2.6 / scale
    with s.group(transform=m):
        s.fill(grid, GRID)
        s.stroke(P().rrect(*BOX, 10), UI, 1.4 / scale, dash=(14, 8))
        s.stroke(wires, UI_ALT, thin, cap="round", join="round")
        s.stroke(parts, UI_HI, thin, cap="round", join="round")
        s.fill(P().dots(junctions, DOT), UI_HI)
        s.stroke(sig, ACCENT, hot, cap="round", join="round")
        s.path(
            amp,
            fill=ACCENT_8,
            stroke=ACCENT,
            stroke_width=hot,
            stroke_linecap="round",
            stroke_linejoin="round",
        )
        # the module's connector pins sit on its boundary
        pins = P().circle((BOX.x, IN_Y), TERM).circle((BOX.x1, OUT_Y), TERM)
        s.path(pins, fill=BG, stroke=ACCENT, stroke_width=hot)
        s.fill(P().dots(sig_junctions, DOT), ACCENT)
