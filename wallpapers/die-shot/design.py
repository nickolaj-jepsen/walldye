"""A 1970s microprocessor die drawn as mask artwork from recursive guillotine cuts, its bit-sliced ALU picked out and bond wires fanning to the screen edges."""

import math

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_8,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    P,
    Rect,
    Rng,
    Vec,
    design,
    mix,
)
from walldye.geom import Affine

# The die is drawn in its own coordinates, top-left at (0, 0), and placed by one transform.
DIE = Rect(0, 0, 720, 560)
REG = Rect(82, 82, 224, 208)  # register file
ROM = Rect(346, 82, 296, 136)
ALU = Rect(82, 332, 224, 146)
LOGIC = Rect(346, 254, 296, 240)  # random logic
DIM, WIRE = mix(BG_DEEP, UI, 0.75), mix(BG_DEEP, BG_ALT, 0.8)


def split(r: Rng, box: Rect, depth: int) -> list[Rect]:
    """Leaf rects of a recursive guillotine cut of `box`, `depth` levels at most: each cut
    usually crosses the longer side, and a branch stops early at random or below 14 units."""
    x, y, w, h = box
    if depth == 0 or (w < 14 and h < 14) or r.random() < 0.06 * (4 - depth):
        return [box]
    if (w > h) if r.random() < 0.8 else (w <= h):
        k = round(w * r.uniform(0.3, 0.7))
        return split(r, Rect(x, y, k, h), depth - 1) + split(r, Rect(x + k, y, w - k, h), depth - 1)
    k = round(h * r.uniform(0.3, 0.7))
    return split(r, Rect(x, y, w, k), depth - 1) + split(r, Rect(x, y + k, w, h - k), depth - 1)


def pads() -> tuple[tuple[Vec, Vec], ...]:
    """Center and outward normal of each of the 16 bond pads spread along the die edges."""
    out: list[tuple[Vec, Vec]] = []
    for i in range(5):
        x = 110 + i * (DIE.w - 220) / 4
        out += [(Vec(x, 30), Vec(0, -1)), (Vec(x, DIE.h - 30), Vec(0, 1))]
    for i in range(3):
        y = 150 + i * (DIE.h - 300) / 2
        out += [(Vec(30, y), Vec(-1, 0)), (Vec(DIE.w - 30, y), Vec(1, 0))]
    return tuple(out)


PADS = pads()


