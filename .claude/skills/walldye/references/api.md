# Writing a design

A working guide to the `walldye` API for designing one piece. `docs/api.md` in the repo root
has every exact signature, the error each call raises and the tool contracts; this file is the
part you need while drawing. The files in `../examples/` are complete designs that pass
`walldye check`.

## Anatomy

```python
"""A filled disc inside faint rings, right of centre on a landscape screen."""

from walldye import ACCENT, UI, Canvas, P, design


@design(aspects="any")
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(0.62, 0.5), portrait=(0.5, 0.4))
    rings = P()
    for k in range(1, 9):
        rings.circle(c, 40 * k)
    s.stroke(rings, UI, 1.5)
    s.fill(P().circle(c, 12), ACCENT)
```

A design is `wallpapers/<slug>/design.py`. The tools import it once and call `draw` many times:
once per version, screen shape and regime. So:

- Module level holds only constants, pure helper functions and classes, a `Params` class, the
  variants mapping and exactly one `@design(...)` function named `draw`. A constant may be any
  expression over literals, earlier constants and a fixed list of pure calls (`math.radians(6)`,
  `np.array([...])`, `mix(UI, BG, 0.5)`, `ladder(...)`, `Vec(...)`, your own earlier
  functions). `P()`, anything on `s`, shapely, scipy and skimage calls, loops and `if`
  statements belong inside `draw`.
- Nothing at module level may change while drawing. A list appended to inside `draw` leaks
  into the next render; the lint and the determinism check both catch it.
- Everything that depends on the render arrives through `s`: the canvas size, the regime, the
  params, random streams and data files.
- Imports: `walldye`, `walldye.geom`, `walldye.field`, `walldye.pixel`, numpy, scipy, shapely
  and skimage, plus `math`, `cmath`, `itertools`, `functools`, `collections`, `heapq`,
  `bisect`, `operator`, `dataclasses`, `typing`, `enum`, `fractions`, `statistics`, `string`,
  `re`, `textwrap`, `json`, `base64`, `zlib` and `copy`. Not `random`, `numpy.random`,
  `colorsys`, `decimal`, relative imports or `from __future__ import annotations`.
- `print()` goes to stderr.

`@design()` takes three keywords, all optional:

| Keyword | Meaning |
|---|---|
| `aspects` | `"any"` (every screen shape the site offers) or a tuple such as `("16:9", "21:9")`. Leave it out for 16:9 only; the site then crops other shapes from the 16:9 render. |
| `variants` | named versions, `{"late": Radar(sweep=210)}`: at most 4, each an instance of `draw`'s params class (see Params and variants) |
| `bg` | the colour of the full-canvas rectangle drawn before `draw` runs; `BG` by default, `BG_DEEP` and `by_regime(...)` are common |

## Canvas and layout

Canvas units are pixels and the short side is always 1080, so a 1.5-unit stroke or a 300-unit
radius looks the same on every screen shape.

| Aspect | Canvas | Aspect | Canvas |
|---|---|---|---|
| 16:9 | 1920x1080 | 32:9 | 3840x1080 |
| 16:10 | 1728x1080 | 9:19.5 | 1080x2340 |
| 21:9 | 2520x1080 | 10:16 | 1080x1728 |

| On `s` | Meaning |
|---|---|
| `s.w`, `s.h` | the canvas size |
| `s.landscape` | `s.w >= s.h` |
| `s.light` | this draw is for the light regime (light ladder step 3) |
| `s.params` | the params of the version being drawn |
| `s.center` | `Vec(s.w / 2, s.h / 2)` |
| `s.frac(fx, fy)` | `Vec(fx * s.w, fy * s.h)` |
| `s.pick(landscape=(fx, fy), portrait=(fx, fy), snap=None)` | the landscape or the portrait fractions as a point; `snap=CELL` rounds it to whole cells |
| `s.inset(margin)` | `Rect(margin, margin, s.w - 2 * margin, s.h - 2 * margin)`; a negative margin grows it |

