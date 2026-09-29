# walldye design API

The reference for the Python API designs draw with, the CLI, and the files the build writes. The docstrings in `walldye/` give the exact behavior, including every error a call raises; [architecture.md](architecture.md) explains why it works this way. When this file and the code disagree, fix one of them in the same change.

## 1. Conventions

- Python 3.13 with PEP 695 generics. `ArrayLike` and `NDArray` are numpy's.
- `type Num = float | np.integer | np.floating`. Every numeric parameter (coordinates, lengths, widths, radii, opacities, angles, mix amounts, `Style` values, the numbers in a `Point`) is `Num` in the code, so numpy scalars type-check; this file writes `float`. Return types, fields and `Params` declarations are `float`, and counts and indices are `int`. `Point = tuple[Num, Num]`, and a `Vec` is one.
- Canvas units are pixels, and the short side is always 1080.
- Runtime checks back up the static types: a `bool` where a number goes, NaN or infinity, or a raw color string raises even where the checker lets it through.

## 2. Modules

Designs import only these four. Each defines `__all__` with exactly these names, which Pyrefly's `implicit-reexport` rule relies on.

| Module | Names |
|---|---|
| `walldye` | `design`, `Canvas`, `Params`, `knob`; `Color`, `MaskColor`, the 20 tokens (§4.1), `MASK_WHITE`, `MASK_BLACK`, `mix`, `ramp`, `ladder`, `Ladder`, `by_regime`; `Paint`, `MaskPaint`, `Ref`, `Style`, `Stop`, `MaskStop`, `LineCap`, `LineJoin`, `FillRule`; `Buckets`, `ClipSurface`, `MaskSurface`, `PatternSurface`, `Rng` and `NpRng` for annotating helpers, since designs may not name `random` or `numpy.random`; `P`, `Path`, `Vec`, `Rect`, `Point`, `Num`, `polar`, `lerp`, `clamp`, `smoothstep` |
| `walldye.geom` | `Affine`, `Polyline`, `spline_points`, `bezier_points`, `ribbon`, `hatch`, `ngon`, `scatter`, `poisson_disk`, `parts` |
| `walldye.field` | `Noise`, `noise_grid`, `cells`, `falloff`, `gauss`, `iso_lines`, `runs`, `sample_field` |
| `walldye.pixel` | `Pixels`, `grid_runs`, `dither`, `bayer`, `blue_noise`, `threshold_matrix`, `sprite`, `glyph`, `glyphs`, `text_width`, `Font`, `DitherMethod` |

The `_*.py` modules implement them. `walldye.tools` is the CLI, which designs never import. Everything under `walldye/` except `tools/` feeds the render-lib hash (architecture.md, Build and check).

## 3. Design files

A design is `wallpapers/<slug>/design.py`, with optional data files in `data/`. The tools import it once per process and draw it once per version, aspect and regime.

