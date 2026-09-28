"""A {7,3} hyperbolic tiling in the Poincaré disk, grown by reflecting heptagons across their geodesic edges; the centre tile is filled in."""

import itertools
import math

from walldye import (
    ACCENT,
    ACCENT_8,
    BG,
    BG_ALT,
    UI_ALT,
    Canvas,
    P,
    Params,
    Path,
    Vec,
    design,
    knob,
    ladder,
    mix,
)
from walldye.geom import ngon


class Tiling(Params):
    p: int = knob(default=7, lo=3, hi=10, doc="sides of each tile")
    q: int = knob(default=3, lo=3, hi=10, doc="tiles meeting at each corner")


VARIANTS = {"pentagons": Tiling(p=5, q=4)}

R = 440  # disc radius
MIN_PX = 2.5  # tiles narrower than this are left out, so the rim dissolves into texture
BANDS = 5  # edge tones from the centre out to the rim
TONES = ladder((UI_ALT, BG_ALT), BANDS)
RIM = mix(BG, BG_ALT, 0.6)  # the outermost band, a step under BG_ALT

type Tile = tuple[int, complex, list[complex]]  # generation, centre, vertices (unit disc)


def geodesic(u: complex, v: complex) -> tuple[complex, float] | None:
    """The circle (centre, radius) through u and v that meets the unit circle at right angles,
    or None when u and v lie on a diameter."""
    w = 1 / u.conjugate()
    d = 2 * (u.real * (v.imag - w.imag) + v.real * (w.imag - u.imag) + w.real * (u.imag - v.imag))
    if abs(d) < 1e-12:
        return None
    a, b, c = abs(u) ** 2, abs(v) ** 2, abs(w) ** 2
    cx = (a * (v.imag - w.imag) + b * (w.imag - u.imag) + c * (u.imag - v.imag)) / d
    cy = (a * (w.real - v.real) + b * (u.real - w.real) + c * (v.real - u.real)) / d
    o = complex(cx, cy)
    return o, abs(u - o)


def reflect(z: complex, u: complex, v: complex) -> complex:
    """z mirrored in the geodesic through u and v (inversion in its circle)."""
    g = geodesic(u, v)
    if g is None:
        e = (v - u) / abs(v - u)
        return e * e * z.conjugate()
    o, r = g
    return o + r * r / (z - o).conjugate()


def sides(vs: list[complex]) -> list[tuple[complex, complex]]:
    """Consecutive vertex pairs of a closed polygon."""
    return list(itertools.pairwise([*vs, vs[0]]))


def tiles(p: int, q: int) -> list[Tile]:
    """The {p,q} tiling centred on a tile, grown breadth first by reflecting each tile across
    its sides, down to tiles about MIN_PX wide on a disc of radius R."""
    if (p - 2) * (q - 2) <= 4:
        raise ValueError(f"{{{p},{q}}} does not tile the hyperbolic plane")
    rv = math.sqrt(math.cos(math.pi / p + math.pi / q) / math.cos(math.pi / p - math.pi / q))
    first = [complex(x, y) for x, y in ngon((0, 0), rv, p, bearing=0)]

    def key(z: complex) -> tuple[float, float]:
        return round(z.real, 6), round(z.imag, 6)

    seen = {key(0j)}
    out: list[Tile] = [(0, 0j, first)]
    front: list[tuple[complex, list[complex]]] = [(0j, first)]
    depth = 0
    while front:
        depth += 1
        nxt: list[tuple[complex, list[complex]]] = []
        for c, vs in front:
            for u, v in sides(vs):
                c2 = reflect(c, u, v)
                if key(c2) in seen:
                    continue
                seen.add(key(c2))
                vs2 = [reflect(z, u, v) for z in vs]
                if max(abs(a - b) for a in vs2 for b in vs2) * R < MIN_PX:
                    continue
                out.append((depth, c2, vs2))
                nxt.append((c2, vs2))
        front = nxt
    return out


def xy(c: Vec, z: complex) -> Vec:
    """Disc point z on a canvas disc of radius R centred at c."""
    return c + (R * z.real, R * z.imag)


def edge(d: Path, c: Vec, u: complex, v: complex, *, move: bool = True) -> Path:
    """The geodesic from u to v: an arc, or a line along a diameter."""
    if move:
        d.M(xy(c, u))
    g = geodesic(u, v)
    if g is None:
        return d.L(xy(c, v))
    o, r = g
    cross = (u - o).real * (v - o).imag - (u - o).imag * (v - o).real
    return d.A(r * R, r * R, 0, 0, cross > 0, xy(c, v))


def poly(d: Path, c: Vec, vs: list[complex]) -> Path:
    """A closed tile outline of geodesic sides."""
    d.M(xy(c, vs[0]))
    for u, v in sides(vs):
        edge(d, c, u, v, move=False)
    return d.Z()


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Tiling]) -> None:
    # right of centre on a landscape screen, leaving the left for windows; above the middle on
    # a portrait one, where the disc spans all but 100 units of the width
    c = s.pick(landscape=(0.6875, 0.5), portrait=(0.5, 0.4))
    ts = tiles(s.params.p, s.params.q)

    ring = P()
    for depth, _, vs in ts:
        if depth == 1:
            poly(ring, c, vs)
    s.fill(ring, ACCENT_8)

    # Each shared side once, banded by distance from the centre so the lines fade to the rim.
    bands = [P() for _ in range(BANDS)]
    done: set[tuple[float, float]] = set()
    for _, _, vs in ts:
        for u, v in sides(vs):
            m = (u + v) / 2
            k = (round(m.real, 5), round(m.imag, 5))
            if k in done:
                continue
            done.add(k)
            edge(bands[min(BANDS - 1, int(abs(m) ** 3 * BANDS))], c, u, v)
    for b, d in enumerate(bands[:-1]):
        s.stroke(d, TONES[b], 1.6 - 0.15 * b, cap="round")
    s.stroke(bands[-1], RIM, 1.0, cap="round")

    # drawn last so the BG stroke trims the stroked sides instead of outlining the filled tile
    centre = poly(P(), c, ts[0][2])
    s.path(centre, fill=ACCENT, stroke=BG, stroke_width=1.6, stroke_linejoin="round")
