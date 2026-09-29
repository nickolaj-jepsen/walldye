"""The NixOS snowflake as a construction drawing: six lattice-snapped lambdas whose edges run on as fading guide lines, one picked out."""

import math
from dataclasses import dataclass

from shapely import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import ACCENT, BG, BG_ALT, UI, UI_ALT, Canvas, P, Params, Vec, design, knob, polar
from walldye.geom import Affine, ngon, parts

U = 52  # bar width, the lattice unit
FADE = 620  # construction lines dissolve into the background by this radius
DASHDOT = (24, 6, 3, 6)
ARROW, ARROW_W = 13, 4.2
# One lambda on a 1/6 triangular lattice (a, b): a along +x, b along 60° down-right; center at
# the origin. Snapped from the official nix-snowflake.svg, which leaves a ~0.14 U gap between
# neighbors.
LATTICE = (
    (-11, 1),
    (-11, 27),
    (-17, 27),
    (-17, 20),
    (-24, 27),
    (-27, 27),
    (-27, 24),
    (-17, 14),
    (-17, 7),
)
LAMBDA = [Vec(a / 6 + b / 12, b / 6 * math.sqrt(3) / 2) for a, b in LATTICE]  # in U
HEX = 11 / 6 * math.sqrt(3) / 2  # apothem of the central void, in U
R = U * max(abs(v) for v in LAMBDA)  # the circumscribed circle


@dataclass
class Guide:
    """A line some emblem edges lie on: direction `ang` (radians, mod pi), signed normal
    offset `off` from the center, and the edges on it."""

    ang: float
    off: float
    edges: list[tuple[Vec, Vec]]


def guides(polys: list[list[Vec]], c: Vec) -> list[Guide]:
    """Every emblem edge grouped by the line it lies on; facing edges one gap apart share the
    line through the middle of the gap."""
    found: list[Guide] = []
    for p in polys:
        for a, b in zip(p, p[1:] + p[:1], strict=True):
            ang = math.atan2(b.y - a.y, b.x - a.x) % math.pi
            off = Vec(math.cos(ang), math.sin(ang)).perp().dot(a - c)
            for g in found:
                if abs((g.ang - ang + 0.1) % math.pi - 0.1) < 1e-3 and abs(g.off - off) < 10:
                    g.off = (g.off + off) / 2
                    g.edges.append((a, b))
                    break
            else:
                found.append(Guide(ang, off, [(a, b)]))
    return found


def strands(g: BaseGeometry) -> list[LineString]:
    """The line parts of `g` longer than 2 units; shorter ones are boolean slivers."""
    return [q for q in parts(g) if isinstance(q, LineString) and q.length > 2]


class Drawing(Params):
    dimensions: bool = knob(default=True, doc="the overall width and one bar's width")


@design(aspects="any", variants={"undimensioned": Drawing(dimensions=False)})
def draw(s: Canvas[Drawing]) -> None:
    c = s.pick(landscape=(31 / 48, 0.5), portrait=(0.5, 0.42))
    polys = [[Affine.frame(c, deg=60 * k, scale=U)(v) for v in LAMBDA] for k in range(6)]
    bars = unary_union([Polygon(p) for p in polys]).buffer(2.5, join_style="mitre")
    void = Polygon(ngon(c, HEX * U / math.cos(math.pi / 6) - 1, 6, deg=30))
    field = Point(c.x, c.y).buffer(FADE, quad_segs=128)
    inner = Point(c.x, c.y).buffer(R - 1, quad_segs=128)

    # construction: every edge extended to the fading field, less where it crosses a bar
    lines = P()
    for g in guides(polys, c):
        d = Vec(math.cos(g.ang), math.sin(g.ang))
        o = c + d.perp() * g.off
        runs = LineString([o - d * 2 * FADE, o + d * 2 * FADE]).intersection(field)
        runs = runs.difference(bars)
        if abs(abs(g.off) - HEX * U) < 10:  # the six lines framing the void are kept whole
            keep = strands(runs)
        else:
            # inside the circle, keep only runs that leave a bar's end, not lattice fill
            ends = [Point(v.x, v.y).buffer(4) for e in g.edges for v in e]
            keep = [
                q
                for q in strands(runs.difference(void))
                if not q.within(inner) or any(q.intersects(e) for e in ends)
            ]
        for q in keep:
            lines.poly(q.coords)
    fade = s.radial_gradient([(0, BG_ALT), (R * 1.2 / FADE, BG_ALT), (1, BG)], c, FADE)
    s.stroke(lines, fade, 1.2)

    # center lines and the circumscribed circle
    cl = P()
    for k in range(3):
        cl.M(polar(c, R + 60, deg=60 * k)).L(polar(c, R + 60, deg=60 * k + 180))
    s.stroke(cl.circle(c, R), UI, 1.2, dash=DASHDOT)

    if s.params.dimensions:
        # dimensions: the overall width below, and the picked-out lambda's foot (one bar wide)
        # above it, with the arrows outside
        ext, dl, heads = P(), P(), P()
        yd = c.y + R + 80
        for x in (c.x - R, c.x + R):
            ext.M(x, c.y + 14).V(yd + 12)
        dl.M(c.x - R, yd).H(c.x + R)
        heads.arrowhead((c.x + R, yd), ARROW, deg=0, width=ARROW_W)
        heads.arrowhead((c.x - R, yd), ARROW, deg=180, width=ARROW_W)
        (x1, yf), x0 = polys[0][1], polys[0][2].x
        yc = yd - 36
        for x in (x0, x1):
            ext.M(x, yf + 12).V(yc + 12)
        dl.M(x0 - 34, yc).H(x0).M(x1, yc).H(x1 + 34)
        heads.arrowhead((x0, yc), ARROW, deg=0, width=ARROW_W)
        heads.arrowhead((x1, yc), ARROW, deg=180, width=ARROW_W)
        s.stroke(ext, UI, 1.2)
        s.stroke(dl, UI_ALT, 1.2)
        s.fill(heads, UI_ALT)

    # the first lambda carries the accent; the rest alternate UI and UI_ALT
    with s.buckets((ACCENT, UI, UI_ALT), "fill") as b:
        for k, p in enumerate(polys):
            b[0 if k == 0 else 2 - k % 2].poly(p, closed=True)
