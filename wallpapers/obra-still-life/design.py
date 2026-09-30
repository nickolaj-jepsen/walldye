"""Plaster cube, sphere, cone and cylinder on a table, ray-cast and dithered into square cells."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, ACCENT_3, ACCENT_6, BG_ALT, UI, UI_ALT, UI_HI, Canvas, Vec, design
from walldye.field import cells, falloff
from walldye.pixel import dither, grid_runs

type F = NDArray[np.float64]
type Hit = tuple[F, F]  # distance along each ray (inf for a miss) and the unit normal there

CELL = 3
# Screen-space constants below are in a 1920x1080 view; s.pick puts ANCHOR (0.7 across,
# mid-height) where the layout wants it, which shifts the lens without moving the camera.
ANCHOR = Vec(1344, 540)
RIGHT = 756  # the most view the landscape layout shows right of ANCHOR
CAM = np.array([960.0, 900.0, -2400.0])  # x, height, z
FOCAL, PITCH, HORIZON = 2300.0, math.radians(14), 560  # focal length, tilt, view y of the axis
WALL_Z, TABLE_X = 900, 560  # the back wall's depth; the table's left end
EDGE_Z = -120  # the table's front edge, well in front of the cone's base
L = np.array([-0.8, 0.5, -0.45]) / np.linalg.norm([-0.8, 0.5, -0.45])  # towards the light
INF = np.inf

# Surface ids: 0 wall below the table top, 1 wall, 2 table, 3 cube, 4 sphere, 5 cylinder, 6 cone.
CUBE = (1110, 330, 135, math.radians(30))  # center x, z, half size, yaw
SPHERE = (1600, 125, 260, 125)  # x, y, z, r
CYL = (1900, 720, 82, 330)  # x, z, r, h
CONE = (1390, 120, 100, 380)  # x, z, base r, h

# Palette: 0 nothing, 1-4 the tone steps, 5-7 the accent ramp for the cone's lit face.
PALETTE = (None, BG_ALT, UI, UI_ALT, UI_HI, ACCENT_6, ACCENT_3, ACCENT)
OUTLINE = 3


def hit_box(o: F, d: F, cx: float, cz: float, hs: float, yaw: float) -> Hit:
    """Rays against a cube of half size `hs` standing on the table, turned by `yaw`."""
    c, s = math.cos(yaw), math.sin(yaw)
    rot = np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
    lo = (o - np.array([cx, hs, cz])) @ rot.T
    ld = d @ rot.T
    with np.errstate(divide="ignore", invalid="ignore"):
        t1, t2 = (-hs - lo) / ld, (hs - lo) / ld
    tn, tf = np.minimum(t1, t2), np.maximum(t1, t2)
    tnear, tfar = tn.max(-1), tf.min(-1)
    t = np.where((tnear < tfar) & (tnear > 1e-3), tnear, INF)
    axis = tn.argmax(-1)[..., None]
    ln = np.zeros_like(ld)
    np.put_along_axis(ln, axis, -np.sign(np.take_along_axis(ld, axis, -1)), -1)
    return t, ln @ rot


def hit_sphere(o: F, d: F, cx: float, cy: float, cz: float, r: float) -> Hit:
    """Rays against a sphere of radius `r` centered on (cx, cy, cz)."""
    oc = o - np.array([cx, cy, cz])
    b = (oc * d).sum(-1)
    c = (oc * oc).sum(-1) - r * r
    disc = b * b - c
    t = np.where(disc > 0, -b - np.sqrt(np.maximum(disc, 0)), INF)
    t = np.where(t > 1e-3, t, INF)
    p = o + d * t[..., None]
    return t, (p - np.array([cx, cy, cz])) / r


def hit_cyl(o: F, d: F, cx: float, cz: float, r: float, h: float) -> Hit:
    """Rays against an upright cylinder of radius `r` and height `h`, with its top cap."""
    ox, oz, dx, dz = o[..., 0] - cx, o[..., 2] - cz, d[..., 0], d[..., 2]
    a = dx * dx + dz * dz
    b = ox * dx + oz * dz
    c = ox * ox + oz * oz - r * r
    disc = b * b - a * c
    with np.errstate(divide="ignore", invalid="ignore"):
        ts = (-b - np.sqrt(np.maximum(disc, 0))) / a
        y = o[..., 1] + d[..., 1] * ts
        ts = np.where((disc > 0) & (ts > 1e-3) & (y > 0) & (y < h), ts, INF)
        tc = (h - o[..., 1]) / d[..., 1]
    px, pz = ox + dx * tc, oz + dz * tc
    tc = np.where((tc > 1e-3) & (px * px + pz * pz < r * r), tc, INF)
    t = np.minimum(ts, tc)
    p = o + d * t[..., None]
    n = np.stack([(p[..., 0] - cx) / r, np.zeros_like(t), (p[..., 2] - cz) / r], -1)
    n = np.where((tc <= ts)[..., None], np.array([0.0, 1.0, 0.0]), n)
    return t, n


def hit_cone(o: F, d: F, cx: float, cz: float, rb: float, h: float) -> Hit:
    """Rays against an upright cone of base radius `rb` and height `h`, its side only."""
    k = (rb / h) ** 2
    ox, oy, oz = o[..., 0] - cx, o[..., 1] - h, o[..., 2] - cz  # apex-relative
    dx, dy, dz = d[..., 0], d[..., 1], d[..., 2]
    a = dx * dx + dz * dz - k * dy * dy
    b = ox * dx + oz * dz - k * oy * dy
    c = ox * ox + oz * oz - k * oy * oy
    disc = b * b - a * c
    sq = np.sqrt(np.maximum(disc, 0))
    best = np.full(a.shape, INF)
    with np.errstate(divide="ignore", invalid="ignore"):
        for t in ((-b - sq) / a, (-b + sq) / a):
            y = oy + dy * t
            ok = (disc > 0) & (t > 1e-3) & (y < 0) & (y > -h)
            best = np.where(ok & (t < best), t, best)
    p = o + d * best[..., None]
    px, py, pz = p[..., 0] - cx, p[..., 1] - h, p[..., 2] - cz
    n = np.stack([px, -k * py, pz], -1)
    with np.errstate(invalid="ignore"):
        n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9  # misses give nan; masked by t=inf
    return best, n


def view_y(z: float) -> float:
    """View y of the point on the table plane at depth `z` (every x lands on the same row)."""
    r = -CAM[1] / (z - CAM[2])  # the slope of the ray down to that point
    cp, sp = math.cos(PITCH), math.sin(PITCH)
    return float(HORIZON - FOCAL * (sp + r * cp) / (cp - r * sp))


APRON = view_y(EDGE_Z) + 76  # the apron's faint tone fades out this far below the lip


def solids(o: F, d: F) -> list[tuple[int, F, F]]:
    """(surface id, distance, normal) for each solid, for rays from `o` along `d`."""
    return [
        (3, *hit_box(o, d, *CUBE)),
        (4, *hit_sphere(o, d, *SPHERE)),
        (5, *hit_cyl(o, d, *CYL)),
        (6, *hit_cone(o, d, *CONE)),
    ]


@design(aspects=("16:9", "32:9", "9:19.5", "10:16"))
def draw(s: Canvas) -> None:
    # landscape: the group right of center, leaving the left free for windows, and never more
    # than RIGHT from the right edge, so the table still runs off it on ultrawide screens;
    # portrait: the group across the middle, a little above center and drawn smaller so it has
    # side margins. Whole cells, so the solids dither alike on every screen.
    a = s.pick(landscape=(0.7, 0.5), portrait=(0.53, 0.46), snap=CELL)
    zoom = 1.0 if s.landscape else 0.85
    if s.landscape:
        a = Vec(max(a.x, s.w - RIGHT), a.y)
    xs, ys = cells(s.inset(0), CELL)
    rows, cols = xs.shape
    sx, sy = ANCHOR.x + (xs - a.x) / zoom, ANCHOR.y + (ys - a.y) / zoom  # view coordinates
    cp, sp = math.cos(PITCH), math.sin(PITCH)
    vy, vz = HORIZON - sy, np.full(sx.shape, FOCAL)
    d = np.stack([sx - CAM[0], vy * cp - vz * sp, vy * sp + vz * cp], -1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    o = np.broadcast_to(CAM, d.shape)

    # Background planes: back wall, then the table top in front of it.
    t = (WALL_Z - o[..., 2]) / d[..., 2]
    ids = np.ones(t.shape, int)
    nrm = np.broadcast_to(np.array([0.0, 0.0, -1.0]), d.shape).copy()
    with np.errstate(divide="ignore"):
        tt = -o[..., 1] / d[..., 1]
    ptab = o + d * tt[..., None]
    on_table = (
        (tt > 0) & (ptab[..., 2] > EDGE_Z) & (ptab[..., 2] < WALL_Z) & (ptab[..., 0] > TABLE_X)
    )
    t = np.where(on_table, tt, t)
    ids[on_table] = 2
    nrm[on_table] = [0, 1, 0]
    for k, tk, nk in solids(o, d):
        closer = tk < t
        t = np.where(closer, tk, t)
        ids[closer] = k
        nrm[closer] = nk[closer]

    p = o + d * t[..., None]
    lam = np.nan_to_num(np.clip((nrm * L).sum(-1), 0, 1))
    lit = np.ones(t.shape, bool)
    for _, tk, _ in solids(p + nrm * 0.5, np.broadcast_to(L, d.shape)):
        lit &= ~np.isfinite(tk)
    light = lam * lit
    # solids ignore each other's cast shadows, whose hard edges read as dents, not shading
    soft = lam

    # Tone per surface: quiet surroundings that fade out to the left, brighter plaster solids.
    fade = np.clip((sx - 600) / 900, 0, 1) ** 1.5
    below = (ids == 1) & (p[..., 1] < 0)
    ids[below] = 0
    wall, tab, obj = ids == 1, ids == 2, ids >= 3
    spot = falloff(np.hypot((sx - 1380) / 1.6, sy - 640), 620)  # a pool of light behind the group
    # the table dissolves before the right edge, so its shadows are never cropped
    end = ANCHOR.x + (s.w - a.x) / zoom - 20
    edge_fade = np.clip((end - sx) / 260, 0, 1)
    # the table's front apron: a faint tone just under the lip, fading down and to the left
    apron = below & (sy < APRON)
    apron_tone = 0.13 * fade * edge_fade * np.clip((APRON - sy) / 140, 0, 1)
    nrm = np.nan_to_num(nrm)
    bounce = 0.16 * np.clip(-nrm[..., 1], 0, 1) + 0.1 * np.clip(nrm[..., 0], 0, 1)  # off the table
    solid_tone = 0.1 + bounce + 0.8 * soft**1.1

    tone = np.zeros(t.shape)
    if s.light:
        # On paper, ink the shade instead of the light: cast shadows on the table and wall,
        # the solids' turned-away sides, and blank paper wherever the light falls.
        tone[wall] = (0.24 * spot * fade * edge_fade * ~lit)[wall]
        tone[tab] = ((0.05 + 0.3 * ~lit) * fade * edge_fade)[tab]
        solid_tone = 0.85 * np.clip(1.08 - solid_tone, 0, 1)
    else:
        tone[wall] = ((0.03 + 0.2 * spot) * fade * (0.45 + 0.55 * lit))[wall]
        tone[tab] = ((0.08 + 0.34 * light) * fade * edge_fade)[tab]
    tone[apron] = apron_tone[apron]

    # Void-and-cluster grain over nothing, UI and UI_HI for the surroundings; the wall and the
    # apron never rise above BG_ALT.
    grid = np.array([0, 2, 4])[dither(tone, 3, method="bluenoise", rng=s.np_rng(3))]
    grid[(wall | apron) & (grid > 0)] = 1
    # Solids use an 8x8 Bayer screen over five tone steps, so the terminator steps down gently.
    grid[obj] = dither(solid_tone, 5, method="bayer", matrix=8)[obj]

    # The cone's lit face takes the accent ramp, mostly its dim steps; only the brightest band
    # reaches full ACCENT.
    cone_lit = (ids == 6) & (light > 0.3)
    glow = 0.75 * np.clip((light - 0.3) / 0.6, 0, 1) ** 1.6
    grid[cone_lit] = (5 + dither(glow, 3, method="bayer", matrix=8))[cone_lit]

    # Edge pass: surface-id or crease breaks, one cell wide, on the nearer side of each break.
    edge = np.zeros(t.shape, bool)
    for dy, dx in ((0, 1), (1, 0)):
        a_id, b_id = ids[: rows - dy, : cols - dx], ids[dy:, dx:]
        a_n, b_n = nrm[: rows - dy, : cols - dx], nrm[dy:, dx:]
        a_t, b_t = t[: rows - dy, : cols - dx], t[dy:, dx:]
        solid_break = (a_id != b_id) & ((a_id >= 3) | (b_id >= 3) | ((a_id == 2) & (b_id == 0)))
        crease = (a_id >= 3) & ((a_n * b_n).sum(-1) < 0.8)
        near = a_t <= b_t
        edge[: rows - dy, : cols - dx] |= (solid_break | crease) & near
        edge[dy:, dx:] |= (solid_break | crease) & ~near
    # curved solids lose their outline where lit; the cube keeps its creases
    edge &= ~(obj & (light > 0.25) & (ids != 3))
    grid[edge] = OUTLINE
    grid[edge & cone_lit] = 7

    grid_runs(s, grid, PALETTE, CELL)
