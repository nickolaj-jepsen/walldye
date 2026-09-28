"""A faint shippo lattice of overlapping circles; ink soaks outward from one flower, petal by touching petal, in four tone steps."""

import math

from walldye import ACCENT, ACCENT_1, ACCENT_3, ACCENT_6, BG, BG_ALT, Canvas, P, Vec, design

D = 56  # lattice spacing; each circle meets its neighbours' at the cell centres
R = D / math.sqrt(2)
INK = (ACCENT, ACCENT_1, ACCENT_3, ACCENT_6)  # petal tones, focus outwards; the rest stay dry
STEP = 52  # stain radius per tone step, before the lobes stretch it
RUN = math.radians(-38)  # the bleed runs furthest this way, as if along the paper's fibres
# the paper grain is read as if the focus sat here (16:9), so every screen gets the same stain
GRAIN = Vec(560, 660)

type Cell = tuple[int, int]  # lattice index of a cell centre
type Petal = tuple[Cell, Cell]  # the lens between two neighbouring cell centres


@design(aspects="any")
def draw(s: Canvas) -> None:
    n = s.noise(11)
    f = s.pick(landscape=(7 / 24, 11 / 18), portrait=(0.42, 0.6), snap=1)
    # anchor the lattice so a four-petal flower sits on the focus
    ox, oy = (f.x - D / 2) % D, (f.y - D / 2) % D
    cols, rows = range(-1, s.w // D + 2), range(-1, s.h // D + 2)

    def centre(c: Cell) -> Vec:
        return Vec(ox + (c[0] + 0.5) * D, oy + (c[1] + 0.5) * D)

    def level(p: Vec) -> int:
        """Tone step of the petal whose middle is `p`: 0 at the focus; len(INK) and up is dry."""
        dx, dy = p - f
        r, a = math.hypot(dx, dy), math.atan2(dy, dx)
        # a few big lobes from noise read around a circle, plus one long run; the core stays level 0
        lobe = n.fbm(1.3 * math.cos(a) + 5.1, 1.3 * math.sin(a) + 2.7, octaves=2)
        lobe += max(0.0, math.cos(a - RUN)) ** 4
        lobe += 0.25 * n((dx + GRAIN.x) / 400, (dy + GRAIN.y) / 400)
        return int(r / (1 + 0.6 * min(1, r / 120) * lobe) / STEP)

    petals: dict[Petal, int] = {}
    for i in cols:
        for j in rows:
            for e in ((i + 1, j), (i, j + 1)):
                k = level((centre((i, j)) + centre(e)) / 2)
                if k < len(INK):
                    petals[((i, j), e)] = k
    # grow from the focus through petals that share a cell centre, never towards a stronger
    # tone, so no inked petal floats apart from the stain
    by_end: dict[Cell, list[Petal]] = {}
    for p in petals:
        for end in p:
            by_end.setdefault(end, []).append(p)
    wet = {p for p, k in petals.items() if k == 0}
    frontier = list(wet)
    while frontier:
        p = frontier.pop()
        for end in p:
            for q in by_end[end]:
                if q not in wet and petals[q] >= petals[p]:
                    wet.add(q)
                    frontier.append(q)

    rings = P()
    for i in cols:
        for j in rows:
            rings.circle((ox + i * D, oy + j * D), R)
    s.stroke(rings, BG_ALT, 1.5)
    # inked petals are walled in BG, like cloisonné wire, so the faint ones don't halo
    with s.buckets(INK, "fill", stroke=BG, stroke_width=1.8) as ink:
        for a, b in sorted(wet):
            c, e = centre(a), centre(b)
            ink[petals[(a, b)]].M(c).A(R, R, 0, 0, 1, e).A(R, R, 0, 0, 1, c).Z()
