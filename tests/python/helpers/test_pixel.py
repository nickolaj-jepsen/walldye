import numpy as np
import pytest
from helpers_support import PINS, canvas, drawn, rects

from walldye import ACCENT, BG_ALT, FG, UI, UI_HI, mix, pixel
from walldye.pixel import (
    Pixels,
    bayer,
    blue_noise,
    dither,
    glyph,
    glyphs,
    grid_runs,
    sprite,
    text_width,
    threshold_matrix,
)


def test_exports_match_the_spec():
    assert sorted(pixel.__all__) == sorted(
        [
            "Pixels",
            "grid_runs",
            "dither",
            "bayer",
            "blue_noise",
            "threshold_matrix",
            "sprite",
            "glyph",
            "glyphs",
            "text_width",
            "Font",
            "DitherMethod",
        ]
    )


# Palette entry k stands for v1's fill "#00000k" in the pinned drawings.
PALETTE = (BG_ALT, UI, ACCENT, FG)
GRID = np.array([[0, 1, 1, 2, 0, 0, 3], [2, 2, 2, 2, 1, 0, 0], [0, 0, 3, 3, 3, 1, 1], [3] * 7])


def as_v1(doc) -> list[tuple[int, list]]:
    """The drawn pixel paths as (palette index, rectangles), comparable with the v1 pins."""
    return [(PALETTE.index(fill), rects(d)) for fill, d, _ in drawn(doc)]


def pinned(case) -> list[tuple[int, list]]:
    return [(int(fill[1:], 16), rects(d)) for fill, d in case["paths"]]


@pytest.mark.parametrize("case", PINS["grid_runs"], ids=lambda c: str(c["args"]))
def test_grid_runs_draws_what_v1_drew(case):
    cell, x, y, skip = case["args"]
    s, doc = canvas()
    grid_runs(s, GRID, PALETTE, cell, (x, y), skip=skip)
    assert as_v1(doc) == pinned(case)
    assert doc.grids == [(cell, x, y)] * len(case["paths"])


@pytest.mark.parametrize("seed", range(5))
def test_grid_runs_cover_each_index_with_maximal_runs(seed):
    rng = np.random.default_rng(seed)
    grid = rng.integers(0, 4, (int(rng.integers(1, 12)), int(rng.integers(1, 12))))
    grid[:, :2] = grid[:, :1]  # some longer runs
    s, doc = canvas()
    grid_runs(s, grid, PALETTE, 3, (6, 9))
    for fill, d, _ in drawn(doc):
        k = PALETTE.index(fill)
        runs = rects(d)
        cells = {
            (round((x - 6) / 3) + i, round((y - 9) / 3))
            for x, y, w, _ in runs
            for i in range(round(w / 3))
        }
        assert cells == {(i, j) for j, i in zip(*np.nonzero(grid == k), strict=True)}
        for x, y, w, _ in runs:  # maximal: the cells either side of a run hold another index
            i0, i1, j = round((x - 6) / 3), round((x + w - 6) / 3), round((y - 9) / 3)
            assert i0 == 0 or grid[j, i0 - 1] != k
            assert i1 == grid.shape[1] or grid[j, i1] != k
    assert 0 not in [PALETTE.index(fill) for fill, _, _ in drawn(doc)]  # skip=0 by default


def test_grid_runs_paths_are_absolute_rectangles_sharing_edges():
    s, doc = canvas()
    grid_runs(s, [[1, 2, 2], [0, 1, 1]], [None, UI, ACCENT], 7.5, (0.5, 2))
    (_, d1, line), (_, d2, _) = drawn(doc)
    assert d1 == "M0.5 2H8V9.5H0.5ZM8 9.5H23V17H8Z"
    assert d2 == "M8 2H23V9.5H8Z"
    assert line.startswith(f'<path d="{d1}" class="px" fill="')


def test_grid_runs_skip_none_entries_and_style():
    s, doc = canvas()
    grid = np.array([[0, 1, 2], [2, 1, 0]], dtype=np.uint8)
    grid_runs(s, grid, [UI, None, ACCENT], 2, skip=None, opacity=0.5)
    out = drawn(doc)
    assert [fill for fill, _, _ in out] == [UI, ACCENT]
    assert all(line.endswith(' opacity="0.5"/>') for _, _, line in out)
    s, doc = canvas()
    grid_runs(s, [[9, 9], [9, 1]], [None, UI], 2, skip=9)  # skipped cells need no palette entry
    assert [rects(d) for _, d, _ in drawn(doc)] == [[(2.0, 2.0, 2.0, 2.0)]]
    s, doc = canvas()
    grid_runs(s, np.zeros((3, 4), dtype=np.int64), PALETTE, 2)
    assert drawn(doc) == [] and doc.grids == []


