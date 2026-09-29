"""The Bonneville speed course from eye level: salt-crust polygons in perspective, a guide line to the vanishing point, one timed mile lit."""

from typing import TypedDict

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import Voronoi

from walldye import ACCENT, BG_ALT, UI, Canvas, P, Path, Rect, design
from walldye.geom import poisson_disk

type F64 = NDArray[np.float64]


class Skyline(TypedDict):
    heading: float  # the course, degrees from north
    az0: float  # bearing of the first sample, degrees
    step: float  # degrees between samples
    far: list[int]  # highest angle above eye level at any range, 1e-5 rad
    near: list[int]  # the same within 40 km


F = 1100  # focal length, canvas units
EYE = 1.7  # camera height, m
OFF = 4.0  # camera to the right of the guide line, m
LINE_W = 0.6  # painted width of the guide line, m
MARK = 25.0  # distance ahead to the two-mile marker, m
MILE = 1609.344
DIP = 6.8e-4  # the salt's horizon below eye level, rad: 5 km off, curvature less refraction
CRACK = (0.8, 2.3)  # Poisson radius of the polygon centres, m: polygons 1 to 3 m across
EDGE = MARK - 3  # cells reaching past this are left smooth, clear of the lit mile, m
NEAR = 12.0  # cells nearer than this are drawn a step louder, m


def spread(cand: F64, rad: F64) -> NDArray[np.intp]:
    """Indices of the points of `cand` kept greedily in order, each kept point at least the larger
    of its own and the other's `rad` from every other kept point."""
    size = float(rad.max())
    grid: dict[tuple[int, int], list[int]] = {}
    kept: list[int] = []
    for i, (x, z) in enumerate(cand):
        gx, gz = int(x // size), int(z // size)
        close = [
            j for dx in (-1, 0, 1) for dz in (-1, 0, 1) for j in grid.get((gx + dx, gz + dz), [])
        ]
        if all(np.hypot(*(cand[j] - cand[i])) >= max(rad[i], rad[j]) for j in close):
            grid.setdefault((gx, gz), []).append(i)
            kept.append(i)
    return np.array(kept)


@design(aspects="any")
def draw(s: Canvas) -> None:
    vp = s.pick(landscape=(0.66, 0.68), portrait=(0.58, 0.76))
    vx, vy = float(vp.x), float(vp.y)
    z0 = F * EYE / (s.h - vy) * 0.9
    half = max(vx, s.w - vx) / F + 0.05  # lateral reach per metre of depth

    def proj(x: F64, z: F64) -> tuple[F64, F64]:
        return vx + F * x / z, vy + F * EYE / z

    # Salt crust: Voronoi cells over the ground in front of the camera, sized by a slow noise,
    # whole cells only.
    zmax = EDGE + 3 * CRACK[1]
    za, xr = max(0.5, z0 - 3), half * zmax + 4
    cand = poisson_disk(Rect(-xr, za, 2 * xr, zmax - za), CRACK[0] * 0.9, s.rng(3))
    cand = cand[np.abs(cand[:, 0]) < half * cand[:, 1] + 4]
    cand = cand[s.np_rng(4).permutation(len(cand))]
    grain = s.noise(5).fbm(cand[:, 0] / 6, cand[:, 1] / 6, octaves=2)
    u = np.clip(np.clip(grain * 1.6 + 0.5, 0, 1) * s.np_rng(6).uniform(0.8, 1.2, len(cand)), 0, 1)
    rad = CRACK[0] + (CRACK[1] - CRACK[0]) * u
    kept = spread(cand, rad)
    seeds, rad = cand[kept], rad[kept]
    vor = Voronoi(seeds)
    whole = np.array([-1 not in e for e in vor.ridge_vertices])
    rv, rp = np.array(vor.ridge_vertices)[whole], vor.ridge_points[whole]
    a, b = vor.vertices[rv[:, 0]], vor.vertices[rv[:, 1]]
    # Clip ridges at a plane just ahead of the camera; what the clip removes is far below the frame.
    lo = 0.3
    for p0, p1 in ((a, b), (b, a)):
        cut = (p0[:, 1] < lo) & (p1[:, 1] > lo)
        k = (lo - p0[cut, 1]) / (p1[cut, 1] - p0[cut, 1])
        p0[cut] = p0[cut] + (p1[cut] - p0[cut]) * k[:, None]
    reach = np.array(
        [
            max((vor.vertices[v, 1] for v in vor.regions[r] if v >= 0), default=np.inf)
            for r in vor.point_region
        ]
    )
    shown = reach <= EDGE
    zs = np.where(shown, seeds[:, 1], np.inf)
    znear = np.minimum(zs[rp[:, 0]], zs[rp[:, 1]])  # the nearer drawn cell sets the tone
    on = np.isfinite(znear) & (np.minimum(a[:, 1], b[:, 1]) >= lo - 1e-9)
    # Fuse some neighbouring cells of one tone, so the crust is not one repeated polygon.
    used = ~shown
    loud_cell = zs < NEAR
    for i in s.np_rng(7).permutation(len(rp))[: len(rp) // 5]:
        p, q = rp[i]
        if not (used[p] or used[q]) and loud_cell[p] == loud_cell[q]:
            used[p] = used[q] = True
            on[i] = False
    ax, ay = proj(a[:, 0], a[:, 1])
    bx, by = proj(b[:, 0], b[:, 1])
    loud, quiet = P(), P()
    for i in np.nonzero(on)[0]:
        (loud if znear[i] < NEAR else quiet).M(ax[i], ay[i]).L(bx[i], by[i])
    s.stroke(quiet, BG_ALT, 1.2, cap="round")
    s.stroke(loud, UI, 1.2, cap="round")

    # Mountains across the flats, from the elevation model: bearing to angle above eye level.
    sky: Skyline = s.data("skyline.json")
    base = vy + F * DIP
    for layer, paint in ((sky["far"], BG_ALT), (sky["near"], UI)):
        alt = np.array(layer, float) * 1e-5
        phi = np.radians(sky["az0"] + sky["step"] * np.arange(len(alt)) - sky["heading"])
        on = np.abs(np.tan(phi)) * F < np.hypot(s.w, s.h)
        xs = vx + F * np.tan(phi[on])
        ys = vy - F * np.tan(np.maximum(alt[on], -DIP)) / np.cos(phi[on])
        outline = [(float(xs[0]), base), *zip(xs.tolist(), ys.tolist()), (float(xs[-1]), base)]
        s.fill(P().poly(np.array(outline), closed=True), paint)
    s.stroke(P().M(0, base).H(s.w), UI, 1.2)

    def strip(z_a: float, z_b: float) -> Path:
        xs = np.array([-OFF - LINE_W / 2, -OFF + LINE_W / 2])
        za, zb = np.full(2, z_a), np.full(2, z_b)
        (x0, y0), (x1, y1) = proj(xs, za), proj(xs[::-1], zb)
        return P().poly(np.c_[np.r_[x0, x1], np.r_[y0, y1]], closed=True)

    s.fill(strip(z0, MARK), UI)
    s.fill(strip(MARK, MARK + MILE), ACCENT)
