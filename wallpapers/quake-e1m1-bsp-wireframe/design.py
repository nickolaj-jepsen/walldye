"""Quake's first level as its map compiler cut it: the traced plan under the split planes of the top nine BSP levels, the exit leaf lit by an ordered-dither lightmap."""

import math
from typing import Literal, TypedDict

import numpy as np
import shapely
from numpy.typing import ArrayLike, NDArray
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_4,
    BG,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Path,
    Rect,
    Vec,
    design,
    polar,
)
from walldye.field import cells, gauss
from walldye.geom import Affine, parts
from walldye.pixel import dither, grid_runs

type Ring = list[list[float]]


class Step(TypedDict):
    child: Literal[0, 1]  # the side the path takes: 0 front, 1 back
    plane: int  # 0-2 axial, 3-5 non-axial
    sibling: Literal["node", "solid", "leaf"]  # what the side not taken holds


class Plan(TypedDict):
    """data/e1m1.json, baked from id's E1M1.MAP compiled with ericw-tools qbsp, in map units
    (x east, y north). `air` is the enclosed-air footprint (the first ring is the main
    outline), `water` and `slime` the liquid brushes, `platforms` the walkways in the slime
    hall, `leaf` the extent of the leaf holding the trigger_changelevel, `splits` the vertical
    node planes of tree depths 0 (the root) to 8 clipped to the level, as (depth, non-axial,
    ax, ay, bx, by), and `path` the node path from the root down to that leaf."""

    air: list[Ring]
    water: list[Ring]
    slime: list[Ring]
    platforms: list[Ring]
    leaf: Ring
    splits: list[list[float]]
    path: list[Step]


S = 0.35  # canvas units per map unit
MAP_X0, MAP_Y0 = -592, -416  # the south-west corner of the level's bounds
PLAN_W, PLAN_H = 3480 * S, 2096 * S  # the level's north-south and east-west extents
START = (480, -352)  # info_player_start, facing north
GATE = (1312, 544)  # the exit slipgate
EXIT_ROOM = ((1100, 360), (1560, 360), (1560, 712), (1100, 712))  # cuts the exit room out of air
CELL = 3
TREE_DY, STUB = 15, 26  # tree row pitch; sibling stub reach


def to_plan(pts: ArrayLike) -> NDArray[np.float64]:
    """Map points (x east, y north) in the plan's frame: north along +x and east along +y (a
    quarter turn clockwise from north up), the level's south-west corner at the origin."""
    a = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    return np.column_stack(((a[:, 1] - MAP_Y0) * S, (a[:, 0] - MAP_X0) * S))


def region(rings: list[Ring]) -> BaseGeometry:
    """The union of map polygons, in the plan's frame."""
    return unary_union([Polygon(to_plan(r)) for r in rings])


def outline(g: BaseGeometry) -> Path:
    """The rings of the polygon parts of `g`, dropping the stray lines a cut can leave."""
    d = P()
    for q in parts(g):
        if isinstance(q, Polygon):
            d.shape(q)
    return d


def snap(v: float) -> int:
    """`v` rounded to a whole number of pixel cells."""
    return CELL * round(v / CELL)


