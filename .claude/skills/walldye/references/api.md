# walldye API reference

Everything a design can import from `walldye` (walldye/__init__.py), plus the third-party
libraries designs may import. Units are SVG user units on a canvas whose short side is
always 1080.

## Anatomy of a design

```python
"""An accent arc over faint concentric rings, offset right of centre: one merged ring path plus arc_band()."""

import math

from walldye import ACCENT, BG_DEEP, UI, H, P, W, rng

ASPECTS = ["any"]  # omit -> 16:9 only; or e.g. ["16:9", "21:9"]
BG = BG_DEEP  # optional: the canvas is filled with this instead of the theme bg
U = min(W, H)  # always 1080: size in U, place in fractions of W/H


def draw(s):
    r = rng(7)
    cx, cy = W * 0.62, H * 0.5
    rings = P()
    for k in range(1, 9):
        rad = U * 0.05 * k + r.uniform(-4, 4)
        rings.M(cx + rad, cy).A(rad, rad, 0, 1, 1, cx - rad, cy).A(rad, rad, 0, 1, 1, cx + rad, cy)
    s.path(rings, fill="none", stroke=UI, stroke_width=1.5)
    s.path(P().arc_band(cx, cy, U * 0.3, U * 0.315, -math.pi / 2, 0), fill=ACCENT)
```

- Imports: `from walldye import ...` binds tokens and `W`/`H` at import time. The tools call
  `set_theme()`, then `set_canvas()`, then exec design.py fresh for every theme and aspect,
  so module-level constants derived from them (`CX = W * 0.6`, `DIM = mix(BG, UI, 0.5)`) are
  safe. Never cache them anywhere else.
- Designs are single files. They may import the standard library, `walldye`, numpy, scipy,
  shapely and skimage; anything else, and any relative import, fails `check`. The design's
  folder is not on `sys.path`.
- `ASPECTS`: a literal list of aspect strings the design composes for. `"any"` expands to
  `SITE_ASPECTS` (16:9, 16:10, 21:9, 32:9, 9:19.5, 10:16), and `check` and `build` render every
  one of them. With no `ASPECTS` the design is 16:9 only and may hardcode 1920×1080; the site
  shows other screen shapes as a crop of the 16:9 render.
- `BG` (optional module attribute): the colour of the full-canvas rect drawn before `draw`.
  Use a token (`BG_DEEP`, `BLACK`), never a hex literal.
- `draw(s)` receives an `Svg` that is already `W×H` and painted with `BG`; append to it and
  return nothing. `print()` output goes to stderr.
- U-scaling: the short side is 1080 in every aspect, so a `1.5` stroke or a `U * 0.3` radius
  looks the same on every screen shape. Put positions in fractions of `W`/`H` (or anchor them
  to an edge) and sizes in `U` or absolute units. Portrait canvases are 1080 wide, so check
  that anything placed at `W * 0.6` still fits.
- Determinism: `check` renders twice in-process, then again in a fresh process with
  `PYTHONHASHSEED=4242`, for every native aspect under one theme per regime, and fails if the
  output differs. Seed everything with `rng(n)` or `np.random.default_rng(n)`, never call the
  global `random.*` or `np.random.*`, and never iterate a `set`/`frozenset` of strings (use
  `sorted()`). Sets of int or float tuples are fine.

## Canvas & aspects

| Name                                   | Meaning                                                                                                    |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `W, H`                                 | Current canvas size, short side 1080. 16:9 1920×1080, 16:10 1728×1080, 21:9 2520×1080, 32:9 3840×1080, 9:19.5 1080×2340, 10:16 1080×1728 |
| `SHORT`                                | `1080`, the fixed short side                                                                               |
| `SITE_ASPECTS`                         | `["16:9", "16:10", "21:9", "32:9", "9:19.5", "10:16"]`: the shapes check, build and the site use          |
| `canvas_size(aspect="16:9") -> (w, h)` | Size for `"a:b"`, `"WxH"` (`"3440x1440"` gives 2580×1080) or a float ratio; no side effects                |
| `supports(declared, aspect) -> bool`   | Whether `ASPECTS=declared` covers `aspect`: `"any"`, or a ratio within 1%                                  |
| `native_aspects(declared) -> list`     | The `SITE_ASPECTS` a declaration covers, in `SITE_ASPECTS` order                                          |
| `set_canvas(aspect) -> (w, h)`         | Sets module `W`/`H`. The tools call it; designs should not                                                 |

