"""Pin v1's helper outputs to helpers.json, for the v2 comparisons in tests/python/helpers/.

Covers poisson_disk, noise_grid, blue_noise (as ranks), threshold_matrix, dither (every
method but "random", reading a pinned field through v1's callback), and the (fill, d) paths
grid_runs, glyphs and sprite drew, with fills "#00000k" standing for palette entry k. v1 is
loaded the way noise.py loads it. Rerun only to add cases:
`uv run python tests/python/fixtures/v1_pins/helpers.py`.
"""

import json
import random
from pathlib import Path

from noise import v1

HERE = Path(__file__).parent

POISSON = [
    # seed, width, height, radius, k, x0, y0
    (9, 300, 200, 25, 30, 0, 0),
    (3, 120, 90, 11, 12, 40, -15),
    (0, 50.5, 70.25, 7.5, 30, 1.5, 2.5),
]
NOISE_GRID = [
    # cols, rows, scale, seed, octaves, gain
    (40, 23, 7, 4, 1, 0.5),
    (33, 20, 12, 0, 3, 0.5),
    (64, 36, 30, 7, 3, 0.55),
    (17, 45, 5.5, 11, 2, 0.6),
]
BLUE_NOISE = [
    # n, seed, sigma
    (16, 0, 1.5),
    (16, 7, 2.0),
    (64, 3, 1.5),
]
THRESHOLDS = [("bayer", 2), ("bayer", 4), ("bayer", 8), ("bayer", 16), ("clustered", 4)]
THRESHOLDS += [("lines", 3), ("lines", 4)]
DITHER = [
    # method, levels, matrix, seed, serpentine
    ("bayer", 2, 4, 0, False),
    ("bayer", 3, 2, 0, False),
    ("bayer", 5, 8, 0, False),
    ("clustered", 2, 4, 0, False),
    ("bluenoise", 2, 4, 3, False),
    ("bluenoise", 4, 16, 5, False),
    ("lines", 3, 3, 0, False),
    ("fs", 2, 4, 0, False),
    ("fs", 4, 4, 0, True),
    ("atkinson", 2, 4, 0, False),
    ("atkinson", 3, 4, 0, True),
    ("jarvis", 2, 4, 0, False),
    ("stucki", 3, 4, 0, False),
    ("burkes", 2, 4, 0, True),
    ("sierra", 2, 4, 0, False),
    ("sierra-lite", 5, 4, 0, False),
    ("riemersma", 2, 4, 0, False),
    ("riemersma", 4, 4, 0, False),
]
ROWS, COLS = 19, 27
GRID = [[0, 1, 1, 2, 0, 0, 3], [2, 2, 2, 2, 1, 0, 0], [0, 0, 3, 3, 3, 1, 1], [3, 3, 3, 3, 3, 3, 3]]
GRID_RUNS = [
    # cell, x, y, skip
    (6, 10, 20, 0),
    (2.5, 0, 0.5, None),
    (4, -8, 12, 2),
]
GLYPH_LINES = ["Hi, v1!", "0x1F \u2591\u2592\u2593\u2588", "\u250c\u2500\u2510 x"]
GLYPHS = [
    # font, px, x, y, gap, per-cell fills
    ("8x16", 2, 10, 20, 0, False),
    ("5x8", 3, 0, 4.5, 1, True),
    ("8x16", 1.5, 3, 0, 2, True),
]
CRAB = "..#.....#..|...#...#...|..#######..|.##.###.##.|###########|#.#######.#|#.#.....#.#|...##.##..."
SHIP = """
..ab..
.abba.
abbbba
a....a
"""
SPRITES = [
    # art, palette keys, cell, x, y
    (CRAB.split("|"), "#", 6, 300, 180),
    (SHIP, "ab", 4, 10.5, 7),
]


def fill(k: int) -> str:
    return f"#{k:06X}"


