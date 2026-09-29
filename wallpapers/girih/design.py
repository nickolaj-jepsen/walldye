"""Hankin's polygons-in-contact star pattern on a 3.12.12 tiling, with one 12-fold star and two rings of faces around it inlaid."""

import math
from collections.abc import Iterator

from shapely import LineString, Point, unary_union
from shapely.ops import polygonize

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    BG,
    BG_ALT,
    Canvas,
    P,
    Rect,
    Vec,
    design,
    ladder,
    mix,
)
from walldye.geom import ngon

CELL = 196  # distance between neighboring dodecagon centers
SIDE = CELL / (2 + math.sqrt(3))  # the tiling's shared edge length
ROW = CELL * math.sqrt(3) / 2
R12, R3 = SIDE / (2 * math.sin(math.pi / 12)), SIDE / math.sqrt(3)  # circumradii
CONTACT = 60  # Hankin's contact angle between each ray and its edge, in degrees
SKIP = {12: 2, 3: 1}  # the ray from edge i meets the returning ray from edge i + SKIP
# the pattern line fades from BG_ALT at the inlay to a whisper at the far edges
LINES = ladder((BG_ALT, mix(BG, BG_ALT, 0.45)), 5)
INLAY = (ACCENT, ACCENT_3, ACCENT_5)  # the star, then each ring of faces around it

type Seg = tuple[Vec, Vec]


def tiling(c: Vec, area: Rect) -> Iterator[list[Vec]]:
    """The 3.12.12 polygons centered inside `area`, with a dodecagon centered on `c`."""
    for j in range(math.floor((area.y - c.y) / ROW), math.ceil((area.y1 - c.y) / ROW) + 1):
        lo = math.floor((area.x - c.x) / CELL - 0.5 * j)
        hi = math.ceil((area.x1 - c.x) / CELL - 0.5 * j)
        for i in range(lo, hi + 1):
            o = c + ((i + 0.5 * j) * CELL, j * ROW)
            if not area.contains(o):
                continue
            yield [Vec(x, y) for x, y in ngon(o, R12, 12, deg=15)]
            # the two gap triangles above-right and below-right of this center
            for dy, base in ((-1, 90), (1, -90)):
                g = o + (CELL / 2, dy * CELL / (2 * math.sqrt(3)))
                yield [Vec(x, y) for x, y in ngon(g, R3, 3, deg=base)]


def hankin(poly: list[Vec]) -> Iterator[Seg]:
    """Contact-angle rays from each edge midpoint, cut where each meets its partner ray."""
    n = len(poly)
    center = sum(poly[1:], poly[0]) / n
    mids: list[Vec] = []
    fwd: list[Vec] = []
    back: list[Vec] = []
    for a, b in zip(poly, poly[1:] + poly[:1], strict=True):
        m, e = (a + b) / 2, (b - a).unit()
        # turn each ray towards the polygon's inside
        turn = CONTACT if e.perp().dot(center - m) > 0 else -CONTACT
        mids.append(m)
        fwd.append(e.rotate(deg=turn))
        back.append((-e).rotate(deg=-turn))
    for i in range(n):
        j = (i + SKIP[n]) % n
        d, f = fwd[i], back[j]
        det = d.perp().dot(f)  # the cross product d x f
        if abs(det) < 1e-9:
            # collinear partner rays (the triangles at 60 degrees): one straight segment
            yield mids[i], mids[j]
            continue
        hit = mids[i] + d * ((mids[j] - mids[i]).perp().dot(f) / det)
        yield mids[i], hit
        yield mids[j], hit


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of center, below the middle on landscape; lower right of center on portrait
    c = s.pick(landscape=(0.71875, 11 / 18), portrait=(0.62, 0.6))
    segs = [seg for poly in tiling(c, s.inset(-CELL)) for seg in hankin(poly)]
    near = [LineString(seg) for seg in segs if min(abs(p - c) for p in seg) < CELL * 2]
    # snapping to a fine grid closes the float gaps where partner rays meet
    faces = list(polygonize(unary_union(near, grid_size=1e-3)))
    # rings of faces outward from the star: each ring shares an edge with the previous one
    ring = [k for k, f in enumerate(faces) if f.contains(Point(c))]
    used = set(ring)
    inlay: list[int] = []
    for tone in INLAY:
        d = P()
        for k in ring:
            d.shape(faces[k])
        s.fill(d, tone)
        inlay += ring
        ring = [
            k
            for k, f in enumerate(faces)
            if k not in used and any(f.intersection(faces[g]).length > 1 for g in ring)
        ]
        used.update(ring)
    with s.buckets(LINES, "stroke", stroke_width=1.5, stroke_linecap="round") as lines:
        for a, b in segs:
            # one rung fainter every 150 units beyond 300 from the star
            lines[LINES.rung((abs((a + b) / 2 - c) - 300) / 750)].M(a).L(b)
    # a crisp edge round the outer ring seats the rosette like an inlaid tile
    edge = P().shape(unary_union([faces[k] for k in inlay]))
    s.stroke(edge, ACCENT_4, 1.5, join="miter")
