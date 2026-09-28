"""Le Mans at night from a camera tower: OSM road geometry projected and z-buffered into a dithered cell grid of woods, Armco and a braking car's light trail at Mulsanne corner."""

import itertools
import math

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree
from skimage.draw import polygon as fill_poly

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_4,
    ACCENT_HI,
    BG,
    BG_ALT,
    BG_DEEP,
    BLACK,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Paint,
    by_regime,
    design,
    ladder,
    mix,
)
from walldye.field import runs
from walldye.geom import Polyline
from walldye.pixel import dither, glyphs, grid_runs

type F64 = NDArray[np.float64]
type Mask = NDArray[np.bool_]

CELL, TC = 4, 2  # scene cell; finer cell for the light trail
PAD = 60  # how far past the frame edge vector strips and posts are kept
VX, VY = 820, 150  # vanishing point, low and left so the frame holds the corner
F, CAM_H = 1390, 40.0  # focal length; TV camera on a tower 210 m before the apex
# (east, north) metres from the D338/raceway junction, in driving order.
APPROACH = [(-52.3, 912.6), (-22.2, 410.7), (0, 0)]  # D338 Route de Tours, way 1505387926
# Virage de Mulsanne raceway, way 256130500.
CIRCUIT = [
    (-0.2, -8.9),
    (-0.6, -16.7),
    (-1.2, -25.0),
    (-1.7, -30.3),
    (-2.3, -36.2),
    (-2.9, -41.1),
    (-3.6, -45.4),
    (-4.4, -49.5),
    (-5.4, -53.8),
    (-7.2, -60.1),
    (-9.5, -68.5),
    (-34.0, -157.2),
    (-35.9, -162.7),
    (-37.3, -165.3),
    (-39.0, -167.2),
    (-41.6, -169.0),
    (-44.1, -170.4),
    (-46.8, -171.6),
    (-49.5, -172.2),
    (-52.2, -172.7),
    (-55.0, -172.7),
    (-58.0, -172.3),
    (-61.5, -171.4),
    (-96.9, -161.4),
]
# D338 straight on towards the Giratoire de Mulsanne (ways 34544562, 124251157), closed as the escape road.
ESCAPE = [(4, -68), (7, -97), (11, -132), (12.5, -142)]
HALF = 5.0  # road half-width
EDGE = (4.55, 4.7)  # solid edge line, lateral band
ARMCO = 6.3
FENCE = 6.8
TREES = 9.5
HC = 16.0  # canopy height
CAM_BACK = 210  # camera distance before the apex
CAR_BACK = 95  # at the 100 board, on the brakes
CAR_LAT = -1.8
CAM_LAT = -1.0
# Approach heading as a compass bearing in the (east, north) world frame, where y points up,
# so polar(bearing=) (screen, y down) does not apply.
BEARING = math.radians(176.8)
FWD = np.array([math.sin(BEARING), math.cos(BEARING)])
RGT = np.array([math.cos(BEARING), -math.sin(BEARING)])
BOARDS = (300, 200, 100)  # braking boards, metres before the apex
# Scene tones by dither level: tree gaps, shaded crowns, lit crowns and sky (the canvas), tarmac,
# lamplight. Light themes keep the night by sinking the whole ladder toward the foreground, so
# the woods stay the darkest mass and the lit road and lamp pool the palest.
NIGHT = by_regime(BG, UI)
SCENE = (
    by_regime(BLACK, UI_ALT),
    by_regime(BG_DEEP, mix(UI, UI_ALT, 0.4)),
    NIGHT,
    BG_ALT,
    by_regime(UI, BG),
)
# Lit metal reads paler than the dimmed canvas on light themes; the tyre wall stays a solid block.
RAIL, RAIL_HI = by_regime(UI, BG_ALT), by_regime(UI_ALT, BG)
TYRES = by_regime(UI, UI_ALT)
LAMP = by_regime(MUTED, BLACK)
TRAIL = ladder((BG, ACCENT_4, ACCENT), 5)


