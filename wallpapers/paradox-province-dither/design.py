"""Europa Universalis IV on 11 November 1444: the game's province outlines rasterised into Bayer-dithered cells, Austria filled in and its trade flow to Venice lit."""

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from skimage.draw import polygon

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_5,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Colour,
    P,
    Paint,
    Path,
    Rect,
    Ref,
    design,
)
from walldye.geom import Polyline, spline_points
from walldye.pixel import bayer, dither, glyphs, grid_runs, text_width

type Grid = NDArray[np.int64]
type Mask = NDArray[np.bool_]
type Province = tuple[int, str, list[Grid]]

CELL = 3
PLAYER, CAPITAL = "HAB", 134  # Austria's tag and Wien's province id
LIT = ("wien", "venice")  # the one trade leg picked out
TONES = (0.22, 0.30, 0.38, 0.26)  # Bayer coverage of the four country tones
DATE, SEG = "11 NOVEMBER 1444", 10  # the date box's text and speed-segment pitch
WING = 43  # chevron arms, degrees off the reversed flow direction
# Cell classes, in palette order: sea (index 0, left as the ground), sea specks, the four
# country tones, wasteland, Austria, the capital province, coastline, Austria's border ring.
SPECK, COUNTRY, WASTE, NATION, SEAT, COAST, BORDER = 1, 2, 6, 7, 8, 9, 10

# Trade node locations and control polylines from EU4's tradenodes (canvas px).
NODES = {
    "constantinople": (1955, 1116),
    "ragusa": (1252, 938),
    "rheinland": (629, 302),
    "wien": (1124, 479),
    "english_channel": (308, 41),
    "krakow": (1382, 291),
    "genua": (454, 1002),
    "venice": (966, 799),
    "saxony": (920, 163),
    "lubeck": (759, -43),
    "champagne": (289, 399),
}
END_NODES = ("english_channel", "genua", "venice")
LEGS: list[tuple[str, str, list[tuple[int, int]]]] = [
    (
        "constantinople",
        "ragusa",
        [(1955, 1116), (1808, 1087), (1641, 994), (1505, 990), (1386, 1008), (1252, 938)],
    ),
    (
        "ragusa",
        "wien",
        [(1252, 938), (1311, 889), (1320, 805), (1285, 713), (1258, 590), (1175, 537), (1124, 479)],
    ),
    ("ragusa", "venice", [(1252, 938), (1166, 920), (966, 799)]),
    (
        "ragusa",
        "genua",
        [
            (1252, 938),
            (1324, 1060),
            (1302, 1280),
            (1122, 1412),
            (1060, 1263),
            (810, 1109),
            (660, 880),
            (454, 1002),
        ],
    ),
    (
        "rheinland",
        "champagne",
        [(629, 302), (563, 260), (506, 216), (449, 207), (356, 242), (289, 399)],
    ),
    ("rheinland", "lubeck", [(629, 302), (678, 180), (730, 123), (713, 48), (757, -4), (759, -43)]),
    ("wien", "venice", [(1124, 479), (994, 528), (1003, 590), (972, 651), (966, 799)]),
    (
        "wien",
        "rheinland",
        [(1124, 479), (1025, 466), (906, 400), (845, 374), (682, 348), (642, 326), (629, 302)],
    ),
    ("wien", "saxony", [(1124, 479), (1016, 383), (1012, 317), (999, 246), (920, 163)]),
    ("krakow", "wien", [(1382, 291), (1364, 317), (1311, 370), (1245, 418), (1124, 479)]),
    ("krakow", "saxony", [(1382, 291), (1245, 255), (1184, 185), (1030, 123), (920, 163)]),
    (
        "krakow",
        "baltic_sea",
        [
            (1382, 291),
            (1307, 202),
            (1272, 158),
            (1298, 44),
            (1302, -66),
            (1399, -207),
            (1483, -496),
        ],
    ),
    ("saxony", "rheinland", [(920, 163), (889, 224), (748, 211), (686, 264), (629, 302)]),
    ("saxony", "lubeck", [(920, 163), (836, 154), (840, 53), (759, -43)]),
    (
        "lubeck",
        "english_channel",
        [(759, -43), (730, -40), (691, -26), (506, -53), (299, 62), (308, 41)],
    ),
    (
        "champagne",
        "genua",
        [(289, 399), (400, 453), (409, 616), (343, 682), (361, 796), (352, 902), (454, 1002)],
    ),
    (
        "champagne",
        "english_channel",
        [(289, 399), (273, 352), (255, 255), (286, 220), (312, 176), (308, 41)],
    ),
]


