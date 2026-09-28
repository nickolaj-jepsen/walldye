"""The Utah teapot as text-mode block art: a z-buffered lathe model shaded with half blocks and shade glyphs."""

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter

from walldye import ACCENT, ACCENT_3, BG_ALT, UI, UI_ALT, Canvas, Paint, by_regime, design
from walldye.geom import bezier_points
from walldye.pixel import glyphs, grid_runs

type Field = NDArray[np.float64]
type Mask = NDArray[np.bool_]
type Index = NDArray[np.int64]
type Profile = list[list[tuple[float, float]]]

PX = 2
CW, CH = 8 * PX, 16 * PX  # Spleen 8x16 at 2x; a half-cell is CW square
COLS, ROWS = 64, 25  # the character window the teapot and its steam are drawn in
POT = (544, 436)  # the teapot's axis, from the window's top-left
SCALE = 136  # px per teapot unit
SS = 6  # supersamples per half-cell edge
STEP = CW / SS
# Shadow to lit; on paper the two ends swap, so the lit side stays the paler one there too.
SHADOW, LIT = by_regime(BG_ALT, UI_ALT), by_regime(UI_ALT, BG_ALT)
SOLID = (SHADOW, UI, LIT)  # half-block paints, grid indices 1 to 3
GLOSS = by_regime(ACCENT, ACCENT_3)  # the glint; on paper a paler step, so it still reads as light
# 5-step ramp per character, shadow to lit: its solid paint and a shade glyph in LIT over it
RAMP_SOLID = np.array([0, 0, 0, 0, 2])
RAMP_GLYPH = np.array([" ", "░", "▒", "▓", " "])
LIGHT = np.array([-0.6, 0.55, 0.75]) / np.linalg.norm([-0.6, 0.55, 0.75])
SHEEN = np.array([-0.5, 0.1, 0.85]) / np.linalg.norm([-0.5, 0.1, 0.85])  # the glint faces this
SHINE = 220
GLINT = [0.28, 0.5, 0.72, 0.9]  # of the peak sheen: ░, ▒, ▓, then a solid cell
YAW, PITCH = np.radians(-18), np.radians(18)
BLUR = 8  # in supersamples
STEAM = ["    ░", "", "  ░", "", " ▒"]  # three puffs drifting up and to the right of the knob


def lathe(segs: Profile, n: int = 900, m: int = 160) -> Field:
    """Surface of revolution, (n, len(segs) * m, 3), from cubic Bézier (r, y) profile segments."""
    prof = np.concatenate([bezier_points(seg, m - 1) for seg in segs])
    prof[:, 0] = np.maximum(prof[:, 0], 0.03)  # keep normals defined on the axis
    a = np.linspace(0, 2 * np.pi, n)[:, None]
    r, y = prof[:, 0], prof[:, 1]
    return np.stack([r * np.cos(a), np.broadcast_to(y, (n, len(prof))), r * np.sin(a)], -1)


