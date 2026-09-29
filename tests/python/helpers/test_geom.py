import cmath
import math
import random

import numpy as np
import pytest
from helpers_support import PINS
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
    box,
)

from walldye import P, Rect, Vec, geom
from walldye._affine import Affine as CoreAffine
from walldye.geom import (
    Affine,
    Polyline,
    bezier_points,
    hatch,
    ngon,
    parts,
    poisson_disk,
    ribbon,
    scatter,
    spline_points,
)


def test_exports_match_the_spec():
    assert sorted(geom.__all__) == sorted(
        [
            "Affine",
            "Polyline",
            "spline_points",
            "bezier_points",
            "ribbon",
            "hatch",
            "ngon",
            "scatter",
            "poisson_disk",
            "parts",
        ]
    )


def test_affine_is_the_core_affine_and_replaces_hand_rotations():
    assert Affine is CoreAffine

    def schotter_square(cx, cy, a, side=40):
        h, c, s = side / 2, math.cos(a), math.sin(a)
        return [
            (cx + x * c - y * s, cy + x * s + y * c)
            for x, y in ((-h, -h), (h, -h), (h, h), (-h, h))
        ]

    corners = [(-20, -20), (20, -20), (20, 20), (-20, 20)]
    got = Affine.frame((300, 200), rad=0.3).apply(corners)
    assert np.allclose(got, schotter_square(300, 200, 0.3))

    def treatise_rot(points, cx, cy, a):
        c, s_ = math.cos(a), math.sin(a)
        return [
            (cx + (x - cx) * c - (y - cy) * s_, cy + (x - cx) * s_ + (y - cy) * c)
            for x, y in points
        ]

    pts = [(10, 0), (3, 7), (-4, 12.5)]
    assert np.allclose(
        Affine.rotate(rad=1.1, about=(5, 5)).apply(pts), treatise_rot(pts, 5, 5, 1.1)
    )


def dandelion_curve():
    """dandelion's drift curve: a cubic Bézier sampled at 800 points."""
    u = np.linspace(0, 1, 800)[:, None]
    p0, p1, p2, p3 = (
        np.array(p, float) for p in [(740, 430), (940, 355), (1280, 280), (1745, 230)]
    )
    return (1 - u) ** 3 * p0 + 3 * u * (1 - u) ** 2 * p1 + 3 * u * u * (1 - u) * p2 + u**3 * p3


def test_polyline_at_matches_dandelions_arc_length_lookup():
    pts = dandelion_curve()
    at = 70 + np.r_[0, np.cumsum([95, 130, 180, 250, 345])]
    arc = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    want = [(np.interp(t, arc, pts[:, 0]), np.interp(t, arc, pts[:, 1])) for t in at]
    line = Polyline(pts)
    assert np.array_equal(line.at(at), np.array(want))
    assert line.at(float(at[2])) == Vec(*want[2])
    assert line.length == arc[-1]


def test_polyline_resample_matches_paradox_province_spline():
    rng = np.random.default_rng(3)
    c = np.cumsum(rng.uniform(0.2, 3, (300, 2)), axis=0)
    d = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(c, axis=0).T))])
    u = np.arange(0, d[-1], 2.0)
    want = np.column_stack([np.interp(u, d, c[:, 0]), np.interp(u, d, c[:, 1])])
    got = Polyline(c).resample(2.0)
    assert np.array_equal(got.pts[:-1], want)
    assert np.array_equal(got.pts[-1], c[-1])
    steps = np.hypot(*np.diff(got.pts[:-1], axis=0).T)
    assert (steps <= 2.0 + 1e-9).all()


def test_polyline_open_and_closed():
    line = Polyline([(0, 0), (0, 0), (10, 0), (10, 10)])
    assert line.pts.tolist() == [[0, 0], [10, 0], [10, 10]]  # repeats dropped
    assert line.length == 20
    assert line.at(-5) == Vec(0, 0) and line.at(99) == Vec(10, 10)  # clamped
    assert line.at(15) == Vec(10, 5)
    assert line.tangent(10) == Vec(0, 1)  # the outgoing segment at a vertex
    assert line.tangent(20) == Vec(0, 1) and line.tangent(0) == Vec(1, 0)
    assert line.at(np.array([[0, 5], [10, 20]])).shape == (2, 2, 2)
    with pytest.raises(ValueError):
        line.pts[0, 0] = 3  # read-only, so the cached lengths stay right

    ring = Polyline([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], closed=True)
    assert len(ring.pts) == 4 and ring.length == 40
    assert ring.at(45) == Vec(5, 0) and ring.at(-5) == Vec(0, 5)  # wraps
    assert ring.tangent(35) == Vec(0, -1)  # the closing segment
    assert np.array_equal(ring.at(np.array([40.0, 85.0])), [[0, 0], [5, 0]])
    assert ring.resample(15).pts.tolist() == [[0, 0], [10, 5], [0, 10]]
    assert "closed=True" in repr(ring)


