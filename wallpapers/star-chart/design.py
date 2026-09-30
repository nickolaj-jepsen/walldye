"""A stereographic star atlas page with Hipparcos stars and one constellation traced."""

import itertools
from typing import Literal, TypedDict

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_2,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Params,
    Path,
    Rect,
    Vec,
    design,
    knob,
)
from walldye.field import runs
from walldye.geom import Affine

type Arr = NDArray[np.float64]


class Chart(Params):
    sky: Literal["cassiopeia", "orion"] = knob(default="cassiopeia", doc="constellation traced")


VARIANTS = {"orion": Chart(sky="orion")}


class Sky(TypedDict):
    tangent: tuple[float, float]  # RA, Dec (deg) of the projection center
    focus: tuple[float, float]  # RA, Dec (deg) of the sky point placed on the focal point
    north: float  # bearing of north at the tangent point, on screen
    scale: float  # px per radian at the tangent point
    stars: tuple[tuple[float, float, float], ...]  # the figure's stars: RA, Dec (deg), V mag
    lines: tuple[tuple[int, ...], ...]  # the figure's strokes, as indices into stars
    ring: int  # the circled star


SKIES: dict[str, Sky] = {
    # Cassiopeia's W from epsilon to beta, Schedar (alpha) circled; the pole lies off the top
    "cassiopeia": {
        "tangent": (15.0, 60.0),
        "focus": (15.0, 60.0),
        "north": -22.0,
        "scale": 2600.0,
        "stars": (
            (28.5989, 63.6701, 3.37),
            (21.454, 60.2353, 2.68),
            (14.1772, 60.7167, 2.47),
            (10.1268, 56.5373, 2.24),
            (2.2945, 59.1498, 2.27),
        ),
        "lines": ((0, 1, 2, 3, 4),),
        "ring": 3,
    },
    # Orion's hourglass and head, Betelgeuse (alpha) circled; projected from 35 degrees north
    # of it, so the declination circles still bend
    "orion": {
        "tangent": (84.0, 35.0),
        "focus": (83.7, 0.0),
        "north": -20.0,
        "scale": 1800.0,
        "stars": (
            (88.7929, 7.4071, 0.45),  # Betelgeuse
            (81.2828, 6.3497, 1.64),  # Bellatrix
            (83.0017, -0.2991, 2.25),  # Mintaka
            (84.0534, -1.2019, 1.69),  # Alnilam
            (85.1897, -1.9426, 1.74),  # Alnitak
            (86.9391, -9.6696, 2.07),  # Saiph
            (78.6345, -8.2016, 0.18),  # Rigel
            (83.7845, 9.9342, 3.39),  # Meissa
        ),
        "lines": ((0, 1, 2, 3, 4, 0), (2, 6, 5, 4), (0, 7, 1)),
        "ring": 0,
    },
}

NGP = (192.85948, 27.12825)  # north galactic pole, RA/Dec (J2000)
L_NCP = 122.93192  # galactic longitude of the north celestial pole
# Star dots by V magnitude: stars fainter than the limit get this radius and tone.
DOTS = (
    (7.0, 0.8, UI),
    (6.0, 1.05, UI_ALT),
    (5.0, 1.45, UI_ALT),
    (4.0, 2.0, UI_HI),
    (-9.0, 2.7, UI_HI),
)
RING, GAP = 16, 9  # ring radius; the atlas-style break in a figure line at each star


def stereo(ra: Arr, dec: Arr, tangent: tuple[float, float]) -> Arr:
    """Oblique stereographic projection about `tangent` of the sky seen from inside, so east
    lies to the left of north. Maps RA and Dec in degrees to (N, 2) plane points in radians at
    the tangent point, with +x west and +y south; points over 120 degrees from the tangent
    point come back as NaN."""
    l0, p0 = np.radians(tangent)
    l, p = np.radians(ra), np.radians(dec)
    cos_c = np.sin(p0) * np.sin(p) + np.cos(p0) * np.cos(p) * np.cos(l - l0)
    k = np.where(cos_c > -0.5, 2 / np.maximum(1 + cos_c, 0.5), np.nan)
    west = -k * np.cos(p) * np.sin(l - l0)
    north = k * (np.cos(p0) * np.sin(p) - np.sin(p0) * np.cos(p) * np.cos(l - l0))
    return np.column_stack([west, -north])


