import math

import numpy as np
import pytest
from helpers_support import PINS
from shapely.geometry import LineString
from skimage.measure import approximate_polygon, find_contours

from walldye import Rect, field
from walldye._noise import Noise as CoreNoise
from walldye.field import (
    Noise,
    cells,
    falloff,
    gauss,
    iso_lines,
    noise_grid,
    runs,
    sample_field,
)


def test_exports_match_the_spec():
    assert sorted(field.__all__) == sorted(
        ["Noise", "noise_grid", "cells", "falloff", "gauss", "iso_lines", "runs", "sample_field"]
    )


def test_noise_is_the_core_noise():
    assert Noise is CoreNoise


@pytest.mark.parametrize("case", PINS["noise_grid"], ids=lambda c: str(c["args"]))
def test_noise_grid_equals_v1(case):
    cols, rows, scale, seed, octaves, gain = case["args"]
    rng = np.random.default_rng(seed)
    got = noise_grid(cols, rows, scale, rng, octaves=octaves, gain=gain)
    assert got.shape == (rows, cols)
    assert np.array_equal(got, np.array(case["grid"]))


def test_noise_grid_takes_any_size_without_padding():
    for cols, rows, scale in [(7, 3, 30), (1, 1, 0.5), (97, 61, 12), (200, 1, 7.3)]:
        g = noise_grid(cols, rows, scale, np.random.default_rng(cols), octaves=3)
        assert g.shape == (rows, cols) and np.isfinite(g).all() and np.abs(g).max() < 1.5


def test_noise_grid_errors():
    with pytest.raises(TypeError, match="Generator"):
        noise_grid(4, 4, 2, 7)
    with pytest.raises(ValueError):
        noise_grid(0, 4, 2, np.random.default_rng(1))
    with pytest.raises(ValueError):
        noise_grid(4, 4, 0, np.random.default_rng(1))
    with pytest.raises(ValueError):
        noise_grid(4, 4, 2, np.random.default_rng(1), octaves=0)


def test_cells_replace_mgrid_centres():
    w, h, ox, oy = 64, 44, 32, 40
    ys, xs = np.mgrid[0:h, 0:w]
    u, v = cells(Rect(-ox, -oy, w, h), 1)
    assert np.array_equal(u, xs + 0.5 - ox) and np.array_equal(v, ys + 0.5 - oy)
    # the on-canvas part of a square of cells around a sun near the edge
    cx, cy, cell, n, i0, j0 = 1400, 520, 6, 90, 3, 0
    cols, rows = 2 * n - i0, 2 * n - j0
    ys, xs = np.mgrid[j0 : j0 + rows, i0 : i0 + cols]
    rect = Rect(cx + (i0 - n) * cell, cy + (j0 - n) * cell, cols * cell, rows * cell)
    x, y = cells(rect, cell)
    assert np.allclose(x, cx + (xs + 0.5 - n) * cell) and np.allclose(y, cy + (ys + 0.5 - n) * cell)


def test_cells_cover_whole_cells_x_first():
    xs, ys = cells(Rect(10, 20, 35, 21), 10)
    assert xs.shape == ys.shape == (2, 3)
    assert xs[0].tolist() == [15, 25, 35] and ys[:, 0].tolist() == [25, 35]
    assert cells(Rect(0, 0, 5, 5), 10)[0].shape == (0, 0)
    with pytest.raises(ValueError):
        cells(Rect(0, 0, 5, 5), 0)


def test_falloff_is_the_clip_idiom():
    rr = np.linspace(-40, 700, 181).reshape(-1, 1) * np.ones((1, 3))
    # dunes
    assert np.array_equal(falloff(rr, 520, 1.3), np.clip(1 - rr / 520, 0, 1) ** 1.3)
    assert np.array_equal(falloff(rr, 150), np.clip(1 - rr / 150, 0, 1))
    for d in (-3.0, 0, 12, 149.9, 150, 900):
        assert falloff(d, 150, 0.7) == pytest.approx(float(falloff(np.array([d]), 150, 0.7)[0]))
    assert falloff(0, 10) == 1.0 and falloff(10, 10) == 0.0 and falloff(np.float32(5), 10) == 0.5
    assert isinstance(falloff(3, 10), float)
    with pytest.raises(ValueError):
        falloff(1, 0)
    with pytest.raises(TypeError):
        falloff(True, 3)


def test_gauss_is_the_exp_idiom():
    d = np.linspace(0, 400, 101)
    # dot-diffusion-caustics
    assert np.array_equal(gauss(d, 140), np.exp(-((d / 140) ** 2)))
    assert np.array_equal(gauss([[3.0, 60.0]], 30), np.exp(-((np.array([[3.0, 60.0]]) / 30) ** 2)))
    assert gauss(0, 5) == 1.0
    assert gauss(30, 30) == pytest.approx(math.exp(-1))
    with pytest.raises(ValueError):
        gauss(1, -2)


def attractor(n=48):
    """A smooth blobby density on an n x n grid, like dejong-veil's histogram after blurring."""
    y, x = np.mgrid[0:n, 0:n] / n
    return np.exp(-((x - 0.35) ** 2 + (y - 0.4) ** 2) / 0.02) + 0.8 * np.exp(
        -((x - 0.7) ** 2 + (y - 0.62) ** 2) / 0.01
    )


