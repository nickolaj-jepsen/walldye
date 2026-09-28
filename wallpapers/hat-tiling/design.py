"""An aperiodic monotile grown by substitution; one supertile is inlaid, its odd tiles solid."""

import math
from collections.abc import Iterator
from typing import Literal

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_4,
    ACCENT_7,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    Canvas,
    P,
    Params,
    Vec,
    by_regime,
    design,
    knob,
    ladder,
    mix,
)
from walldye.geom import Affine


class Tiling(Params):
    tile: Literal["hat", "spectre"] = knob(
        default="hat", doc="the hat, with mirrored copies, or the spectre, with none"
    )


LEVELS = 5  # substitution rounds, enough to cover 32:9 for either tile
HR3 = math.sqrt(3) / 2
HAT_SCALE = 26  # px per unit of the hat's hex grid
SPECTRE_SCALE = 22  # px per spectre edge
ANCHOR = (-400, -160)  # the inlaid supertile is the one nearest this point of the unshifted tiling
MARGIN = 78  # tiles this far past the canvas edge are still drawn (three hat-grid units)
JITTER = 60  # px of noise on each tile's distance, so the tone bands do not read as rings
# outlines settle from UI next to the inlay to a quiet far field, one step per 175 px past 200 px
LINES = ladder((UI, mix(BG, BG_ALT, 0.5)), 5)
LINE_START, LINE_STEP = 200, 175
# odd tiles are shaded, deepest next to the inlay, out to SHADE_R; BG_DEEP is paler than BG on
# light themes, so there the shade leans towards BG_ALT instead
RECESS = by_regime(BG_DEEP, BG_ALT)
SHADES = ladder((mix(RECESS, BG, 0.3), mix(RECESS, BG, 0.85)), 4)
SHADE_R = 600


def hexpt(x: float, y: float) -> Vec:
    """A point of the hex grid, in units where neighbouring hex centres are 1 apart."""
    return Vec(x + 0.5 * y, HR3 * y)


HAT = [
    hexpt(x, y)
    for x, y in (
        (0, 0),
        (-1, -1),
        (0, -2),
        (2, -2),
        (2, -1),
        (4, -2),
        (5, -1),
        (4, 0),
        (3, 0),
        (2, 2),
        (0, 3),
        (0, 2),
        (-1, 2),
    )
]

# The patch of 29 metatiles that the next level's hat supertiles are cut from (after hatviz).
# After child 0, an H at the origin, each rule (a, i, b, j, kind, k) adds a `kind` metatile
# whose edge from vertex k to k + 1 runs from vertex j of child b to vertex i of child a.
HAT_RULES = (
    (0, 0, 0, 1, "P", 2),
    (1, 0, 1, 1, "H", 2),
    (2, 0, 2, 1, "P", 2),
    (3, 0, 3, 1, "H", 2),
    (4, 4, 4, 5, "P", 2),
    (0, 4, 0, 5, "F", 3),
    (2, 4, 2, 5, "F", 3),
    (4, 1, 3, 2, "F", 0),
    (8, 3, 8, 4, "H", 0),
    (9, 2, 9, 3, "P", 0),
    (10, 2, 10, 3, "H", 0),
    (11, 4, 11, 5, "P", 2),
    (12, 0, 12, 1, "H", 2),
    (13, 0, 13, 1, "F", 3),
    (14, 2, 14, 3, "F", 1),
    (15, 3, 15, 4, "H", 4),
    (8, 2, 8, 3, "F", 1),
    (17, 3, 17, 4, "H", 0),
    (18, 2, 18, 3, "P", 0),
    (19, 2, 19, 3, "H", 2),
    (20, 4, 20, 5, "F", 3),
    (20, 0, 20, 1, "P", 2),
    (22, 0, 22, 1, "H", 2),
    (23, 4, 23, 5, "F", 3),
    (23, 0, 23, 1, "F", 3),
    (16, 0, 16, 1, "P", 2),
    (9, 4, 0, 2, "T", 2),
    (4, 0, 4, 1, "F", 3),
)