```python
"""A filled disc inside faint rings, right of center on a landscape screen."""

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

The design lint (§13.1) enforces these rules:
- The module docstring is one theme-neutral line (wallpapers.md, Copy).
- Imports come from an allowlist: some standard-library modules, the four `walldye` modules, numpy, scipy, shapely and skimage. The design's folder is not on `sys.path`.
- Module level holds constants, pure helper functions and classes, `Params` subclasses, the variants mapping, and exactly one `@design(...)` function named `draw`. Nothing there can depend on the canvas, the theme or the variant.
- Nothing at module level is mutated while drawing. The same module object draws every render, so a list appended to in `draw` leaks into the next one; the determinism check catches what the lint misses.
- Everything render-dependent arrives through `s`: size, regime, params, random streams and data files. A render depends only on the design file, its data, the params, the aspect and the regime. The theme is applied afterwards, when the document is serialized.
- `print()` goes to stderr.

For complete designs, see the Examples table in `.claude/skills/walldye/SKILL.md`; `wallpapers/radar-sweep/design.py` has params and a named variant.

## 4. Colors

A `Color` is a formula over theme tokens, never a hex value (architecture.md, Designs draw in formulas).

- `Color` and `MaskColor` have no public constructor; colors come from the tokens and the functions below. They compare and hash by formula, stably across processes, so `mix(a, b, 0.5) != mix(b, a, 0.5)` although both resolve to the same hex. Ordering, `str()` and `format()` raise `TypeError`: key and sort by index or role.
- Mask colors are `MASK_WHITE` (shows), `MASK_BLACK` (hides) and mixes of the two, the same under every theme. Only a mask surface takes them, and it takes nothing else.
- Each token and each `mix` rounds to 8 bits when resolved, so a long chain of nested mixes drifts, and check fails a color more than 2 units off (architecture.md, Recoloring).

### 4.1 Tokens

`Final[Color]` constants in `walldye`. `beyond` is black in the dark regime and white in the light one. In the light regime the four fractions marked * are multiplied by 1.6, capped at 0.5. The `fireproof` preset pins every token by hand, well off these fractions, so never assume a token equals its formula.

| Token | Derivation | Token | Derivation |
|---|---|---|---|
| `BLACK` | `mix(bg, beyond, 0.43)` | `FG_ALT` | `mix(bg, fg, 0.816)` |
| `BG_DEEP` | `mix(bg, beyond, 0.15)` | `FG` | seed |
| `BG` | seed | `ACCENT_HI` | `mix(accent, fg, 0.28)` |
| `BG_ALT` | `mix(bg, fg, 0.063)`* | `ACCENT` | seed |
| `UI` | `mix(bg, fg, 0.126)`* | `ACCENT_1` ... `ACCENT_8` | `mix(accent, bg, t)`, t = .17 .26 .5 .56 .68 .8 .9 .955 |
| `UI_ALT` | `mix(bg, fg, 0.189)`* | | |
| `UI_HI` | `mix(bg, fg, 0.31)`* | | |
| `MUTED` | `mix(bg, fg, 0.563)` | | |

The site's 21st token, `orange_dark`, has no design constant.

### 4.2 Building colors

| Function | Result |
|---|---|
| `mix(a, b, t)` | `a` blended towards `b` by `t` in [0, 1]; both `Color` or both `MaskColor`. `t == 0` gives `a`, `t == 1` gives `b`, and `a == b` gives `a` |
| `ramp(a, b, n)` | `n` colors evenly spaced from `a` to `b`, both included |
| `ladder(stops, n)` | a `Ladder` of `n` rungs spaced evenly along the piecewise-linear path through two or more `stops`; `ladder((lo, ACCENT_4, hi), n)` is the usual accent ramp |
| `by_regime(dark, light)` | `dark` in the dark regime and `light` in the light one, while both regimes keep one template |

A `Ladder` is a tuple of colors, so it indexes, slices and goes into `s.buckets`. `rung(v)` quantizes `v` in [0, 1], scalar or array, into `n` equal bins, and `at(v)` is that rung's color.

### 4.3 Paints and refs

```python
type Paint = Color | Literal["none"] | Ref
type MaskPaint = MaskColor | Literal["none"] | Ref
type Stop = tuple[float, Color] | tuple[float, Color, float]  # offset, color[, opacity]
type MaskStop = tuple[float, MaskColor] | tuple[float, MaskColor, float]
```

A `Ref` comes only from a gradient, pattern, clip or mask, and its kind decides where it goes: `"paint"` on the canvas or a pattern, `"mask_paint"` on a mask surface, `"clip"` in `clip_path=`, `"mask"` in `mask=`. Any other string in a paint position, such as a hex value, raises `TypeError`.

## 5. Geometry

- `Vec(x, y)` is a named tuple with `abs(v)` (its length), `dot`, `perp` (a quarter turn clockwise on screen), `unit` and `rotate(*, deg= | rad=, about=)`. It goes wherever a `Point` does; plain tuples work everywhere, and `(N, 2)` arrays wherever a signature says `ArrayLike`.
- `+` and `-` with a point, and `*` and `/` with a number, give a `Vec`. With an ndarray on either side the result is an ndarray, as Pyrefly infers, so `s.center + offsets` of shape `(N, 2)` is `(N, 2)`. For operators Vec does not define (`**`, `@`, comparisons), write `np.asarray(v)`. Write `v + (1, 2)`, not `(1, 2) + v`, which the checker reads as tuple concatenation.
- `Rect(x, y, w, h)` has `x1`, `y1`, `center`, `frac(fx, fy)` and `contains(p, margin=0.0)`.
- `lerp(a, b, t)`, `clamp(v, lo=0.0, hi=1.0)` and `smoothstep(e0, e1, x)` take scalars or arrays and return the same kind.

### 5.1 Angles

Every API that takes an angle takes exactly one keyword naming the unit:
- `deg=` or `rad=`: 0 points east (+x) and angles grow clockwise on screen, as in SVG (y points down).
- `bearing=`: degrees, 0 points north (up) and bearings grow clockwise, as on a compass. `bearing=b` equals `deg=b - 90`.

Ranges take a pair under the same keyword: `deg=(a0, a1)`. The one exception is the x-axis rotation of `Path.A`, positional SVG degrees as in the path command.

`polar(c, r, *, deg= | rad= | bearing=)` is the point at distance `r` from `c` in that direction.

## 6. Paths

`P(nd=1)` returns a `Path`, a fluent builder for SVG path data with `nd` (0 to 4) decimals. Every method appends and returns the path, and one path holds any number of subpaths, so the usual pattern is one path per paint and stroke style, drawn once.

Commands are absolute and positional, taking numbers or points: `M`, `L`, `H`, `V`, `C`, `Q`, `A(rx, ry, rot, large, sweep, ...)` and `Z`. The `A` flags take a `bool`, an `np.bool`, or 0 or 1; write `cond` and `not s`, since `int(cond)` types as `int`.

Primitives each start a new subpath, so any number merge into one element:

| Method | Draws |
|---|---|
| `rect(x, y, w, h)`, `rrect(x, y, w, h, r)` | a rectangle; `rrect` rounds its corners by `min(r, w/2, h/2)` |
| `circle(c, r)`, `ellipse(c, rx, ry)` | two arcs; `r == 0` draws nothing |
| `ring(c, r0, r1)` | an annulus whose hole shows under the default fill rule |
| `arc(c, r, *, deg=(a0, a1))` | an open arc from `a0` to `a1`, less than a full turn |
| `arc_band(c, r0, r1, *, deg=(a0, a1))` | a closed annular sector; a pie wedge when `r0 == 0` |
| `ngon(c, r, n, *, deg=, inner=None)` | a regular polygon with vertex 0 at the angle; with `inner`, a star alternating `r` and `inner` |
| `dots(pts, r)` | one circle per point |
| `arrowhead(tip, size, *, deg=, width=None)` | a triangle pointing along the angle |
| `poly(pts, *, closed=False)` | a polyline through an `(N, 2)` array |
| `spline(pts, *, closed=False, tension=1.0)` | a Catmull-Rom curve through the points |
| `shape(geom)` | any shapely geometry, holes included |

## 7. Canvas

`draw` receives a `Canvas[Pm]` that lives for one draw. The type parameter is covariant, so helpers can take a plain `Canvas`.

| Property | Value |
|---|---|
| `w`, `h` | the canvas size in pixels |
| `landscape` | `w >= h` |
| `light` | the regime of this draw |
| `params` | this version's `Params` instance |
| `center` | `Vec(w / 2, h / 2)` |

`s.light` is the only theme fact a design can read, and branching on it costs a light template per aspect and variant. There is no `s.variant` or `s.aspect`: designs branch on params and on the canvas shape, never on names.

### 7.1 Layout

- `frac(fx, fy)` is `Vec(fx * w, fy * h)`.
- `pick(*, landscape, portrait, snap=None)` scales the `landscape` fractions when `s.landscape`, else the `portrait` ones, rounding each coordinate to a multiple of `snap` when given, so that a pixel grid anchored there has a whole-cell origin.
- `inset(margin)` is `Rect(margin, margin, w - 2 * margin, h - 2 * margin)`; a negative margin grows it.

### 7.2 Random streams

`s.rng(key)` (a `random.Random`), `s.np_rng(key)` (a `np.random.Generator`) and `s.noise(key)` (a `Noise`) are the only randomness a design may use. Each call returns a fresh generator in the stream's initial state. A key is an int of at least 0, or a string.

With `seed = s.params.seed`:

| Case | `rng` | `np_rng` | `noise` |
|---|---|---|---|
| `seed is None` and `key` is an int | `random.Random(key)` | `np.random.default_rng(key)` | `Noise(key)` |
| otherwise | `random.Random(name)` | `np.random.default_rng(int.from_bytes(sha256(name).digest()[:16], "big"))` | `Noise(name)` |

`name = f"{'' if seed is None else seed}:{key!r}"`, so seed 11 with key 5 is `"11:5"`. With no seed, the literal keys a design was tuned with are its seeds; setting `seed` in a variant moves every stream at once. Neither form depends on `PYTHONHASHSEED`.

### 7.3 Data files

`s.data(name)` reads `data/<name>` beside the design: `.json` as parsed JSON, `.txt` as text and `.npy` through `np.load(allow_pickle=False)`. The result is `Any`, the one unchecked value a design gets, so annotate it where it is read: `coast: list[list[float]] = s.data("coast.json")`. Put anything over a few kilobytes of coordinates, tables or text in a data file.

### 7.4 Drawing

```python
def fill(self, d: Path, paint: Paint, *, rule: FillRule | None = None,
         opacity: float | None = None) -> None
