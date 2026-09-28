import json
from pathlib import Path

import numpy as np
import pytest

from walldye._noise import Noise

PINS = json.loads((Path(__file__).parents[1] / "fixtures" / "v1_pins" / "noise.json").read_text())


@pytest.mark.parametrize("pin", PINS, ids=lambda p: repr(p["seed"]))
def test_scalars_equal_v1(pin):
    n = Noise(pin["seed"])
    for p in pin["points"]:
        x, y, z = p["xyz"]
        assert n(x, y) == p["n2"]
        assert n.n3(x, y, z) == p["n3"]
        assert n.fbm(x / 50, y / 50) == p["fbm"]
        assert n.fbm(x / 50, y / 50, 3, 2.5, 0.4) == p["fbm_3_2.5_0.4"]


@pytest.mark.parametrize("seed", [0, 5, "11:5"])
def test_arrays_equal_scalars(seed):
    n = Noise(seed)
    r = np.random.default_rng(9)
    x, y, z = r.uniform(-300, 300, 500), r.uniform(-300, 300, 500), r.uniform(-40, 40, 500)
    x[:3] = (0.0, 1.0, -1.0)
    assert n(x, y).tolist() == [n(a, b) for a, b in zip(x, y, strict=True)]
    assert n.n3(x, y, z).tolist() == [n.n3(a, b, c) for a, b, c in zip(x, y, z, strict=True)]
    assert n.fbm(x / 50, y / 50).tolist() == [
        n.fbm(a / 50, b / 50) for a, b in zip(x, y, strict=True)
    ]


def test_broadcasting_and_types():
    n = Noise(3)
    grid = n(np.arange(4.0)[None, :] * 0.3, np.arange(3.0)[:, None] * 0.7)
    assert grid.shape == (3, 4) and grid.dtype == np.float64
    assert grid[2, 1] == n(0.3, 1.4)
    assert type(n(1.5, 2.5)) is float and type(n(np.float64(1.5), 2)) is float
    assert n(np.float64(1.5), 2.5) == n(1.5, 2.5)
    assert n.fbm([0.1, 0.2], 0.3).shape == (2,)
    with pytest.raises(TypeError):
        Noise(True)
    with pytest.raises(TypeError):
        Noise(1.5)
    with pytest.raises(TypeError):
        n(True, 1)
