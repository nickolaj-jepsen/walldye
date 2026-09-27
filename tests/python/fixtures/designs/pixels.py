"""Pixel cells anchored off the whole-unit grid, on every screen shape."""

from walldye import ACCENT, BG, H, W, grid_runs

ASPECTS = ["any"]


def draw(s):
    grid_runs(s, [[1, 0, 1], [0, 1, 0]], [BG, ACCENT], 3, 0.37 * W, 0.41 * H)