def stroke(self, d: Path, paint: Paint, width: float, *, cap: LineCap | None = None,
           join: LineJoin | None = None, dash: Sequence[float] | None = None,
           opacity: float | None = None) -> None
def path(self, d: Path, *, fill: Paint, **style: Unpack[Style]) -> None
```

Each emits one `<path>`, and an empty path draws nothing. `path` is the typed escape hatch for everything else; its `fill` is required, `"none"` for an outline.

### 7.5 Style

```python
class Style(TypedDict, total=False):
    stroke: Paint
    stroke_width: float
    stroke_linecap: LineCap  # "butt" | "round" | "square"
    stroke_linejoin: LineJoin  # "miter" | "round" | "bevel"
    stroke_dasharray: Sequence[float]
    stroke_dashoffset: float
    stroke_opacity: float
    fill_opacity: float
    fill_rule: FillRule  # "nonzero" | "evenodd"
    opacity: float
    transform: Affine
    clip_path: Ref
    mask: Ref
```

Style has no `fill` key; the methods that take a fill take it as their own keyword. A shared style is a typed dict: `THIN: Style = {"stroke": UI, "stroke_width": 1.0}`, then `s.path(d, fill="none", **THIN)`.

Values are checked at runtime as well (unknown keys, non-finite numbers, negative widths, opacities outside [0, 1], bad literals, paints as in §4.3), and attributes are written in one fixed order.

### 7.6 Groups and buckets

- `with s.group(**style):` wraps what is drawn inside in a `<g>`. It takes no `fill`, because every element sets its own; children inherit an unset `stroke`, `stroke_width` or `fill_rule`.
- `with s.buckets(paints, kind, **style) as b:` gives one `Path` per paint, `b[i]`, and emits one element per non-empty bucket, in index order, where the block opened; anything else drawn inside lands above them. `kind="fill"` fills each with `paints[i]`; `kind="stroke"` strokes each, and `style` must set `stroke_width` but not `stroke`. Buckets are keyed by index, never by color, so two equal paints give two elements.

### 7.7 Clips, masks and patterns

```python
def clip(self) -> AbstractContextManager[ClipSurface]
def mask(self) -> AbstractContextManager[MaskSurface]
def pattern(self, w: float, h: float, *,
            transform: Affine | None = None) -> AbstractContextManager[PatternSurface]