## Theme tokens

A theme is three seeds (`bg`, `fg`, `accent`). Every other token is derived from them. Tokens
are semantic, so a light theme inverts naturally: `BG_DEEP`/`BLACK` step _beyond_ bg (darker
on dark themes, lighter on light ones), the greys walk bg to fg, and the accent ramp walks
accent to bg.

| Token                 | Derivation                                              | Role in the house style                                |
| --------------------- | ------------------------------------------------------- | ------------------------------------------------------ |
| `BLACK`               | `mix(bg, beyond, 0.43)`                                 | Deepest void: holes, cast shadows, night sky           |
| `BG_DEEP`             | `mix(bg, beyond, 0.15)`                                 | Recessed ground; a common `BG` override                |
| `BG`                  | seed                                                    | Canvas                                                 |
| `BG_ALT`              | `mix(bg, fg, 0.063)`                                    | Barely-there panels, far layers, faint grids           |
| `UI`                  | `mix(bg, fg, 0.126)`                                    | Default line work and quiet structure                  |
| `UI_ALT`              | `mix(bg, fg, 0.189)`                                    | Secondary lines, a step above `UI`                     |
| `UI_HI`               | `mix(bg, fg, 0.31)`                                     | Brightest grey most designs use: outlines, key edges   |
| `MUTED`               | `mix(bg, fg, 0.563)`                                    | Rare highlights. Already loud on a wallpaper           |
| `FG_ALT`              | `mix(bg, fg, 0.816)`                                    | Text-level contrast. Almost never right on a wallpaper |
| `FG`                  | seed                                                    | Avoid; far too bright behind windows                   |
| `ACCENT_HI`           | `mix(accent, fg, 0.28)`                                 | Specular glint on the accent, tiny areas only          |
| `ACCENT`              | seed                                                    | The single "event"                                     |
| `ACCENT_1`…`ACCENT_8` | `mix(accent, bg, t)`, t = .17 .26 .5 .56 .68 .8 .9 .955 | Accent shading, 1 = strongest, 8 = nearly bg           |
| `ORANGE_DARK`         | `= ACCENT_1` in derived themes                          | Legacy; prefer the ACCENT ramp                         |

`beyond` is `#000000` when bg is darker than fg, else `#FFFFFF`. On light themes the
`BG_ALT`…`UI_HI` fractions are ×1.6, capped at 0.5 (thin grey lines read fainter on paper).
The default `fireproof` preset pins all 21 tokens by hand, and several sit well off these
fractions (`ACCENT_1`…`ACCENT_3` by about 20 RGB units), so never assume a token equals its
formula.

- `GREYS`: `[BLACK, BG_DEEP, BG, BG_ALT, UI, UI_ALT, UI_HI, MUTED]`, from beyond bg toward fg.
- `ACCENTS`: `[ACCENT_8, …, ACCENT_1, ACCENT]`, 9 steps from near-bg to full accent. Index it
  with a 0..1 value: `ACCENTS[min(8, int(v * 9))]`.
- `THEME`: dict of every token, lowercase keys (`THEME["ui_hi"]`).
- `TOKENS`, `PRESETS`, `DEFAULT_THEME`, `set_theme(spec)`, `parse_theme(spec)`,
  `parse_seeds(spec)`, `theme_tokens(seeds)`, `theme_token(seeds)`, `derive_theme(seeds)`:
  theme machinery the tools drive. Designs only read tokens.

`is_light() -> bool` is the one theme test a design may branch on. It is true when the current
theme is in the light regime: bg strictly brighter than fg by WCAG luminance, with ties
counting as dark. Build, the site and derive_theme use the same test.