Composing for every aspect (`aspects="any"`): place the focal point with `s.pick` or
`s.frac`, anchor edge furniture to `s.w` and `s.h` (`s.h - 80`), loop full-bleed fields over
the real `s.w` and `s.h`, and size things in plain units. Branch on `s.landscape` when a
portrait screen needs a different arrangement (glyph-terrain turns its map a quarter turn). A
right-thirds point that works at 16:9 can be cramped at 9:19.5, so preview 32:9, 9:19.5 and
10:16. There is no `s.aspect` and no variant name to branch on.

## Colours

Colours are symbolic: a token such as `UI`, or a formula over tokens. They become hex values
only when the tools write the SVG under a theme, so nothing in `draw` can depend on a colour's
value, and the geometry is the same under every theme of a regime.

| Token | Derivation | Role in the house style |
|---|---|---|
| `BLACK` | `mix(bg, beyond, 0.43)` | deepest void: holes, cast shadows, night sky |
| `BG_DEEP` | `mix(bg, beyond, 0.15)` | recessed ground; a common `bg=` |
| `BG` | seed | canvas |
| `BG_ALT` | `mix(bg, fg, 0.063)` | barely-there panels, far layers, faint grids |
| `UI` | `mix(bg, fg, 0.126)` | default line work and quiet structure |
| `UI_ALT` | `mix(bg, fg, 0.189)` | secondary lines, a step above `UI` |
| `UI_HI` | `mix(bg, fg, 0.31)` | the brightest grey most designs use: outlines, key edges |
| `MUTED` | `mix(bg, fg, 0.563)` | rare highlights; already loud on a wallpaper |
| `FG_ALT` | `mix(bg, fg, 0.816)` | text-level contrast; almost never right |
| `FG` | seed | avoid: far too bright behind windows |
| `ACCENT_HI` | `mix(accent, fg, 0.28)` | a glint on the accent, tiny areas only |
| `ACCENT` | seed | the single event |
| `ACCENT_1` ... `ACCENT_8` | `mix(accent, bg, t)`, t = .17 .26 .5 .56 .68 .8 .9 .955 | accent shading, 1 strongest, 8 nearly bg |

`beyond` is black on dark themes and white on light ones, so `BG_DEEP` and `BLACK` are lighter
than `BG` on paper. On light themes the `BG_ALT` ... `UI_HI` fractions are x1.6, capped at 0.5.
The default `fireproof` theme pins every token by hand, well off these formulas, so never
assume a token equals its formula. themes.md has the presets and the light ladder.

Building colours:

- `mix(a, b, t)`: `t` from 0 (gives `a`) to 1 (gives `b`); outside [0, 1] raises.
- `ramp(a, b, n)`: `n` colours from `a` to `b`, both included.
- `ladder(stops, n)`: `n` rungs spaced evenly along the path through `stops`, as a `Ladder`
  (a tuple). `ladder((BG, ACCENT_4, ACCENT), 5)` is an accent ramp whose middle is already
  visibly accent. `TONES.rung(v)` quantises `v` in [0, 1] to a rung index, arrays too, and
  `TONES.at(v)` is `TONES[TONES.rung(v)]`.
- `by_regime(dark, light)`: one colour that is `dark` in the dark regime and `light` in the
  light one (light ladder step 2).

What colours cannot do, on purpose: they have no text form (`str()`, f-strings and `format()`
raise), no order (`sorted()` raises), and a raw hex string is never a paint. `==` and hashing
compare formulas, so `mix(UI, BG, 0.5) == mix(UI, BG, 0.5)` holds under every theme. Key
buckets, dicts and sorts by index or role; give an explicit sort key where order matters.

Masks take their own colours: `MASK_WHITE` shows, `MASK_BLACK` hides, and
`mix(MASK_BLACK, MASK_WHITE, t)` is a grey. They are the only colours that stay the same under
every theme, only a mask surface accepts them, and a mask surface rejects theme colours.

## Drawing

```python
s.fill(d, paint, rule=None, opacity=None)
s.stroke(d, paint, width, cap=None, join=None, dash=None, opacity=None)
s.path(d, fill=paint, **style)  # anything else: fill and stroke together, transforms, masks
```

- `d` is a `Path` from `P()`. An empty path draws nothing.
- A paint is a colour, `"none"`, or the ref of a gradient or pattern.
- `cap` is `"butt"`, `"round"` or `"square"`; `join` `"miter"`, `"round"` or `"bevel"`;
  `rule` `"nonzero"` or `"evenodd"`; `dash` a sequence of lengths.