def test_iso_lines_match_dejong_veils_regions():
    density = attractor()
    cell, ox, oy, level = 22.5, 100 - 11.25, 60 - 11.25, 0.3
    want = []
    for c in find_contours(density, level):
        c = approximate_polygon(c, 0.25)
        want.append(np.array([(ox + j * cell, oy + i * cell) for i, j in c]))
    got = iso_lines(density, level, cell=cell, origin=(ox, oy), simplify=0.25 * cell)
    assert len(got) == len(want) == 2
    for g, w in zip(got, want, strict=True):
        assert g.shape == w.shape and np.allclose(g, w)
        assert np.array_equal(g[0], g[-1])  # closed lines repeat their first point


def test_iso_lines_match_nautical_charts_unsimplified_lines():
    depth = attractor(40)
    cell = 8
    for level in (0.1, 0.5, 0.9):
        want = [c[:, ::-1] * cell for c in find_contours(depth, level)]
        got = iso_lines(depth, level, cell=cell)
        assert len(got) == len(want)
        assert all(np.array_equal(g, w) for g, w in zip(got, want, strict=True))
    # nautical-chart then simplifies with shapely; skimage's Douglas-Peucker keeps the ends too
    line = iso_lines(depth[:, :20], 0.5, cell=cell, simplify=0.6)[0]
    assert np.array_equal(line[[0, -1]], iso_lines(depth[:, :20], 0.5, cell=cell)[0][[0, -1]])
    assert (
        LineString(line).hausdorff_distance(LineString(iso_lines(depth[:, :20], 0.5, cell=cell)[0]))
        <= 0.6 + 1e-9
    )


def test_iso_lines_errors():
    with pytest.raises(ValueError):
        iso_lines(np.zeros(5), 0)
    with pytest.raises(ValueError):
        iso_lines(np.zeros((1, 5)), 0)
    with pytest.raises(ValueError):
        iso_lines(np.zeros((5, 5)), 0, cell=0)
    with pytest.raises(ValueError):
        iso_lines(np.zeros((5, 5)), 0, simplify=-1)
    assert iso_lines(np.zeros((5, 5)), 1) == []


def crater_runs(on):
    """crater-field's run finder."""
    edges = np.flatnonzero(np.diff(np.concatenate([[0], on, [0]]).astype(int)))
    return list(zip(edges[::2].tolist(), edges[1::2].tolist(), strict=True))


def navball_runs(z):
    """The index ranges navball's visible_runs draws: runs of z > 0 longer than one point."""
    out, run = [], []
    for i, zz in enumerate(z):
        if zz > 0:
            run.append(i)
        else:
            if len(run) > 1:
                out.append((run[0], run[-1] + 1))
            run = []
    if len(run) > 1:
        out.append((run[0], run[-1] + 1))
    return out


def test_runs_match_crater_field_and_navball():
    rng = np.random.default_rng(5)
    for _ in range(20):
        z = rng.normal(size=int(rng.integers(0, 40)))
        assert runs(z > 0) == crater_runs(z > 0)
        assert [r for r in runs(z > 0) if r[1] - r[0] > 1] == navball_runs(z)
    assert runs([True, True, False, True]) == [(0, 2), (3, 4)]
    assert runs(np.zeros(0, dtype=bool)) == []
    assert all(isinstance(v, int) for r in runs([False, True]) for v in r)


def test_runs_errors():
    with pytest.raises(TypeError):
        runs([0, 1, 1])
    with pytest.raises(ValueError):
        runs(np.ones((2, 2), dtype=bool))


def test_sample_field_matches_v1_on_eclipse_contours():
    n, cell, half = Noise(7), 6, 20
    cx, cy = 900, 540
    ox, oy = cx - half * cell, cy - half * cell

    def f(i, j):  # eclipse-contours' scalar field, as v1's sample_field called it
        dx, dy = ox + i * cell - cx, oy + j * cell - cy
        d = math.hypot(dx, dy) / 330
        return n.fbm(2.95 + dx / 420, 1.29 + dy / 420, 4) - 0.9 * max(0.0, d - 0.85)

    def fv(i, j):  # the same field, vectorised
        dx, dy = ox + i * cell - cx, oy + j * cell - cy
        d = np.hypot(dx, dy) / 330
        return n.fbm(2.95 + dx / 420, 1.29 + dy / 420, 4) - 0.9 * np.maximum(0.0, d - 0.85)

    want = [[f(i, j) for i in range(2 * half + 1)] for j in range(2 * half + 1)]
    got = sample_field(fv, 2 * half, 2 * half)
    assert got.dtype == np.float64 and np.allclose(got, want, rtol=0, atol=1e-12)


def test_sample_field_calls_once_with_lattice_indices():
    calls = []

    def fn(i, j):
        calls.append((i.shape, i.dtype, j.shape))
        return i * 100 + j

    got = sample_field(fn, 3, 2)
    assert calls == [((3, 4), np.int64, (3, 4))]
    assert got.tolist() == [[0, 100, 200, 300], [1, 101, 201, 301], [2, 102, 202, 302]]
    assert sample_field(lambda i, j: 0.5, 2, 1).tolist() == [[0.5] * 3] * 2
    with pytest.raises(ValueError):
        sample_field(lambda i, j: np.zeros(7), 2, 1)
    with pytest.raises(ValueError):
        sample_field(lambda i, j: i, 0, 1)