```

Each surface collects its content inside the block and goes to `<defs>` when the block closes; use its `ref` afterwards: `with s.group(clip_path=clip.ref):`, `mask=m.ref`, `s.fill(d, pat.ref)`. While a surface is open, the canvas cannot be drawn on.
- `ClipSurface.add(d, *, rule="nonzero", transform=None)` takes geometry only.
- `MaskSurface` has `fill`, `stroke`, `group` and its own gradients, taking mask colors only; grays are `mix(MASK_BLACK, MASK_WHITE, t)`.
- `PatternSurface` has `fill`, `stroke`, `path` and `group` with theme paints, in pattern-local coordinates.

### 7.8 Gradients

`s.linear_gradient(stops, p0, p1, *, units="user")` and `s.radial_gradient(stops, center, r, *, focus=None, units="user")` return a `"paint"` ref and go to `<defs>` at once, so a pattern can use one made inside its own block. `units="user"` means canvas pixels, and `"bbox"` 0 to 1 over the painted shape's bounding box. Offsets are within [0, 1] and non-decreasing.

### 7.9 Pixel paths

`s.pixel_path(d, fill, *, cell, origins, **style)`, which the `walldye.pixel` helpers call, emits a `<path class="px">` and records its grid. The class tells the exporter to draw these paths with crisp edges, and the grids give slots.json its `cells` and feed check's whole-origin warning.

## 8. Params and knob

A design's parameters are a frozen, typed subclass of `Params`. Its metaclass makes every subclass a frozen, keyword-only dataclass, and carries the `dataclass_transform` so that the checker sees the inherited `seed: int | None = None`.

```python
class Moon(Params):
    phase: float = knob(default=58, lo=-150, hi=150, unit="deg", doc="sun angle from the viewer")
    method: Literal["bayer", "bluenoise"] = knob(default="bluenoise", doc="dither method")
    cells: int = knob(default=3, choices=(2, 3, 4))
    earthshine: bool = True