# the spectre, Tile(1, 1): fourteen unit edges, all turning by multiples of 30 degrees
SPECTRE = [
    Vec(0, 0),
    Vec(1, 0),
    Vec(1.5, -HR3),
    Vec(1.5 + HR3, 0.5 - HR3),
    Vec(1.5 + HR3, 1.5 - HR3),
    Vec(2.5 + HR3, 1.5 - HR3),
    Vec(3 + HR3, 1.5),
    Vec(3, 2),
    Vec(3 - HR3, 1.5),
    Vec(2.5 - HR3, 1.5 + HR3),
    Vec(1.5 - HR3, 1.5 + HR3),
    Vec(0.5 - HR3, 1.5 + HR3),
    Vec(-HR3, 1.5),
    Vec(0, 1),
]
SPECTRE_KINDS = ("Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Phi", "Psi")
# The spectre substitution from the chiral monotile paper: the eight slots of each supertile
# (Gamma leaves one empty), and the (turn in degrees, from key point, to key point) steps that
# place the slots.
SPECTRE_RULES = {
    "Gamma": ("Pi", "Delta", None, "Theta", "Sigma", "Xi", "Phi", "Gamma"),
    "Delta": ("Xi", "Delta", "Xi", "Phi", "Sigma", "Pi", "Phi", "Gamma"),
    "Theta": ("Psi", "Delta", "Pi", "Phi", "Sigma", "Pi", "Phi", "Gamma"),
    "Lambda": ("Psi", "Delta", "Xi", "Phi", "Sigma", "Pi", "Phi", "Gamma"),
    "Xi": ("Psi", "Delta", "Pi", "Phi", "Sigma", "Psi", "Phi", "Gamma"),
    "Pi": ("Psi", "Delta", "Xi", "Phi", "Sigma", "Psi", "Phi", "Gamma"),
    "Sigma": ("Xi", "Delta", "Xi", "Phi", "Sigma", "Pi", "Lambda", "Gamma"),
    "Phi": ("Psi", "Delta", "Psi", "Phi", "Sigma", "Pi", "Phi", "Gamma"),
    "Psi": ("Psi", "Delta", "Psi", "Phi", "Sigma", "Psi", "Phi", "Gamma"),
}
SPECTRE_STEPS = ((60, 3, 1), (0, 2, 0), (60, 3, 1), (60, 3, 1), (0, 2, 0), (60, 3, 1), (-120, 3, 3))


class Meta:
    """A tile (no children) or a metatile: an outline, a kind, and children placed by affines."""

    def __init__(self, shape: list[Vec], kind: str) -> None:
        self.shape = shape
        self.kind = kind
        self.children: list[tuple[Affine, Meta]] = []

    def add(self, t: Affine, child: "Meta") -> None:
        self.children.append((t, child))

    def at(self, n: int, i: int) -> Vec:
        """Vertex i (wrapping) of child n, in this metatile's coordinates."""
        t, g = self.children[n]
        return t(g.shape[i % len(g.shape)])

    def recentre(self) -> None:
        """Move the origin to the mean of the outline's vertices."""
        c = sum(self.shape, Vec(0, 0)) / len(self.shape)
        self.shape = [p - c for p in self.shape]
        shift = Affine.translate(-c.x, -c.y)
        self.children = [(shift @ t, g) for t, g in self.children]


def seg_frame(p: Vec, q: Vec) -> Affine:
    """The similarity (no reflection) taking (0, 0) to p and (1, 0) to q."""
    d = q - p
    return Affine(d.x, d.y, -d.y, d.x, p.x, p.y)


def match_two(p1: Vec, q1: Vec, p2: Vec, q2: Vec) -> Affine:
    """The similarity taking segment p1-q1 onto segment p2-q2."""
    return seg_frame(p2, q2) @ seg_frame(p1, q1).inverse()


def intersect(p1: Vec, q1: Vec, p2: Vec, q2: Vec) -> Vec:
    """Where line p1-q1 crosses line p2-q2; ZeroDivisionError when they are parallel."""
    d1, d2 = q1 - p1, q2 - p2
    u = (d2.x * (p1.y - p2.y) - d2.y * (p1.x - p2.x)) / (d2.y * d1.x - d2.x * d1.y)
    return p1 + d1 * u