- `s.stroke` writes `fill="none"`, so a stroked open path never fills.
- `s.path` takes these style keys: `stroke`, `stroke_width`, `stroke_linecap`,
  `stroke_linejoin`, `stroke_dasharray`, `stroke_dashoffset`, `stroke_opacity`,
  `fill_opacity`, `fill_rule`, `opacity`, `transform` (an `Affine`), `clip_path` and `mask`
  (refs). A shared style is a typed dict: `THIN: Style = {"stroke": UI, "stroke_width": 1.0}`.
- Bools, NaN, infinity, negative widths and opacities outside [0, 1] raise.

One element per paint and stroke style: collect subpaths in one `P()` and draw it once.

```python
with s.group(opacity=0.6, transform=Affine.rotate(deg=8, about=s.center)):
    s.stroke(frame, UI, 1.2)  # a group takes any style key except fill

TONES = ladder((BG_ALT, UI, ACCENT), 6)  # at module level
with s.buckets(TONES, "stroke", stroke_width=1.4, stroke_linecap="round") as b:
    for x, y, v in samples:
        b[TONES.rung(v)].M(x, y).L(x + 8, y)
```

`s.buckets(paints, kind, **style)` gives one path per paint, filled through `b[i]`, and draws
one element per non-empty bucket, in index order, where the `with` opened. `kind="fill"` fills
each; `kind="stroke"` strokes each and needs `stroke_width`. Buckets are keyed by index, so two
equal paints stay two elements.

Clips, masks and patterns are blocks; use their `ref` after the block closes:

```python
with s.clip() as disc:
    disc.add(P().circle(c, 300))
with s.group(clip_path=disc.ref):
    s.stroke(stripes, UI, 1)  # stripes only inside the disc

with s.mask() as m:
    m.fill(P().rect(0, 0, s.w, s.h), MASK_WHITE)
    m.fill(P().circle(c, 120), MASK_BLACK)  # a hole
s.path(texture, fill=UI, mask=m.ref)

with s.pattern(10, 10) as pat:
    pat.stroke(P().M(0, 10).L(10, 0), UI_ALT, 1)  # tile coordinates, theme colours
s.fill(P().circle(c, 200), pat.ref)

fade = s.linear_gradient([(0, BG, 0), (1, BG)], (0, s.h * 0.6), (0, s.h))
s.fill(P().rect(0, s.h * 0.6, s.w, s.h * 0.4), fade)
```

- Inside a clip, mask or pattern block, draw only on the surface; drawing on `s` raises.
- A clip takes geometry only (`add(d, rule=..., transform=...)`). A mask draws with `fill`,
  `stroke`, `group` and its own `linear_gradient` and `radial_gradient` of mask colours.
- Gradients take canvas coordinates by default (`units="user"`); `units="bbox"` uses the
  painted shape's box, 0 to 1. `s.radial_gradient(stops, center, r, focus=None)`. Stops are
  `(offset, colour)` or `(offset, colour, opacity)`.
- Do not fake overlaps with opacity: alpha composites land between tokens as off-ramp colours.

## Paths and geometry

`P(nd=1)` is a fluent builder: every method appends and returns the path. Coordinates are
written with `nd` decimals.

| Method | Draws |
|---|---|
| `M(x, y)` `L(x, y)` `H(x)` `V(y)` `Z()` | move, line, horizontal, vertical, close; `M(p)` and `L(p)` take a point |
| `C(c1, c2, p)` `Q(c, p)` | cubic and quadratic Béziers (or six and four numbers) |
| `A(rx, ry, rot, large, sweep, x, y)` | an SVG arc; the flags are bools or 0/1 |
| `rect(x, y, w, h)`, `rrect(x, y, w, h, r)` | a rectangle, and one with rounded corners |
| `circle(c, r)`, `ellipse(c, rx, ry)` | closed, as two arcs |
| `ring(c, r0, r1)` | an annulus with a real hole |
| `arc(c, r, deg=(a0, a1))` | an open arc from a0 towards a1 |
| `arc_band(c, r0, r1, deg=(a0, a1))` | a closed annular sector; a pie wedge when r0 is 0 |
| `ngon(c, r, n, deg=a, inner=None)` | a regular polygon, or a star with `inner` |
| `dots(pts, r)` | one circle per point of an (N, 2) array |
| `arrowhead(tip, size, deg=a, width=None)` | a triangle pointing along the angle |
| `poly(pts, closed=False)` | a polyline through (N, 2) points |
| `spline(pts, closed=False, tension=1.0)` | a Catmull-Rom curve through the points |
| `shape(geom)` | any shapely geometry, holes and multi-part results included |