def test_grid_runs_errors():
    s, _ = canvas()
    with pytest.raises(IndexError, match="index 4"):
        grid_runs(s, [[0, 4]], PALETTE, 2)
    with pytest.raises(IndexError, match="index -1"):
        grid_runs(s, [[-1, 1]], PALETTE, 2)
    with pytest.raises(TypeError, match="integer index grid"):
        grid_runs(s, [[None, 1]], PALETTE, 2)
    with pytest.raises(TypeError):
        grid_runs(s, np.ones((2, 2), dtype=bool), PALETTE, 2)
    with pytest.raises(TypeError):
        grid_runs(s, np.ones((2, 2)), PALETTE, 2)
    with pytest.raises(ValueError, match="grid"):
        grid_runs(s, [1, 2], PALETTE, 2)
    with pytest.raises(ValueError, match="cell"):
        grid_runs(s, GRID, PALETTE, 0)
    with pytest.raises(TypeError):
        grid_runs(s, GRID, PALETTE, 2, skip=True)
    with pytest.raises(TypeError, match="raw colour"):
        grid_runs(s, [[1]], [None, "#FF0000"], 2)


@pytest.mark.parametrize("case", PINS["sprite"], ids=lambda c: c["args"][1])
def test_sprite_draws_what_v1_drew(case):
    art, keys, cell, x, y = case["args"]
    s, doc = canvas()
    sprite(s, art, {ch: PALETTE[k + 1] for k, ch in enumerate(keys)}, cell, (x, y))
    assert as_v1(doc) == pinned(case)
    assert doc.grids == [(cell, x, y)] * len(case["paths"])


def test_sprite_rows_and_errors():
    s, doc = canvas()
    sprite(s, ["ab", "b"], {"b": UI, "a": ACCENT}, 3)  # ragged rows; paths in sorted key order
    assert [(fill, rects(d)) for fill, d, _ in drawn(doc)] == [
        (ACCENT, [(0.0, 0.0, 3.0, 3.0)]),
        (UI, [(3.0, 0.0, 3.0, 3.0), (0.0, 3.0, 3.0, 3.0)]),
    ]
    with pytest.raises(ValueError, match="single characters"):
        sprite(s, "ab", {"ab": UI}, 3)
    with pytest.raises(TypeError):
        sprite(s, [1, 2], {"a": UI}, 3)


def cell_fill(c: int, r: int, ch: str) -> int | None:
    """The pinned per-cell glyph fills: palette entry (c + 2r) % 3 + 1, none for "x"."""
    return None if ch == "x" else (c + 2 * r) % 3 + 1


@pytest.mark.parametrize("case", PINS["glyphs"], ids=lambda c: str(c["args"]))
def test_glyphs_draw_what_v1_drew(case):
    font, px, x, y, gap, per_cell = case["args"]
    s, doc = canvas()

    def paint(c: int, r: int, ch: str):
        k = cell_fill(c, r, ch)
        return None if k is None else PALETTE[k]

    fill = paint if per_cell else PALETTE[1]
    glyphs(s, PINS["glyph_lines"], fill, at=(x, y), font=font, px=px, gap=gap)
    assert as_v1(doc) == pinned(case)


def glyph_cells(ch: str, font: str, x: float, y: float, px: float, flip: bool = False) -> set:
    """The (x, y) top-left corners of the pixels of one glyph drawn at (x, y)."""
    bits = glyph(ch, font)[:, ::-1] if flip else glyph(ch, font)
    return {(x + i * px, y + j * px) for j, i in zip(*np.nonzero(bits), strict=True)}


def cells_of(d: str, px: float) -> set:
    return {(x + k * px, y) for x, y, w, _ in rects(d) for k in range(round(w / px))}


@pytest.mark.parametrize(("anchor", "shift"), [("start", 0), ("middle", 0.5), ("end", 1)])
def test_glyphs_anchor_places_each_line_on_its_own(anchor, shift):
    s, doc = canvas()
    lines = ["AB", "CDEF"]
    glyphs(s, lines, UI, at=(100, 50), font="5x8", px=2, gap=1, anchor=anchor)
    ((_, d, _),) = drawn(doc)
    want = set()
    origins = []
    for r, line in enumerate(lines):
        lx = 100 - shift * text_width(line, font="5x8", px=2, gap=1)
        ly = 50 + r * (8 + 1) * 2
        origins.append((2.0, lx, ly))
        for c, ch in enumerate(line):
            want |= glyph_cells(ch, "5x8", lx + c * 12, ly, 2)
    assert cells_of(d, 2) == want
    assert doc.grids == origins