def hat_base() -> dict[str, Meta]:
    """The level-0 metatiles H, T, P and F, made of hats; each H holds one mirrored hat."""
    hat, hat1 = Meta(HAT, "hat"), Meta(HAT, "odd")
    ho = [Vec(0, 0), Vec(4, 0), Vec(4.5, HR3), Vec(2.5, 5 * HR3), Vec(1.5, 5 * HR3), Vec(-0.5, HR3)]
    h = Meta(ho, "H")
    h.add(match_two(HAT[5], HAT[7], ho[5], ho[0]), hat)
    h.add(match_two(HAT[9], HAT[11], ho[1], ho[2]), hat)
    h.add(match_two(HAT[5], HAT[7], ho[3], ho[4]), hat)
    h.add(Affine.translate(2.5, HR3) @ Affine.rotate(deg=120) @ Affine.scale(0.5, -0.5), hat1)
    t = Meta([Vec(0, 0), Vec(3, 0), Vec(1.5, 3 * HR3)], "T")
    t.add(Affine.translate(0.5, HR3) @ Affine.scale(0.5), hat)
    pair = Affine.translate(0, 2 * HR3) @ Affine.rotate(deg=-60) @ Affine.scale(0.5)
    p = Meta([Vec(0, 0), Vec(4, 0), Vec(3, 2 * HR3), Vec(-1, 2 * HR3)], "P")
    f = Meta([Vec(0, 0), Vec(3, 0), Vec(3.5, HR3), Vec(3, 2 * HR3), Vec(-1, 2 * HR3)], "F")
    for m in (p, f):
        m.add(Affine.translate(1.5, HR3) @ Affine.scale(0.5), hat)
        m.add(pair, hat)
    return {"H": h, "T": t, "P": p, "F": f}


def hat_patch(tiles: dict[str, Meta]) -> Meta:
    """The 29-metatile patch laid out by HAT_RULES."""
    ret = Meta([], "patch")
    ret.add(Affine.identity(), tiles["H"])
    for a, i, b, j, kind, k in HAT_RULES:
        n = tiles[kind]
        edge = match_two(n.shape[k], n.shape[(k + 1) % len(n.shape)], ret.at(b, j), ret.at(a, i))
        ret.add(edge, n)
    return ret


def hat_supertiles(pt: Meta) -> dict[str, Meta]:
    """The next level's H, T, P and F: outlines traced on the patch, holding its children."""
    bps1, bps2 = pt.at(8, 2), pt.at(21, 2)
    rbps = Affine.rotate(deg=-120, about=bps1)(bps2)
    p72, p252 = pt.at(7, 2), pt.at(25, 2)
    llc = intersect(bps1, rbps, pt.at(6, 2), p72)
    w = (pt.at(6, 2) - llc).rotate(deg=-60)
    ho = [llc, bps1, bps1 + w, pt.at(14, 2)]
    ho += [ho[3] - w.rotate(deg=-60), pt.at(6, 2)]
    a, b = ho[2], ho[1] + (ho[4] - ho[5])
    outlines = {
        "H": (ho, (0, 9, 16, 27, 26, 6, 1, 8, 10, 15)),
        "T": ([b, a.rotate(deg=-60, about=b), a], (11,)),
        "P": ([p72, p72 + (bps1 - llc), bps1, llc], (7, 2, 3, 4, 28)),
        "F": (
            [bps2, pt.at(24, 2), pt.at(25, 0), p252, p252 + (llc - bps1)],
            (21, 20, 22, 23, 24, 25),
        ),
    }
    out = {}
    for kind, (shape, kids) in outlines.items():
        m = Meta(shape, kind)
        for c in kids:
            m.add(*pt.children[c])
        m.recentre()
        out[kind] = m
    return out


def hat_tiling() -> Meta:
    """An H supertile LEVELS substitutions up."""
    tiles = hat_base()
    for _ in range(LEVELS):
        tiles = hat_supertiles(hat_patch(tiles))
    return tiles["H"]


def spectre_tiling() -> Meta:
    """A Delta supertile LEVELS substitutions up. Every spectre has the same handedness; the
    second spectre of each Gamma pair is the odd one, turned 30 degrees off the others."""
    tiles = {k: Meta(SPECTRE, k) for k in SPECTRE_KINDS}
    gamma = Meta([], "Gamma")
    gamma.add(Affine.identity(), Meta(SPECTRE, "Gamma1"))
    gamma.add(Affine.translate(*SPECTRE[8]) @ Affine.rotate(deg=30), Meta(SPECTRE, "odd"))
    tiles["Gamma"] = gamma
    quad = [SPECTRE[3], SPECTRE[5], SPECTRE[7], SPECTRE[11]]
    for _ in range(LEVELS):
        slots = [Affine.identity()]
        turn, rot, turned = 0, Affine.identity(), quad
        for step, src, dst in SPECTRE_STEPS:
            if step:
                turn += step
                rot = Affine.rotate(deg=turn)
                turned = [rot(q) for q in quad]
            d = slots[-1](quad[src]) - turned[dst]
            slots.append(Affine.translate(d.x, d.y) @ rot)
        # each level is mirrored, so the tiles come out all of one hand
        slots = [Affine.scale(-1, 1) @ t for t in slots]
        quad = [slots[6](quad[2]), slots[5](quad[1]), slots[3](quad[2]), slots[0](quad[1])]
        nxt = {}
        for kind, subs in SPECTRE_RULES.items():
            sup = Meta([], kind)
            for t, sub in zip(slots, subs, strict=True):
                if sub is not None:
                    sup.add(t, tiles[sub])
            nxt[kind] = sup
        tiles = nxt
    return tiles["Delta"]