```python
STRUCT = MUTED if is_light() else UI  # a per-regime token choice: one template serves both
if is_light():
    tone = 0.8 * (MAX_TONE - tone)  # a geometry branch: build writes a .light.svg per aspect
```

Colour helpers (all take and return `#RRGGBB`):

- `mix(a, b, t) -> str`: linear RGB blend, `t=0` gives `a`. The only way to make an in-between
  colour: `mix(BG, UI, 0.5)`.
- `ramp(a, b, n) -> list[str]`: `n` evenly spaced colours from `a` to `b`, both included.
- `accent_ramp(n, lo=BG, hi=ACCENT) -> list[str]`: `n` tones from `lo` through `ACCENT_4` to
  `hi`, piecewise, so the middle of the ramp is already visibly accent. `accent_ramp(5)` is
  `[BG, mix(BG, ACCENT_4, .5), ACCENT_4, mix(ACCENT_4, ACCENT, .5), ACCENT]`.
- `luminance`, `hex_to_rgb`, `rgb_to_hex`: exported for the tools. `check` warns when a
  design calls `luminance(` or `hex_to_rgb(` (or imports `colorsys`): branch on `is_light()`
  and colour with tokens and `mix()`.

### Constant slots and masks

`walldye build` fits every colour occurrence in the SVG (a "slot") as
`a*bg + b*fg + c*accent + d`, so the site can recolour the template for any seeds. A colour
that does not move with the seeds fits as a constant slot, and `check` allows that only in
mask content: inside `<mask>` or `<clipPath>`, or in a gradient or pattern referenced only
from those. Anywhere else a constant colour counts as hardcoded and fails. The reverse also
fails: a theme-dependent colour inside a mask.

So mask content is `#fff` (shows) and `#000` (hides) only, and every painted colour is a token
or a `mix()`/`ramp()` of tokens. `preview` prints a fast hint when a colour is far from the
theme's palette; `check` is the real test.

## Svg

The tools build the canvas as `Svg(bg=BG)` and pass it to `draw`. Every element method
appends markup and returns it as a string.

Attribute keywords: a trailing `_` is dropped and `_` becomes `-`, so `stroke_width=1.5`,
`fill_rule="evenodd"`, `clip_path=url`, `stroke_linecap="round"`, `class_="x"`. `None` values
are skipped; floats are written with 2 decimals.

| Method                                   | Notes                                                          |
| ---------------------------------------- | -------------------------------------------------------------- |
| `Svg(bg=THEME["bg"], width=W, height=H)` | `bg=None` for a transparent canvas; `.w`/`.h` hold the size    |
| `rect(x, y, w, h, **kw)`                 |                                                                |
| `circle(cx, cy, r, **kw)`                |                                                                |
| `ellipse(cx, cy, rx, ry, **kw)`          |                                                                |
| `line(x1, y1, x2, y2, **kw)`             | One element per call. Merge many lines into a `P()` path       |
| `path(d, **kw)`                          | `d` is a `P()` builder or a string                             |
| `polyline(points, nd=1, **kw)`           | `fill` defaults to `"none"`                                    |
| `polygon(points, nd=1, **kw)`            |                                                                |
| `text(x, y, content, **kw)`              | Exists, but `check` rejects `<text>`. Use `glyphs()`           |
| `el(tag, _content=None, **kw)`           | Any other element, e.g. `s.el("use", href="#a")`. Pass children positionally, `s.el("g", inner, opacity=0.5)`; `content=` becomes an attribute |
| `raw(markup)`                            | Append literal markup to the body                              |
| `with s.g(**kw):`                        | Group: `with s.g(opacity=0.5, transform="rotate(8 960 540)"):` |
| `defs(markup)`                           | Append literal markup to `<defs>`                              |
| `uid(prefix="i") -> str`                 | Unique id for hand-written defs                                |
| `to_string() -> str`                     | The tools call this                                            |

Paint servers and clips return a `url(#id)` string to pass as `fill`, `stroke`, `clip_path`
or `mask`:

