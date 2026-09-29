"""Unlabeled op-amp circuits in schematic symbols on a dotted drafting grid, with the signal path picked out."""

import math
from dataclasses import dataclass
from typing import Literal

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
    Params,
    Path,
    Rect,
    Vec,
    design,
    knob,
    mix,
)
from walldye.geom import Affine


class Sheet(Params):
    circuit: Literal["lowpass", "wien", "inamp", "ramp"] = knob(
        default="lowpass", doc="the circuit drawn"
    )


VARIANTS = {
    "wien-bridge": Sheet(circuit="wien"),
    "instrumentation": Sheet(circuit="inamp"),
    "triangle-wave": Sheet(circuit="ramp"),
}

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
# module outlines of the other circuits, each sized to its own parts
WIEN_BOX = Rect(600, 100, 840, 660)
INAMP_BOX = Rect(680, 150, 960, 660)
RAMP_BOX = Rect(640, 280, 1080, 480)


@dataclass(frozen=True)
class Ink:
    """What one circuit draws, in schematic units: wires, part bodies, the lit signal path, the
    op-amp bodies, junction dots off and on that path, and the module's connector pins."""

    wires: Path
    parts: Path
    sig: Path
    amp: Path
    dots: list[tuple[float, float]]
    sig_dots: list[tuple[float, float]]
    pins: list[tuple[float, float]]