def test_glyphs_flip_mirrors_each_character_in_place():
    s, doc = canvas()
    glyphs(s, "Fb7", UI, at=(0, 0), flip=True)
    ((_, d, _),) = drawn(doc)
    want = set().union(
        *(glyph_cells(ch, "8x16", c * 16, 0, 2, flip=True) for c, ch in enumerate("Fb7"))
    )
    assert cells_of(d, 2) == want
    assert want != set().union(
        *(glyph_cells(ch, "8x16", c * 16, 0, 2) for c, ch in enumerate("Fb7"))
    )


def test_glyphs_group_by_paint_formula_and_by_key():
    s, doc = canvas()
    # two mixes with one hex under some themes still get their own paths, in first-seen order
    a, b = mix(UI, UI_HI, 0.5), mix(UI_HI, UI, 0.5)
    glyphs(s, ["xy", "yx"], lambda c, r, ch: a if ch == "x" else b, at=(0, 0), px=1)
    assert [fill for fill, _, _ in drawn(doc)] == [a, b]
    assert doc.grids == [(1.0, 0.0, 0.0), (1.0, 0.0, 16.0)] * 2
    s, doc = canvas()
    glyphs(s, "ab c", UI, at=(0, 0), key=lambda c, r, ch: ch == "c")
    assert [fill for fill, _, _ in drawn(doc)] == [UI, UI]
    with pytest.raises(ValueError, match="two paints"):
        glyphs(s, "ab", lambda c, r, ch: UI if ch == "a" else ACCENT, at=(0, 0), key=lambda *_: 0)


def test_glyphs_skip_spaces_none_and_blank_lines():
    s, doc = canvas()
    glyphs(s, "  \n\nab", lambda c, r, ch: None if ch == "a" else UI, at=(0, 0), px=1)
    ((_, d, _),) = drawn(doc)
    assert cells_of(d, 1) == glyph_cells("b", "8x16", 8, 32, 1)
    assert doc.grids == [(1.0, 0.0, 32.0)]
    s, doc = canvas()
    glyphs(s, " ", UI, at=(0, 0))
    glyphs(s, [], UI, at=(0, 0))
    assert drawn(doc) == [] and doc.grids == []


def test_glyphs_errors():
    s, _ = canvas()
    with pytest.raises(ValueError, match="font"):
        glyphs(s, "a", UI, at=(0, 0), font="6x12")
    with pytest.raises(ValueError, match="anchor"):
        glyphs(s, "a", UI, at=(0, 0), anchor="left")
    with pytest.raises(ValueError, match="px"):
        glyphs(s, "a", UI, at=(0, 0), px=0)
    with pytest.raises(ValueError, match="gap"):
        glyphs(s, "a", UI, at=(0, 0), gap=-1)
    with pytest.raises(TypeError):
        glyphs(s, [1], UI, at=(0, 0))


def test_glyph_bitmaps():
    a = glyph("A")
    assert a.shape == (16, 8) and a.dtype == np.bool_ and a.any()
    assert glyph("A", "5x8").shape == (8, 5)
    assert not glyph("一").any()  # not in the font: blank
    a[:] = False
    assert glyph("A").any()  # callers get their own copy
    assert glyph("█").all()  # the full block
    with pytest.raises(ValueError):
        glyph("ab")
    with pytest.raises(ValueError):
        glyph("a", "3x5")


def test_text_width():
    font_w = (5 + 1) * 2  # timing-diagram's FONT_W for 5x8 glyphs at px 2, gap 1
    for msg in ("ACK", "0x1F", "a"):
        assert text_width(msg, font="5x8", px=2, gap=1) == len(msg) * font_w - 2
    assert text_width("abc") == 48
    assert text_width("abc", px=1.5, gap=2) == (3 * 10 - 2) * 1.5
    assert text_width("") == 0
    with pytest.raises(ValueError):
        text_width("a", gap=-1)


def spelunky_stamp(g, art, pal, x, y):
    """A v1 design's stamp, with its role lookup folded into `pal`."""
    rows = art.strip("\n").split("\n") if isinstance(art, str) else art
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in pal and 0 <= y + j < g.shape[0] and 0 <= x + i < g.shape[1]:
                g[y + j, x + i] = pal[ch]