def inside(pts: Arr, box: Rect) -> NDArray[np.bool_]:
    """Which of the (N, 2) points lie strictly inside `box`; NaN points never do."""
    x, y = pts[:, 0], pts[:, 1]
    return (x > box.x) & (x < box.x1) & (y > box.y) & (y < box.y1)


def trace(d: Path, pts: Arr, box: Rect) -> None:
    """Add the runs of the sampled curve `pts` that lie inside `box` to `d`."""
    for a, b in runs(inside(pts, box)):
        if b - a > 1:
            d.poly(pts[a:b])


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Chart]) -> None:
    sky = SKIES[s.params.sky]
    spot = s.pick(landscape=(1300 / 1920, 480 / 1080), portrait=(0.52, 0.38))
    focus = np.array([sky["focus"]])
    fx, fy = stereo(focus[:, 0], focus[:, 1], sky["tangent"])[0]
    # plane x (west) points a quarter turn clockwise from north, as the sky looks from below
    frame = Affine.frame(spot, bearing=sky["north"] + 90, scale=sky["scale"])
    frame = frame @ Affine.translate(-fx, -fy)

    def at(ra: Arr, dec: Arr) -> Arr:
        return frame.apply(stereo(ra, dec, sky["tangent"]))

    box = s.inset(-40)
    grid = P()
    t = np.linspace(-180, 180, 1441)
    for dec in range(-80, 90, 10):
        trace(grid, at(t, np.full_like(t, dec)), box)
    t = np.linspace(-89.9, 89.9, 1441)
    for ra in range(0, 360, 15):
        trace(grid, at(np.full_like(t, ra), t), box)
    s.stroke(grid, BG_ALT, 1.2)

    # the galactic equator, which runs through Cassiopeia and just east of Orion
    gl = np.radians(np.linspace(0, 360, 1441))
    ag, dg = np.radians(NGP)
    ln = np.radians(L_NCP)
    dec = np.arcsin(np.cos(dg) * np.cos(ln - gl))
    ra = ag + np.arctan2(np.sin(ln - gl), -np.sin(dg) * np.cos(ln - gl))
    galaxy = P()
    trace(galaxy, at(np.degrees(ra), np.degrees(dec)), box)
    s.stroke(galaxy, UI, 1.2, dash=(3, 9))

    # Hipparcos stars to V 7.3 that fall on some screen shape: RA, Dec (deg), V mag
    stars: list[list[float]] = s.data(f"{s.params.sky}.json")
    cat = np.array(stars)
    xy = at(cat[:, 0], cat[:, 1])
    on = inside(xy, s.inset(-10))
    xy, mag = xy[on], cat[on, 2]
    lo = 99.0
    for hi, r, tone in DOTS:
        s.fill(P().dots(xy[(mag <= lo) & (mag > hi)], r), tone)
        lo = hi

    fig = np.array(sky["stars"])
    pts = [Vec(x, y) for x, y in at(fig[:, 0], fig[:, 1])]
    gaps = [RING + 5 if i == sky["ring"] else GAP for i in range(len(pts))]
    figure = P()
    for line in sky["lines"]:
        for i, j in itertools.pairwise(line):
            u = (pts[j] - pts[i]).unit()
            figure.M(pts[i] + u * gaps[i]).L(pts[j] - u * gaps[j])
    s.stroke(figure, ACCENT_2, 1.5)
    dots = P()
    for p, m in zip(pts, fig[:, 2], strict=True):
        dots.circle(p, 7.5 - m * 1.3)
    s.fill(dots, ACCENT)
    s.stroke(P().circle(pts[sky["ring"]], RING), ACCENT, 1.5)
