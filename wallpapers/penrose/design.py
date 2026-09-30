"""Penrose P3 rhomb tiling by Robinson-triangle deflation."""

from typing import Literal

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    BG,
    BG_ALT,
    Canvas,
    Params,
    Rect,
    Vec,
    design,
    knob,
    polar,
)


class Tiling(Params):
    tiles: Literal["rhombs", "kites"] = knob(
        default="rhombs", doc="P3 thin and thick rhombs, or P2 kites and darts"
    )


PHI = (1 + 5**0.5) / 2
EDGE = 42  # rhomb edge, and the long edge of a kite or dart
# Deflation rounds. The patch round the center repeats every 4 rounds, so 12 draws the same
# rhombs as 8 while the wheel (radius EDGE * PHI**12, about 13,500) covers any screen. For the
# kites, 11 rounds put five darts at the center (the star); 12 would put five kites there.
GENS = {"rhombs": 12, "kites": 11}
ORIGIN = Vec(0, 0)
# Fills, and per ring outward from the center vertex the (thin or kite, thick or dart) index
# into them; rings past these are outlines only.
FILLS = (ACCENT, ACCENT_1, ACCENT_3, ACCENT_5, ACCENT_6)
RING_FILLS = {"rhombs": ((1, 0), (1, 2), (4, 3)), "kites": ((0, 0), (2, 2), (4, 3))}
# Edges take the innermost ring they touch: BG_ALT seams on the fills, then the glow dissolves
# into accent outlines; every edge farther out is BG_ALT.
STROKES = (BG_ALT, BG, ACCENT_6, ACCENT_5)
RING_SEAMS = (0, 0, 1, 3, 2)

type Tri = tuple[int, Vec, Vec, Vec]  # kind, then corners A, B, C
type Key = tuple[float, float]
type Edge = tuple[Key, Key]


def near(t: Tri, view: Rect) -> bool:
    """Whether the bounding box of triangle `t` overlaps `view`."""
    xs, ys = (t[1].x, t[2].x, t[3].x), (t[1].y, t[2].y, t[3].y)
    return max(xs) > view.x and min(xs) < view.x1 and max(ys) > view.y and min(ys) < view.y1


def deflate(view: Rect, gens: int) -> list[Tri]:
    """Robinson triangles of a P3 tiling with rhomb edge EDGE round a five-fold vertex at the
    origin: Preshing's deflation of a wheel of ten half thin rhombs, `gens` times, keeping after
    each round only the triangles whose box overlaps `view`. Kind 0 is half a thin rhomb and 1
    half a thick one; each pairs with its mirror image across BC."""
    r = EDGE * PHI**gens
    tris: list[Tri] = []
    for i in range(10):
        b, c = (polar(ORIGIN, r, deg=(2 * i + k) * 18) for k in (-1, 1))
        tris.append((0, ORIGIN, c, b) if i % 2 == 0 else (0, ORIGIN, b, c))
    for _ in range(gens):
        out: list[Tri] = []
        for kind, a, b, c in tris:
            if kind == 0:
                p = a + (b - a) / PHI
                out += [(0, c, p, b), (1, p, c, a)]
            else:
                q, rr = b + (a - b) / PHI, b + (c - b) / PHI
                out += [(1, rr, c, a), (1, q, rr, b), (0, rr, q, a)]
        tris = [t for t in out if near(t, view)]
    return tris


def kites(tris: list[Tri]) -> list[Tri]:
    """The P2 tiling that P3 triangles imply: each half thick rhomb splits into half a kite and
    half a dart. Every half comes back as (kind, C, A, B), kind 0 for a kite and 1 for a dart,
    so that it pairs with its mirror image across its last two corners, as `deflate`'s do."""
    out: list[Tri] = []
    for kind, a, b, c in tris:
        if kind == 0:
            out.append((0, c, a, b))
        else:
            r = b + (c - b) / PHI
            out += [(0, r, b, a), (1, a, r, c)]
    return out