def to_edge(p: Vec, d: Vec, frame: Rect) -> Vec:
    """Where the ray from `p` along `d` leaves `frame`, which contains `p`."""
    t = min(
        ((frame.x1 if d.x > 0 else frame.x) - p.x) / d.x if d.x else math.inf,
        ((frame.y1 if d.y > 0 else frame.y) - p.y) / d.y if d.y else math.inf,
    )
    return p + d * t


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of center on a landscape screen (1150, 520 at 16:9); centered, a little low, in portrait
    o = s.pick(landscape=(1150 / 1920, 520 / 1080), portrait=(0.5, 0.56), snap=2) - DIE.center
    frame = Rect(-o.x, -o.y, s.w, s.h)  # the canvas in die coordinates
    r = s.rng(4004)

    with s.group(transform=Affine.translate(o.x, o.y)):
        # Bond wires fan from each pad away from the die center.
        wires = P()
        for p, n in PADS:
            wires.M(p).L(to_edge(p, n + (p - DIE.center).unit() * 0.9, frame))
        s.stroke(wires, BG_ALT, 1.2)

        s.path(P().rect(*DIE), fill=BG_DEEP, stroke=UI, stroke_width=2)

        # Two-line power ring inside the pad frame, with a stub from every pad.
        ring, stubs, pad = P(), P(), P()
        for i in (62, 68):
            ring.rect(i, i, DIE.w - 2 * i, DIE.h - 2 * i)
        for p, n in PADS:
            stubs.M(p - n * 15).L(p - n * 38)
            pad.rect(p.x - 15, p.y - 15, 30, 30)
        s.stroke(ring, DIM, 1.2)
        s.stroke(stubs, UI, 3)
        s.path(pad, fill=BG_DEEP, stroke=UI_ALT, stroke_width=1.2)

        # Buses between blocks.
        bus = P()
        for k in range(8):
            x = ALU.x + (k // 2) * ALU.w / 4 + ALU.w / 8 - 4 + (k % 2 * 2 - 1) * 8
            bus.M(x, REG.y1 + 4).V(ALU.y - 4)
        for k in range(6):
            bus.M(REG.x1 + 4, REG.y + 20 + k * 8).H(ROM.x - 4)
            bus.M(ROM.x + 40 + k * 44, ROM.y1 + 4).V(LOGIC.y - 4)
        for k in range(4):
            bus.M(ALU.x1 + 6, ALU.y + 30 + k * 26).H(LOGIC.x - 4)
        s.stroke(bus, DIM, 1.2)

        # Register file: 8 x 16 latch cells with word lines.
        cells, lines = P(), P()
        cw, ch = REG.w / 8, REG.h / 16
        for j in range(16):
            y = REG.y + j * ch
            lines.M(REG.x, y + ch - 1.5).H(REG.x1)
            for i in range(8):
                x = REG.x + i * cw
                cells.rect(x + 2, y + 2, cw / 2 - 4, ch - 6)
                cells.rect(x + cw / 2 + 1, y + 2, cw / 2 - 5, ch - 6)
        s.stroke(lines, WIRE, 1)
        s.stroke(cells, UI, 1)

        # ROM: every bit site on a 6-unit lattice, faint when clear and a step up when set.
        with s.buckets((BG_ALT, UI), "fill") as bits:
            for j in range(int(ROM.h // 6)):
                for i in range(int(ROM.w // 6)):
                    bits[int(r.random() < 0.45)].rect(ROM.x + i * 6 + 1, ROM.y + j * 6 + 2, 4, 2)

        # Random logic: four gate rows with channel-routed Manhattan nets and square vias.
        gates, routes, vias = P(), P(), P()
        rows_y: list[float] = []
        pins: list[tuple[int, float]] = []
        for row in range(4):
            gy = LOGIC.y + row * (LOGIC.h / 4) + 6
            rows_y.append(gy)
            x = LOGIC.x
            while x < LOGIC.x1 - 26:
                gw = min(r.choice((12, 18, 24, 30)), LOGIC.x1 - x)
                for lx, ly, lw, lh in split(r, Rect(x, gy, gw, 22), 2):
                    gates.rect(lx + 1, ly + 1, lw - 2, lh - 2)
                pins.append((row, x + gw / 2))
                x += gw + r.choice((4, 6, 10))
        for _ in range(60):
            row, ax = r.choice(pins)
            brow, bx = r.choice([p for p in pins if abs(p[0] - row) <= 1 and p != (row, ax)])
            top = min(row, brow)
            # the net's channel: one of four tracks under its upper row, or below the last row
            ty = rows_y[top] + 22 + 5 + r.randrange(4) * 7 if top < 3 else rows_y[3] + 22 + 6
            ay = rows_y[row] + (22 if row == top else 0)
            by = rows_y[brow] + (22 if brow == top else 0)
            routes.M(ax, ay).V(ty).H(bx).V(by)
            vias.rect(ax - 2, ty - 2, 4, 4).rect(bx - 2, ty - 2, 4, 4)
        s.stroke(gates, DIM, 1)
        s.stroke(routes, UI, 1.3)
        s.fill(vias, UI_ALT)

        # ALU: one bit-slice template stamped four times, joined by a carry chain.
        sw = ALU.w / 4
        tw = round(sw) - 8
        tmpl = split(s.rng(30), Rect(0, 0, tw, ALU.h - 18), 5)
        slices, chain = P(), P()
        for i in range(4):
            for lx, ly, lw, lh in tmpl:
                # odd slices mirror to share rails with their neighbor
                x = ALU.x + i * sw + (tw - lx - lw if i % 2 else lx)
                slices.rect(x + 1.5, ALU.y + ly + 1.5, lw - 3, lh - 3)
        chain.M(ALU.x - 6, ALU.y1 - 6).H(ALU.x1 + 4)
        for i in range(4):
            chain.M(ALU.x + i * sw + sw / 2 - 4, ALU.y1 - 16).V(ALU.y1 - 6)
        s.stroke(chain, ACCENT_3, 2)
        s.path(slices, fill=ACCENT_8, stroke=ACCENT, stroke_width=1.4)
