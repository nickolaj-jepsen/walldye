# Drawing with walldye

How to draw a piece with the `walldye` API in practice. docs/api.md has every signature, and the
docstrings in `walldye/` the exact behavior; this file does not repeat them. The pieces in
SKILL.md's Examples table are complete designs.

## Module level

- Annotate `draw` as `def draw(s: Canvas[YourParams]) -> None` (plain `Canvas` without params)
  and your helpers' parameters, so Pyrefly can check them.

## Canvas and layout

| Aspect | Canvas | Aspect | Canvas |
|---|---|---|---|
| 16:9 | 1920x1080 | 32:9 | 3840x1080 |
| 16:10 | 1728x1080 | 9:19.5 | 1080x2340 |
| 21:9 | 2520x1080 | 10:16 | 1080x1728 |

## Colors

- Quantize continuous tone into a module-level ladder and bucket by rung, one element per rung:
  ```python
  TONES = ladder((BG_ALT, UI, ACCENT), 6)  # at module level
  with s.buckets(TONES, "stroke", stroke_width=1.4, stroke_linecap="round") as b:
      for x, y, v in samples:
          b[TONES.rung(v)].M(x, y).L(x + 8, y)
  ```
  `ladder((BG, ACCENT_4, ACCENT), 5)` is an accent ramp whose middle is already visibly accent.

## Drawing

```python
with s.group(opacity=0.6, transform=Affine.rotate(deg=8, about=s.center)):
    s.stroke(frame, UI, 1.2)  # a group takes any style key except fill

with s.clip() as disc:
    disc.add(P().circle(c, 300))
with s.group(clip_path=disc.ref):
    s.stroke(stripes, UI, 1)  # stripes only inside the disc

with s.mask() as m:
    m.fill(P().rect(0, 0, s.w, s.h), MASK_WHITE)
    m.fill(P().circle(c, 120), MASK_BLACK)  # a hole
s.path(texture, fill=UI, mask=m.ref)

with s.pattern(10, 10) as pat:
    pat.stroke(P().M(0, 10).L(10, 0), UI_ALT, 1)  # tile coordinates, theme colors
s.fill(P().circle(c, 200), pat.ref)

fade = s.linear_gradient([(0, BG, 0), (1, BG)], (0, s.h * 0.6), (0, s.h))
s.fill(P().rect(0, s.h * 0.6, s.w, s.h * 0.4), fade)
```

## Random streams

- A library sampler needs a stream: `stats.norm.rvs(size=9, random_state=s.np_rng(4))`.
- `n = s.noise(5)`: `n(x, y)`, `n.n3(x, y, z)` (z as time, or to decorrelate layers) and
  `n.fbm(x, y, octaves=4)` all take arrays that broadcast, so a whole field is one call:
  `n.fbm(xs[None, :] / 300, ys[:, None] / 300)`.

## Fields

- `noise_grid`'s range is narrower than ±1 (about ±0.6 at 3 octaves): normalize before
  thresholding.
- `iso_lines(..., simplify=)` costs about 0.7 ms per line per draw, and a check draws each aspect
  and regime three times. On dense fields use a coarser cell or fewer levels instead.

```python
noise = s.noise(5)
field = sample_field(lambda i, j: noise.fbm(i / 40, j / 40), s.w // 6, s.h // 6)
lines = P()
for k in range(-4, 5):
    for line in iso_lines(field, k * 0.08, cell=6):
        lines.spline(line)
s.stroke(lines, UI, 1.2)
```

## Pixels, dither and glyphs

Anchor a pixel grid with `s.pick(..., snap=CELL)` so its origin is a multiple of the cell.

Dither methods, with their look and cost at 480x270 cells.

| Method | Look | Cost |
|---|---|---|
| `bayer` | crisp crosshatch lattice, very "computer"; `matrix` 2, 4, 8 or 16 | 0.05 s |
| `clustered` | print halftone: dots grow from cell centers | 0.05 s |
| `bluenoise` | even organic grain, no visible pattern | 0.25 s |
| `lines` | a line screen thickening with tone; `matrix` is the pitch | 0.05 s |
| `random` | white-noise grain, clumpy | 0.05 s |
| `fs` | Floyd-Steinberg: fine, with slight worms; `serpentine=True` helps | 0.1 s |
| `atkinson` | 1-bit Macintosh: punchy, highlights and shadows clip to flat | 0.3 s |
| `jarvis`, `stucki` | wide kernels: the smoothest diffusion | 0.5 s |
| `burkes`, `sierra`, `sierra-lite` | between fs and jarvis; lite is cheapest | 0.2-0.4 s |
| `riemersma` | diffusion along a Hilbert curve: soft, curly texture | 0.8 s |

