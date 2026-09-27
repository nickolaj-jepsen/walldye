"""A radio telescope at dusk in 1-bit Atkinson dither: an empty sky above, grain gathering in the bowl and along the horizon."""

import math

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely.geometry import LineString, MultiPoint, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import ACCENT, ACCENT_3, UI, Canvas, Vec, design
from walldye.field import cells, noise_grid
from walldye.geom import Affine
from walldye.pixel import Pixels

CELL = 3
RIM, TILT = 300, math.radians(35)  # mouth radius; boresight tilt from the zenith towards the west
LIFT = 394  # mouth centre above the ground
PHASE = 10  # rim index of the first feed leg (180 rim points)
HAZE = 124  # height of the grain band above the horizon
STARS, AREA = 22, 1920 * 1080  # stars on a 16:9 canvas, scaled by area elsewhere
# Glint at the feed tip: a 2x2 core (A) inside a broken cross (a), stamped over the dither.
GLINT = """
..aa..
......
a.AA.a
a.AA.a
......
..aa..
"""

type Pts = NDArray[np.float64]


def dish(c: Vec) -> tuple[BaseGeometry, Polygon, Pts, Vec, Vec]:
    """Screen projection of a paraboloid with f/D = 0.4 whose mouth is centred on `c`, aimed
    up-left and slightly towards the viewer: (outline, mouth, 180 rim points, focus, vertex)."""
    a = np.array([-math.sin(TILT), -math.cos(TILT), 0.32])
    a /= np.linalg.norm(a)
    u = np.cross(a, [0, 0, 1.0])
    u /= np.linalg.norm(u)
    v = np.cross(a, u)
    f = 0.8 * RIM
    depth = RIM**2 / (4 * f)
    o = np.array([c.x, c.y, 0.0])
    rho = np.linspace(0, RIM, 12)[:, None, None]
    t = np.linspace(0, 2 * math.pi, 96, endpoint=False)[None, :, None]
    bowl = o + (rho**2 / (4 * f) - depth) * a + rho * (np.cos(t) * u + np.sin(t) * v)
    t = np.linspace(0, 2 * math.pi, 180, endpoint=False)[:, None]
    rim = (o + RIM * (np.cos(t) * u + np.sin(t) * v))[:, :2]
    focus, vertex = o + (f - depth) * a, o - depth * a
    return (
        MultiPoint(bowl.reshape(-1, 3)[:, :2]).convex_hull,
        Polygon(rim),
        rim,
        Vec(focus[0], focus[1]),
        Vec(vertex[0], vertex[1]),
    )


@design(aspects="any")
def draw(s: Canvas) -> None:
    # where the mount meets the ground: right of centre over a thin strip of land on a landscape
    # screen; just right of the middle on a portrait one, over a deeper foreground
    g = s.pick(landscape=(0.698, 0.93), portrait=(0.55, 0.8))
    ground, c = g.y, g - (0, LIFT)
    hull, mouth, rim, focus, vertex = dish(c)
    axis = (focus - vertex).unit()
    feed = Affine.frame(focus, rad=math.atan2(axis.y, axis.x))  # local +x out along the boresight
    b = vertex + (14, 24)  # elevation bearing behind the bowl
    arm = Affine.frame(b, rad=math.atan2(-axis.y, -axis.x))  # local +x back, away from the sky

    legs = [LineString([rim[k % 180], focus]).buffer(3) for k in (PHASE, PHASE + 60, PHASE + 120)]
    cabin = Polygon(feed.apply([(4, -12), (4, 12), (30, 9), (30, -9)])).buffer(1.5)
    q = np.linspace(0, 2 * math.pi, 40)
    sub = Polygon(feed.apply(np.column_stack([6 * np.cos(q), 34 * np.sin(q)])))  # subreflector
    mount = [
        Polygon([(b.x - 110, ground), (b.x - 88, ground), (b.x - 4, b.y), (b.x - 20, b.y)]),
        Polygon([(b.x + 88, ground), (b.x + 110, ground), (b.x + 20, b.y), (b.x + 4, b.y)]),
        LineString([(b.x - 78, ground - 70), (b.x + 78, ground - 70)]).buffer(3),
        shapely.Point(b.x, b.y).buffer(22),
        LineString([b, arm((176, 0))]).buffer(5),
        Polygon(arm.apply([(154, -30), (198, -30), (198, 30), (154, 30)])),  # counterweight
        Polygon(
            [
                (b.x - 34, ground - 16),
                (b.x + 34, ground - 16),
                (b.x + 40, ground),
                (b.x - 40, ground),
            ]
        ),
    ]
    solid = unary_union(
        [hull.difference(mouth), mouth.exterior.buffer(4), cabin, sub, *legs, *mount]
    )

    X, Y = cells(s.inset(0), CELL)
    rows, cols = X.shape
    dx = X - c.x  # the haze and the hills are laid out from the dish, not the frame
    haze = np.clip((Y - ground + HAZE) / HAZE, 0, 1) ** 1.6 * np.clip((dx + 1140) / 900, 0.2, 1)
    sky = 0.42 * haze + 0.04 * noise_grid(cols, rows, 60, s.np_rng(2), octaves=3) * (haze > 0)
    x0, y0, x1, y1 = mouth.bounds
    bowl = np.clip((X - x0) / (x1 - x0) * 0.3 + (Y - y0) / (y1 - y0) * 0.7, 0, 1)  # deeper low
    tone = np.where(shapely.contains_xy(mouth, X, Y), 0.22 + 0.24 * bowl**1.4, sky)
    # low hills west of the dish
    hills = np.clip(np.sin(dx / 260 + 5.75) + 0.5 * np.sin(dx / 97 + 1.25), 0, None)
    # flat land: Atkinson diffuses only 6/8 of the error, so tones under 1/8 come out empty
    tone = np.where(Y >= ground - 14 * hills * np.clip((-240 - dx) / 250, 0, 1), 0.2, tone)
    tone = np.where(shapely.contains_xy(solid, X, Y), 1.0, tone)

    px = Pixels(cols, rows, [None, UI, ACCENT_3, ACCENT])
    px.dither(tone, (0, 1), method="atkinson")
    tip = feed((38, 0))
    px.stamp(GLINT, int(tip.x // CELL) - 2, int(tip.y // CELL) - 2, {"a": 2, "A": 3})

    rng, halo = s.np_rng(8), solid.buffer(40)
    for _ in range(round(STARS * s.w * s.h / AREA)):
        i, j = rng.integers(0, cols), rng.integers(4, rows // 2)
        if not shapely.contains_xy(halo, i * CELL, j * CELL):
            px.grid[j, i] = 1
    px.draw(s, CELL)
