import math
import random

import numpy as np
import pytest

from walldye import Rect, Vec, clamp, lerp, polar, smoothstep
from walldye._vec import angle


def floats(v: Vec) -> bool:
    return type(v) is Vec and type(v.x) is float and type(v.y) is float


def test_vec_is_a_tuple():
    v = Vec(3.0, 4.0)
    x, y = v
    assert (x, y) == (3.0, 4.0) and [*v] == [3.0, 4.0] and v == (3.0, 4.0)
    assert abs(v) == 5.0
    assert v.dot((1, 2)) == 11.0
    assert Vec(1.0, 0.0).perp() == (0.0, 1.0)  # a quarter turn clockwise on screen
    assert Vec(3.0, 4.0).unit() == (0.6, 0.8)
    with pytest.raises(ValueError):
        Vec(0.0, 0.0).unit()


def test_vec_arithmetic_with_points_and_numbers():
    v = Vec(1.0, 2.0)
    for got, want in (
        (v + (1, 2), (2.0, 4.0)),
        ((1, 2) + v, (2.0, 4.0)),
        (v - (1, 1), (0.0, 1.0)),
        ((5, 5) - v, (4.0, 3.0)),
        (v + Vec(1.0, 1.0), (2.0, 3.0)),
        (v * 2, (2.0, 4.0)),
        (2 * v, (2.0, 4.0)),
        (v * 2.5, (2.5, 5.0)),
        (v / 2, (0.5, 1.0)),
        (-v, (-1.0, -2.0)),
        (np.float64(2) * v, (2.0, 4.0)),
        (np.int64(2) * v, (2.0, 4.0)),
        (v * np.float32(0.5), (0.5, 1.0)),
        (v + (np.float64(1), np.int64(1)), (2.0, 3.0)),
    ):
        assert floats(got) and got == want
    t = np.linspace(0, 1, 5)[2]
    assert floats(t * (v - (0, 0)))
    assert floats(Vec(1, 2).perp()) and floats(-Vec(1, 2))


def test_vec_with_arrays_gives_arrays():
    v = Vec(1.0, 2.0)
    arr = np.array([[1.0, 2.0], [3.0, 5.0]])
    for got, want in (
        (v + arr, [[2, 4], [4, 7]]),
        (arr + v, [[2, 4], [4, 7]]),
        (arr - v, [[0, 0], [2, 3]]),
        (v - arr, [[0, 0], [-2, -3]]),
        (arr / v, [[1, 1], [3, 2.5]]),
        (v * np.array([2.0, 3.0]), [2, 6]),
    ):
        assert type(got) is np.ndarray
        assert got.tolist() == want
    assert np.cos(v).tolist() == [math.cos(1.0), math.cos(2.0)]


def test_vec_operator_errors():
    v = Vec(1.0, 2.0)
    for op, other in (("__add__", 3), ("__add__", (1, 2, 3)), ("__add__", "ab"),
                      ("__radd__", (True, 1)), ("__sub__", None), ("__rsub__", 3),
                      ("__mul__", v), ("__mul__", True), ("__rmul__", "x"),
                      ("__truediv__", (1, 2)), ("__rtruediv__", 3)):  # fmt: skip
        assert getattr(v, op)(other) is NotImplemented
    with pytest.raises(TypeError, match="unsupported operand"):
        v * True
    with pytest.raises(TypeError, match="unsupported operand"):
        v + (1, 2, 3)
    with pytest.raises(TypeError):
        3 / v
    with pytest.raises(TypeError, match="unsupported operand"):
        v + 3

    class Scale:
        """An operand that implements the reflected operator itself."""

        def __radd__(self, o: Vec) -> str:
            return "reflected"

    assert v + Scale() == "reflected"
    with pytest.raises(ValueError, match="finite"):
        v + (math.nan, 1)