def level(node: Meta, t: Affine, depth: int) -> Iterator[tuple[Affine, Meta]]:
    """The descendants `depth` levels below `node`, placed by `t`, depth first in child order."""
    if depth == 0:
        yield t, node
        return
    for c, child in node.children:
        yield from level(child, t @ c, depth - 1)


def leaves(node: Meta, t: Affine) -> Iterator[tuple[Affine, Meta]]:
    """The tiles under `node`, placed by `t`, depth first in child order."""
    if not node.children:
        yield t, node
        return
    for c, child in node.children:
        yield from leaves(child, t @ c)


@design(aspects="any", variants={"spectre": Tiling(tile="spectre")})
def draw(s: Canvas[Tiling]) -> None:
    # the inlay is a level-1 hat supertile (25 hats) or a level-2 spectre one (71 spectres)
    if s.params.tile == "hat":
        root, outline, scale, depth = hat_tiling(), HAT, HAT_SCALE, LEVELS - 1
    else:
        root, outline, scale, depth = spectre_tiling(), SPECTRE, SPECTRE_SCALE, LEVELS - 1

    # every tile, grouped by the supertile it belongs to
    maps: list[Affine] = []
    odd: list[bool] = []
    group: list[int] = []
    for g, (t1, sup) in enumerate(level(root, Affine.scale(scale), depth)):
        for t, tile in leaves(sup, t1):
            maps.append(t)
            odd.append(tile.kind == "odd")
            group.append(g)
    m = np.array([[t.a, t.b, t.c, t.d, t.e, t.f] for t in maps])
    ox, oy = np.array(outline).T
    polys = np.stack(
        [
            m[:, 0:1] * ox + m[:, 2:3] * oy + m[:, 4:5],
            m[:, 1:2] * ox + m[:, 3:4] * oy + m[:, 5:6],
        ],
        axis=2,
    )  # (tiles, vertices, 2)
    gid = np.array(group)
    polys -= polys.reshape(-1, 2).mean(axis=0)  # centre the tiling on the origin

    # the inlay: of the supertiles holding the most odd tiles, the one nearest ANCHOR, moved
    # onto the focal point ((560, 380) on 16:9)
    ngroups = gid[-1] + 1
    centres = np.array([polys[gid == g].mean(axis=(0, 1)) for g in range(ngroups)])
    counts = np.bincount(gid, weights=np.array(odd), minlength=ngroups)
    near = np.hypot(*(centres - ANCHOR).T)
    hot = int(np.argmin(np.where(counts == counts.max(), near, np.inf)))
    focus = s.pick(landscape=(560 / 1920, 380 / 1080), portrait=(0.36, 0.3))
    polys += focus - centres[hot]

    view = s.inset(-MARGIN)
    lo, hi = np.array([view.x, view.y]), np.array([view.x1, view.y1])
    shown = ((polys > lo) & (polys < hi)).all(axis=2).any(axis=1)
    dist = np.hypot(*(polys.mean(axis=1) - focus).T)

    rng = s.rng(3)
    fill, solid, inlay, cluster = P(), P(), P(), []
    with (
        s.buckets(SHADES, "fill") as shades,
        s.buckets(LINES, "stroke", stroke_width=1, stroke_linejoin="round") as lines,
    ):
        for i in np.flatnonzero(shown):
            poly = polys[i]
            if gid[i] == hot:
                (solid if odd[i] else fill).poly(poly, closed=True)
                inlay.poly(poly, closed=True)
                cluster.append(Polygon(poly).buffer(0.3, join_style="mitre"))
                continue
            d = dist[i] + rng.uniform(-JITTER, JITTER)
            lines[LINES.rung((d - LINE_START) / (LINE_STEP * len(LINES)))].poly(poly, closed=True)
            if odd[i] and d < SHADE_R:
                shades[SHADES.rung(d / SHADE_R)].poly(poly, closed=True)
    s.fill(fill, ACCENT_7)
    s.fill(solid, ACCENT)
    s.stroke(inlay, ACCENT_4, 1.2, join="round")
    # one union outline, so the supertile reads as a single inlay
    edge = unary_union(cluster).buffer(-0.3, join_style="mitre")
    s.stroke(P().shape(edge), ACCENT_3, 1.6, join="round")
