import math

import numpy as np
import pytest
from shapely.geometry import (
    GeometryCollection,
    LinearRing,
    LineString,
    MultiPolygon,
    Point,
    Polygon,
)

from walldye import P, Path, Vec
from walldye._path import fmt, ngon_vertices


@pytest.mark.parametrize(
    ("v", "nd", "want"),
    [
        (3, 1, "3"),
        (np.int64(-7), 1, "-7"),
        (2.0, 1, "2"),
        (2.25, 1, "2.2"),  # half to even in formatting
        (2.35, 2, "2.35"),
        (-0.04, 1, "0"),
        (-0.0, 1, "0"),
        (np.float32(0.1), 2, "0.1"),
        (np.float64(1.23456), 4, "1.2346"),
        (1.5, 0, "2"),
        (1e6 + 0.25, 1, "1000000.2"),
    ],
)
def test_fmt(v, nd, want):
    assert fmt(v, nd) == want


def test_fmt_errors():
    with pytest.raises(TypeError):
        fmt(True, 1)
    with pytest.raises(TypeError):
        fmt(np.True_, 1)
    with pytest.raises(TypeError):
        fmt("1", 1)
    with pytest.raises(ValueError, match="^M"):
        P().M(float("nan"), 0)
    with pytest.raises(ValueError, match="^L"):
        P().L(0, float("inf"))
    with pytest.raises(TypeError):
        P().M(True, 0)


def test_commands():
    d = P().M(1, 2).L(3.25, 4).H(5).V(-6).C(1, 2, 3, 4, 5, 6).Q(1, 2, 3, 4).A(5, 6, 30, 0, 1, 7, 8)
    assert str(d.Z()) == "M1 2L3.2 4H5V-6C1 2 3 4 5 6Q1 2 3 4A5 6 30 0 1 7 8Z"
    pts = P().M((1, 2)).L(Vec(3, 4)).C((1, 2), (3, 4), (5, 6)).Q((1, 2), (3, 4))
    assert str(pts.A(5, 5, 0, True, False, (7, 8))) == "M1 2L3 4C1 2 3 4 5 6Q1 2 3 4A5 5 0 1 0 7 8"
    assert str(P().M(np.array([1.5, 2.0])).L(np.float64(3), np.int64(4))) == "M1.5 2L3 4"
    assert str(P(3).M(1 / 3, 2 / 3)) == "M0.333 0.667"
    with pytest.raises(TypeError):
        P().M((1, 2, 3))
    with pytest.raises(TypeError):
        P().C(1, 2, 3)
    with pytest.raises(ValueError):
        Path(5)


def test_arc_flags():
    for flag in (True, False, np.True_, 0, 1, np.int64(1)):
        P().A(1, 1, 0, flag, flag, 0, 0)
    assert str(P().A(1, 1, 0, np.True_, 0, 2, 3)) == "A1 1 0 1 0 2 3"
    with pytest.raises(ValueError):
        P().A(1, 1, 0, 2, 0, 0, 0)
    with pytest.raises(TypeError):
        P().A(1, 1, 0, 0.5, 0, 0, 0)


def test_builder_basics():
    d = P()
    assert d.empty and str(d) == ""
    assert d.M(0, 0) is d
    assert not d.empty


