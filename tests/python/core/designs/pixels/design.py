"""Pixel rows read from data files, stamped as crisp cells in two grids."""

from walldye import ACCENT, UI, Canvas, P, design


@design()
def draw(s: Canvas) -> None:
    rows: list[str] = s.data("rows.json")
    names = s.data("names.txt").split()
    grid = s.data("grid.npy")
    cell = 12
    lit, dim = P(), P()
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == "#":
                lit.rect(120 + i * cell, 120 + j * cell, cell, cell)
    for (j, i), v in zip(zip(*grid.nonzero(), strict=True), grid[grid.nonzero()], strict=True):
        (dim if v == 1 else lit).rect(600 + i * cell, 120 + j * cell, cell, cell)
    s.pixel_path(lit, ACCENT, cell=cell, origins=[(120, 120), (600, 120)])
    s.pixel_path(dim, UI, cell=cell, origins=[(600, 120)])
    s.pixel_path(P(), UI, cell=cell, origins=[(0, 0)])
    s.stroke(P().M(120, 100).H(120 + 40 * len(names)), UI, 2)