def road(
    raw: list[tuple[float, float]], extend: float = 0.0, sigma: float = 16
) -> tuple[F64, F64, F64, F64]:
    """The polyline `raw` in the approach frame (x right, y ahead), extended straight on by
    `extend` metres, resampled every 0.5 m and smoothed: arc lengths, points, unit tangents
    and right normals."""
    p = np.array(raw, float)
    loc = np.c_[p @ RGT, p @ FWD]
    if extend:
        d = loc[-1] - loc[-2]
        loc = np.vstack([loc, loc[-1] + d / np.hypot(d[0], d[1]) * extend])
    line = Polyline(loc)
    ss = np.arange(0, line.length, 0.5)
    xy = gaussian_filter1d(line.at(ss), sigma, axis=0, mode="nearest")
    t = np.gradient(xy, axis=0)
    t /= np.hypot(t[:, 0], t[:, 1])[:, None]
    return ss, xy, t, np.c_[t[:, 1], -t[:, 0]]


def dist_to(
    tree: cKDTree, c: F64, t: F64, n: F64, pts: F64, end_cap: bool = False
) -> tuple[F64, F64]:
    """Lateral offset of `pts` from the road (c, t, n) through its KD-tree, and how far past
    the road's last point each lies along it (0 elsewhere, and without `end_cap`)."""
    _, j = tree.query(pts)
    d = pts - c[j]
    lat = np.einsum("ij,ij->i", d, n[j])
    over = np.einsum("ij,ij->i", d, t[j]) if end_cap else np.zeros(len(pts))
    return lat, np.where(j == len(c) - 1, over, 0)