Angles are always a keyword naming the unit: `deg=` or `rad=` (0 points east and angles grow
clockwise on screen, as in SVG) or `bearing=` (degrees, 0 points north, clockwise, as on a
compass). Ranges take a pair, `deg=(a0, a1)`. The one positional angle is `A`'s x-axis
rotation.

Points: `Vec(x, y)` is a tuple with arithmetic: `a + b`, `a - b`, `v * k`, `v / k`, `-v`,
`abs(v)` for the length, `v.dot(o)`, `v.perp()`, `v.unit()` and `v.rotate(deg=30, about=c)`.
Plain tuples work wherever a point goes (write `vec + tuple`, not `tuple + vec`), and (N, 2)
arrays wherever a call takes several points; `c + offsets` with an (N, 2) array is an array.

- `polar(c, r, deg=a)` (or `rad=`, `bearing=`): the point at distance `r` from `c`.
- `Rect(x, y, w, h)`: `.x1`, `.y1`, `.center`, `.frac(fx, fy)`, `.contains(p, margin=0)`.
- `lerp(a, b, t)`, `clamp(v, lo=0, hi=1)`, `smoothstep(e0, e1, x)`: numbers or numpy arrays.
  `smoothstep` works with `e0 > e1` for falloffs.

## Randomness

`s.rng(key)` (a `random.Random`), `s.np_rng(key)` (a numpy `Generator`) and `s.noise(key)`
(Perlin noise) are the only random sources; the lint rejects `random`, `numpy.random`,
`scipy.stats.qmc` and `Noise(...)`, and a library sampler (`rvs`, skimage's `random_noise`,
`scipy.sparse.random`, any `random_state=`) unless it is handed a stream:
`stats.norm.rvs(size=9, random_state=s.np_rng(4))`. Each call returns a fresh stream: two calls with one key give two identical
generators, and different keys give independent ones.

With no seed set, an int key gives exactly `random.Random(key)`,
`np.random.default_rng(key)` or `Noise(key)`. Setting `seed` in a variant, or
`--set seed=3` while exploring, moves every stream at once. String keys (`s.rng("coast")`)
name streams too.

`n = s.noise(5)`: `n(x, y)` is 2D Perlin noise roughly in [-1, 1], `n.n3(x, y, z)` 3D (use z
as time or to decorrelate layers), and `n.fbm(x, y, octaves=4, lacunarity=2.0, gain=0.5)` sums
octaves. All three take numbers or numpy arrays that broadcast, so a whole field is one call:
`n.fbm(xs[None, :] / 300, ys[:, None] / 300)`.

Helpers take generators, never seeds: `poisson_disk(rect, 12, s.rng(2))`,
`noise_grid(cols, rows, 60, s.np_rng(4))`. Annotate a helper's generator parameter with `Rng`
or `NpRng` from `walldye`.

## Params and variants

```python
class Moon(Params):
    phase: float = knob(default=58, lo=-150, hi=150, unit="deg", doc="sun angle")
    method: Literal["bayer", "bluenoise"] = knob(default="bluenoise", doc="dither method")
    cells: int = knob(default=3, choices=(2, 3, 4))
    earthshine: bool = True


@design(aspects="any", variants={"crescent": Moon(phase=120), "full": Moon(phase=0)})
def draw(s: Canvas[Moon]) -> None:
    sun = math.radians(s.params.phase)
```

- A `Params` subclass is a frozen dataclass. Fields are `int`, `float`, `bool`, `str` or a
  `Literal`, each with a default, so `Moon()` is the default version. Every class also has
  `seed: int | None = None`.