def test_polyline_errors():
    with pytest.raises(ValueError, match="2 distinct"):
        Polyline([(1, 1), (1, 1)])
    with pytest.raises(ValueError, match="2 distinct"):
        Polyline([(1, 1), (1, 1), (1, 1)], closed=True)
    with pytest.raises(ValueError):
        Polyline([(0, 0, 0), (1, 1, 1)])
    with pytest.raises(ValueError):
        Polyline([(0, 0), (1, math.nan)])
    with pytest.raises(TypeError):
        Polyline([(0, 0), (1, 1)], closed=1)
    line = Polyline([(0, 0), (1, 0)])
    with pytest.raises(ValueError):
        line.resample(0)
    with pytest.raises(ValueError):
        line.at(np.array([0.5, np.inf]))
    with pytest.raises(TypeError):
        line.at(True)


def test_polyline_resample_closed_needs_two_points():
    ring = Polyline([(0, 0), (4, 0), (4, 4)], closed=True)
    with pytest.raises(ValueError, match="fewer than 2"):
        ring.resample(100)


def test_polyline_offset_moves_along_the_unit_bisector():
    line = Polyline([(0, 0), (10, 0), (10, 10)])
    # east then south: right of travel is +y (down) on the first leg, -x on the second
    got = line.offset(2).pts
    b = np.array([-1, 1]) / math.sqrt(2)
    assert np.allclose(got, [(0, 2), (10 + 2 * b[0], 2 * b[1]), (8, 10)])
    ring = Polyline([(0, 0), (10, 0), (10, 10), (0, 10)], closed=True)
    inner = ring.offset(1).pts  # clockwise on screen, so right is inward
    assert np.allclose(
        inner,
        np.array([(0, 0), (10, 0), (10, 10), (0, 10)])
        + np.array([(1, 1), (-1, 1), (-1, -1), (1, -1)]) / math.sqrt(2),
    )
    assert np.allclose(np.hypot(*(inner - ring.pts).T), 1)
    hairpin = Polyline([(0, 0), (10, 0), (0, 0.0)]).offset(1).pts
    assert np.allclose(hairpin[1], (11, 0))  # a full reversal moves along the incoming direction


def patent_lamp_catmull(points, n=12):
    """patent-lamp's catmull: open Catmull-Rom samples, ends repeated, last point appended."""
    p = [points[0], *points, points[-1]]
    out = []
    for p0, p1, p2, p3 in zip(p, p[1:], p[2:], p[3:], strict=False):
        for t in (k / n for k in range(n)):
            out.append(
                tuple(
                    0.5
                    * (
                        2 * b
                        + (c - a) * t
                        + (2 * a - 5 * b + 4 * c - d) * t * t
                        + (3 * b - a - 3 * c + d) * t**3
                    )
                    for a, b, c, d in zip(p0, p1, p2, p3, strict=True)
                )
            )
    return out + [points[-1]]


def weather_front_spline(pts, n=24):
    """weather-front's spline: the same curve written per coordinate."""
    p = [pts[0], *pts, pts[-1]]
    out = []
    for i in range(1, len(p) - 2):
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = p[i - 1 : i + 3]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(
                tuple(
                    0.5
                    * (
                        2 * b
                        + (-a + c) * t
                        + (2 * a - 5 * b + 4 * c - d) * t2
                        + (-a + 3 * b - 3 * c + d) * t3
                    )
                    for a, b, c, d in ((x0, x1, x2, x3), (y0, y1, y2, y3))
                )
            )
    return out + [pts[-1]]


KNOTS = [(100, 400), (260, 330), (420, 380), (610, 300), (700, 520)]