def resistor(body: Path, wire: Path, a: Vec, b: Vec, size: float = 64, amp: float = 9) -> None:
    """Zigzag of six half-waves `amp` either side of a to b, `size` long and centered on the span;
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


def opamp(k: Ink, x: float, y: float, flip: bool = False) -> None:
    """Op-amp with its left edge at x and its output at (x + 140, y); the - input sits 40 above
    y and the + input 40 below, the other way round when `flip`."""
    k.amp.poly([(x, y - 80), (x, y + 80), (x + 140, y)], closed=True)
    minus, plus = (y + 40, y - 40) if flip else (y - 40, y + 40)
    k.amp.M(x + 14, minus).H(x + 28).M(x + 14, plus).H(x + 28).M(x + 21, plus - 7).V(plus + 7)


def lowpass(k: Ink) -> None:
    """Two-pole RC low-pass into a non-inverting stage, with a Zobel network and clamp diodes."""
    wires, parts, sig, amp = k.wires, k.parts, k.sig, k.amp

    # input RC ladder: IN, R1, C1 to ground, R2, C2 to ground, then the + input
    sig.M(BOX.x + TERM, IN_Y).H(680)
    resistor(sig, sig, Vec(680, IN_Y), Vec(800, IN_Y))
    sig.M(800, IN_Y).H(840)
    resistor(sig, sig, Vec(840, IN_Y), Vec(960, IN_Y))
    sig.M(960, IN_Y).H(1080)
    for x in (820, 1000):
        capacitor(parts, wires, Vec(x, IN_Y), Vec(x, GND_Y))
        ground(parts, wires, x, GND_Y)
        k.sig_dots.append((x, IN_Y))

    # op-amp: - at 500, + at 580, output at (1220, OUT_Y); supply pins end at the clamp's rails
    amp.poly([(1080, 460), (1080, 620), (1220, OUT_Y)], closed=True)
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
    k.dots.extend([(1040, 360), (1300, 360)])

    # output: a Zobel network and a pair of clamp diodes
    sig.M(1220, OUT_Y).H(BOX.x1 - TERM)
    resistor(parts, wires, Vec(1440, OUT_Y), Vec(1440, 650))
    capacitor(parts, wires, Vec(1440, 650), Vec(1440, GND_Y))
    ground(parts, wires, 1440, GND_Y)
    diode(parts, wires, Vec(1580, OUT_Y), Vec(1580, 440))
    diode(parts, wires, Vec(1580, 640), Vec(1580, OUT_Y))
    rail(parts, wires, 1580, 440, RAIL_HI)
    rail(parts, wires, 1580, 640, RAIL_LO)
    k.sig_dots.extend([(1300, OUT_Y), (1440, OUT_Y), (1580, OUT_Y)])
    k.pins.extend([(BOX.x, IN_Y), (BOX.x1, OUT_Y)])


def wien(k: Ink) -> None:
    """Wien-bridge oscillator: series RC from the output to +, parallel RC from + to ground, and
    a gain of about three set by Rf over Rg, with two diodes across part of Rf."""
    box = WIEN_BOX
    # op-amp: - at 400, + at 480, output at (1140, 440)
    opamp(k, 1000, 440)
    k.sig.M(1140, 440).H(box.x1 - TERM)

    # the loop that oscillates: series R and C back to +, parallel R and C from + to ground
    k.sig.M(1320, 440).V(560)
    capacitor(k.sig, k.sig, Vec(1320, 560), Vec(1200, 560))
    resistor(k.sig, k.sig, Vec(1200, 560), Vec(1080, 560))
    k.sig.M(1080, 560).H(920).V(480).H(1000)
    k.wires.M(920, 560).H(680)
    resistor(k.parts, k.wires, Vec(800, 560), Vec(800, 680))
    ground(k.parts, k.wires, 800, 680)
    capacitor(k.parts, k.wires, Vec(680, 560), Vec(680, 680))
    ground(k.parts, k.wires, 680, 680)

    # negative feedback: Rg to ground, Rf in two parts, the second shunted by opposed diodes
    # that lower the gain as the swing grows
    k.wires.M(1000, 400).H(960).V(320)
    resistor(k.parts, k.wires, Vec(960, 320), Vec(840, 320))
    k.wires.M(840, 320).H(800)
    ground(k.parts, k.wires, 800, 320)
    resistor(k.parts, k.wires, Vec(960, 320), Vec(1080, 320))
    resistor(k.parts, k.wires, Vec(1080, 320), Vec(1240, 320))
    k.wires.M(1080, 320).V(160).M(1240, 440).V(160)
    diode(k.parts, k.wires, Vec(1080, 240), Vec(1240, 240))
    diode(k.parts, k.wires, Vec(1240, 160), Vec(1080, 160))

    k.dots.extend([(960, 320), (1080, 320), (1080, 240), (1240, 320), (1240, 240), (800, 560)])
    k.sig_dots.extend([(1240, 440), (1320, 440), (920, 560)])
    k.pins.append((box.x1, 440))


def inamp(k: Ink) -> None:
    """Three-op-amp instrumentation amplifier: two input buffers joined by R1, Rgain, R1, then a
    difference stage of R2 and R3."""
    box = INAMP_BOX
    # buffers: each input drives a +, and the two - inputs face each other
    k.sig.M(box.x + TERM, 240).H(880).M(box.x + TERM, 720).H(880)
    opamp(k, 880, 280, flip=True)
    opamp(k, 880, 680)
    resistor(k.parts, k.wires, Vec(1080, 280), Vec(1080, 400))
    resistor(k.parts, k.wires, Vec(1080, 400), Vec(1080, 560))
    resistor(k.parts, k.wires, Vec(1080, 560), Vec(1080, 680))
    k.wires.M(880, 320).H(840).V(400).H(1080)
    k.wires.M(880, 640).H(840).V(560).H(1080)

    # difference stage: R2 into each input, R3 from - to the output and from + to ground
    k.sig.M(1020, 280).H(1080)
    resistor(k.sig, k.sig, Vec(1080, 280), Vec(1280, 280))
    k.sig.M(1280, 280).V(440).H(1320)
    k.sig.M(1020, 680).H(1080)
    resistor(k.sig, k.sig, Vec(1080, 680), Vec(1280, 680))
    k.sig.M(1280, 680).V(520).H(1320)
    opamp(k, 1320, 480)
    resistor(k.parts, k.wires, Vec(1280, 280), Vec(1520, 280))
    k.wires.M(1520, 280).V(480)
    resistor(k.parts, k.wires, Vec(1280, 680), Vec(1520, 680))
    ground(k.parts, k.wires, 1520, 680)
    k.sig.M(1460, 480).H(box.x1 - TERM)

    k.dots.extend([(1080, 400), (1080, 560)])
    k.sig_dots.extend([(1080, 280), (1080, 680), (1280, 280), (1280, 680), (1520, 480)])
    k.pins.extend([(box.x, 240), (box.x, 720), (box.x1, 480)])


def ramp(k: Ink) -> None:
    """Triangle and square generator: an integrator ramps until a comparator with hysteresis
    flips, and the comparator's square output drives the integrator back."""
    box = RAMP_BOX
    # integrator: in through Ri to -, C from the output back to -, + to ground
    opamp(k, 880, 480)
    k.wires.M(880, 520).H(840)
    ground(k.parts, k.wires, 840, 520)
    k.wires.M(840, 440).V(360)
    capacitor(k.parts, k.wires, Vec(840, 360), Vec(1080, 360))
    k.wires.M(1080, 360).V(480)

    # comparator: the ramp into + through R1, R2 from the output back to +, - to ground
    k.sig.M(1020, 480).H(1160)
    resistor(k.sig, k.sig, Vec(1160, 480), Vec(1280, 480))
    k.sig.M(1280, 480).H(1320)
    opamp(k, 1320, 520, flip=True)
    k.wires.M(1280, 480).V(400)
    resistor(k.parts, k.wires, Vec(1280, 400), Vec(1520, 400))
    k.wires.M(1520, 400).V(520)
    k.wires.M(1320, 560).H(1280)
    ground(k.parts, k.wires, 1280, 560)

    # the square wave runs back under both stages to Ri; the ramp is brought out at the top
    k.sig.M(1460, 520).H(box.x1 - TERM)
    k.sig.M(1600, 520).V(680).H(720).V(440)
    resistor(k.sig, k.sig, Vec(720, 440), Vec(840, 440))
    k.sig.M(840, 440).H(880)
    k.sig.M(1160, 480).V(box.y + TERM)

    k.sig_dots.extend([(840, 440), (1080, 480), (1160, 480), (1280, 480), (1520, 520), (1600, 520)])
    k.pins.extend([(1160, box.y), (box.x1, 520)])


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Sheet]) -> None:
    circuit = s.params.circuit
    box = {"lowpass": BOX, "wien": WIEN_BOX, "inamp": INAMP_BOX, "ramp": RAMP_BOX}[circuit]

    # landscape: right of center, pulled in to keep EDGE clear on narrow screens; portrait:
    # scaled down to the width and set in the upper half, above the dock
    scale = SCALE if s.landscape else (s.w - 2 * SIDE) / box.w
    c = s.pick(landscape=(0.6276, 0.5), portrait=(0.5, 0.42))
    if s.landscape:
        c = Vec(min(c.x, s.w - EDGE - box.w * scale / 2), c.y)
    m = Affine.translate(*(c - box.center * scale)) @ Affine.scale(scale)

    # the grid lies on the schematic's own lattice, so every part sits on a dot
    inv = m.inverse()
    lo, hi = inv((0, 0)), inv((s.w, s.h))
    xs = np.arange(math.floor(lo.x / PITCH) * PITCH, hi.x + PITCH, PITCH)
    ys = np.arange(math.floor(lo.y / PITCH) * PITCH, hi.y + PITCH, PITCH)
    gx, gy = np.meshgrid(xs, ys)
    grid = P().dots(np.column_stack([gx.ravel(), gy.ravel()]), 1.6)

    k = Ink(P(), P(), P(), P(), [], [], [])
    if circuit == "wien":
        wien(k)
    elif circuit == "inamp":
        inamp(k)
    elif circuit == "ramp":
        ramp(k)
    else:
        lowpass(k)

    # widths are in canvas units, so they stay put when the schematic scales
    thin, hot = 1.8 / scale, 2.6 / scale
    with s.group(transform=m):
        s.fill(grid, GRID)
        s.stroke(P().rrect(*box, 10), UI, 1.4 / scale, dash=(14, 8))
        s.stroke(k.wires, UI_ALT, thin, cap="round", join="round")
        s.stroke(k.parts, UI_HI, thin, cap="round", join="round")
        s.fill(P().dots(k.dots, DOT), UI_HI)
        s.stroke(k.sig, ACCENT, hot, cap="round", join="round")
        s.path(
            k.amp,
            fill=ACCENT_8,
            stroke=ACCENT,
            stroke_width=hot,
            stroke_linecap="round",
            stroke_linejoin="round",
        )
        # the module's connector pins sit on its boundary
        pins = P()
        for p in k.pins:
            pins.circle(p, TERM)
        s.path(pins, fill=BG, stroke=ACCENT, stroke_width=hot)
        s.fill(P().dots(k.sig_dots, DOT), ACCENT)