def draw_plan(s: Canvas, plan: Plan) -> None:
    """The level in the plan's frame: split planes, liquids, walls, the exit leaf and the start."""
    air = region(plan["air"])
    main = Polygon(to_plan(plan["air"][0]))

    # split planes: the top two depths a step stronger
    with s.buckets((UI_ALT, UI_HI), "stroke", stroke_width=1) as planes:
        for depth, _skew, ax, ay, bx, by in plan["splits"]:
            a, b = to_plan([(ax, ay), (bx, by)])
            planes[int(depth < 2)].M(a[0], a[1]).L(b[0], b[1])

    # canal: staggered flow dashes, whole-pixel columns so they stay crisp
    with s.pattern(16, 20) as flow:
        flow.stroke(P().M(4.5, 0).V(9).M(12.5, 10).V(19), UI, 1)
    s.fill(P().shape(region(plan["water"]).intersection(air).buffer(-2)), flow.ref)

    # slime: a sparse ordered dither around the walkways
    plats = region(plan["platforms"])
    slime = region(plan["slime"]).intersection(air).difference(plats.buffer(3)).buffer(-2)
    x0, y0, x1, y1 = slime.bounds
    box = Rect(snap(x0 - 2), snap(y0 - 2), x1 - x0 + 6, y1 - y0 + 6)
    xs, ys = cells(box, CELL)
    lit = dither(np.full(xs.shape, 0.13), 2) * shapely.contains_xy(slime, xs, ys)
    grid_runs(s, lit, [None, UI_ALT], CELL, (box.x, box.y))
    s.stroke(outline(plats), UI_HI, 1)

    # walls: the brush face outside, the air edge inside
    s.stroke(outline(air.buffer(2.5, join_style="mitre")), UI_ALT, 1)
    s.stroke(outline(air), MUTED, 1)

    # exit leaf: the lightmap on its floor, falling off from the slipgate
    gate = Vec(*to_plan([GATE])[0])
    leaf = Polygon(to_plan(plan["leaf"])).intersection(main)
    x0, y0, x1, y1 = leaf.bounds
    cols, rows = int((x1 - x0) // CELL), int((y1 - y0) // CELL)
    # an odd column count centred on the gate fits no multiple of CELL, so centre on whole units
    box = Rect(
        round(x0 + (x1 - x0 - cols * CELL) / 2),
        round(y0 + (y1 - y0 - rows * CELL) / 2),
        cols * CELL,
        rows * CELL,
    )
    xs, ys = cells(box, CELL)
    r = np.hypot(xs - gate.x, ys - gate.y)
    tone = 0.45 * gauss(r, 22) * (r > 10)
    grid_runs(s, dither(tone, 2), [None, ACCENT_4], CELL, (box.x, box.y))
    s.stroke(outline(main.intersection(Polygon(to_plan(EXIT_ROOM)))), ACCENT, 1.5)
    s.stroke(outline(leaf.buffer(-1, join_style="mitre")), ACCENT_2, 1)

    # the slipgate: a ring round a swirl
    s.path(P().circle(gate, 7), fill=BG, stroke=ACCENT, stroke_width=1.5)
    swirl = [polar(gate, 1 + 4.5 * t, rad=3.2 * math.pi * t) for t in np.linspace(0, 1, 25)]
    s.stroke(P().poly(swirl), ACCENT, 1)

    # the start, an arrowhead facing north
    p = Vec(*to_plan([START])[0])
    s.fill(P().poly(p + np.array([(5, 0), (-4, -4), (-2, 0), (-4, 4)]), closed=True), UI_HI)


def draw_tree(s: Canvas, root: Vec, path: list[Step]) -> None:
    """The node path from the BSP root to the exit leaf as a spine down from `root`, one row
    per node; each sibling is a stub to its side (front left, back right) ending in a mark of
    its kind, and each joint is a dot, or a diamond for a non-axial plane."""
    stubs, solids, marks, leaves = P(), P(), P(), P()
    for k, step in enumerate(path):
        at = root + (0, k * TREE_DY)
        end = at + (STUB if step["child"] == 0 else -STUB, TREE_DY)
        stubs.M(at).L(end)
        if step["sibling"] == "solid":
            solids.rect(end.x - 2.5, end.y - 2.5, 5, 5)
        elif step["sibling"] == "node":
            marks.circle(end, 2)
        else:
            leaves.circle(end, 2.5)
        if step["plane"] > 2:
            marks.ngon(at, 3, 4, deg=0)
        else:
            marks.circle(at, 2)
    bottom = root + (0, len(path) * TREE_DY)
    s.stroke(stubs, UI, 1)
    s.stroke(P().M(root).L(bottom), ACCENT_2, 1.5)
    s.fill(solids, UI_ALT)
    s.fill(marks, UI_HI)
    s.path(leaves, fill=BG, stroke=MUTED, stroke_width=1)
    s.fill(P().circle(bottom, 4), ACCENT)


@design(aspects="any")
def draw(s: Canvas) -> None:
    plan: Plan = s.data("e1m1.json")
    tall = len(plan["path"]) * TREE_DY
    if s.landscape:
        # North to the right, so the start sits at the left. The plan centres at 0.6 across,
        # keeping 162 clear on the right; the tree stands left of it, bottoms level, and closes
        # in when the screen is narrow.
        x = snap(min(s.w * 0.6 - PLAN_W / 2, s.w - 162 - PLAN_W))
        y = snap((s.h - PLAN_H) / 2)
        place = Affine.translate(x, y)
        root = Vec(x - min(270, x / 2), y + PLAN_H - 3 - tall)
    else:
        # north up; the tree stands in the empty south-west corner of the plan
        x = snap((s.w - PLAN_H) / 2)
        y = snap(s.h * 0.44 - PLAN_W / 2)
        place = Affine.translate(x, y + PLAN_W) @ Affine.rotate(deg=-90)
        root = Vec(x + 60, y + PLAN_W - 3 - tall)
    with s.group(transform=place):
        draw_plan(s, plan)
    draw_tree(s, root, plan["path"])
