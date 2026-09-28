"""A tall shoji panel of asanoha kumiko: a triangle lattice split into hemp-leaf cells, with the cells round one joint lit from behind in three steps."""

import math
from collections.abc import Iterator

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    Canvas,
    P,
    Vec,
    clamp,
    design,
    ramp,
)

WIDTH, RAIL, BAR = 380, 24, 14  # panel width, stile width, crossbar height
SIDE = 70
HT = SIDE * math.sqrt(3) / 2
SECTION = 12 * HT  # crossbar spacing; the lamp sits mid-section on a lattice joint
LAMP_LAND = (1370 / 1920, 6 * HT / 1080)  # the 16:9 panel spans x 1180-1560
LAMP_PORT = (0.64, 0.38)
GLOW = (ACCENT, ACCENT_1, ACCENT_3)
BANDS = (40, 70, 100)  # lamp distance of a leaf cell's centroid for each glow step
FADE = 4  # frame tone steps from lamp-lit wood down to the quiet lattice
# Wood by step: 0 is the backlit silhouette, 1..FADE step from lamp-lit frames out to BG_ALT.
FRAME = (BG, *ramp(UI, BG_ALT, FADE))
LEAF = (BG, *[BG_ALT] * FADE)
FRAME_W = (2.6, *[2.2] * FADE)
LEAF_W = (1.6, *[1.2] * FADE)


def triangles(lamp: Vec, x0: float, x1: float, h: float) -> Iterator[tuple[Vec, Vec, Vec]]:
    """The lattice triangles overlapping the strip `x0`..`x1`, 0..`h`, with a joint on `lamp`.

    Rows run `HT` apart from the lamp's row, each odd row shifted half a side."""
    for j in range(math.floor(-lamp.y / HT), math.ceil((h - lamp.y) / HT)):
        y = lamp.y + j * HT
        for i in range(math.floor((x0 - lamp.x) / SIDE) - 1, math.ceil((x1 - lamp.x) / SIDE) + 1):
            a = Vec(lamp.x + i * SIDE + (j % 2) * SIDE / 2, y)
            b, c, d = a + (SIDE, 0), a + (SIDE / 2, HT), a + (-SIDE / 2, HT)
            for tri in ((a, b, c), (a, c, d)):
                if max(p.x for p in tri) > x0 and min(p.x for p in tri) < x1:
                    yield tri


@design(aspects="any")
def draw(s: Canvas) -> None:
    at = s.pick(landscape=LAMP_LAND, portrait=LAMP_PORT)
    lamp = Vec(round(at.x), at.y)  # whole-pixel stiles
    x0 = lamp.x - WIDTH / 2
    x1 = x0 + WIDTH
    inner = P().rect(x0 + RAIL, 0, WIDTH - 2 * RAIL, s.h)
    with s.clip() as pane:
        pane.add(inner)
    s.fill(inner, BG_DEEP)
    wood = [(P(), P()) for _ in FRAME]  # (frame, leaf) per step
    with s.group(clip_path=pane.ref):
        with s.buckets(GLOW, "fill") as lit:
            for tri in triangles(lamp, x0 + RAIL, x1 - RAIL, s.h):
                c = (tri[0] + tri[1] + tri[2]) / 3
                any_lit = False
                for k in range(3):
                    a, b = tri[k], tri[(k + 1) % 3]
                    lvl = sum(abs((a + b + c) / 3 - lamp) > t for t in BANDS)
                    if lvl < len(GLOW):
                        lit[lvl].poly([c, a, b], closed=True)
                        any_lit = True
                far = clamp((abs(c - lamp) - BANDS[-1]) / (2.2 * HT))
                frame, leaf = wood[0 if any_lit else 1 + min(FADE - 1, int(far * FADE))]
                frame.poly(tri, closed=True)
                for p in tri:
                    leaf.M(c).L(p)
        # far to near, so shared edges take the tone of the wood nearer the lamp
        for step in reversed(range(len(FRAME))):
            frame, leaf = wood[step]
            s.stroke(leaf, LEAF[step], LEAF_W[step])
            s.stroke(frame, FRAME[step], FRAME_W[step], join="round")
    rails = P().rect(x0, 0, RAIL, s.h).rect(x1 - RAIL, 0, RAIL, s.h)
    # crossbars halfway between lamp sections, on lattice rows, only where wholly on screen
    for k in range(math.floor(-lamp.y / SECTION), math.ceil((s.h - lamp.y) / SECTION)):
        y = lamp.y + (k + 0.5) * SECTION
        if HT < y < s.h - HT:
            rails.rect(x0, round(y - BAR / 2), WIDTH, BAR)
    s.fill(rails, BG_ALT)