@design(bg=NIGHT)
def draw(s: Canvas) -> None:
    cols, rows = s.w // CELL, s.h // CELL
    ss, C, T, N = road(APPROACH + CIRCUIT, extend=500)
    es, EC, ET, EN = road(APPROACH + ESCAPE, sigma=8)
    ang = np.unwrap(np.arctan2(T[:, 0], T[:, 1]))
    apex = int(np.argmax(np.abs(np.gradient(ang))))
    ic = int(np.searchsorted(ss, ss[apex] - CAM_BACK))
    cam, fwd = C[ic] + N[ic] * CAM_LAT, T[ic]
    rgt = np.array([fwd[1], -fwd[0]])
    ctree, etree = cKDTree(C), cKDTree(EC)

    def cam_xz(p: F64) -> tuple[float, float]:
        d = p - cam
        return float(d @ rgt), float(d @ fwd)

    def proj(p: F64, a: float = 0.0) -> tuple[float, float, float]:
        """Screen x, y of world point `p` at height `a`, and its depth."""
        x, z = cam_xz(p)
        return VX + F * x / z, VY + F * (CAM_H - a) / z, z

    def lat_circuit(p: F64) -> F64:
        return dist_to(ctree, C, T, N, np.atleast_2d(p))[0]

    def on_circuit(p: F64) -> F64:
        return np.abs(lat_circuit(p))

    def on_escape(p: F64) -> F64:
        lat, over = dist_to(etree, EC, ET, EN, np.atleast_2d(p), end_cap=True)
        return np.where(over > 0.5, np.inf, np.abs(lat))

    # --- raster: z-buffered sky / forest / ground on the cell grid -------------------------
    zbuf = np.full((rows, cols), np.inf)
    kind = np.zeros((rows, cols), int)  # 0 sky, 1 ground, 2 canopy tops, 3 wall faces
    cy, cx = np.mgrid[0:rows, 0:cols]
    px, py = (cx + 0.5) * CELL, (cy + 0.5) * CELL
    below = py > VY
    zg = np.where(below, F * CAM_H / np.maximum(py - VY, 1e-6), np.inf)
    zbuf[below] = zg[below]
    kind[below] = 1

    r = s.np_rng(38)

    def canopy(n: int) -> F64:
        """Treeline heights for `n` wall points: overlapping domed crowns."""
        hs = np.zeros(n)
        k = 0
        while k < n:
            w = int(r.uniform(12, 30))
            top = r.uniform(15.5, 17.5) + (r.uniform(1.5, 3) if r.random() < 0.3 else 0)
            u = np.linspace(-1, 1, w)
            crown = top - 2.5 + 2.5 * np.sqrt(1 - u**2) + r.uniform(-0.6, 0.6, w)
            hs[k : k + w] = np.maximum(hs[k : k + w], crown[: len(hs[k : k + w])])
            k += w - int(r.uniform(3, 8))
        return hs

    # A few big standalone trees on the lawns by the Mulsanne houses, inside the corner.
    lawn_trees = cKDTree(
        np.array(
            [
                C[apex - 60] + N[apex - 60] * 30,
                C[apex - 180] + N[apex - 180] * 26,
                C[apex + 80] + N[apex + 80] * 34,
                C[apex - 120] + N[apex - 120] * 60,
                C[apex + 200] + N[apex + 200] * 24,
                C[apex - 250] + N[apex - 250] * 45,
            ]
        )
    )

    def in_lawn(p: F64) -> Mask:
        """Open ground: lawns inside the corner and the grass island between circuit and escape road."""
        pts = np.atleast_2d(p)
        lc = lat_circuit(pts)
        le, over = dist_to(etree, EC, ET, EN, pts, end_cap=True)
        _, j = ctree.query(pts)
        island = (lc < 0) & (le > 0) & (over < 6) & (j < apex)
        solo = lawn_trees.query(pts)[0] < 6
        return (((j > apex - 300) & (lc > 0) & (lc < 150)) | island) & ~solo

    def wall(pts: F64) -> None:
        """Forest wall along world polyline `pts`, skipping stretches that stand on either road."""
        hs = canopy(len(pts))
        clear = (on_circuit(pts) > TREES - 0.5) & (on_escape(pts) > TREES - 0.5) & ~in_lawn(pts)
        for i in range(len(pts) - 1):
            if not (clear[i] and clear[i + 1]):
                continue
            p0, p1 = pts[i], pts[i + 1]
            (_, z0), (_, z1) = cam_xz(p0), cam_xz(p1)
            if min(z0, z1) < 3:
                continue
            quad = [proj(p0, 0), proj(p1, 0), proj(p1, hs[i + 1]), proj(p0, hs[i])]
            qc = np.array([q[0] for q in quad]) / CELL
            qr = np.array([q[1] for q in quad]) / CELL
            if qc.max() < -1 or qc.min() > cols + 1:
                continue
            rr, cc = fill_poly(qr, qc, (rows, cols))
            z = (z0 + z1) / 2
            m = z < zbuf[rr, cc]
            zbuf[rr[m], cc[m]] = z
            kind[rr[m], cc[m]] = 2

    sel = slice(ic, None)
    wall(C[sel] + N[sel] * TREES)
    wall(C[sel] - N[sel] * TREES)
    je = int(np.searchsorted(es, ss[ic]))
    wall(EC[je:] - EN[je:] * TREES)
    wall(EC[je:] + EN[je:] * TREES)
    # Woods closing the escape road beyond the tyre wall.
    e0 = EC[-1] + ET[-1] * 10
    wall(np.array([e0 + EN[-1] * u for u in np.arange(-TREES, TREES, 0.5)]))

    # Canopy tops: the ray meets the crown plane before the ground wherever it is over the woods.
    zc = np.where(below, F * (CAM_H - HC) / np.maximum(py - VY, 1e-6), 1e9)
    wc = cam + ((px - VX) * zc / F)[..., None] * rgt + zc[..., None] * fwd
    flat = wc[below]
    wood = (on_circuit(flat) > TREES) & (on_escape(flat) > TREES) & ~in_lawn(flat)
    ctop = np.zeros((rows, cols), bool)
    ctop[below] = wood
    ctop &= zc < zbuf
    zbuf[ctop] = zc[ctop]
    kind[ctop] = 2
    kind[(kind == 2) & ~ctop] = 3

    # Ground: tarmac where within HALF of either road.
    gi = np.nonzero(kind == 1)
    xg = (px[gi] - VX) * zg[gi] / F
    wp = cam + np.outer(xg, rgt) + np.outer(zg[gi], fwd)
    road_m = np.zeros((rows, cols), bool)
    road_m[gi] = (on_circuit(wp) < HALF) | (on_escape(wp) < HALF)

    # Floodlight at the marshal post on the outside of the corner, and the pool it throws.
    lamp = C[apex] - N[apex] * 11.5 - T[apex] * 4
    lit = C[apex] - N[apex] * 4
    pool = np.zeros((rows, cols))
    pool[gi] = np.exp(-np.sum((wp - lit) ** 2, axis=1) / (2 * 24**2))

    # Moonlit crowns: jittered-grid tree centres, each a dome lit from the far side of the frame.
    g = np.mgrid[-300:400:6.5, -100:1000:6.5].reshape(2, -1).T
    tc_ = g + r.uniform(-2.2, 2.2, g.shape)
    tr_ = r.uniform(3.4, 4.8, len(tc_))
    wq = wc[ctop]
    dd, kk = cKDTree(tc_).query(wq, k=2)
    k = kk[:, 0]
    rel = (wq - tc_[k]) / tr_[k][:, None]
    gap = dd[:, 0] / tr_[k] > 0.92
    shade = np.where(gap, 0, np.where((rel @ np.array([0.5, 0.85])) > 0.2, 2, 1))
    near = zc[ctop] < 420

    val = np.zeros((rows, cols))
    skyt = np.clip(1 - (VY - py) / VY, 0, 1)
    val[kind == 0] = (0.5 + 0.06 * skyt**6)[kind == 0]
    depth = np.clip((py - VY) / (rows * CELL - VY), 0, 1)
    val[road_m] = (0.7 + 0.04 * depth + 0.55 * pool)[road_m]
    verge = (kind == 1) & ~road_m
    val[verge] = (0.26 + 0.6 * pool)[verge]
    # Tree faces: the deepest tone, catching a little track light at the foot, more near the lamp.
    face = kind == 3
    fz = zbuf[face]
    fh = CAM_H - (py[face] - VY) * fz / F
    fw = cam + ((px[face] - VX) * fz / F)[:, None] * rgt + fz[:, None] * fwd
    fpool = np.exp(-np.sum((fw - lit) ** 2, axis=1) / (2 * 40**2))
    val[face] = 0.08 + (0.1 + 0.35 * fpool) * np.exp(-np.maximum(fh, 0) / 5)
    lv = dither(np.minimum(val, 0.999), len(SCENE), method="bluenoise", rng=s.np_rng(3))
    # Woods posterised rather than dithered: crown clumps near by, a flat shaded mass far off.
    lv[ctop] = np.where(near, shade, 1)
    under = np.roll(kind, -1, axis=0)  # the kind of the cell beneath
    lv[ctop & (under != 2) & (under != 3)] = 2  # crown edge catching the track lights
    grid_runs(s, lv, SCENE, CELL, skip=2)

    def in_frame(x: float, y: float) -> bool:
        return -PAD <= x <= s.w + PAD and -PAD <= y <= s.h + PAD

    def visible(p: F64, a: float) -> bool:
        x, y, z = proj(p, a)
        c, rw = int(x // CELL), int(y // CELL)
        if z < 3:
            return False
        if not (0 <= c < cols and 0 <= rw < rows):
            return True
        return bool(zbuf[rw, c] >= z - 2 or kind[rw, c] < 2)

    def band(
        p0: F64,
        p1: F64,
        a0: float,
        a1: float,
        paint: Paint,
        keep: Mask | None = None,
        step: int = 4,
    ) -> None:
        """Filled strip between world polylines p0 (top, height a1) and p1 (bottom, height a0),
        broken wherever the woods hide it."""
        mids = [((p0[i] + p1[i]) / 2, (a0 + a1) / 2) for i in range(len(p0))]
        ok = np.array([visible(p, a) for p, a in mids])
        # Only the stretch in frame, plus one point past each end so the strip runs off it.
        seen = np.array([in_frame(*proj(p, a)[:2]) for p, a in mids])
        ok &= seen | np.r_[seen[1:], False] | np.r_[False, seen[:-1]]
        if keep is not None:
            ok &= keep
        d = P()
        for i, k in runs(ok):
            u = list(range(i, k, step)) + ([k - 1] if (k - 1 - i) % step else [])
            if len(u) > 1:
                top = [proj(p0[j], a1)[:2] for j in u]
                bot = [proj(p1[j], a0)[:2] for j in reversed(u)]
                d.poly(top + bot, closed=True)
        s.fill(d, paint)

    def posts(
        pts: F64,
        keep: Mask,
        every: int,
        a0: float,
        a1: float,
        width: float,
        paint: Paint,
        zmax: float,
    ) -> None:
        """Upright posts every `every` points of `pts`, from height a0 to a1, up to depth zmax."""
        d = P()
        for i in range(0, len(pts), every):
            if not keep[i]:
                continue
            p = pts[i]
            x0, y0, z = proj(p, a0)
            if z < 3 or z > zmax or not visible(p, (a0 + a1) / 2):
                continue
            y1 = proj(p, a1)[1]
            w = max(1.0, width * F / z)
            if in_frame(x0, y0) or in_frame(x0, y1):
                d.rect(x0 - w / 2, y1, w, y0 - y1)
        s.fill(d, paint)

    ca, ea = slice(ic + 4, None), slice(je + 4, None)
    Cc, Nc, Ec, Enc = C[ca], N[ca], EC[ea], EN[ea]
    # Barrier lines: the combined tarmac's outside edges, plus the island between the two roads.
    lines: list[tuple[float, F64, Mask]] = []
    for side in (-1, 1):
        for lat in (ARMCO, FENCE):
            pc, pe = Cc + Nc * side * lat, Ec + Enc * side * lat
            kc = on_escape(pc) > HALF + 1.2 if side < 0 else np.ones(len(pc), bool)
            lines.append((lat, pc, kc))
            lines.append((lat, pe, on_circuit(pe) > lat + 0.4))

    # Catch fence: dense wire mesh on close-set posts.
    for lat, p, k in lines:
        if lat != FENCE:
            continue
        for a in np.linspace(1.2, 3.8, 6):
            band(p, p, a, a + 0.04, BG_ALT, keep=k)
        posts(p, k, 6, 1.0, 3.9, 0.08, BG_ALT, 220)

    # Armco: triple-stacked W-rail on posts every 2 m.
    for lat, p, k in lines:
        if lat != ARMCO:
            continue
        band(p, p, 0.25, 1.05, RAIL, keep=k)
        for a in (0.25, 0.52, 0.79):
            band(p, p, a + 0.05, a + 0.13, RAIL_HI, keep=k)
        posts(p, k, 4, 0, 0.25, 0.12, RAIL_HI, 160)

    # Tyre wall across the end of the escape road.
    tw = np.array([EC[-1] + EN[-1] * u for u in np.linspace(-HALF - 1, HALF + 1, 24)])
    band(tw, tw, 0, 1.1, TYRES, step=1)
    band(tw, tw, 0.5, 0.6, BG_ALT, step=1)

    # Road markings: circuit edge lines (left one picks up after the fork), D338 dashed centre line.
    for side in (-1, 1):
        p0, p1 = Cc + Nc * side * EDGE[0], Cc + Nc * side * EDGE[1]
        k = on_escape(p0) > HALF + 0.3 if side < 0 else None
        band(p0, p1, 0, 0, UI_HI, keep=k, step=2)
    le0, le1 = Ec - Enc * EDGE[0], Ec - Enc * EDGE[1]
    band(le0, le1, 0, 0, UI_HI, keep=on_circuit(le0) > HALF + 0.3, step=2)
    # Kerb blocks on the inside of the corner.
    kerb = P()
    for i in range(apex - 70, apex + 50, 6):
        q = [
            proj(C[i] + N[i] * 4.4),
            proj(C[i + 3] + N[i + 3] * 4.4),
            proj(C[i + 3] + N[i + 3] * 5.4),
            proj(C[i] + N[i] * 5.4),
        ]
        if min(v[2] for v in q) > 3:
            kerb.poly([v[:2] for v in q], closed=True)
    s.fill(kerb, MUTED)
    dashes = P()
    fork = int(np.argmax(on_circuit(EC) > 1.0))
    for i in range(je + 4, fork, 26):
        j = i + 6
        q = [
            proj(EC[i] - EN[i] * 0.07),
            proj(EC[j] - EN[j] * 0.07),
            proj(EC[j] + EN[j] * 0.07),
            proj(EC[i] + EN[i] * 0.07),
        ]
        dashes.poly([v[:2] for v in q], closed=True)
    s.fill(dashes, UI_ALT)

    # Braking boards on the left verge of the D338; the ones behind the camera are skipped.
    s_ap = ss[apex]
    stems, boards = P(), P()
    numbers: list[tuple[str, float, float, int]] = []
    for dist in BOARDS:
        i = int(np.searchsorted(ss, s_ap - dist))
        j = int(etree.query(C[i])[1])
        p = EC[j] - EN[j] * (ARMCO + 1.0)
        x, yb, z = proj(p, 1.2)
        if z < 3:
            continue
        yt = proj(p, 2.6)[1]
        w = 1.8 * F / z
        stems.rect(
            round(x - max(1, 0.05 * F / z)),
            round(yb),
            max(1, round(0.1 * F / z)),
            round(proj(p, 0)[1] - yb),
        )
        boards.rect(round(x - w / 2), round(yt), round(w), round(yb - yt))
        numbers.append((str(dist), x, (yt + yb) / 2, max(1, int(w * 0.7 // 15))))
    s.fill(stems, UI_ALT)
    s.fill(boards, UI_HI)
    for label, x, y, gpx in numbers:
        glyphs(s, label, BG_DEEP, at=(round(x - 7.5 * gpx), round(y - 4 * gpx)), font="5x8", px=gpx)

    # Floodlight mast and marshal post.
    xl, yl0, zl = proj(lamp, 0)
    yl1 = proj(lamp, 9)[1]
    wl = max(1.0, 0.25 * F / zl)
    s.fill(P().rect(round(xl - wl / 2), round(yl1), max(1, round(wl)), round(yl0 - yl1)), RAIL)
    hw = max(3, round(1.4 * F / zl))
    s.fill(P().rect(round(xl - hw / 2), round(yl1 - 2), hw, 3), LAMP)
    mp = C[apex] - N[apex] * 9.5 - T[apex] * 14
    xm0, ym0, zm = proj(mp, 0)
    ym1 = proj(mp, 2.4)[1]
    wm = 2.4 * F / zm
    s.fill(P().rect(round(xm0 - wm / 2), round(ym1), round(wm), round(ym0 - ym1)), UI_ALT)
    hm = max(2, round((ym0 - ym1) * 0.25))
    s.fill(P().rect(round(xm0 - wm / 2), round(ym1 + (ym0 - ym1) * 0.3), round(wm), hm), MUTED)

    # Light trail: the light bar's two ends, from behind the camera's view to the braking car,
    # as a distance field on a TC grid around the ribbons.
    tcols, trows = s.w // TC, s.h // TC
    ica = int(np.searchsorted(ss, s_ap - CAR_BACK))
    trail = np.arange(ic + 40, ica + 1, 2)
    ribbons = [
        np.array([proj(C[i] + N[i] * (CAR_LAT + e), 0.8)[:2] for i in trail]) for e in (-0.85, 0.85)
    ]
    allp = np.vstack(ribbons)
    c0, r0 = max(int(allp[:, 0].min() // TC) - 6, 0), max(int(allp[:, 1].min() // TC) - 6, 0)
    c1 = min(int(allp[:, 0].max() // TC) + 7, tcols)
    r1 = min(int(allp[:, 1].max() // TC) + 7, trows)
    ty, tx = np.mgrid[0 : r1 - r0, 0 : c1 - c0]
    qx, qy = (tx + c0 + 0.5) * TC, (ty + r0 + 0.5) * TC
    field = np.zeros(qx.shape)
    tz = np.array([cam_xz(C[i] + N[i] * CAR_LAT)[1] for i in trail])
    tbu = np.zeros(qx.shape)
    for rib in ribbons:
        best = np.full(qx.shape, 1e9)
        bu = np.zeros(qx.shape)
        n = len(rib) - 1
        for k, (p, q) in enumerate(itertools.pairwise(rib)):
            dd = q - p
            L2 = dd @ dd + 1e-9
            tt = np.clip(((qx - p[0]) * dd[0] + (qy - p[1]) * dd[1]) / L2, 0, 1)
            dist = np.hypot(qx - p[0] - tt * dd[0], qy - p[1] - tt * dd[1])
            m = dist < best
            best[m] = dist[m]
            bu[m] = (k + tt[m]) / n
        sigma = 1.4 + 2.2 * (1 - bu)
        f = np.exp(-((best / sigma) ** 2) / 2) * 0.95 * bu**1.2
        tbu = np.where(f > field, bu, tbu)
        field = np.maximum(field, f)
    zr = zbuf[
        np.clip((qy // CELL).astype(int), 0, rows - 1),
        np.clip((qx // CELL).astype(int), 0, cols - 1),
    ]
    field[(zr < np.interp(tbu, [0, 1], [tz[0], tz[-1]]) - 5)] = 0  # nearer forest occludes
    tg = dither(field, len(TRAIL), method="atkinson")
    grid_runs(s, tg, TRAIL, TC, (c0 * TC, r0 * TC))

    # The car: full-width light bar plus the central rain light.
    xl, y, _ = proj(C[ica] + N[ica] * (CAR_LAT - 0.95), 0.8)
    xr = proj(C[ica] + N[ica] * (CAR_LAT + 0.95), 0.8)[0]
    xm = proj(C[ica] + N[ica] * CAR_LAT, 0.9)[0]
    cl, cr, rw = int(xl // TC), int(xr // TC), int(y // TC)
    s.fill(P().rect(cl * TC, (rw + 1) * TC, (cr - cl + 1) * TC, TC), ACCENT_3)
    s.fill(P().rect(cl * TC, rw * TC, (cr - cl + 1) * TC, TC), ACCENT)
    s.fill(P().rect((cl + 1) * TC, rw * TC, (cr - cl - 1) * TC, TC), ACCENT_HI)
    cm = int(xm // TC)
    s.fill(P().rect(cm * TC, (rw - 2) * TC, TC, TC * 2), ACCENT_HI)