def key(v: Vec) -> Key:
    return round(v.x, 1), round(v.y, 1)


def edge(u: Vec, v: Vec) -> Edge:
    a, b = key(u), key(v)
    return (a, b) if a <= b else (b, a)


def trails(edges: list[Edge]) -> list[list[Key]]:
    """`edges` joined end to end into polylines by a greedy walk, each edge used once; drawn
    with round caps and joins they look exactly like the separate edges, in about half the
    bytes."""
    links: dict[Key, list[Key]] = {}
    for a, b in edges:
        links.setdefault(a, []).append(b)
        links.setdefault(b, []).append(a)
    used: set[Edge] = set()

    def walk(p: Key) -> list[Key]:
        out: list[Key] = []
        while (q := next((q for q in links[p] if (p, q) not in used), None)) is not None:
            used.update(((p, q), (q, p)))
            out.append(q)
            p = q
        return out

    lines: list[list[Key]] = []
    for a, b in edges:
        if (a, b) not in used:
            used.update(((a, b), (b, a)))
            lines.append([*reversed(walk(a)), a, b, *walk(b)])
    return lines


@design(aspects="any", variants={"kites": Tiling(tiles="kites")})
def draw(s: Canvas[Tiling]) -> None:
    kind_of = s.params.tiles
    # right of center in the upper half on a landscape screen, the upper third on a portrait one
    c = s.pick(landscape=(1340 / 1920, 420 / 1080), portrait=(0.62, 0.36), snap=1)
    # the tiling is built round the origin, so the canvas is shifted by -c and grown by two edges
    view = s.inset(-2 * EDGE)
    view = Rect(view.x - c.x, view.y - c.y, view.w, view.h)
    tris = deflate(view, GENS[kind_of])
    if kind_of == "kites":
        tris = kites(tris)

    halves: dict[tuple[int, Edge], list[Tri]] = {}
    for t in tris:
        halves.setdefault((t[0], edge(t[2], t[3])), []).append(t)
    # (kind, corners); unpaired halves past the canvas edge stay triangles
    tiles: list[tuple[int, list[Vec]]] = []
    for (kind, _), hs in halves.items():
        _, a, b, cc = hs[0]
        tiles.append((kind, [a, b, hs[1][1], cc] if len(hs) == 2 else [a, b, cc]))
    by_edge: dict[Edge, list[int]] = {}
    for i, (_, quad) in enumerate(tiles):
        for u, v in zip(quad, quad[1:] + quad[:1], strict=True):
            by_edge.setdefault(edge(u, v), []).append(i)

    # rings by edge adjacency, from the tiles meeting at the center vertex
    ring = {i: 0 for i, (_, q) in enumerate(tiles) if min(abs(v) for v in q) < 1}
    front = list(ring)
    for n in range(1, len(RING_SEAMS)):
        nxt: list[int] = []
        for i in front:
            q = tiles[i][1]
            for u, v in zip(q, q[1:] + q[:1], strict=True):
                for j in by_edge[edge(u, v)]:
                    if j not in ring:
                        ring[j] = n
                        nxt.append(j)
        front = nxt

    tones = RING_FILLS[kind_of]
    with s.buckets(FILLS, "fill") as fills:
        for i, n in ring.items():
            kind, quad = tiles[i]
            if n < len(tones):
                fills[tones[n][kind]].poly([c + v for v in quad], closed=True)
    seams: list[list[Edge]] = [[] for _ in STROKES]
    for e in sorted(by_edge):
        n = min(ring.get(i, len(RING_SEAMS)) for i in by_edge[e])
        seams[RING_SEAMS[n] if n < len(RING_SEAMS) else 0].append(e)
    with s.buckets(
        STROKES, "stroke", stroke_width=1.2, stroke_linecap="round", stroke_linejoin="round"
    ) as lines:
        for i, group in enumerate(seams):
            for line in trails(group):
                lines[i].poly([c + p for p in line])