def test_spline_points_match_the_corpus_catmull_rom():
    assert np.allclose(spline_points(KNOTS, 12), patent_lamp_catmull(KNOTS, 12))
    assert np.allclose(spline_points(KNOTS, 24), weather_front_spline(KNOTS, 24))
    assert len(spline_points(KNOTS, 5)) == 4 * 5 + 1


def test_spline_points_follow_the_drawn_spline():
    # n = 1 gives the knots; the curve passes through them at t = 0, as P().spline's Béziers do
    assert np.array_equal(spline_points(KNOTS, 1), KNOTS)
    closed = spline_points(KNOTS, 4, closed=True)
    assert len(closed) == 5 * 4 and np.array_equal(closed[::4], KNOTS)
    # the midpoint of the closing segment, from P().spline's control points written at 4 decimals
    d = str(P(4).spline(KNOTS, closed=True))
    last = [float(v) for v in d.split("C")[-1].rstrip("Z").split()]
    c1, c2, end = last[0:2], last[2:4], last[4:6]
    mid = (np.array(KNOTS[-1]) + 3 * np.array(c1) + 3 * np.array(c2) + np.array(end)) / 8
    assert np.allclose(closed[-2], mid, atol=1e-3)
    assert np.array_equal(spline_points(KNOTS[:2], 9), KNOTS[:2])  # too few points: unchanged
    with pytest.raises(ValueError):
        spline_points(KNOTS, 0)


def test_bezier_points_match_folds_and_suprematist_drift():
    t = np.linspace(0, 1, 41)

    def folds_bezier(pts, t):
        p0, p1, p2, p3 = (np.array(p, float) for p in pts)
        t = t[:, None]
        return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3 * p3

    cubic = [(740, 430), (940, 355), (1280, 280), (1745, 230)]
    assert np.array_equal(bezier_points(cubic, 40), folds_bezier(cubic, t))

    def suprematist_bez(t, p0=(400, 750), p1=(790, 580), p2=(1160, 320)):
        a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
        return tuple(a * p + b * q + c * r for p, q, r in zip(p0, p1, p2, strict=True))

    quad = bezier_points([(400, 750), (790, 580), (1160, 320)], 40)
    assert np.allclose(quad, [suprematist_bez(v) for v in t])
    assert np.array_equal(quad[[0, -1]], [(400, 750), (1160, 320)])
    for bad in ([(0, 0), (1, 1)], [(0, 0)] * 5):
        with pytest.raises(ValueError):
            bezier_points(bad, 4)
    with pytest.raises(ValueError):
        bezier_points(cubic, 0)


def kintsugi_ribbon(pts, widths):
    d = np.gradient(pts, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1) / np.linalg.norm(d, axis=1)[:, None]
    h = (widths / 2)[:, None]
    return np.vstack([pts + nrm * h, (pts - nrm * h)[::-1]])


def test_ribbon_matches_kintsugi_on_evenly_spaced_points():
    # np.gradient's central difference is the bisector direction when neighbors are equidistant
    a = np.linspace(0.2, 2.5, 30)
    pts = np.column_stack([500 + 300 * np.cos(a), 400 + 300 * np.sin(a)])
    widths = 2 + 6 * np.sin(np.linspace(0, math.pi, 30))
    assert np.allclose(ribbon(pts, widths), kintsugi_ribbon(pts, widths))
    got = ribbon(pts, 4)
    assert got.shape == (60, 2)
    assert np.allclose(got[:30], Polyline(pts).offset(2).pts)
    assert np.allclose(got[30:], Polyline(pts).offset(-2).pts[::-1])


def test_ribbon_errors():
    with pytest.raises(ValueError, match="repeats"):
        ribbon([(0, 0), (0, 0), (1, 1)], 2)
    with pytest.raises(ValueError):
        ribbon([(0, 0), (1, 1)], [1, 2, 3])
    with pytest.raises(ValueError):
        ribbon([(0, 0)], 1)
    with pytest.raises(ValueError):
        ribbon([(0, 0), (1, 1)], math.inf)