```

- `knob` takes `default` and optionally `lo` and `hi` (numbers), `choices` (str or int), `doc` and `unit`, all by keyword, since PEP 681 checkers see a field's default only through `default=`. A field without `knob` is a plain default.
- `lo` and `hi` are soft: they bound `sheet --wedge`, and `--set` and check warn outside them. `choices`, and the members of a `Literal` annotation, are hard.
- Fields are `int`, `float`, `bool`, `str` or a `Literal` of str or int values, and all have defaults, since the default version is `Moon()`. There are no color params; a `Literal` chosen in `draw` covers role choices.
- Instances validate their values, store floats as `float`, and hash and compare by value.

## 9. The design decorator

```python
def design[Pm: Params](
    *,
    aspects: Literal["any"] | tuple[Aspect, ...] = ("16:9",),
    variants: Mapping[str, Pm] | None = None,
    bg: Color = BG,
) -> Callable[[Callable[[Canvas[Pm]], None]], Design[Pm]]: ...
```

It decorates the one `draw(s: Canvas[Pm]) -> None` and replaces it with a `Design`.

- `aspects`: `"any"` for every aspect in `SITE_ASPECTS`, or a tuple of them. 16:9 is always native, because the site's plates and social cards need it; a design that composes only for 16:9 leaves `aspects` out.
- `variants`: at most 4 named variants, so 5 versions with the default. Each is an instance of exactly `draw`'s params class and differs from `Pm()` and from the others. Names match `[a-z0-9]+(-[a-z0-9]+)*`, are at most 24 characters and are not `default`. Labels, descriptions and draft flags live in meta.yaml (wallpapers.md, meta.yaml).
- `bg`: the color of the full-canvas rectangle drawn before `draw` runs; a `by_regime` color is fine.
- The params class comes from `draw`'s annotation, `Canvas[X]`, so annotate it when there are variants.

`Design.draw(spec)` draws one `RenderSpec(variant, params, aspect, regime)` into a `Document`, which the tools serialize under each theme they need.

## 10. Helper modules

Helpers take randomness as a generator from `s.rng`, `s.np_rng` or `s.noise`, never as an integer seed. Point arrays are `NDArray[np.float64]` of shape `(N, 2)`.

### 10.1 `walldye.geom`

| Name | Does |
|---|---|
| `Affine` | an SVG `matrix(a b c d e f)` and the type of `transform=`: `translate`, `scale`, `rotate`, `frame` (local coordinates to the canvas), `@`, `apply`, `inverse` |
| `Polyline(pts, *, closed=False)` | arc-length walking: `length`, `at(d)`, `tangent(d)`, `resample(step)`, `offset(dist)` |
| `spline_points(pts, n)`, `bezier_points(ctrl, n)` | points sampled on a Catmull-Rom spline or a Bézier |
| `ribbon(pts, width)` | the closed outline of a stroke of varying width |
| `hatch(region, pitch, *, deg=)` | parallel segments clipped to a shapely region |
| `ngon(c, r, n, *, deg=, inner=None)` | the vertices `P().ngon` draws |
| `scatter(n, rect, rng, *, min_dist=0.0, accept=None)` | dart throwing; may return fewer than `n` points |
| `poisson_disk(rect, radius, rng)` | Bridson sampling |
| `parts(g)` | a shapely geometry flattened to its non-empty parts |

### 10.2 `walldye.field`

| Name | Does |
|---|---|
| `Noise` | seeded 2D and 3D Perlin noise, roughly within [-1, 1], with `n3` and `fbm`, on scalars or arrays. Designs get one only from `s.noise(key)` |
| `noise_grid(cols, rows, scale, rng, *, octaves=1, gain=0.5)` | an fBm Perlin field of shape `(rows, cols)` |
| `cells(rect, cell)` | the cell-center arrays `xs` and `ys` covering `rect`; x first, unlike `np.mgrid` |
| `falloff(d, r, power=1.0)`, `gauss(d, sigma)` | `clip(1 - d / r, 0, 1) ** power` and `exp(-(d / sigma) ** 2)` |
| `sample_field(fn, cols, rows)` | `fn(i, j)` over the corner lattice `iso_lines` expects |
| `iso_lines(field, level, *, cell=1.0, origin=(0.0, 0.0), simplify=0.0)` | contour lines in canvas coordinates; `simplify` is slow on dense fields |
| `runs(mask)` | the `(start, stop)` ranges of true values in a 1-D boolean array |

### 10.3 `walldye.pixel`

| Name | Does |
|---|---|
| `grid_runs(s, grid, palette, cell, origin=(0.0, 0.0), *, skip=0)` | an index grid drawn as merged horizontal runs, one pixel path per palette index |
| `Pixels(cols, rows, palette)` | an index grid to build with `stamp`, `line` and `dither`, then `draw`; index 0 is the background |
| `dither(field, levels, *, method="bayer", rng=None)` | quantizes a field in [0, 1] into level indices, by any `DitherMethod` |
| `bayer`, `blue_noise`, `threshold_matrix` | threshold masks |
| `sprite(s, art, palette, cell, origin=(0.0, 0.0))` | pixel art from a string, one character per pixel |
| `glyph(ch, font="8x16")`, `glyphs(s, lines, paint, *, at, ...)`, `text_width` | bitmap text from the bundled Spleen fonts (`"5x8"`, `"8x16"`), drawn as pixel paths |

## 11. Build files

### 11.1 Layout

```
wallpapers/<slug>/
  design.py
  data/                       # optional and flat; .json, .txt and .npy only
  meta.yaml
  build/                      # generated and gitignored; only `walldye build` writes here
    16x9.svg                  # the default version under fireproof
    16x9.light.svg            # under flexoki-light, only when light geometry differs
    <aspect>[.light].svg      # the other native aspects
    slots.json
    <variant>/                # one directory per named variant, laid out the same way