def tube(
    centre: list[tuple[float, float]], r0: float, r1: float, flat: float = 1.0, n: int = 900
) -> Field:
    """Tube swept along a planar cubic Bézier in (x, y), radius r0 to r1, depth scaled by `flat`."""
    c = bezier_points(centre, 259)
    d = np.gradient(c, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    r = np.linspace(r0, r1, len(c))
    a = np.linspace(0, 2 * np.pi, n)[:, None, None]
    xy = c + nrm * (r[:, None] * np.cos(a))
    z = (r * flat)[None, :] * np.sin(a[..., 0])
    return np.concatenate([xy, z[..., None]], -1)


def surfaces() -> list[Field]:
    """Body, lid, handle and spout; the body and lid follow Newell's profile curves."""
    body = lathe(
        [
            [(1.4, 2.4), (1.3375, 2.53), (1.4375, 2.53), (1.5, 2.4)],
            [(1.5, 2.4), (1.75, 1.875), (2.0, 1.35), (2.0, 0.9)],
            [(2.0, 0.9), (2.0, 0.45), (1.5, 0.225), (1.5, 0.15)],
            [(1.5, 0.15), (1.0, 0.0), (0.4, 0.0), (0.0, 0.0)],
        ]
    )
    lid = lathe(
        [
            [(0.0, 3.15), (0.8, 3.15), (0.0, 2.85), (0.2, 2.7)],
            [(0.2, 2.7), (0.4, 2.55), (1.3, 2.55), (1.3, 2.4)],
        ]
    )
    handle = tube([(1.5, 2.1), (2.9, 2.3), (3.4, 1.5), (1.9, 0.7)], 0.17, 0.15, flat=1.6)
    spout = tube([(-1.6, 0.85), (-2.85, 0.95), (-2.35, 1.95), (-3.1, 2.3)], 0.44, 0.22)
    return [body, lid, handle, spout]


def render(w: int, h: int) -> tuple[Field, Field, Mask, Mask, Index]:
    """Supersampled z-buffer splat of the surfaces, each result (h, w): Lambert tone, specular
    tone, coverage, the lid knob, and part id (0 empty, 1 body, 2 lid, 3 handle, 4 spout)."""
    cy, sy, cp, sp = np.cos(YAW), np.sin(YAW), np.cos(PITCH), np.sin(PITCH)
    rot = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]]) @ np.array(
        [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    )
    zbuf = np.full((h, w), -np.inf)
    shade = np.zeros((h, w))
    spec = np.zeros((h, w))
    knob = np.zeros((h, w), bool)
    part = np.zeros((h, w), np.int64)
    for k, surf in enumerate(surfaces(), start=1):
        surf = surf - np.array([0, 1.55, 0])  # the axis origin sits mid-height
        n = np.cross(np.gradient(surf, axis=0), np.gradient(surf, axis=1))
        n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12
        pts = surf.reshape(-1, 3)
        p, n = pts @ rot.T, n.reshape(-1, 3) @ rot.T
        n[n[:, 2] < 0] *= -1  # face the viewer (+z)
        val = 0.05 + 0.95 * np.clip(n @ LIGHT, 0, 1)
        gl = np.clip(n @ SHEEN, 0, 1) ** SHINE * (k == 1)  # a sheen on the body only
        px = np.round((POT[0] + p[:, 0] * SCALE) / STEP).astype(int)
        py = np.round((POT[1] - p[:, 1] * SCALE) / STEP).astype(int)
        ok = (px >= 0) & (px < w) & (py >= 0) & (py < h)
        order = np.argsort(p[ok, 2])  # far to near, so the nearest point lands last
        xs, ys, zs = px[ok][order], py[ok][order], p[ok, 2][order]
        vs, gs, hs = val[ok][order], gl[ok][order], pts[ok, 1][order]
        front = zs > zbuf[ys, xs]
        xs, ys = xs[front], ys[front]
        zbuf[ys, xs], shade[ys, xs], part[ys, xs] = zs[front], vs[front], k
        spec[ys, xs] = gs[front]
        knob[ys, xs] = (k == 2) & (hs[front] > 1.1)  # the lid above y = 2.65
    return shade, spec, np.isfinite(zbuf), knob, part


def clean(m: Mask) -> Mask:
    """Drop half-cells with < 2 filled 4-neighbours and fill enclosed ones, so the outline has
    no stray steps."""
    for _ in range(2):
        p = np.pad(m, 1)
        nb = p[:-2, 1:-1].astype(int) + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]
        m = (m & (nb >= 2)) | (~m & (nb >= 4))
    return m