- `knob(default=..., lo=, hi=, choices=, unit=, doc=)` takes keywords only. `lo` and `hi` are
  soft: they bound `sheet --wedge`, and values outside them only warn. `choices` and `Literal`
  members are hard.
- Variants are instances of the class `draw` is annotated with (`Canvas[Moon]`): at most 4,
  named like `late` or `open-sea`. Each needs a label under `variants:` in meta.yaml, and
  `walldye check` fails two versions whose thumbnails look alike (ink-map cosine 0.93 or more).
  SKILL.md has the variant policy.
- A colour is never a param: use a `Literal` field and pick the colour in `draw`.

Exploring values:

```bash
uv run walldye params <slug>                         # fields, ranges and the variants
uv run walldye preview <slug> --set phase=120        # try a value; never published
uv run walldye preview <slug> --variant crescent
uv run walldye sheet <slug> --wedge phase=-120..120..30 --seeds 0..3
```

## Helper modules

Import them as `from walldye.geom import ...` (or `field`, `pixel`). Point sets are (N, 2)
float arrays; draw them with `P().poly(...)` or `P().dots(...)`.

### walldye.geom

| Name | What it does |
|---|---|
| `Affine` | an SVG matrix: `Affine.translate(dx, dy)`, `.scale(sx, sy=None, about=)`, `.rotate(deg=, about=)`, `.frame(origin, deg=, scale=)` (local +x along the angle); `m @ n` composes, `m(p)` maps a point, `m.apply(pts)` an array, `m.inverse()`. It is also the type of `transform=`. |
| `Polyline(pts, closed=False)` | `.length`, `.at(d)` (the point at arc length `d`, arrays too), `.tangent(d)`, `.resample(step)`, `.offset(dist)` (positive is to the right of travel) |
| `spline_points(pts, n, closed=False)` | points on the curve `P().spline` draws, `n` per segment, for shapely |
| `bezier_points(ctrl, n)` | `n + 1` points on a quadratic or cubic Bézier |
| `ribbon(pts, width)` | the closed outline of a stroke of varying width (`width` a number or one per point) |
| `hatch(region, pitch, deg=, offset=0)` | parallel segments across a shapely region |
| `ngon(c, r, n, deg=, inner=None)` | the vertices `P().ngon` draws |
| `scatter(n, rect, rng, min_dist=0, accept=None, tries=30)` | dart throwing, with an optional `accept(Vec)` test |
| `poisson_disk(rect, radius, rng, k=30)` | Bridson blue-noise points at least `radius` apart |
| `parts(g)` | the single parts of any shapely geometry, empties dropped |

### walldye.field

| Name | What it does |
|---|---|
| `noise_grid(cols, rows, scale, rng, octaves=1, gain=0.5)` | a (rows, cols) fBm Perlin field from `s.np_rng(k)`; `scale` is the feature size in cells. Its range is narrower than ±1 (about ±0.6 at 3 octaves), so normalise before thresholding. |
| `cells(rect, cell)` | the centres of the whole cells covering `rect`, as `xs, ys`, each (rows, cols) |
| `falloff(d, r, power=1)` | `clip(1 - d / r, 0, 1) ** power` |
| `gauss(d, sigma)` | `exp(-(d / sigma) ** 2)` |
| `iso_lines(field, level, cell=1, origin=(0, 0), simplify=0)` | marching-squares lines where the field crosses `level`, in canvas units; `simplify=` costs about 0.7 ms per line per draw (a check draws each aspect and regime three times), so on dense fields use a coarser cell or fewer levels instead |
| `sample_field(fn, cols, rows)` | calls `fn(i, j)` once on the (rows + 1, cols + 1) lattice of integer indices, for `iso_lines` |
| `runs(mask)` | the `(start, stop)` ranges of true values in a 1-D boolean array |

```python
noise = s.noise(5)
field = sample_field(lambda i, j: noise.fbm(i / 40, j / 40), s.w // 6, s.h // 6)
lines = P()
for k in range(-4, 5):
    for line in iso_lines(field, k * 0.08, cell=6):
        lines.spline(line)
s.stroke(lines, UI, 1.2)
```

### walldye.pixel