ROPE_TOP = """
...aa...
..abba..
.abaaca.
acadeaca
"""


@pytest.mark.parametrize(("x", "y"), [(2, 1), (-3, 0), (8, 5), (0, -2)])
def test_pixels_stamp_matches_spelunky(x, y):
    key = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
    px = Pixels(10, 7, [None, *([UI] * 5)])
    px.stamp(ROPE_TOP, x, y, key)
    want = np.zeros((7, 10), dtype=np.int64)
    spelunky_stamp(want, ROPE_TOP, key, x, y)
    assert np.array_equal(px.grid, want)


def test_pixels_stamp_flip_mirrors_within_the_art_width():
    px = Pixels(6, 2, [None, UI, ACCENT])
    px.stamp(["ab.", "a"], 1, 0, {"a": 1, "b": 2}, flip=True)
    assert px.grid.tolist() == [[0, 0, 2, 1, 0, 0], [0, 0, 0, 1, 0, 0]]
    with pytest.raises(IndexError):
        px.stamp("a", 0, 0, {"a": 3})
    with pytest.raises(TypeError):
        px.stamp("a", 0.5, 0, {"a": 1})


def crane_bresenham(x0, y0, x1, y1):
    """A v1 design's bresenham: the 8-connected cells from (x0, y0) to (x1, y1)."""
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
    err, out = dx + dy, []
    while True:
        out.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return out
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


@pytest.mark.parametrize(
    "seg", [(0, 0, 9, 3), (9, 6, 1, 0), (4, 4, 4, 4), (-5, 2, 14, 5), (3, -4, 5, 10), (0, 6, 9, 6)]
)
def test_pixels_line_matches_crane_bresenham(seg):
    px = Pixels(10, 7, [None, UI])
    px.line(*seg, 1)
    want = np.zeros((7, 10), dtype=np.int64)
    for x, y in crane_bresenham(*seg):
        if 0 <= x < 10 and 0 <= y < 7:
            want[y, x] = 1
    assert np.array_equal(px.grid, want)
    assert px.grid[seg[1], seg[0]] == 1 or not (0 <= seg[0] < 10 and 0 <= seg[1] < 7)


def test_pixels_dither_writes_levels_where_asked():
    field = np.array(PINS["dither_field"])
    rows, cols = field.shape
    px = Pixels(cols, rows, [None, UI, ACCENT, FG])
    px.grid[:, :2] = 3
    where = np.zeros(field.shape, dtype=bool)
    where[:, 2:] = True
    px.dither(field, [0, 2, 1], method="fs", where=where)
    want = np.array([0, 2, 1])[dither(field, 3, method="fs")]
    assert np.array_equal(px.grid[:, 2:], want[:, 2:])
    assert (px.grid[:, :2] == 3).all()
    px.dither(field, [1, 2], method="bayer", matrix=2)
    assert np.array_equal(px.grid, np.array([1, 2])[dither(field, 2, matrix=2)])
    with pytest.raises(ValueError, match="shape"):
        px.dither(field[1:], [0, 1])
    with pytest.raises(IndexError):
        px.dither(field, [0, 4])
    with pytest.raises(TypeError, match="boolean"):
        px.dither(field, [0, 1], where=where.astype(int))


def test_pixels_draw_is_grid_runs():
    px = Pixels(7, 4, PALETTE)
    px.grid[:] = GRID
    s, doc = canvas()
    px.draw(s, 6, (10, 20))
    assert as_v1(doc) == pinned(PINS["grid_runs"][0])
    assert px.grid.dtype == np.int64 and px.palette == PALETTE and (px.cols, px.rows) == (7, 4)
    with pytest.raises(ValueError):
        Pixels(0, 3, PALETTE)
    with pytest.raises(ValueError):
        Pixels(3, 3, [])


@pytest.mark.parametrize("case", PINS["dither"], ids=lambda c: str(c["args"]))
def test_dither_equals_v1(case):
    method, levels, matrix, seed, serpentine = case["args"]
    rng = np.random.default_rng(seed) if method == "bluenoise" else None
    field = np.array(PINS["dither_field"])
    got = dither(field, levels, method=method, matrix=matrix, rng=rng, serpentine=serpentine)
    assert got.dtype == np.int64
    assert np.array_equal(got, np.array(case["grid"]))