`"bluenoise"` and `"random"` need `rng=s.np_rng(k)`.

```python
CELL = 3
c = s.pick(landscape=(0.68, 0.46), portrait=(0.56, 0.34), snap=CELL)
xs, ys = cells(s.inset(0), CELL)
tone = np.clip(1 - np.hypot(xs - c.x, ys - c.y) / 420, 0, 1)
grid = dither(tone, 4, method="bayer", matrix=8)
grid_runs(s, grid, [None, ACCENT_6, ACCENT_3, ACCENT], CELL)
sprite(s, "..aa..\n.abba.\n..aa..", {"a": UI_HI, "b": ACCENT}, 8, (1600, 200))
```

Glyphs:

- `"5x8"` covers ASCII plus light box drawing. `"8x16"` covers ASCII, all box drawing and block
  elements (`░▒▓█▀▄▌▐`), `▬▲▼◆◊○●◘◙◢◣◤◥` and braille U+2800-28FF. Unknown characters are blank,
  and spaces are never drawn.
- Brightness ramps are plain strings, `" .:-=+*#%@"` or `" ░▒▓█"`, indexed with
  `min(len(r) - 1, int(v * len(r)))`.

```python
glyphs(
    s,
    lines,
    lambda col, row, ch: ACCENT if ch.isdigit() else UI,
    at=s.frac(0.6, 0.3),
    anchor="middle",
)
```

## Third-party libraries

- numpy: compute whole fields at once. `cells(rect, cell)` or `np.mgrid` give coordinates;
  `np.hypot`, `np.clip`, `np.where` and `np.gradient` build tone maps for `dither` and
  `iso_lines`.
- shapely: boolean geometry, drawn back with `P().shape(geom)`, which keeps holes and handles
  multi-part results.
  - `unary_union([...])` merges overlapping shapes; `a.difference(b)` and `a.intersection(b)`
    cut; `Point(x, y).buffer(r, quad_segs=48)` makes a disc and `box(x0, y0, x1, y1)` a
    rectangle.
  - `line.buffer(w / 2, cap_style="flat")` turns a stroke into a fillable outline, and
    `.buffer(-k).buffer(k)` rounds off corners.
  - `LineString(...).difference(obstacle.buffer(6))` breaks lines around a shape, for a
    technical-drawing gap. `parts(g)` from `walldye.geom` iterates any result.
- scipy: `spatial.Delaunay`, `Voronoi` and `cKDTree` for meshes, cells and neighbors;
  `ndimage.gaussian_filter`, `distance_transform_edt`, `label` and `map_coordinates` for
  fields; `interpolate.CubicSpline` for smooth rails.
- scikit-image: `graph.route_through_array` finds cheapest paths over a cost grid;
  `iso_lines` already wraps `measure.find_contours`.

```python
blob = unary_union([Point(x, 540).buffer(120, quad_segs=32) for x in (800, 960, 1120)])
s.fill(P().shape(blob), UI)
rules = P()
for seg in hatch(blob, 8, deg=-45):
    rules.poly(seg)
s.stroke(rules, UI_HI, 1)

pts = poisson_disk(s.inset(0), 90, s.rng(2))
mesh = P()
for a, b, c in Delaunay(pts).simplices.tolist():
    mesh.poly(pts[[a, b, c]], closed=True)
s.stroke(mesh, BG_ALT, 1)
```

## Staying under the limits

check warns above 600 kB or 15,000 elements and fails above 1 MB or 20,000.

- One path per paint and stroke style: accumulate subpaths in one `P()`, or use `s.buckets`.
  `grid_runs`, `glyphs` and `sprite` already merge runs.
- `P()` rounds to 1 decimal, which is crisp at 4K; use `P(nd=2)` only for fine detail.
- A 4-unit pixel cell gives 480x270 cells at 16:9, 50 to 400 kB after `grid_runs`. Use 2-unit
  cells only for sparse content; 32:9 doubles the cell count.
- Many dots are one path: `P().dots(pts, r)`, or zero-length segments with round caps,
  `d.M(x, y).H(x)` for each and `s.stroke(d, UI, diameter, cap="round")`.
