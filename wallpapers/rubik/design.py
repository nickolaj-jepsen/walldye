"""A Rubik's cube mid-turn, drawn as a patent figure with ruled shading."""

import math

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely import MultiPoint

from walldye import ACCENT, BG, UI, UI_ALT, UI_HI, Canvas, P, Path, Vec, design
from walldye.field import runs
from walldye.geom import Affine

S = 100  # cubie edge on screen
TURN = math.radians(-24)  # how far the top layer has turned
YAW, PITCH = math.radians(40), math.radians(30)
FACES = ((0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1))  # (axis, sign)
HOT = ((1, 1, 1), 1)  # (cubie, axis) of the one lit sticker
ORBIT_R, ORBIT_N = 2.6, 720  # turn arrow: orbit radius in cubies, samples round it


def rot_y(a: float) -> NDArray[np.float64]:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


VIEW = np.array(
    [[1, 0, 0], [0, math.cos(PITCH), -math.sin(PITCH)], [0, math.sin(PITCH), math.cos(PITCH)]]
) @ rot_y(YAW)


def project(p: NDArray[np.float64]) -> Vec:
    """Parallel projection of a cube-space point (y up) to the figure's screen space, cube center
    at the origin."""
    v = VIEW @ p
    return Vec(S * v[0], -S * v[1])


def face_quad(
    c: tuple[int, int, int], axis: int, sign: int, inset: float
) -> list[NDArray[np.float64]]:
    """Corners of cubie `c`'s face on `axis` at `sign`, shrunk about its center to `inset`."""
    u, v = [k for k in range(3) if k != axis]
    out = []
    for du, dv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        p = np.array(c, float)
        p[axis] += 0.5 * sign
        p[u] += 0.5 * du * inset
        p[v] += 0.5 * dv * inset
        out.append(p)
    return out


def rounded(d: Path, quad: list[Vec], r: float) -> None:
    """A quad with each corner cut back by fraction `r` of its edges and rounded with a
    quadratic curve."""
    n = len(quad)
    for i in range(n):
        p0, p1, p2 = quad[i - 1], quad[i], quad[(i + 1) % n]
        a, b = p1 + (p0 - p1) * r, p1 + (p2 - p1) * r
        (d.M if i == 0 else d.L)(a)
        d.Q(p1, b)
    d.Z()


def shade_lines(d: Path, quad: list[Vec], n: int = 4) -> None:
    """Patent shade lines across a sticker, crowding toward its shadowed edge."""
    a, b, c, e = quad
    for k in range(n):
        t = 0.9 - 0.55 * (k / (n - 1)) ** 1.4
        p, q = a + (b - a) * t, e + (c - e) * t
        m = (q - p) * 0.14
        d.M(p + m).L(q - m)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: where the 16:9 figure sat, right of center; portrait: larger and low, under
    # the clock, nudged left because the arrow widens the right side
    at = s.pick(landscape=(1240 / 1920, 520 / 1080), portrait=(0.48, 0.54))
    k = 1.0 if s.landscape else 1.3
    place = Affine.translate(at.x, at.y) @ Affine.scale(k)

    # The lower two layers, then the turned top layer; viewed from above, the top layer hides
    # the block beneath wherever they overlap. Each block is convex, so its front-facing
    # outer faces never overlap one another and need no depth sort.
    blocks = (((-1, 0), np.eye(3)), ((1,), rot_y(TURN)))
    sils = []
    with s.group(transform=place):
        for layer, rot in blocks:
            bodies, stickers, lit, hatch = P(), P(), P(), P()
            corners: list[Vec] = []
            for c in ((x, y, z) for x in (-1, 0, 1) for y in layer for z in (-1, 0, 1)):
                for axis, sign in FACES:
                    edge = min(layer) - 0.5 if sign < 0 else max(layer) + 0.5
                    outer = c[axis] == sign if axis != 1 else c[1] + 0.5 * sign == edge
                    n = rot @ np.eye(3)[axis] * sign
                    facing = (VIEW @ n)[2]
                    if not outer or facing <= 0:
                        continue
                    body = [project(rot @ p) for p in face_quad(c, axis, sign, 1.0)]
                    bodies.poly(body, closed=True)
                    corners += body
                    # no stickers on the block's cut face (inside the cube) or on faces seen
                    # too edge-on to read
                    if c[axis] != sign or facing < 0.2:
                        continue
                    quad = [project(rot @ p) for p in face_quad(c, axis, sign, 0.78)]
                    if (c, axis) == HOT:
                        rounded(lit, quad, 0.2)
                        continue
                    rounded(stickers, quad, 0.2)
                    # shade lines on faces turned away from the light (screen right)
                    if (VIEW @ n)[0] > 0.3:
                        shade_lines(hatch, quad)
            sil = MultiPoint(corners).convex_hull
            sils.append(sil)
            s.path(bodies, fill=BG, stroke=UI_HI, stroke_width=1.5, stroke_linejoin="round")
            s.stroke(stickers, UI_ALT, 1.4)
            s.path(lit, fill=ACCENT, stroke=ACCENT, stroke_width=1.4)
            s.stroke(hatch, UI, 1.2)
            s.stroke(P().shape(sil), UI_HI, 2.6, join="round")

        # Turn arrow hugging the top layer: the longest run of its orbit that clears the cube,
        # trimmed by an eighth at each end.
        solid = shapely.unary_union(sils).buffer(14)
        a = np.linspace(0, 2 * math.pi, ORBIT_N, endpoint=False)
        ring = np.stack([ORBIT_R * np.cos(a), np.ones_like(a), ORBIT_R * np.sin(a)])
        orbit = (S * (VIEW @ rot_y(TURN) @ ring)[:2] * [[1], [-1]]).T
        free = ~shapely.contains_xy(solid, orbit[:, 0], orbit[:, 1])
        # start the scan inside the cube so no run wraps past the end
        k0 = int(np.argmin(free))
        orbit, free = np.roll(orbit, -k0, axis=0), np.roll(free, -k0)
        i0, i1 = max(runs(free), key=lambda r: r[1] - r[0])
        trim = (i1 - i0) // 8
        arc = orbit[i0 + trim : i1 - trim]
        s.stroke(P().poly(arc), UI_HI, 1.6, cap="round")
        end = Vec(*arc[-1])
        heading = (end - Vec(*arc[-3])).unit()
        tip = end + heading * 16
        s.fill(P().arrowhead(tip, 16, rad=math.atan2(heading.y, heading.x), width=6), UI_HI)