- `linear_gradient(stops, x1=0, y1=0, x2=0, y2=1, units=None)`: `stops` is
  `[(offset, colour[, opacity])]`. Defaults to a top-to-bottom gradient over the shape's own
  bounding box. Pass `units="userSpaceOnUse"` to give canvas coordinates instead.
- `radial_gradient(stops, cx=0.5, cy=0.5, r=0.5, units=None)`: same stop format.
- `clip(markup)`: a clipPath from raw shape markup.
- `mask(markup)`: a mask in canvas space. `#fff` shows, `#000` hides, and nothing else belongs
  in it (see Constant slots and masks).
- `pattern(w, h, markup, transform=None)`: tiles `markup` on a `w×h` grid in canvas units.

```python
cx, cy = W * 0.6, H * 0.5
stripes = P()
for y in range(0, H, 14):
    stripes.M(0, y).H(W)
with s.g(clip_path=s.clip(f'<circle cx="{cx}" cy="{cy}" r="300"/>')):
    s.path(stripes, fill="none", stroke=UI, stroke_width=1)  # stripes only inside the disc
hatch = s.pattern(10, 10, f'<path d="M0 10L10 0" stroke="{UI_ALT}" stroke-width="1"/>')
s.rect(0, 0, W, H, fill=hatch, mask=s.mask(f'<circle cx="{cx}" cy="{cy}" r="130" fill="#fff"/>'))
fade = s.linear_gradient([(0, BG, 0), (1, BG)], 0, H * 0.6, 0, H, units="userSpaceOnUse")
s.rect(0, H * 0.6, W, H * 0.4, fill=fade)  # fade the bottom into bg
```

## Paths

`P(nd=1) -> Path_` is a fluent builder for path data. Each method returns the builder, and
`str()` gives the `d` string (numbers rounded to `nd` decimals). One builder can hold any
number of subpaths, so use one per colour/stroke style.

| Method                                      | Emits                                                                          |
| ------------------------------------------- | ------------------------------------------------------------------------------ |
| `M(x, y)` `L(x, y)` `H(x)` `V(y)` `Z()`     | move / line / horizontal / vertical / close                                    |
| `C(x1, y1, x2, y2, x, y)` `Q(x1, y1, x, y)` | cubic / quadratic Bézier                                                       |
| `A(rx, ry, rot, large, sweep, x, y)`        | elliptical arc; `sweep=1` is clockwise on screen                               |
| `poly(points, closed=False)`                | `M` then `L` through the points                                                |
| `smooth(points, closed=False, tension=1.0)` | Catmull-Rom spline through the points, as cubics; fewer than 3 points: `poly`  |
| `arc_band(cx, cy, r0, r1, a0, a1)`          | Closed annular sector, radii `r0<r1`, angles in radians going clockwise        |

```python
d = P()
for y in range(100, 1000, 12):
    d.M(0, y).H(W)  # 75 lines, one element
s.path(d, fill="none", stroke=BG_ALT, stroke_width=1)
loop = [
    polar(960, 540, 200 + 20 * math.sin(5 * a), a)
    for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)
]
s.path(P().smooth(loop, closed=True), fill=UI)  # closed: no repeated end point
s.path(P().arc_band(960, 540, 300, 312, -math.pi / 2, 0.4), fill=ACCENT)
```

A full circle as a path is two arcs: `.M(cx + r, cy).A(r, r, 0, 1, 1, cx - r, cy).A(r, r, 0, 1, 1, cx + r, cy)`.

Rounded shapes without kinks (joined curves must be C1-continuous): a rounded rectangle is just
`s.rect(x, y, w, h, rx=r)`; for a softer CRT/"squircle" outline, sample a superellipse and let
`smooth()` close it:

```python
def squircle(cx, cy, a, b, n=4.0, k=96):
    pts = []
    for t in np.linspace(0, 2 * math.pi, k, endpoint=False):
        c, s_ = math.cos(t), math.sin(t)
        pts.append(
            (
                cx + a * math.copysign(abs(c) ** (2 / n), c),
                cy + b * math.copysign(abs(s_) ** (2 / n), s_),
            )
        )
    return P().smooth(pts, closed=True)


s.path(squircle(W * 0.7, H * 0.5, 320, 240), fill=BG_ALT, stroke=UI_ALT, stroke_width=2)
```

## Noise

- `Noise(seed=0)`: seeded pure-Python Perlin, roughly in [-1, 1]. `n(x, y)` gives 2D noise,
  `n.n3(x, y, z)` gives 3D (use z as time or to decorrelate layers), and
  `n.fbm(x, y, octaves=4, lacunarity=2.0, gain=0.5)` sums octaves. Cost is about 1 µs per 2D
  call, which suits per-vertex jitter. For whole fields use `noise_grid`.
- `noise_grid(cols, rows, scale, seed=0, octaves=1, gain=0.5) -> ndarray (rows, cols)`:
  vectorised fBm Perlin. `scale` is the base feature size in cells. The real range is narrower
  than ±1 (about ±0.85 at 1 octave, ±0.6 at 3), so normalise before thresholding or dithering.
- `rng(seed=0) -> random.Random`: the seeded stdlib RNG designs should use.

```python
n = Noise(3)
wobble = [(x, 540 + 40 * n.fbm(x / 300, 0.5)) for x in range(0, W + 1, 8)]
f = noise_grid(W // 4, H // 4, 60, seed=1, octaves=3)
f = (f - f.min()) / (f.max() - f.min())  # to 0..1
```

## Pixel art, dithering & glyphs

`dither(value, cols, rows, levels, method="bayer", matrix=4, seed=0, serpentine=False) -> list[list[int]]`
quantises `value(col, row) -> 0..1` (clamped) to indices `0..levels-1`. Pair it with
`grid_runs`, where index 0 is usually `BG` and is not drawn.

| Method                              | Look                                                         | Knobs / cost (480×270 cells)            |
| ----------------------------------- | ------------------------------------------------------------ | --------------------------------------- |
| `bayer`                             | Crisp crosshatch lattice, very "computer"                    | `matrix` 2/4/8/16 · 0.05 s              |
| `clustered`                         | Print halftone: dots grow from cell centres                  | fixed 8×8 · 0.05 s                      |
| `bluenoise`                         | Even organic grain, no visible pattern                       | `seed` picks the mask · 0.25 s          |
| `lines`                             | Horizontal line screen, thickening with tone                 | `matrix` = line pitch in cells · 0.05 s |
| `random`                            | White-noise grain, clumpy                                    | `seed` · 0.05 s                         |
| `fs`                                | Floyd–Steinberg: fine, with slight "worms"                   | `serpentine` · 0.25 s                   |
| `atkinson`                          | 1-bit Macintosh: punchy, highlights and shadows clip to flat | 0.3 s                                   |
| `jarvis` / `stucki`                 | Wide kernels: smoothest diffusion, least worming             | 0.5 s                                   |
| `burkes` / `sierra` / `sierra-lite` | Between fs and jarvis; lite is cheapest                      | 0.2–0.4 s                               |
| `riemersma`                         | Diffusion along a Hilbert curve: soft, curly texture         | 0.8 s                                   |

- `grid_runs(s, grid, colors, cell, ox=0, oy=0, skip=0, **kw)`: emits a 2D index grid (lists
  or an int ndarray) as merged horizontal runs, one `<path>` per colour index, in index order.
  Cells equal to `skip` or `None` are not drawn; pass `skip=None` to draw index 0 too. Extra
  `**kw` go on every path.
- `sprite(s, art, palette, cell, x=0, y=0, **kw)`: pixel art from a multi-line string (or a
  list of rows). `palette` maps characters to colours; unmapped characters are transparent.
  It draws through `grid_runs`.
- `threshold_matrix(method, size=4, seed=0)`: the ordered-dither mask as rows of values in
  (0, 1). `bayer(n)` is the n×n Bayer matrix. `blue_noise(n=64, seed=0, sigma=1.5)` is a
  void-and-cluster mask (tuple of tuples), cached per `(n, seed)`. Use these to threshold
  numpy fields yourself.