def engine_section_hatch(geom, ang, gap):
    """engine-section's section lining, collecting segments instead of drawing them."""
    out = []
    x0, y0, x1, y1 = geom.bounds
    cx, cy, rr = (x0 + x1) / 2, (y0 + y1) / 2, math.hypot(x1 - x0, y1 - y0) / 2 + gap
    a = math.radians(ang)
    ux, uy, nx, ny = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    k = -rr
    while k <= rr:
        px, py = cx + nx * k, cy + ny * k
        cut = LineString([(px - ux * rr, py - uy * rr), (px + ux * rr, py + uy * rr)]).intersection(
            geom
        )
        for g in getattr(cut, "geoms", [cut]):
            if isinstance(g, LineString) and not g.is_empty:
                out.append(list(g.coords))
        k += gap
    return out, -rr


def petra_sancta_hatch(region, angle, pitch):
    """Lines through the center, k * pitch apart."""
    x0, y0, x1, y1 = region.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = math.hypot(x1 - x0, y1 - y0) / 2 + pitch
    a = math.radians(angle)
    ux, uy, nx, ny = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    lines = []
    k = -int(r / pitch)
    while k * pitch <= r:
        ox, oy = cx + nx * k * pitch, cy + ny * k * pitch
        lines.append([(ox - ux * r, oy - uy * r), (ox + ux * r, oy + uy * r)])
        k += 1
    cut = MultiLineString(lines).intersection(region)
    return [list(g.coords) for g in getattr(cut, "geoms", [cut]) if isinstance(g, LineString)]


def ray_diagram_hatch(poly, step, angle):
    """ray-diagram's hatch: angle in radians, pieces of length 1 or less dropped."""
    out = []
    minx, miny, maxx, maxy = poly.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    ext = max(maxx - minx, maxy - miny)
    ux, uy = math.cos(angle), math.sin(angle)
    k = -ext
    while k <= ext:
        ox, oy = cx - uy * k, cy + ux * k
        seg = LineString(
            [(ox - ux * ext, oy - uy * ext), (ox + ux * ext, oy + uy * ext)]
        ).intersection(poly)
        for g in getattr(seg, "geoms", [seg]):
            if not g.is_empty and g.length > 1:
                out.append(list(g.coords))
        k += step
    return out, -ext


def segments(pieces) -> np.ndarray:
    """Pieces as sorted (N, 4) rows of their end points."""
    rows = [(*p[0], *p[-1]) for p in pieces]
    return np.array(sorted(tuple(round(v, 6) for v in r) for r in rows))


# a ring with a notch: holes, re-entrant edges and several pieces per line
REGION = (
    Point(400, 300)
    .buffer(120)
    .difference(Point(420, 290).buffer(45))
    .difference(box(260, 280, 330, 320))
)


def test_hatch_matches_the_corpus_hatchers():
    want, offset = engine_section_hatch(REGION, 30, 9)
    got = hatch(REGION, 9, deg=30, offset=offset)
    assert np.allclose(segments(got), segments(want), atol=1e-6)
    assert np.allclose(
        segments(hatch(REGION, 7, deg=-45)), segments(petra_sancta_hatch(REGION, -45, 7))
    )
    want, offset = ray_diagram_hatch(REGION, 11, 1.2)
    got = [g for g in hatch(REGION, 11, rad=1.2, offset=offset) if math.dist(*g) > 1]
    assert np.allclose(segments(got), segments(want), atol=1e-6)


def test_hatch_orders_by_line_then_along_it():
    pieces = hatch(REGION, 10, bearing=90)  # horizontal lines, running east
    assert all(p.shape == (2, 2) for p in pieces)
    assert all(p[0, 0] < p[1, 0] for p in pieces)
    ys = [p[0, 1] for p in pieces]
    assert ys == sorted(ys)
    for y in set(ys):
        xs = [p[0, 0] for p in pieces if p[0, 1] == y]
        assert xs == sorted(xs)
    assert {round(y - 300, 6) % 10 for y in ys} == {0}  # through the center of the bounds
    assert hatch(Polygon(), 5, deg=0) == []
    with pytest.raises(ValueError):
        hatch(REGION, 0, deg=0)
    with pytest.raises(TypeError):
        hatch(REGION, 5)


