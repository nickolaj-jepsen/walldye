import math

import numpy as np
import pytest

from walldye._affine import Affine


def close(p, q) -> bool:
    return all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(p, q, strict=True))


def test_basic_maps():
    assert Affine.identity()((3, 4)) == (3.0, 4.0)
    assert Affine.translate(1, 2)((3, 4)) == (4.0, 6.0)
    assert Affine.scale(2)((3, 4)) == (6.0, 8.0)
    assert Affine.scale(2, 3, about=(1, 1))((2, 2)) == (3.0, 4.0)
    assert close(Affine.rotate(deg=90)((1, 0)), (0, 1))  # clockwise on screen
    assert close(Affine.rotate(rad=math.pi, about=(1, 1))((2, 1)), (0, 1))


def test_frame():
    f = Affine.frame((10, 10), bearing=90, scale=2)
    assert close(f((0, 0)), (10, 10))
    assert close(f((1, 0)), (12, 10))  # local +x along the bearing (east)
    assert close(f((0, 1)), (10, 12))  # local +y a quarter turn clockwise from it
    assert close(Affine.frame((0, 0), deg=0)((1, 0)), (1, 0))
    assert close(Affine.frame((0, 0), rad=math.pi / 2)((1, 0)), (0, 1))


def test_compose_apply_and_inverse():
    m, n = Affine.rotate(deg=30, about=(5, 5)), Affine.translate(3, -2) @ Affine.scale(1.5)
    p = (7.0, -3.0)
    assert close((m @ n)(p), m(n(p)))
    pts = np.array([[0.0, 0.0], [1.0, 2.0], [-3.0, 4.5]])
    got = (m @ n).apply(pts)
    assert got.shape == (3, 2)
    for row, q in zip(got, pts, strict=True):
        assert close(row, (m @ n)(q))
    inv = (m @ n).inverse()
    assert close(inv((m @ n)(p)), p)
    assert Affine.identity().apply([]).shape == (0, 2)
    with pytest.raises(ValueError):
        Affine.scale(0).inverse()
    with pytest.raises(ValueError):
        Affine.identity().apply([1, 2, 3])


def test_errors():
    with pytest.raises(TypeError):
        Affine.rotate()
    with pytest.raises(TypeError):
        Affine.frame((0, 0), deg=1, bearing=2)
    with pytest.raises(TypeError):
        Affine(True, 0, 0, 1, 0, 0)
    with pytest.raises(ValueError):
        Affine(float("nan"), 0, 0, 1, 0, 0)
    assert Affine(np.float32(1), 0, 0, 1, 0, 0).a == 1.0