- Tables: `BAYER2`, `CLUSTERED8`, `DIFFUSION` (kernel taps), `DIFFUSION_DIV`.

`grid_runs`, `sprite` and `glyphs` tag their paths `class="px"` and record `(cell, x, y)` of
every call that drew something (`pixel_grids()` lists them for the last render). Build writes
the cell sizes into slots.json as `cells`, and the site's exporter adds
`shape-rendering="crispEdges"` to `px` paths only, so pixel edges stay hard at any export size
while curves elsewhere stay smooth. Draw pixel work through these helpers, not with `s.rect`
loops, or it loses both. Keep the origin a whole unit and a multiple of the cell
(`round(x / CELL) * CELL`); `check` warns on a fractional origin, which blurs every cell edge.

```python
CELL = 4
ys, xs = (np.mgrid[0 : H // CELL, 0 : W // CELL] + 0.5) * CELL  # cell centres in canvas units
tone = np.clip(1 - np.hypot(xs - W * 0.68, ys - H * 0.44) / 420, 0, 1)
grid = dither(lambda i, j: tone[j, i], W // CELL, H // CELL, 4, "bayer", matrix=8)
grid_runs(s, grid, [BG, ACCENT_6, ACCENT_3, ACCENT], CELL)
sprite(s, "..aa..\n.abba.\n..aa..", {"a": UI_HI, "b": ACCENT}, 8, x=1600, y=200)
```

Glyphs are bitmap text drawn as crisp pixel paths from the bundled Spleen font; no font files
and no `<text>`.

- Fonts: `"5x8"` covers ASCII plus light box drawing `─│┌┐└┘├┤┬┴┼`. `"8x16"` covers ASCII,
  all box drawing and block elements U+2500–25A0 (including `░▒▓█▀▄▌▐`), `▬▲▼◆◊○●◘◙◢◣◤◥`,
  and all braille U+2800–28FF. Unknown characters render blank.
- `glyph(ch, font="8x16") -> list[list[bool]]`: the character's pixel rows, for custom rendering.
- `glyphs(s, lines, color, font="8x16", px=2, x=0, y=0, gap=0, key=None, **kw)`: draws a list
  of strings. Each font pixel is `px×px` units; a cell is `(fw+gap)*px` wide and
  `(fh+gap)*px` tall, so 8x16 at `px=2` is 16×32. `color` is one colour, or
  `color(col, row, ch) -> colour | None` for per-cell tone (`None` skips the cell). Spaces are
  never drawn.
- Paths group by colour unless you pass `key(col, row, ch) -> hashable`. With more than one
  role, always pass a key: two roles that share a hex under some theme would otherwise merge
  into one path, the geometry would change with the theme, and `check` fails. Every cell of one
  key must get the same colour (ValueError otherwise). Paths come out in first-seen key order.
- `SHADES = " ░▒▓█"` and `DENSITY = " .:-=+*#%@"` are brightness ramps:
  `DENSITY[min(9, int(v * 10))]`.

```python
TONE = {"frame": UI, "digit": ACCENT}
role = lambda c, r, ch: "digit" if ch.isdigit() else "frame"
glyphs(
    s,
    ["┌──────┐", "│ T+42 │", "└──────┘"],
    lambda c, r, ch: TONE[role(c, r, ch)],
    key=role,
    px=2,
    x=200,
    y=200,
)
# braille: 2×4 sub-pixels per character; dot bit for (dx 0..1, dy 0..3)
BIT = [0x01, 0x02, 0x04, 0x40, 0x08, 0x10, 0x20, 0x80]
dots = {(0, 0), (1, 3)}  # sub-pixels that are on
ch = chr(0x2800 + sum(BIT[dx * 4 + dy] for dx, dy in dots))  # '⢁'
```

## Geometry & fields