def test_ngon_matches_tempest_and_poincare_vertices():
    c, r, inner = (1300, 540), 390, 0.8
    tempest = [
        (
            c[0] + r * (1 if k % 2 == 0 else inner) * math.cos(-math.pi / 2 + 2 * math.pi * k / 16),
            c[1] + r * (1 if k % 2 == 0 else inner) * math.sin(-math.pi / 2 + 2 * math.pi * k / 16),
        )
        for k in range(16)
    ]
    assert np.allclose(ngon(c, r, 8, bearing=0, inner=r * inner), tempest)
    rv = 0.62
    poincare = [cmath.rect(rv, -math.pi / 2 + 2 * math.pi * k / 7) for k in range(7)]
    assert np.allclose(ngon((0, 0), rv, 7, rad=-math.pi / 2), [(z.real, z.imag) for z in poincare])
    assert np.allclose(ngon((0, 0), 1, 4, deg=0), [(1, 0), (0, 1), (-1, 0), (0, -1)])
    with pytest.raises(ValueError):
        ngon((0, 0), 1, 2, deg=0)


def test_scatter_is_the_klee_bands_rejection_loop():
    rad, box_ = 22, (100, -50, 1400, 500)
    edges = LineString([(0, 150), (1600, 170)])

    def accept(p):
        return not rad - 12 < Point(p).distance(edges) < rad + 8

    r = random.Random(65)
    circles = []
    while len(circles) < 25:  # klee-bands' circle placement, with every radius equal
        cx, cy = r.uniform(100, 1500), r.uniform(-50, 450)
        if not accept((cx, cy)):
            continue
        if all(math.hypot(cx - x, cy - y) > rad + rad + 24 for x, y in circles):
            circles.append((cx, cy))
    got = scatter(25, Rect(*box_), random.Random(65), min_dist=2 * rad + 24, accept=accept)
    assert np.array_equal(got, np.array(circles))


def test_scatter_draws_x_first_and_keeps_its_promises():
    r = random.Random(4)
    want = [(r.uniform(10, 60), r.uniform(20, 50)) for _ in range(6)]
    assert np.array_equal(scatter(6, Rect(10, 20, 50, 30), random.Random(4)), want)
    pts = scatter(400, Rect(0, 0, 300, 200), random.Random(1), min_dist=25, tries=5)
    assert 0 < len(pts) < 400  # dense: it gives up after n * tries candidates
    d = np.hypot(*(pts[:, None, :] - pts[None, :, :]).transpose(2, 0, 1))
    assert d[np.triu_indices(len(pts), 1)].min() >= 25
    assert ((pts >= 0) & (pts <= (300, 200))).all()
    none = scatter(5, Rect(0, 0, 10, 10), random.Random(1), accept=lambda p: p.x < 0)
    assert none.shape == (0, 2)
    with pytest.raises(TypeError):
        scatter(3, Rect(0, 0, 1, 1), np.random.default_rng(1))
    with pytest.raises(ValueError):
        scatter(3, Rect(0, 0, 1, 1), random.Random(1), min_dist=-1)


@pytest.mark.parametrize("case", PINS["poisson_disk"], ids=lambda c: str(c["args"]))
def test_poisson_disk_equals_v1(case):
    seed, w, h, radius, k, x0, y0 = case["args"]
    got = poisson_disk(Rect(x0, y0, w, h), radius, random.Random(seed), k=k)
    assert np.array_equal(got, np.array(case["points"]))
    d = np.hypot(*(got[:, None, :] - got[None, :, :]).transpose(2, 0, 1))
    assert d[np.triu_indices(len(got), 1)].min() >= radius
    assert ((got >= (x0, y0)) & (got < (x0 + w, y0 + h))).all()


def test_poisson_disk_errors():
    with pytest.raises(ValueError):
        poisson_disk(Rect(0, 0, 10, 10), 0, random.Random(1))
    with pytest.raises(ValueError):
        poisson_disk(Rect(0, 0, 10, 10), 1, random.Random(1), k=0)


def test_parts_flattens_like_the_geoms_idiom():
    a, b, c = box(0, 0, 1, 1), box(2, 2, 3, 3), LineString([(0, 5), (4, 5)])
    nested = GeometryCollection([MultiPolygon([a, b]), Polygon(), GeometryCollection([c, Point()])])
    assert [g.wkt for g in parts(nested)] == [a.wkt, b.wkt, c.wkt]
    assert parts(a) == [a]
    assert parts(Polygon()) == []
    # dragon-quartet's rings(): every ring of every part
    union = a.union(b).union(box(10, 0, 20, 10).difference(box(12, 2, 14, 4)))
    rings = [r for g in parts(union) for r in (g.exterior, *g.interiors)]
    assert len(rings) == 4
