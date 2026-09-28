"""Typical helper calls in a design, which must type-check at the design level."""

import numpy as np
from shapely.geometry import Point

from walldye import ACCENT, BG_ALT, UI, Canvas, P, Vec, design
from walldye.field import cells, falloff, gauss, iso_lines, noise_grid, runs, sample_field
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
from walldye.pixel import Pixels, dither, glyphs, grid_runs, sprite, text_width


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.center
    line = Polyline(spline_points([(100, 200), (400, 260), (700, 180)], 12))
    mid: Vec = line.at(line.length / 2)
    marks = line.at(np.linspace(0, line.length, 9))
    s.stroke(P().poly(line.offset(6).pts).poly(marks), UI, 1.2)
    s.fill(P().poly(ribbon(line.resample(4).pts, 3), closed=True), ACCENT)
    s.fill(P().circle(mid + line.tangent(10) * 5, 3), UI)
    s.fill(P().poly(ngon(c, 90, 5, bearing=0, inner=40), closed=True), BG_ALT)
    s.stroke(P().poly(bezier_points([c, (c.x + 200, c.y - 80), (c.x + 300, c.y)], 30)), UI, 1)
    hatched = P()
    for seg in hatch(Point(c).buffer(120), 6, deg=30):
        hatched.poly(seg)
    for g in parts(Point(c).buffer(200).difference(Point(c).buffer(80))):
        hatched.shape(g)
    s.stroke(hatched, UI, 1)
    frame = Affine.frame(c, bearing=45)
    dots = scatter(40, s.inset(60), s.rng(3), min_dist=30, accept=lambda p: abs(p - c) > 150)
    s.fill(P().dots(frame.apply(poisson_disk(s.inset(40), 60, s.rng(4))), 2).dots(dots, 3), UI)

    xs, ys = cells(s.inset(0), 8)
    d = np.hypot(xs - c.x, ys - c.y)
    tone = gauss(d, 300) * falloff(d, 500, 1.5) + 0.2 * noise_grid(
        xs.shape[1], xs.shape[0], 12, s.np_rng(5)
    )
    grid_runs(s, dither(tone, 3, method="bluenoise", rng=s.np_rng(6)), [None, UI, ACCENT], 8)
    field = sample_field(lambda i, j: np.sin(i / 7) + np.cos(j / 5), 60, 40)
    contour = P()
    for iso in iso_lines(field, 0.5, cell=10, origin=(200, 100), simplify=0.5):
        contour.poly(iso)
    s.stroke(contour, UI, 1)
    for a, b in runs(field[0] > 0):
        s.stroke(P().M(200 + a * 10, 90).H(200 + b * 10), ACCENT, 2)

    px = Pixels(32, 16, [None, UI, ACCENT])
    px.grid[4:8, 2:30] = 1
    px.stamp(["ab", "ba"], 3, 3, {"a": 1, "b": 2}, flip=True)
    px.line(0, 0, 31, 15, 2)
    px.dither(np.linspace(0, 1, 32)[None, :].repeat(16, 0), [0, 1], method="fs", where=px.grid == 0)
    px.draw(s, 4, s.pick(landscape=(0.1, 0.1), portrait=(0.2, 0.2), snap=4))
    sprite(s, "ab\nba", {"a": UI, "b": ACCENT}, 6, (40, 40), opacity=0.5)
    w = text_width("walldye", font="5x8", px=2, gap=1)
    glyphs(
        s,
        ["walldye", "v2"],
        lambda col, row, ch: ACCENT if ch == "v" else UI,
        at=(c.x - w / 2, 40),
        font="5x8",
        px=2,
        gap=1,
        anchor="middle",
        key=lambda col, row, ch: ch == "v",
    )