- `contours(field, level, cell=1.0, ox=0, oy=0) -> list[list[(x, y)]]`: marching squares over
  `field[row][col]` (nested lists or a 2D ndarray). Returns joined polylines in canvas units
  (`index * cell + offset`). Closed loops repeat their first point at the end. Cells above
  `level` count as inside.
- `sample_field(fn, cols, rows)`: evaluates `fn(col, row)` on a `(rows+1)×(cols+1)` lattice,
  ready for `contours` with the same `cell`.
- `poisson_disk(r, width, height, radius, k=30, x0=0, y0=0) -> list[(x, y)]`: Bridson
  blue-noise points at least `radius` apart inside the box offset by `(x0, y0)`. `r` is a
  `random.Random` (`rng(n)`), not a seed. Radius 12 over the full canvas gives about 9k
  points in 0.6 s.
- `polar(cx, cy, r, a) -> (x, y)`: `a` in radians, 0 = +x, increasing clockwise on screen.
- `lerp(a, b, t)`, `clamp(v, lo=0.0, hi=1.0)`, `smoothstep(e0, e1, x)` (0..1 eased; works with
  `e0 > e1` for falloffs).
- `fmt(v, nd=1) -> str`: a compact number, `fmt(3.0) == "3"`. `pts(points, nd=1)` gives
  `"x,y x,y"`. Use both when writing raw markup by hand.

```python
n = Noise(5)
f = sample_field(lambda i, j: n.fbm(i / 40, j / 40), W // 6, H // 6)
d = P()
for k in range(-4, 5):
    for line in contours(f, k * 0.08, cell=6):
        d.smooth(line)
s.path(d, fill="none", stroke=UI, stroke_width=1.2)
```

## Third-party libraries

Designs may import numpy, scipy, shapely (2.x) and scikit-image. These are the patterns the
reference designs use:

- numpy: compute whole fields at once. `ys, xs = np.mgrid[0:rows, 0:cols] * cell`, then
  `np.hypot`, `np.clip`, `np.where` and `np.gradient` build tone maps for `dither` or
  `find_contours`. `np.random.default_rng(seed)` for seeded arrays.
- shapely: boolean geometry, whose output you convert back to paths.
  - `unary_union([...])` merges overlapping shapes. `a.difference(b)` and `a.intersection(b)`
    cut. `Point(x, y).buffer(r, quad_segs=48)` makes a disc. `box(x0, y0, x1, y1)` makes a rect.
  - `line.buffer(w / 2, cap_style="flat")` turns a stroke into a fillable outline. Chaining
    `.buffer(-k).buffer(k)` rounds off corners.
  - `LineString(...).difference(obstacle.buffer(6))` breaks lines around a shape, for a
    technical-drawing gap.
  - `shapely.affinity.rotate(geom, deg, origin=(0, 0))` rotates a shape.
  - Results may be a `Multi*`, so always iterate `getattr(g, "geoms", [g])`.
- scipy: `spatial.Delaunay` for triangle meshes, `Voronoi` for cells, and `cKDTree` for
  nearest-neighbour or `query_pairs(r)` connections. `ndimage.gaussian_filter` smooths a
  field; `distance_transform_edt(~mask)` gives the distance to a shape, for offset rings and
  glows. `map_coordinates` samples a field at arbitrary points. `interpolate.CubicSpline`
  gives smooth rails.
- scikit-image: `measure.find_contours(field, level)` is a fast iso-line tracer on
  ndarrays, and `approximate_polygon(c, 0.3)` simplifies the result. It returns `(row, col)`,
  so swap the columns. `graph.route_through_array` finds cheapest paths over a cost grid.