def provinces(text: str) -> list[Province]:
    """Parse provinces.txt: one province per line, "id owner ring | ring", each ring an absolute
    canvas point followed by deltas. Owner S is sea or lake, W wasteland."""
    out: list[Province] = []
    for line in text.strip().splitlines():
        pid, owner, rest = line.split(" ", 2)
        rings = [
            np.cumsum([[int(v) for v in p.split(",")] for p in ring.split()], axis=0)
            for ring in rest.split(" | ")
        ]
        out.append((int(pid), owner, rings))
    return out


def rasterise(provs: list[Province], cols: int, rows: int) -> Grid:
    """The (rows, cols) grid of province indices into `provs`; rings are XOR-filled, so a ring
    inside another cuts a hole."""
    label = np.full((rows, cols), -1, dtype=np.int64)
    for k, (_, _, rings) in enumerate(provs):
        mask = np.zeros((rows, cols), dtype=bool)
        for pts in rings:
            rr, cc = polygon(pts[:, 1] / CELL - 0.5, pts[:, 0] / CELL - 0.5, (rows, cols))
            mask[rr, cc] ^= True
        label[mask] = k
    # Simplification leaves hairline gaps between neighbours; give them to the nearest province.
    near = np.asarray(
        ndimage.distance_transform_edt(label < 0, return_distances=False, return_indices=True)
    )
    return label[near[0], near[1]]


def differs(a: NDArray[np.generic], both: bool = True) -> Mask:
    """Cells whose right or lower neighbour differs (a 1-cell seam); `both` also marks the
    other side."""
    d = np.zeros(a.shape, dtype=bool)
    h, v = a[:, 1:] != a[:, :-1], a[1:, :] != a[:-1, :]
    d[:, :-1] |= h
    d[:-1, :] |= v
    if both:
        d[:, 1:] |= h
        d[1:, :] |= v
    return d


def country_tones(owner: NDArray[np.str_], land: Mask) -> dict[str, int]:
    """Greedy-colour the country adjacency graph so neighbouring realms get different tones."""
    tags = sorted({str(t) for t in owner[land].tolist()})
    adj: dict[str, set[str]] = {t: set() for t in tags}
    for a, b in ((owner[:, 1:], owner[:, :-1]), (owner[1:, :], owner[:-1, :])):
        edge = a != b
        for x, y in set(zip(a[edge].tolist(), b[edge].tolist(), strict=True)):
            if x in adj and y in adj:
                adj[x].add(y)
                adj[y].add(x)
    tone: dict[str, int] = {}
    for t in sorted(tags, key=lambda t: -len(adj[t])):
        used = {tone[n] for n in adj[t] if n in tone}
        tone[t] = next(k for k in range(8) if k not in used)
    return tone


def bayer_tile(s: Canvas, v: float, paint: Colour) -> Ref:
    """A 4 x 4-cell pattern that fills the cells whose Bayer threshold is below `v`."""
    tile = P()
    for j, i in np.argwhere(bayer(4) < v).tolist():
        tile.rect(i * CELL, j * CELL, CELL, CELL)
    with s.pattern(4 * CELL, 4 * CELL) as pat:
        pat.fill(tile, paint)
    return pat.ref