@pytest.mark.parametrize(
    ("d", "want"),
    [
        (P().rect(10, 20, 30, 40), "M10 20H40V60H10Z"),
        (
            P().rrect(0, 0, 100, 50, 10),
            (
                "M10 0H90A10 10 0 0 1 100 10V40A10 10 0 0 1 90 50H10A10 10 0 0 1 0 40V10"
                "A10 10 0 0 1 10 0Z"
            ),
        ),
        (P().rrect(0, 0, 100, 50, 0), "M0 0H100V50H0Z"),
        (P().rrect(0, 0, 20, 10, 99).M(0, 0), str(P().rrect(0, 0, 20, 10, 5).M(0, 0))),
        (P().circle((100, 50), 10), "M110 50A10 10 0 1 1 90 50A10 10 0 1 1 110 50Z"),
        (P().circle((100, 50), 0), ""),
        (P().ellipse((100, 50), 20, 10), "M120 50A20 10 0 1 1 80 50A20 10 0 1 1 120 50Z"),
        (
            P().ring((0, 0), 5, 10),
            "M10 0A10 10 0 1 1 -10 0A10 10 0 1 1 10 0ZM5 0A5 5 0 1 0 -5 0A5 5 0 1 0 5 0Z",
        ),
        (P().ring((0, 0), 0, 10), "M10 0A10 10 0 1 1 -10 0A10 10 0 1 1 10 0Z"),
        (P().arc((0, 0), 10, deg=(0, 90)), "M10 0A10 10 0 0 1 0 10"),
        (P().arc((0, 0), 10, deg=(90, -180)), "M0 10A10 10 0 1 0 -10 0"),
        (P().arc((0, 0), 10, bearing=(0, 90)), "M0 -10A10 10 0 0 1 10 0"),
        (P().arc((0, 0), 10, rad=(0, math.pi / 2)), "M10 0A10 10 0 0 1 0 10"),
        (P().arc_band((0, 0), 5, 10, deg=(0, 90)), "M10 0A10 10 0 0 1 0 10L0 5A5 5 0 0 0 5 0Z"),
        (P().arc_band((0, 0), 0, 10, deg=(0, 270)), "M0 0L10 0A10 10 0 1 1 0 -10Z"),
        (P().ngon((0, 0), 10, 4, deg=0), "M10 0L0 10L-10 0L0 -10Z"),
        (
            P().ngon((0, 0), 10, 3, bearing=0, inner=5),
            "M0 -10L4.3 -2.5L8.7 5L0 5L-8.7 5L-4.3 -2.5Z",
        ),
        (
            P().dots([(0, 0), (10, 10)], 2),
            "M2 0A2 2 0 1 1 -2 0A2 2 0 1 1 2 0ZM12 10A2 2 0 1 1 8 10A2 2 0 1 1 12 10Z",
        ),
        (P().dots(np.zeros((0, 2)), 2), ""),
        (P().arrowhead((10, 0), 10, deg=0), "M10 0L0 3L0 -3Z"),
        (P().arrowhead((10, 0), 10, deg=0, width=1), "M10 0L0 1L0 -1Z"),
        (P().poly([(0, 0), (1, 2), (3, 4)]), "M0 0L1 2L3 4"),
        (P().poly(np.array([[0, 0], [1, 2]]), closed=True), "M0 0L1 2Z"),
        (P().poly([]), ""),
        (P().spline([(0, 0), (6, 0), (12, 6)]), "M0 0C1 0 4 -1 6 0C8 1 11 5 12 6"),
        (
            P().spline([(0, 0), (6, 0), (12, 6)], closed=True),
            "M0 0C-1 -1 4 -1 6 0C8 1 13 6 12 6C11 6 1 1 0 0Z",
        ),
        (P().spline([(0, 0), (6, 0)], tension=0.5), "M0 0L6 0"),
    ],
)
def test_primitive_goldens(d, want):
    assert str(d) == want


def test_primitive_errors():
    for bad in (
        lambda: P().rect(0, 0, -1, 1),
        lambda: P().rrect(0, 0, 1, 1, -1),
        lambda: P().circle((0, 0), -1),
        lambda: P().ellipse((0, 0), -1, 1),
        lambda: P().ring((0, 0), 10, 5),
        lambda: P().ring((0, 0), -1, 5),
        lambda: P().arc((0, 0), 1, deg=(10, 10)),
        lambda: P().arc((0, 0), 1, deg=(0, 360)),
        lambda: P().arc_band((0, 0), 5, 5, deg=(0, 90)),
        lambda: P().arc_band((0, 0), 1, 5, rad=(0, 7)),
        lambda: P().ngon((0, 0), 1, 2, deg=0),
        lambda: P().poly([1, 2, 3]),
        lambda: P().poly([(0, float("nan"))]),
    ):
        with pytest.raises(ValueError):
            bad()
    with pytest.raises(TypeError):
        P().arc((0, 0), 1)
    with pytest.raises(TypeError):
        P().arc((0, 0), 1, deg=(0, 90), rad=(0, 1))
    with pytest.raises(TypeError):
        P().ngon((0, 0), 1, 5)
    with pytest.raises(TypeError):
        P().poly([(True, False)])


def test_ngon_vertices():
    v = ngon_vertices((1, 2), 3, 6, 0.25, None)
    assert v.shape == (6, 2)
    for k, (x, y) in enumerate(v):
        a = 0.25 + 2 * math.pi * k / 6
        assert (x, y) == (1 + 3 * math.cos(a), 2 + 3 * math.sin(a))
    star = ngon_vertices((0, 0), 3, 5, 0, 1)
    assert star.shape == (10, 2)
    assert math.hypot(*star[1]) == pytest.approx(1)


def test_shape():
    outer = [(0, 0), (0, 10), (10, 10), (10, 0)]  # clockwise in maths axes
    hole = [(2, 2), (4, 2), (4, 4), (2, 4)]
    poly = Polygon(outer, [hole])
    # orient(1.0): exterior counter-clockwise, holes clockwise, in maths axes.
    assert str(P().shape(poly)) == "M0 0L10 0L10 10L0 10ZM2 2L2 4L4 4L4 2Z"
    assert str(P().shape(LineString([(0, 0), (1, 1)]))) == "M0 0L1 1"
    assert str(P().shape(LinearRing([(0, 0), (1, 0), (1, 1)]))) == "M0 0L1 0L1 1Z"
    multi = MultiPolygon([Polygon([(0, 0), (1, 0), (1, 1)]), Polygon([(5, 5), (6, 5), (6, 6)])])
    assert str(P().shape(multi)) == "M0 0L1 0L1 1ZM5 5L6 5L6 6Z"
    coll = GeometryCollection([Point(3, 3), LineString([(0, 0), (2, 0)]), Polygon()])
    assert str(P().shape(coll)) == "M0 0L2 0"
    assert P().shape(Polygon()).empty and P().shape(Point(1, 1)).empty