def paths(mod, draw) -> list[list[str]]:
    """The [fill, d] of each path v1's `draw(svg)` emitted, in order."""
    svg = mod.Svg(bg=None)
    draw(svg)
    out = []
    for line in svg.body:
        d = line.split(' d="')[1].split('"')[0]
        out.append([line.split(' fill="')[1].split('"')[0], d])
    return out


def cell_fill(c: int, r: int, ch: str) -> int | None:
    """The palette entry the per-cell glyph cases paint (col, row, ch) with; None skips."""
    return None if ch == "x" else (c + 2 * r) % 3 + 1


def field() -> list[list[float]]:
    """A diagonal ramp with grain, running a little past [0, 1] at both ends."""
    r = random.Random(2026)
    return [
        [-0.1 + 1.2 * (i + j) / (COLS + ROWS - 2) + r.uniform(-0.08, 0.08) for i in range(COLS)]
        for j in range(ROWS)
    ]


def main() -> None:
    mod = v1()
    f = field()
    out: dict[str, object] = {
        "poisson_disk": [
            {"args": list(a), "points": mod.poisson_disk(random.Random(a[0]), *a[1:])}
            for a in POISSON
        ],
        "noise_grid": [
            {
                "args": list(a),
                "grid": mod.noise_grid(*a[:3], seed=a[3], octaves=a[4], gain=a[5]).tolist(),
            }
            for a in NOISE_GRID
        ],
        "blue_noise": [
            {
                "args": [n, seed, sigma],
                "ranks": [
                    [round(v * n * n - 0.5) for v in row]
                    for row in mod.blue_noise(n, seed, sigma=sigma)
                ],
            }
            for n, seed, sigma in BLUE_NOISE
        ],
        "threshold_matrix": [
            {"args": [m, size], "matrix": mod.threshold_matrix(m, size)} for m, size in THRESHOLDS
        ],
        "dither_field": f,
        "dither": [
            {
                "args": [method, levels, matrix, seed, serpentine],
                "grid": mod.dither(
                    lambda i, j: f[j][i],
                    COLS,
                    ROWS,
                    levels,
                    method=method,
                    matrix=matrix,
                    seed=seed,
                    serpentine=serpentine,
                ),
            }
            for method, levels, matrix, seed, serpentine in DITHER
        ],
    }
    out["grid_runs"] = [
        {
            "args": [cell, x, y, skip],
            "paths": paths(
                mod,
                lambda svg, cell=cell, x=x, y=y, skip=skip: mod.grid_runs(
                    svg, GRID, [fill(k) for k in range(4)], cell, x, y, skip
                ),
            ),
        }
        for cell, x, y, skip in GRID_RUNS
    ]
    out["glyph_lines"] = GLYPH_LINES
    out["glyphs"] = [
        {
            "args": [font, px, x, y, gap, per_cell],
            "paths": paths(
                mod,
                lambda svg, font=font, px=px, x=x, y=y, gap=gap, per_cell=per_cell: mod.glyphs(
                    svg,
                    GLYPH_LINES,
                    (lambda c, r, ch: None if (k := cell_fill(c, r, ch)) is None else fill(k))
                    if per_cell
                    else fill(1),
                    font=font,
                    px=px,
                    x=x,
                    y=y,
                    gap=gap,
                ),
            ),
        }
        for font, px, x, y, gap, per_cell in GLYPHS
    ]
    out["sprite"] = [
        {
            "args": [art, keys, cell, x, y],
            "paths": paths(
                mod,
                lambda svg, art=art, keys=keys, cell=cell, x=x, y=y: mod.sprite(
                    svg, art, {ch: fill(k + 1) for k, ch in enumerate(keys)}, cell, x, y
                ),
            ),
        }
        for art, keys, cell, x, y in SPRITES
    ]
    lines = [f"{json.dumps(k)}: {json.dumps(v)}" for k, v in out.items()]
    (HERE / "helpers.json").write_text("{\n" + ",\n".join(lines) + "\n}\n")


if __name__ == "__main__":
    main()