Pixel work goes through these helpers: their paths carry `class="px"`, the exporter keeps their
edges crisp at every size, and build records the cell size. Keep the origin a whole unit and a
multiple of the cell (`s.pick(..., snap=CELL)`); check warns on a fractional one.

| Name | What it does |
|---|---|
| `grid_runs(s, grid, palette, cell, origin=(0, 0), skip=0, **style)` | an int index grid (rows, cols) as merged runs, one path per palette index; index `skip` (0 by default, usually the background) and `None` palette entries are not drawn |
| `Pixels(cols, rows, palette)` | a grid to paint: `px.grid[mask] = 2` with numpy, `.stamp(art, x, y, key, flip=False)`, `.line(x0, y0, x1, y1, index)`, `.dither(field, levels, method=, where=)`, then `.draw(s, cell, origin)` |
| `dither(field, levels, method="bayer", matrix=4, rng=None, serpentine=False)` | quantises a (rows, cols) field in [0, 1] to indices `0 .. levels - 1`; `"bluenoise"` and `"random"` need `rng=s.np_rng(k)` |
| `bayer(n)`, `blue_noise(n, rng)`, `threshold_matrix(method, size, rng)` | ordered-dither masks, to threshold numpy fields yourself |
| `sprite(s, art, palette, cell, origin)` | pixel art, one character per pixel; `palette` maps characters to paints, others are transparent |
| `glyphs(s, lines, paint, at=, font="8x16", px=2, gap=0, anchor="start", flip=False, key=None)` | bitmap text from the bundled Spleen fonts |
| `glyph(ch, font)`, `text_width(text, font=, px=, gap=)` | one character's bitmap; the drawn width of a line |

Dither methods, with their look and cost at 480x270 cells:

| Method | Look | Cost |
|---|---|---|
| `bayer` | crisp crosshatch lattice, very "computer"; `matrix` 2, 4, 8 or 16 | 0.05 s |
| `clustered` | print halftone: dots grow from cell centres | 0.05 s |
| `bluenoise` | even organic grain, no visible pattern | 0.25 s |
| `lines` | a line screen thickening with tone; `matrix` is the pitch | 0.05 s |
| `random` | white-noise grain, clumpy | 0.05 s |
| `fs` | Floyd-Steinberg: fine, with slight worms; `serpentine=True` helps | 0.1 s |
| `atkinson` | 1-bit Macintosh: punchy, highlights and shadows clip to flat | 0.3 s |
| `jarvis`, `stucki` | wide kernels: the smoothest diffusion | 0.5 s |
| `burkes`, `sierra`, `sierra-lite` | between fs and jarvis; lite is cheapest | 0.2-0.4 s |
| `riemersma` | diffusion along a Hilbert curve: soft, curly texture | 0.8 s |

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

- Fonts: `"5x8"` covers ASCII plus light box drawing; `"8x16"` covers ASCII, all box drawing
  and block elements (`░▒▓█▀▄▌▐`), `▬▲▼◆◊○●◘◙◢◣◤◥` and braille U+2800-28FF. Unknown
  characters are blank, and spaces are never drawn.
- Each font pixel is `px` by `px` units, and a character cell is `(fw + gap) * px` wide, so
  8x16 at `px=2` is 16x32. Keep `px` an integer.
- `paint` is one paint, or `paint(col, row, ch)` returning a paint, or `None` to skip the cell.
  Cells group into one path per paint; `key(col, row, ch)` groups by your own key instead.
- `anchor` places each line at `at[0]` by its start, middle or end.
- Brightness ramps are plain strings, `" .:-=+*#%@"` or `" ░▒▓█"`, indexed with
  `min(len(r) - 1, int(v * len(r)))`.

```python
glyphs(s, ["┌──────┐", "│ T+42 │", "└──────┘"], UI, at=(200, 200), px=2)
glyphs(
    s,
    lines,
    lambda col, row, ch: ACCENT if ch.isdigit() else UI,
    at=s.frac(0.6, 0.3),
    anchor="middle",
)
```

## Data files

Data that would bloat design.py (a star catalogue, a game record, a coastline) goes in
`wallpapers/<slug>/data/` as flat `.json`, `.txt` or `.npy` files, read with `s.data(name)`:
parsed JSON, text, or a numpy array. Data files are part of the piece's hash, so editing one
means a rebuild. `s.data` returns an unchecked value, so annotate it where you read it, or
Pyrefly checks nothing downstream:

```python
coast: list[list[float]] = s.data("coast.json")
```

## Third-party libraries

- numpy: compute whole fields at once. `cells(rect, cell)` or `np.mgrid` give coordinates;
  `np.hypot`, `np.clip`, `np.where` and `np.gradient` build tone maps for `dither` and
  `iso_lines`. Random arrays come from `s.np_rng(k)`.
- shapely: boolean geometry, drawn back with `P().shape(geom)`, which keeps holes and handles
  multi-part results.
  - `unary_union([...])` merges overlapping shapes; `a.difference(b)` and `a.intersection(b)`
    cut; `Point(x, y).buffer(r, quad_segs=48)` makes a disc and `box(x0, y0, x1, y1)` a
    rectangle.
  - `line.buffer(w / 2, cap_style="flat")` turns a stroke into a fillable outline, and
    `.buffer(-k).buffer(k)` rounds off corners.
  - `LineString(...).difference(obstacle.buffer(6))` breaks lines around a shape, for a
    technical-drawing gap. `parts(g)` from `walldye.geom` iterates any result.
- scipy: `spatial.Delaunay`, `Voronoi` and `cKDTree` for meshes, cells and neighbours;
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

## Lint, types and limits

`walldye check` runs these before drawing anything:

- the design lint: the import allowlist above; randomness only from `s`; no `Colour(`,
  `Ref(`, `Canvas(` and friends; no `hash`, `id`, `open`, `eval` or `global`; exactly one
  `@design` `draw`; the module-level rules; no changes to module-level objects inside
  functions; no raw hex strings or colour text forms; no `# type: ignore`,
  `# pyrefly: ignore`, `typing.cast` or `typing.Any` (fix what Pyrefly reports instead);
- `ruff format --check` and `ruff check` (line length 100, sorted imports); fix with
  `uv run ruff format wallpapers/<slug> && uv run ruff check --fix wallpapers/<slug>`;
- Pyrefly at the standard level. Annotate `draw` as `def draw(s: Canvas[YourParams]) -> None`
  (plain `Canvas` without params) and your helpers' parameters. The types catch a raw hex where
  a paint goes, a misspelt style key, a positional angle, a theme colour in a mask and a
  variant of the wrong params class. `f(*p, r)` is miscounted as too many arguments when `p`
  has no known length (a list, an array): type the point as `tuple[float, float]` or `Vec`, or
  pass `p[0], p[1]`.

Then, for each version, screen shape and regime, two draws in-process and one in a fresh
process must match, every basis, held-out and probe theme must serialise and fit within 2 RGB
units, and constant colours may appear only inside masks and clips.

Errors: `<text>`, `<filter>` or `<image>` (the API cannot write them), more than 1 MB or 20,000
elements, and two versions that look alike. Warnings: more than 600 kB or 15,000 elements,
colour words in the docstring, comments or meta.yaml copy (the list includes black, white,
grey and golden, and plurals such as "greys" match, so "golden section" trips it), a
fractional pixel-grid origin, a version whose check took over 2 minutes, and a variant value
outside its knob's `lo`..`hi`.

Staying under the limits:

- One path per paint and stroke style: accumulate subpaths in one `P()`, or use `s.buckets`.
  `grid_runs`, `glyphs` and `sprite` already merge runs.
- Quantise continuous tone into 4 to 8 rungs of a `ladder` and bucket by `TONES.rung(v)`,
  never one element per value.
- `P()` rounds to 1 decimal, which is crisp at 4K; use `P(nd=2)` only for fine detail.
- A 4-unit pixel cell gives 480x270 cells at 16:9, 50 to 400 kB after `grid_runs`. Use 2-unit
  cells only for sparse content; 32:9 doubles the cell count.
- Compute fields in numpy, not per-point Python loops: `Noise` and the field helpers take
  arrays.
- Many dots are one path: `P().dots(pts, r)`, or zero-length segments with round caps,
  `d.M(x, y).H(x)` for each and `s.stroke(d, UI, diameter, cap="round")`.