```

Build removes template files it did not write and directories that are not declared variants, and touches nothing else.

### 11.2 SVG format

One element per line, with a trailing newline and no XML declaration: the `<svg>` tag, `<defs>` on one line when anything was defined, the background `<rect>`, then the drawing. The only elements are `svg`, `defs`, `rect`, `path`, `g`, `clipPath`, `mask`, `pattern`, `linearGradient`, `radialGradient` and `stop`, and colors appear only in `fill`, `stroke` and `stop-color`, as uppercase `#RRGGBB`.

### 11.3 slots.json

One per variant directory, with one top-level key per line and each value compact JSON:
- `design_sha`: the hash of design.py (or source.svg and palette.yaml) and every data file, plus a `variant\t<name>` line for a named variant, which also gets a `"variant"` key;
- `focus`: the ink-weighted centroid of the 16:9 dark template, which centers crops and social cards;
- `cells`: the cell sizes of pixel pieces;
- `probes` and `render_lib`: the probe render hashes and the render-lib hash they were made under;
- `checked`: the walldye version that last checked it;
- one `"<aspect>/<regime>"` entry per template, `{file, sha256, n, coefs, occ}`: `coefs` holds the deduplicated `[a, b, c, dr, dg, db]` rows at 5 decimals, and `occ` the row for each of the `n` color occurrences.

architecture.md (Build and check) says how the hashes decide what to redraw.

### 11.4 index.json