def despeckle(cell: Index) -> Index:
    """Two passes in which a level cell (-1 marks none) unlike all of its >= 2 level
    4-neighbours takes their median level."""
    for _ in range(2):
        p = np.pad(cell, 1, constant_values=-1)
        nb = np.stack([p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
        fix = (cell >= 0) & ((nb >= 0).sum(0) >= 2) & ~(nb == cell).any(0)
        if fix.any():
            cell = cell.copy()
            cell[fix] = np.nanmedian(np.where(nb[:, fix] >= 0, nb[:, fix], np.nan), 0)
    return cell


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Right of centre on a landscape screen, the upper middle on a portrait one; the axis snaps
    # to whole half-cells so the window's origin is a whole unit.
    origin = s.pick(landscape=(2 / 3, 14 / 27), portrait=(0.515, 0.44), snap=CW) - POT
    shade, spec, cov, knob, part = render(COLS * SS, ROWS * 2 * SS)
    # Blur the tone inside the silhouette only, into broad clean bands.
    shade = gaussian_filter(shade * cov, BLUR) / np.maximum(gaussian_filter(cov * 1.0, BLUR), 1e-6)

    def block(a: Field) -> Field:
        """Supersamples averaged into half-cells."""
        return a.reshape(ROWS * 2, SS, COLS, SS).mean(axis=(1, 3))

    c = block(cov.astype(np.float64))
    t = np.clip(block(shade * cov) / np.maximum(c, 1e-6), 0, 1)
    lv = np.minimum(4, (t * 5).astype(np.int64))
    on = clean(c >= 0.5)
    pid = part[SS // 2 :: SS, SS // 2 :: SS]
    # Seams: body half-cells touching the lid, handle or spout drop to the shadow level, like
    # an inked outline.
    near = np.zeros_like(on)
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        near |= np.roll(on & (pid > 1), (dr, dc), (0, 1))
    lv[on & (pid == 1) & near] = 0

    # A character whose two halves are both in and agree on seam-or-not takes one ramp step;
    # the rest (silhouette and seam edges) become half blocks in the nearest solid tone.
    ht, hb, lt, lb = on[0::2], on[1::2], lv[0::2], lv[1::2]
    full = ht & hb & ((lt == 0) == (lb == 0))
    cell = despeckle(np.where(full, (lt + lb) // 2, -1))
    step = np.maximum(cell, 0)
    half = np.where(
        np.repeat(full, 2, axis=0),
        np.repeat(RAMP_SOLID[step], 2, axis=0) + 1,
        np.where(on, (lv + 1) // 2 + 1, 0),
    )
    chars = np.where(full, RAMP_GLYPH[step], " ")

    # Glint: where the belly faces SHEEN the ramp carries on past the lit solid, in GLOSS shade
    # glyphs over LIT that close on a solid GLOSS core, as ANSI art blends one colour into the next.
    sheen = gaussian_filter(spec * cov, BLUR / 2) / np.maximum(
        gaussian_filter(cov * 1.0, BLUR / 2), 1e-6
    )
    g = block(sheen * cov) / np.maximum(c, 1e-6)
    g = (g[0::2] + g[1::2]) / 2
    gc = np.digitize(g / g.max(), GLINT) * full
    gh = np.repeat(gc, 2, axis=0)
    half = np.where(gh == 4, 4, np.where(gh > 0, 3, half))
    chars = np.where(gc > 0, RAMP_GLYPH[gc], chars)

    def ink(col: int, row: int, ch: str) -> Paint:
        """GLOSS for the glint's glyphs, LIT for the rest."""
        return GLOSS if gc[row, col] > 0 else LIT

    # Lid knob: flat mid tone, lit on its upper left.
    ks = np.argwhere((block(knob.astype(np.float64)) > 0.4) & on)
    half[ks[:, 0], ks[:, 1]] = 2
    chars[ks[:, 0] // 2, ks[:, 1]] = " "
    r0 = int(ks[:, 0].min())
    top = ks[ks[:, 0] == r0, 1]
    c0 = int(top.min())
    half[r0, top.max()] = 0  # round off the top-right corner
    half[[r0, r0, r0, r0 + 1, r0 + 1, r0 + 2], [c0, c0 + 1, c0 + 2, c0, c0 + 1, c0]] = 3

    grid_runs(s, half, [None, *SOLID, GLOSS], CW, origin)
    glyphs(s, ["".join(row) for row in chars], ink, at=origin, px=PX)
    glyphs(s, STEAM, UI, at=origin + (c0 * CW, (r0 // 2 - 6) * CH), px=PX)