def chevrons(
    d: Path,
    pts: list[tuple[int, int]],
    frame: Rect,
    pitch: float = 22,
    size: float = 6,
    clear: float = 14,
) -> None:
    """EU4's trade-map-mode flow: chevrons every `pitch` along the leg's spline, pointing
    downstream and at least `clear` from the node markers at both ends; those whose centre
    falls outside `frame` are skipped."""
    line = Polyline(spline_points(pts, 24))
    n = int((line.length - 2 * clear) // pitch)
    off = (line.length - n * pitch) / 2
    for k in range(n + 1):
        at = off + k * pitch
        p, t = line.at(at), line.tangent(at)
        if frame.contains(p):
            back = t * -size
            d.M(p + back.rotate(deg=-WING)).L(p + t * (0.45 * size)).L(p + back.rotate(deg=WING))


def hud(s: Canvas) -> None:
    """EU4's top-right date box: the date, then the five speed segments at speed 1."""
    w = text_width(DATE, font="5x8", px=2)
    x, y = s.w - 64 - w - 5 * SEG, 40
    s.path(P().rect(x - 14, y - 10, w + 5 * SEG + 30, 36), fill=BG, stroke=UI_ALT, stroke_width=1.5)
    glyphs(s, DATE, UI_HI, at=(x, y), font="5x8", px=2)
    x += w + 8
    slow = P()
    for k in range(1, 5):
        slow.rect(x + k * SEG, y + 1, 6, 14)
    s.fill(slow, UI)
    s.fill(P().rect(x, y + 1, 6, 14), ACCENT)


@design()
def draw(s: Canvas) -> None:
    text: str = s.data("provinces.txt")
    provs = provinces(text)
    label = rasterise(provs, s.w // CELL, s.h // CELL)
    owner = np.array([o for _, o, _ in provs])[label]
    pid = np.array([p for p, _, _ in provs])[label]
    sea = owner == "S"
    waste = owner == "W"
    land = ~sea & ~waste

    prov_seam = differs(label, both=False) & land
    realm_seam = differs(owner) & land & ~differs(land)
    body = land & ~prov_seam & ~realm_seam
    nation = owner == PLAYER

    cls = np.zeros(label.shape, dtype=np.int64)
    for t, k in country_tones(owner, land).items():
        cls[(owner == t) & body] = COUNTRY + k % len(TONES)
    speck = dither(np.where(sea, 0.04, 0.0), 2, method="bluenoise", rng=s.np_rng(2))
    cls[(speck == 1) & sea] = SPECK
    cls[waste & ~differs(label)] = WASTE
    cls[nation & body] = NATION
    cls[(pid == CAPITAL) & body] = SEAT
    square = np.ones((3, 3), dtype=np.int64)
    # Coast as a crisp 1-cell line so the Adriatic and the Italian boot read at a glance.
    cls[land & ndimage.binary_dilation(sea, square)] = COAST
    # Realm border: a 1-cell ring just inside the nation, like EU4's thick country outline.
    cls[nation & ~ndimage.binary_erosion(nation, square, border_value=1)] = BORDER

    # Dither tones as cell-aligned Bayer tiles, so each province is a handful of runs.
    palette: list[Paint | None] = [
        None,
        BG_ALT,
        *(bayer_tile(s, v, UI) for v in TONES),
        bayer_tile(s, 0.12, UI),
        bayer_tile(s, 0.3, ACCENT_5),
        bayer_tile(s, 0.55, ACCENT_5),
        UI_ALT,
        ACCENT_3,
    ]
    grid_runs(s, cls, palette, CELL)

    flows, lit = P(), P()
    for a, b, pts in LEGS:
        chevrons(lit if (a, b) == LIT else flows, pts, s.inset(0))
    s.stroke(flows, UI_HI, 1.5, join="miter")
    s.stroke(lit, ACCENT, 1.5, join="miter")

    # End nodes as ringed pips, the others as small squares; the lit leg's ends in the accent.
    rings, pips, marts = P(), P(), P()
    for k, (x, y) in NODES.items():
        if k in END_NODES:
            rings.circle((x, y), 9)
            if k != LIT[1]:
                pips.rect(x - 2.5, y - 2.5, 5, 5)
        elif k != LIT[0]:
            marts.rect(x - 3, y - 3, 6, 6)
    s.path(rings, fill=BG, stroke=UI_HI, stroke_width=1.5)
    s.fill(pips, UI_HI)
    vx, vy = NODES[LIT[1]]
    s.fill(P().rect(vx - 2.5, vy - 2.5, 5, 5), ACCENT)
    s.path(marts, fill=UI_HI, stroke=BG, stroke_width=1.5)
    cx, cy = NODES[LIT[0]]
    s.path(P().rect(cx - 5, cy - 5, 10, 10), fill=ACCENT, stroke=BG, stroke_width=1.5)

    hud(s)