def test_rotate():
    v = Vec(2.0, 0.0)
    got = v.rotate(deg=90)
    assert got.x == pytest.approx(0) and got.y == pytest.approx(2)  # clockwise on screen
    got = v.rotate(rad=math.pi, about=(1, 0))
    assert got.x == pytest.approx(0) and got.y == pytest.approx(0)
    with pytest.raises(TypeError, match="exactly one"):
        v.rotate()
    with pytest.raises(TypeError, match="exactly one"):
        v.rotate(deg=1, rad=1)


def test_angle_keywords():
    assert angle(90, None, None) == math.radians(90)
    assert angle(None, 1.5, None) == 1.5
    assert angle(None, None, 0) == math.radians(-90)
    with pytest.raises(TypeError):
        angle(None, None, None)
    with pytest.raises(TypeError):
        angle(True, None, None)
    with pytest.raises(ValueError):
        angle(float("nan"), None, None)


def test_polar():
    assert polar((10, 10), 5, deg=0) == (15.0, 10.0)
    up = polar((10, 10), 5, bearing=0)
    assert up.x == pytest.approx(10) and up.y == pytest.approx(5)
    east = polar((0, 0), 1, bearing=90)
    assert east.x == pytest.approx(1) and east.y == pytest.approx(0)
    for b in (0, 37.5, 200):
        assert polar((1, 2), 3, bearing=b) == polar((1, 2), 3, deg=b - 90)
    assert polar((0, 0), 2, rad=math.pi / 2).y == 2.0
    with pytest.raises(TypeError):
        polar((0, 0), 1)
    with pytest.raises(TypeError):
        polar((0, 0), 1, deg=1, bearing=1)


def test_rect():
    r = Rect(10, 20, 100, 50)
    assert (r.x1, r.y1) == (110, 70)
    assert r.center == (60.0, 45.0)
    assert r.frac(0.5, 1) == (60.0, 70.0)
    assert r.contains((10, 20)) and r.contains((110, 70))
    assert not r.contains((9.9, 20))
    assert r.contains((9, 20), margin=1)
    assert Rect(*r) == r


def v1_lerp(a, b, t):
    return a + (b - a) * t


def v1_clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else min(v, hi)


def v1_smoothstep(e0, e1, x):
    t = v1_clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def test_scalar_maths_is_bit_identical_to_v1():
    r = random.Random(3)
    for _ in range(2000):
        a, b, t = r.uniform(-50, 50), r.uniform(-50, 50), r.uniform(-1, 2)
        assert lerp(a, b, t) == v1_lerp(a, b, t)
        assert clamp(t) == v1_clamp(t)
        assert clamp(a, -10, 10) == v1_clamp(a, -10, 10)
        if a != b:
            assert smoothstep(a, b, t * 50) == v1_smoothstep(a, b, t * 50)
    assert type(lerp(1, 3, 0.5)) is float and type(clamp(2)) is float
    assert type(smoothstep(0, 1, np.float64(0.3))) is float


def test_array_maths_is_element_wise():
    r = np.random.default_rng(1)
    a, b, t = r.uniform(-5, 5, 50), r.uniform(-5, 5, 50), r.uniform(-1, 2, 50)
    assert lerp(a, b, t).tolist() == [lerp(*v) for v in zip(a, b, t, strict=True)]
    assert clamp(t).tolist() == [clamp(v) for v in t]
    assert smoothstep(0.2, 0.8, t).tolist() == [smoothstep(0.2, 0.8, v) for v in t]
    assert smoothstep(0.8, 0.2, t).tolist() == [smoothstep(0.8, 0.2, v) for v in t]
    assert lerp(0, 10, [0.5, 1]).tolist() == [5.0, 10.0]
    assert clamp([-1, 3], 0, 2).dtype == np.float64


def test_smoothstep_edges():
    assert smoothstep(1, 0, 0.25) == pytest.approx(1 - smoothstep(0, 1, 0.25))
    with pytest.raises(ValueError):
        smoothstep(1, 1, 0.5)
    with pytest.raises(ValueError):
        smoothstep(np.array([1, 2]), np.array([1, 3]), 0.5)