```python
blob = unary_union([Point(x, 540).buffer(120, quad_segs=32) for x in (800, 960, 1120)])
d = P()
for g in getattr(blob, "geoms", [blob]):
    for ring in [g.exterior, *g.interiors]:
        d.poly(ring.coords[:-1], closed=True)
s.path(d, fill=UI, fill_rule="evenodd")  # holes survive via evenodd

h = P()  # 45° hatching clipped to the blob
for k in range(-600, 600, 8):
    cut = LineString([(960 + k - 400, 940), (960 + k + 400, 140)]).intersection(blob)
    for seg in getattr(cut, "geoms", [cut]):
        if not seg.is_empty:
            h.poly(seg.coords)
s.path(h, fill="none", stroke=UI_HI, stroke_width=1)

p = np.array(poisson_disk(rng(2), W, H, 90))
tri = Delaunay(p)
edges = sorted(
    {
        tuple(sorted((a, b)))
        for t in tri.simplices
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))
    }
)
mesh = P()
for a, b in edges:
    mesh.M(*p[a]).L(*p[b])

vor = Voronoi(p)  # bounded cells only
cells = [
    vor.vertices[vor.regions[i]]
    for i in vor.point_region
    if vor.regions[i] and -1 not in vor.regions[i]
]

F = gaussian_filter(np.random.default_rng(4).random((H // 4, W // 4)), 8)
iso = P()
for c in find_contours(F, 0.5):
    iso.poly(approximate_polygon(c, 0.3)[:, ::-1] * 4)  # (row, col) to (x, y) in canvas units
```

## Performance & lint limits

`walldye check` (and `build`, which runs it first) enforces these:

- Errors:
  - output that differs between two renders, or in the `PYTHONHASHSEED=4242` subprocess;
  - a `viewBox` other than `0 0 W H` for each aspect;
  - geometry that changes between themes of one regime, including two probe themes: one where
    bg, fg and accent are equal (every token collapses to one hex, so colour-keyed dicts
    merge) and one whose token hex strings sort the opposite way to fireproof's;
  - a held-out theme predicted more than 2 RGB units off by the fitted slots;
  - a constant slot outside mask content, or a theme-dependent one inside it;
  - `<text>`, any `<filter>`, any `<image>`, more than 1 MB or more than 20,000 elements;
  - imports outside the standard library and walldye/numpy/scipy/shapely/skimage;
  - meta.yaml problems (see SKILL.md).
- Warnings:
  - over 600 kB or 15,000 elements;
  - `luminance(`, `hex_to_rgb(` or `colorsys` in design.py;
  - colour words in the docstring, comments or meta.yaml copy (the list includes black,
    white, grey and golden, so "golden section" trips it too);
  - a fractional grid origin in `grid_runs`, `glyphs` or `sprite`.

`check --set` also lists near-clone pairs (committed build/16x9.svg ink maps with cosine
0.93 or more), so a piece takes part only after `walldye build`; concept duplicates (same
idea, different drawing) still need a look.

How to stay under the limits:

- One `<path>` per colour/stroke style. Accumulate subpaths in a single `P()` instead of
  calling `s.line`/`s.circle` in a loop. `grid_runs`, `glyphs` and `sprite` already merge runs.
- Quantise continuous tone into buckets. Pick 4–8 tones from `ACCENTS`, `GREYS` or
  `accent_ramp(n)`, keep one `P()` per bucket index (`paths[int(v * n)]`), and emit each once.
  This is how the reference designs fade meshes and hatching without per-element opacity.
  Key the buckets by index, never by the colour string.
- Round coordinates. `P()` rounds to 1 decimal by default, which is crisp at 4K and keeps
  files small. Pass `P(nd=2)` only for fine detail.
- Pixel grids: a 4-unit cell gives 480×270 cells at 16:9. After `grid_runs` that is
  50–400 kB in the reference designs. Use a 2-unit cell only with sparse content. Remember
  that 32:9 doubles the cell count.
- Fields in numpy, not per-pixel Python calls. Use `noise_grid` or vectorised maths, and
  feed `dither` via `lambda i, j: arr[j, i]`. Pure-Python `Noise` costs about 1 µs a call
  (5 µs for 4-octave fbm), which is fine for thousands of calls and slow for millions.
- Dots in bulk: zero-length segments with round caps, `d.M(x, y).H(x)` for every dot and
  then `s.path(d, fill="none", stroke=UI, stroke_width=diameter, stroke_linecap="round")`,
  are one element instead of thousands of `<circle>`s.