`wallpapers/index.json` summarizes every built piece, keyed by slug, for consumers outside the site: `aspects` (the native ones, from the default version's slots.json), `draft`, `license`, `title` and `variants` (named variants only, in meta.yaml order, each with `draft` and `label`; `{}` when there are none). Build, review and drop rewrite it, leaving out a piece that has no `build/slots.json` yet. It is gitignored.

### 11.5 Tool API

`walldye/tools/common.py` holds what the other tools and the batch workflow call: `load(slug)`, `render`, `rasterize`, `crop_svg`, `ink_map` and `focus`. `check` and `build` run one task per (slug, variant) in a process pool whose workers never write files; the parent prints and writes.

## 12. CLI

Run `uv run walldye <command>`; `-h` lists any command's flags. Commands that take slugs need them named, or `--all`.

### 12.1 Commands

| Command | Does |
|---|---|
| `new <slug> --model M` | writes the starter design.py (§12.3) and a draft meta.yaml with `model: M`, today's date and no `license:` |
| `preview <slug>` | a PNG in `$WALLDYE_PREVIEW` (default `<tmp>/walldye`), printing the design lint, the regime and whether light geometry differs. `--theme`, `--aspect`, `--crop X,Y,W,H`, `--variant`, `--set k=v`, `--width`, `--renderer resvg\|inkscape` |
| `render <slug>` | one SVG in the working directory, or `-o PATH` (`-` for stdout); never into `build/`. A PATH ending in `.png` gets an opaque PNG `--width PX` wide (default the canvas's). `--fit` cuts an aspect the piece doesn't declare from its 16:9 render around the focus, as the site does, instead of refusing it. Takes preview's `--theme`, `--aspect`, `--crop`, `--variant` and `--set` |
| `check [<slug>... \| --all]` | the gate (architecture.md, Build and check). `--variant NAME`, `--jobs N` (default every core), `--paranoid` (redraw from a fresh import for every theme), `--similar` (near-clone pairs across pieces) |
| `build [<slug>... \| --all]` | check, then write `build/` and index.json. `--variant`, `--jobs`, `--force`, `--published` (skip drafts; what CI runs). Refuses `--set`: published values belong in a named variant |
| `review [<slug>... \| --all]` | the review page (§12.4). `--port`, `--timeout` (default 7200 s), `--no-open` |
| `sheet [<slug>... \| --all]` | a contact sheet (§12.2). `--theme`, `--aspect`, `--variant`, `--set`, `--wedge k=SPEC`, `--seeds A..B`, `--cols`, `--thumb`, `-o PATH` |
| `params <slug>` | the params, their ranges and each named variant's values and label; `--json` for scripts |
| `list` | slug, title, description, draft, native aspects and named variants, tab-separated |
| `drop <slug>...` | deletes the folder after a y/N prompt and takes the piece off `featured.yaml`; `--yes` when the owner has already confirmed |
| `themes` | the presets; `--theme T` also prints that theme's 21 tokens |

`--theme` takes a preset name or bg-fg-accent seeds (also `bg,fg,accent` and `bg=..,fg=..,accent=..`), defaulting to `$WALLDYE_THEME`, else fireproof. `--variant` takes `default` or a declared name.

The CLI works on the checkout it is installed from. `$WALLDYE_ROOT` points an installed copy, such as the Nix package, at another folder holding `wallpapers/` and `taxonomy.yaml`.

### 12.2 Exploring

- `--set k=v` overrides one params field in preview, render and sheet (`seed` takes an int or `none`).
- `sheet <slug> --wedge k=SPEC --seeds A..B` draws one piece for every combination into a labeled grid of at most 64 cells. `SPEC` is `a..b..step` or `v1,v2,...`.
- Without `--wedge`, `--seeds` or `--set`, `sheet` tiles built templates recolored under `--theme`.

### 12.3 The `walldye new` template

```python
"""TODO: one theme-neutral line, concept + technique."""

from walldye import ACCENT, UI, Canvas, P, design


@design()  # aspects="any" once the composition follows s.w and s.h
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(0.62, 0.5), portrait=(0.5, 0.4))
    s.stroke(P().circle(c, 240), UI, 2)
    s.fill(P().circle(c, 10), ACCENT)
```

### 12.4 `walldye review`

A localhost page that goes through versions one at a time and blocks until Apply. Without slugs its queue is every unpublished version; with slugs, every version of those pieces; with `--all`, everything. The sidebar edits the piece's words and facets and decides proposed facets; a new facet value needs a label. Each step is accepted (<kbd>A</kbd>), sent back for an edit (<kbd>E</kbd>), removed (<kbd>R</kbd>, which unpublishes a published version) or skipped (<kbd>S</kbd>). A note on an accept asks for more like it, and a note on an edit says what should change.

Decisions are saved to the gitignored `.walldye-review.json` as they are made, so a review resumes where it stopped. Only Apply writes to the repository:
- Accepting an unpublished version removes its `draft:`, and removing a published one sets `draft: true`. Nothing else about a version changes; review never edits design.py.
- Edits and facet decisions go to meta.yaml, and a new facet value to taxonomy.yaml with its label in `src/lib/labels.ts`.
- A piece is refused, and nothing of it written, when an edit adds a lint error, a new facet value has no label, or it would be published with proposed facets undecided.

It then prints JSON:

| Key | Holds |
|---|---|
| `approved`, `rejected` (`[{slug, note}]`), `undecided` | the unpublished default versions |
| `variants` | the same three keys over the unpublished named versions (`[{slug, variant, note?}]`) |
| `edit` | `[{slug, variant, published, note}]`, every version sent back |
| `notes` | `[{slug, variant, note}]`, every note |
| `published`, `published_variants`, `unpublished` | `[{slug, variant}]`, what Apply changed |
| `refused` | `[{slug, reason}]` |
| `edits` | `[{slug, variant, field, before, after}]` |
| `new_facets` | `[{facet, value, label}]` |
| `finished` | false after a timeout or an `error` |

A rejection is never a reason to delete a piece: `drop` is a separate step the owner confirms.

## 13. Lint and typing

### 13.1 Design lint

`walldye/tools/lint.py`, run by `preview` and `check`. Errors, each naming the line:

| Rule | Fails |
|---|---|
| imports | anything off the allowlist: `math`, `cmath`, `itertools`, `functools`, `collections`, `heapq`, `bisect`, `operator`, `dataclasses`, `typing`, `enum`, `fractions`, `statistics`, `string`, `re`, `textwrap`, `json`, `base64`, `zlib`, `copy`, the four `walldye` modules, numpy (not `numpy.random`), scipy, shapely and skimage. Relative imports and `from __future__ import annotations` fail too |
| randomness | `numpy.random`, `scipy.stats.qmc`, and constructing generators or `Noise` directly; library samplers unless handed `s.np_rng(key)` |
| constructors | calls of `Color`, `MaskColor`, `Ref`, `Canvas`, `Document` or `Design` |
| process state | the builtins `hash`, `id`, `open`, `exec`, `eval`, `compile`, `globals` and `__import__`, and `global` statements |
| entry point | anything but exactly one module-level `draw` decorated with `@design(...)` |
| module level | anything §13.2 does not allow |
| mutation | mutating a module-level name inside a function |
| data | files in `data/` other than `.json`, `.txt` and `.npy`, and subdirectories |
| type escapes | `# type: ignore`, `# pyrefly: ignore`, `typing.cast` and `typing.Any` |

Warnings: color words in docstrings and comments, a pixel-grid origin that is not a whole unit, and a variant whose check took more than 120 seconds.

### 13.2 Module level

A module-level statement is the docstring, an import, a `type` alias, an assignment (plain, annotated or augmented) of a constant expression to names, an `assert` of one, a `def` (undecorated, except `draw`), or a class (undecorated or `@dataclass(...)`). `if`, `for`, `while`, `with` and `try` fail.

A constant expression uses literals, displays, comprehensions and lambdas, names bound earlier and their attributes, any operator, and calls of pure builtins, `math` and `cmath`, numpy's array constructors and element-wise trigonometry, `walldye`'s color and vector functions, the design's own `Params` subclasses, functions defined earlier in the module, and string methods. The `CONST_*` sets in `walldye/tools/lint.py` have the exact lists. So `TILT = math.radians(6)` and `SPOKES = np.array([...])` pass, while `P()`, anything on `s`, and shapely, scipy or skimage calls belong in `draw`.

### 13.3 Formatting

Ruff, configured in pyproject.toml: line length 100 and import sorting. All Python passes `uv run ruff format --check .` and `uv run ruff check .`, including every ` ```python ` block in Markdown that parses; fix findings rather than adding a blanket `noqa`.

### 13.4 Typing

Pyrefly, with `scipy-stubs`, `types-shapely` and `types-pyyaml`, checks two levels:
- The library, `walldye/` including `tools/`, at the strictest preset, `all`, except `unused-call-result`, because fluent `Path` calls are statements by design. `uv run pyrefly check` must report 0 errors. The only sanctioned suppressions are `s.data`'s `Any` and Vec's three `bad-override`s, and `test_typing.py` counts them.
- Designs at the standard level, through `wallpapers/pyrefly.toml`.

The prek hook and CI run ruff and both Pyrefly levels; `walldye check` runs none of them.

Pyrefly 1.3.1 wrongly reports `bad-argument-count` when a call star-unpacks a value of unknown length and then passes more positional arguments, as in `f(None, *p, 2.0)` with `p: list[float]`. Return points as `tuple[float, float]` or `Vec`, or index explicitly.