@pytest.mark.parametrize(
    "method",
    ["bayer", "clustered", "lines", "fs", "atkinson", "jarvis", "stucki", "burkes", "sierra"]
    + ["sierra-lite", "riemersma", "bluenoise", "random"],
)
def test_dither_levels_stay_in_range_and_follow_the_field(method):
    field = np.random.default_rng(9).uniform(-0.5, 1.5, (23, 31))
    for levels in (2, 3, 7):
        got = dither(field, levels, method=method, rng=np.random.default_rng(2))
        assert got.shape == field.shape and got.min() >= 0 and got.max() <= levels - 1
        assert (got[field <= 0] == 0).all() and (got[field >= 1] == levels - 1).all()
    ramp = np.tile(np.linspace(0, 1, 64), (16, 1))
    # the ink of 8-column blocks follows the ramp
    ink = dither(ramp, 2, method=method, rng=np.random.default_rng(2)).reshape(16, 8, 8)
    assert np.corrcoef(ink.mean(axis=(0, 2)), np.arange(8))[0, 1] > 0.95


def test_dither_takes_any_array_like_and_clamps():
    assert dither([[-5.0, 0.0, 1.0, 7.0]], 3, method="bayer").tolist() == [[0, 0, 2, 2]]
    assert dither([[0.5] * 3], 2, method="fs").tolist() == [[0, 1, 0]]


def test_dither_random_uses_the_generator():
    field = np.full((5, 70), 0.5)
    got = dither(field, 2, method="random", matrix=4, rng=np.random.default_rng(1))
    thr = np.random.default_rng(1).random((64, 64))
    assert np.array_equal(got, (0.5 > thr[np.arange(5)[:, None] % 64, np.arange(70) % 64]) * 1)


def test_dither_errors():
    with pytest.raises(ValueError, match="levels"):
        dither([[0.5]], 1)
    with pytest.raises(ValueError, match="finite"):
        dither([[np.nan]], 2)
    with pytest.raises(ValueError, match="rows, cols"):
        dither([0.5], 2)
    with pytest.raises(ValueError, match="rng"):
        dither([[0.5]], 2, method="bluenoise")
    with pytest.raises(ValueError, match="rng"):
        dither([[0.5]], 2, method="random")
    with pytest.raises(ValueError, match="method"):
        dither([[0.5]], 2, method="halftone")


@pytest.mark.parametrize("case", PINS["threshold_matrix"], ids=lambda c: str(c["args"]))
def test_threshold_matrix_equals_v1(case):
    method, size = case["args"]
    assert np.array_equal(threshold_matrix(method, size), np.array(case["matrix"]))


def test_bayer():
    assert bayer(2).tolist() == [[0.125, 0.625], [0.875, 0.375]]
    b = bayer(8)
    assert sorted(((b * 64) - 0.5).ravel().tolist()) == list(range(64))
    for n in (0, 1, 3, 12):
        with pytest.raises(ValueError):
            bayer(n)


@pytest.mark.parametrize("case", PINS["blue_noise"], ids=lambda c: str(c["args"]))
def test_blue_noise_equals_v1(case):
    n, seed, sigma = case["args"]
    got = blue_noise(n, np.random.default_rng(seed), sigma=sigma)
    assert np.array_equal(got, (np.array(case["ranks"]) + 0.5) / (n * n))


def test_blue_noise_cache_leaves_the_generator_where_a_fresh_call_would():
    fresh = np.random.default_rng(123)
    first = blue_noise(16, fresh, sigma=1.1)
    after_fresh = fresh.random(3)
    cached = np.random.default_rng(123)
    again = blue_noise(16, cached, sigma=1.1)
    assert np.array_equal(first, again)
    assert np.array_equal(cached.random(3), after_fresh)
    again[:] = 0  # a copy: the cache is untouched
    assert np.array_equal(blue_noise(16, np.random.default_rng(123), sigma=1.1), first)
    other = blue_noise(16, np.random.default_rng(123), sigma=2.5)
    assert not np.array_equal(other, first)  # sigma is part of the key
    mt = np.random.Generator(np.random.MT19937(5))
    assert np.array_equal(
        blue_noise(8, mt), blue_noise(8, np.random.Generator(np.random.MT19937(5)))
    )


def test_threshold_matrix_errors():
    with pytest.raises(ValueError):
        threshold_matrix("bluenoise")
    with pytest.raises(ValueError):
        threshold_matrix("waves")
    with pytest.raises(TypeError):
        blue_noise(8, 3)
