# walldye API v2

The reference for the Python design API, the helper modules, and the tool contracts that change with them. Decided 2026-09-28 in the design interview behind [design.md](design.md), which records the why and links here for signatures. There is no compatibility layer: every v1 name a design could import that this file does not list is gone (see [Removed names](#16-removed-names)). When this file and the code disagree, fix one of them in the same change.

Conventions:
- Python 3.13, PEP 695 generics. `ArrayLike` and `NDArray` are numpy's.
- Numbers: `type Num = float | np.integer | np.floating` (in `_vec.py`, exported). Wherever a signature here writes `float` for a parameter, including `Style`'s numeric keys, the numbers inside `Point`, `Stop` and dash sequences, and every coordinate, length, width, radius, opacity, angle and mix amount, the code writes `Num`, so numpy scalars type-check (`arr.max()`, `s.np_rng(k).integers(...)` and `np.float32` values are not `float` to Pyrefly). Return types, fields, `Params` declarations and `knob`'s arguments stay `float`. Counts and indices (`n`, `nd`, `cols`, `rows`, `levels`) stay `int`. `Point = tuple[Num, Num]`; a `Vec` is one.
- Canvas units are pixels, and the short side is always 1080.
- "Raises X" names the exception and when it happens. Runtime checks back up the static types; both must hold.
- Evidence counts come from the 2026-09-27/28 scans of 219 files (208 nixos designs, 8 skill examples, 3 wallpapers), in the scratch reports the interview used.

## Contents

1. [Implementation split](#1-implementation-split)
2. [Module layout](#2-module-layout)
3. [Design files](#3-design-files)
4. [Colours](#4-colours)
5. [Geometry values](#5-geometry-values)
6. [Paths](#6-paths)
7. [Canvas](#7-canvas)
8. [Params and knob](#8-params-and-knob)
9. [design and Design](#9-design-and-design)
10. [Documents and the render model](#10-documents-and-the-render-model)
11. [Helper modules](#11-helper-modules)
12. [Tool contracts](#12-tool-contracts)
13. [Build layout, hashes and metadata](#13-build-layout-hashes-and-metadata)
14. [CLI](#14-cli)
15. [Lint, typing and formatting](#15-lint-typing-and-formatting)
16. [Removed names](#16-removed-names)
17. [Worked example](#17-worked-example)
18. [Tests](#18-tests)
19. [Departures to confirm](#19-departures-to-confirm)

## 1. Implementation split

Four parts with disjoint files, built in parallel against this document. A part never edits another part's files; where one needs something from another, the interface is spelled out here.

| Part | Owns | Uses from other parts |
|---|---|---|
| A, core | `walldye/__init__.py`, `_colour.py`, `_vec.py`, `_affine.py`, `_path.py`, `_params.py`, `_noise.py`, `_canvas.py`, `_document.py`, `_design.py`, `_aspect.py`; the typing and ruff fixes in `_theme.py` and `_basis.py`, with their behaviour unchanged (Pyrefly `all` reports 11 errors in them today); `tests/python/core/`; the v1 pins `tests/python/fixtures/v1_pins/noise.{py,json}` (§18) | nothing |
| B, helpers | `walldye/geom.py`, `walldye/field.py`, `walldye/pixel.py`, `walldye/font.py`; `tests/python/helpers/`; the v1 pins `tests/python/fixtures/v1_pins/helpers.{py,json}` (§18) | A's public names, plus `walldye._vec.angle`, `walldye._path.ngon_vertices` and `Canvas.pixel_path` with its `origins` (§7.9) |
| C, tools | `walldye/tools/**`, `walldye/__main__.py`, `pyproject.toml`, `uv.lock`, `wallpapers/pyrefly.toml`, `tests/python/tools/`, `tests/python/fixtures/**` except `v1_pins/`, and the fixture formats `regen.py` generates, including `src/lib/__fixtures__/hash-vector.json` (§13.2) | A's `Design`, `RenderSpec`, `Document`, `describe`, `_aspect` and `walldye._colour.token` (§4.1) |
| D, site, docs and content | `src/**` except `src/lib/__fixtures__/`, `scripts/check-artifacts.ts`, `tests/unit/**`, `tests/e2e/**`, `LICENSES/LicenseRef-fan-work.txt`, `.claude/**`, `AGENTS.md`, `README.md`, and the three M1 pieces' `design.py` and `meta.yaml` | the file formats in §13, the CLI in §14, and the fixtures C's `regen.py` writes to `src/lib/__fixtures__/` (D's vitest only reads them) |

D writes the ports of the M1 pieces and the 8 skill examples against this document; they are built in the integration step. Every Python file a part writes, and every parseable ` ```python ` block in the Markdown D writes, passes ruff (§15.2). Nobody edits `wallpapers/*/build/` by hand.

Until the integration step, each part verifies only its own paths, because the other parts' files are half-written: `uv run ruff format --check <owned paths>`, `uv run ruff check <owned paths>`, `uv run pyrefly check <owned .py files>` and its own tests. A Pyrefly error that comes from another part's unfinished module is left for the integration step. Ruff was green on the whole repo before the parts started.

### Integration step

Owned by the orchestrator, run once A to D have landed. It writes only generated files, and they are committed with API v2:
1. `uv run walldye build --all`: the M1 pieces' `build/**`, `wallpapers/index.json` and `wallpapers/.render-lib.sha256`.
2. `uv run python tests/python/fixtures/regen.py`: `src/lib/__fixtures__/**` and `tests/fixtures/**` with its manifest.
3. `uv run walldye build --verify`, `uv run pytest`, `pnpm test` and `pnpm check-artifacts`.
4. Repo-wide `uv run ruff format --check .`, `uv run ruff check .` and `uv run pyrefly check`.

## 2. Module layout

Designs import only these four modules. Each defines `__all__` with exactly the names below (Pyrefly's `implicit-reexport` rule relies on it).

### `walldye` (core)

| Group | Names |
|---|---|
| Declaring a design | `design`, `Canvas`, `Params`, `knob` |
| Colour | `Colour`, `MaskColour`, the 20 tokens (§4.2), `MASK_WHITE`, `MASK_BLACK`, `mix`, `ramp`, `ladder`, `Ladder`, `by_regime` |
| Paint and style types | `Paint`, `MaskPaint`, `Ref`, `Style`, `Stop`, `MaskStop`, `LineCap`, `LineJoin`, `FillRule` |
| Types for annotating helpers | `Buckets`, `ClipSurface`, `MaskSurface`, `PatternSurface`; `type Rng = random.Random` and `type NpRng = np.random.Generator`, the types of `s.rng(k)` and `s.np_rng(k)`, since designs may not name `random` or `numpy.random` (§15.1) |
| Geometry | `P`, `Path`, `Vec`, `Rect`, `Point`, `Num`, `polar`, `lerp`, `clamp`, `smoothstep` |

### `walldye.geom`

`Affine`, `Polyline`, `spline_points`, `bezier_points`, `ribbon`, `hatch`, `ngon`, `scatter`, `poisson_disk`, `parts`. See §11.1.

### `walldye.field`

`Noise`, `noise_grid`, `cells`, `falloff`, `gauss`, `iso_lines`, `runs`, `sample_field`. See §11.2.

### `walldye.pixel`

`Pixels`, `grid_runs`, `dither`, `bayer`, `blue_noise`, `threshold_matrix`, `sprite`, `glyph`, `glyphs`, `text_width`, `Font`, `DitherMethod`. See §11.3.

### Private modules

All of `walldye/` except `tools/` feeds the render-lib hash.

| Module | Holds |
|---|---|
| `_colour.py` | `Colour`, `MaskColour`, tokens, `mix`, `ramp`, `ladder`, `by_regime`, `resolve`, `token` |
| `_vec.py` | `Num`, `Vec`, `Rect`, `Point`, `polar`, `lerp`, `clamp`, `smoothstep`, `angle` |
| `_affine.py` | `Affine` (re-exported by `walldye.geom`) |
| `_path.py` | `Path`, `P`, `Flag`, `fmt`, `ngon_vertices` |
| `_params.py` | `Params`, `knob`, `KnobInfo`, `describe` |
| `_noise.py` | `Noise` (re-exported by `walldye.field`) |
| `_canvas.py` | `Canvas`, `ClipSurface`, `MaskSurface`, `PatternSurface`, `Buckets`, `Ref`, `Style`, `Rng`, `NpRng` and the paint aliases |
| `_document.py` | `Document` and the serialiser |
| `_design.py` | `design`, `Design`, `RenderSpec` |
| `_aspect.py` | `Aspect`, `SHORT`, `SITE_ASPECTS`, `TEMPLATE_NAME`, `canvas_size`, `supports`, `native_aspects`, `aspect_label`, `template_name`, `parse_template_name` (moved out of `__init__.py`) |
| `_theme.py`, `_basis.py` | behaviour unchanged, typed for Pyrefly `all`: the theme model (hex `mix`, `derive_theme`, `is_light`, `parse_theme`...) and the fit themes |
| `font.py` | Spleen glyph tables (BSD-2-Clause header kept) |

### `walldye.tools`

The CLI and its Python API (§12). Designs never import it, and it is outside the render-lib hash. Its public Python entry points are listed in §12.

## 3. Design files

A design is `wallpapers/<slug>/design.py`, optionally with `wallpapers/<slug>/data/`. The tools import it once per process and draw it many times.

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

Rules (the lint in §15.1 enforces them):
- The module docstring is one theme-neutral line (design.md, Copy rules).
- Imports: the standard-library modules on the allowlist (§15.1), `walldye`, `walldye.geom`, `walldye.field`, `walldye.pixel`, numpy, scipy, shapely and skimage. No relative imports; the design's folder is not on `sys.path`.
- Module level holds constants, pure helper functions and classes, one or more `Params` subclasses, the variants mapping, and exactly one `@design(...)`-decorated function named `draw`. A constant may be any expression over literals, earlier constants and a fixed list of pure calls (`math.radians(6)`, `np.array([...])`, `mix(UI, BG, 0.5)`, `X0 + BAYS * BAY`); §15.1 defines the rule exactly. Nothing render-dependent exists at import time, so module constants cannot depend on the canvas, the theme or the variant.
- Module-level objects are never mutated while drawing. The same module object draws every (variant, aspect, regime), so a list appended to during `draw` leaks into the next render; the in-process determinism check catches what the lint misses.
- Everything render-dependent arrives through `s`: size and layout, regime, params, random streams and data files.
- A render depends only on the design file, its data files, the params, the aspect and the regime. The theme is applied afterwards, when the document is serialised (§10).
- `print()` output goes to stderr.

## 4. Colours

Colours are symbolic. A `Colour` holds a formula over theme tokens, never a hex value, so geometry cannot depend on colour values: grouping, keying or comparing colours gives the same answer under every theme. Hex values exist only when a document is serialised under a theme (§10.3).

### 4.1 `Colour` and `MaskColour`

```python
@final
class Colour:        # a theme colour: a token, a mix of theme colours, or a per-regime choice
    def __eq__(self, other: object) -> bool      # formula equality; NotImplemented for non-Colours
    def __hash__(self) -> int                     # from the formula; stable across processes
    def __lt__(self, other: object) -> bool      # and __le__, __gt__, __ge__: raise TypeError
    def __str__(self) -> str                      # raises TypeError
    def __format__(self, spec: str) -> str        # raises TypeError
    def __repr__(self) -> str                     # the formula: "mix(UI, BG_ALT, 0.5)"

@final
class MaskColour:    # a mask colour: MASK_WHITE, MASK_BLACK, or a mix of the two
    # same methods and semantics as Colour
```

- There is no public constructor. Colours come from the tokens, `mix`, `ramp`, `ladder` and `by_regime`; mask colours from `MASK_WHITE`, `MASK_BLACK`, `mix` and `ramp`. The lint bans calling `Colour(` or `MaskColour(` in designs.
- For the tools, `walldye._colour.token(name: str) -> Colour` returns the token colour for any of the 21 names in `_theme.TOKENS`, `orange_dark` included, and raises `ValueError` for any other name. C uses it to turn palette.yaml entries into colours (§12.4).
- Formula representation (internal, fixed because the hash depends on it): a token is `(0, i)` with `i` its index in `_theme.TOKENS`; a mask constant is `(1, level)` with level 0 or 255; a mix is `(2, a, b, t)`; a regime choice is `(3, dark, light)`. `__hash__` is `hash` of that tuple. It contains only ints, floats and nested colours, never strings, so it does not change with `PYTHONHASHSEED` and a `set` of colours iterates in the same order in every process.
- `__eq__` compares formulas: `mix(a, b, 0.5) == mix(a, b, 0.5)` is true and `mix(a, b, 0.5) == mix(b, a, 0.5)` is false, even though both resolve to the same hex.
- `str()`, `format()` and f-strings raise `TypeError("a Colour has no text form; pass it to a drawing call (got mix(UI, BG_ALT, 0.5))")`. Ordering raises `TypeError("colours have no order; key by index or role")`, so `sorted()` over colours fails loudly.
- The two classes never mix: every function that takes both raises `TypeError` when given one of each, and the static overloads reject it too.

### 4.2 Tokens

`Final[Colour]` module constants in `walldye`, visible to the type checker. `beyond` is `#000000` in the dark regime and `#FFFFFF` in the light one. In the light regime the four fractions marked * are multiplied by 1.6, capped at 0.5. The `fireproof` preset pins every token by hand, well off these fractions, so never assume a token equals its formula.

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

`MASK_WHITE: Final[MaskColour]` resolves to `#FFFFFF` (shows) and `MASK_BLACK: Final[MaskColour]` to `#000000` (hides), under every theme. The `orange_dark` token stays in `_theme` for the site but has no design constant (0 uses).

### 4.3 Building colours

```python
@overload
def mix(a: Colour, b: Colour, t: float) -> Colour: ...
@overload
def mix(a: MaskColour, b: MaskColour, t: float) -> MaskColour: ...
```

- `t` is any real number (numpy scalars included) and is stored as `float(t)`. A `bool` raises `TypeError`; a value outside [0, 1], or NaN, raises `ValueError("mix t must be within [0, 1], got 1.7")`.
- Canonical forms, applied in this order: `t == 0` returns `a`, `t == 1` returns `b`, and `a == b` returns `a`. Each resolves to the same hex as the uncanonicalised mix under every theme, so `mix(UI, BG, 0) == UI` is true.
- Mixing a `Colour` with a `MaskColour`, or passing a str, raises `TypeError`.

```python
@overload
def ramp(a: Colour, b: Colour, n: int) -> list[Colour]: ...
@overload
def ramp(a: MaskColour, b: MaskColour, n: int) -> list[MaskColour]: ...
```

`n` colours evenly spaced from `a` to `b`, both included: `[mix(a, b, i / (n - 1)) for i in range(n)]`, or `[a]` when `n == 1`. `ValueError` when `n < 1`. Evidence: 9 designs.

```python
def ladder(stops: Sequence[Colour], n: int) -> Ladder: ...


@final
class Ladder(tuple[Colour, ...]):
    @overload
    def rung(self, v: float) -> int: ...
    @overload
    def rung(self, v: NDArray[np.float64]) -> NDArray[np.int64]: ...
    def at(self, v: float) -> Colour: ...
```

- `ladder(stops, n)` is `n` rungs spaced evenly along the piecewise-linear path through `stops`. With `k = len(stops)`, rung `i` sits at `u = i / (n - 1) * (k - 1)`; with `j = min(k - 2, floor(u))` it is `mix(stops[j], stops[j + 1], u - j)`. Rung 0 is `stops[0]` and rung `n - 1` is `stops[-1]`. `ValueError` unless `k >= 2` and `n >= 2`.
- `ladder((lo, ACCENT_4, hi), n)` equals the removed `accent_ramp(n, lo, hi)` formula for formula.
- `rung(v)` quantises `v`, clamped to [0, 1], into `n` equal bins: `min(n - 1, int(v * n))`, element-wise for arrays. NaN raises `ValueError`, in an array too. `at(v)` is `self[self.rung(v)]`. The quantiser is not called `index`, because that would override `tuple.index` with another meaning (Pyrefly reports `bad-override`) and turn `TONES.index(UI)` into a quantisation.
- A `Ladder` is a tuple: index it, slice it, iterate it, pass it to `s.buckets`.
- Evidence: 130 of the 186 `mix()` calls are grey to grey; 35 designs define TONES lists; 8 hand-roll the `min(len(T) - 1, int(v * len(T)))` quantiser that `rung` replaces; `accent_ramp` is used in 17 designs; the tone-index cluster spans 20 designs.

```python
def by_regime(dark: Colour, light: Colour) -> Colour: ...
```

A colour that resolves to `dark` in the dark regime and to `light` in the light one. It replaces `X if is_light() else Y` for colours (light ladder step 2) and keeps one template for both regimes. `by_regime(a, a)` returns `a`. Mask colours raise `TypeError`.

### 4.4 Resolution

Internal to the serialiser (`walldye._colour.resolve`), and specified because pytest pins it:

```python
def resolve(c: Colour | MaskColour, tokens: Mapping[str, str]) -> str   # "#RRGGBB"
```

- `tokens` is the 21-token dict `_theme.theme_tokens(seeds)` or `_theme.parse_theme(spec)` returns.
- A token resolves to `tokens[name]`; a mask constant to `#FFFFFF` or `#000000`; `mix(a, b, t)` to `_theme.mix(resolve(a), resolve(b), t)`, which rounds each channel half to even and clamps, once per mix, exactly as before; `by_regime(d, l)` to `resolve(l)` when `_theme.is_light(tokens["bg"], tokens["fg"])`, else `resolve(d)`.
- Results are memoised per serialisation, keyed by colour.

### 4.5 Paint, Ref and stops

```python
type Paint = Colour | Literal["none"] | Ref
type MaskPaint = MaskColour | Literal["none"] | Ref
type Stop = tuple[float, Colour] | tuple[float, Colour, float]          # offset, colour[, opacity]
type MaskStop = tuple[float, MaskColour] | tuple[float, MaskColour, float]

@final
@dataclass(frozen=True, slots=True)
class Ref:
    id: str                                                   # "lg1", "cp3", ...
    kind: Literal["paint", "mask_paint", "clip", "mask"]
    def __str__(self) -> str                                  # "url(#lg1)"
```

- Refs come only from gradients, patterns, clips and masks (§7.7, §7.8); the lint bans `Ref(` in designs.
- Where each kind is accepted: a paint position on `Canvas` or `PatternSurface` takes `Colour`, `"none"` or a `"paint"` Ref; on `MaskSurface` it takes `MaskColour`, `"none"` or a `"mask_paint"` Ref; `clip_path=` takes a `"clip"` Ref; `mask=` takes a `"mask"` Ref.
- Runtime checks in every paint position: any other `str` (a hex, a colour name) raises `TypeError("raw colour strings are not paints; use a token or mix()")`; the wrong colour class or Ref kind raises `TypeError`.

## 5. Geometry values

```python
type Num = float | np.integer | np.floating
type Point = tuple[Num, Num]

class Vec(NamedTuple):
    x: float
    y: float
    __array_priority__ = 1000.0                  # numpy defers to Vec's operators
    def __add__(self, o: Point) -> Vec          # also __radd__, __sub__, __rsub__
    def __mul__(self, k: Num) -> Vec            # also __rmul__, __truediv__; and __neg__
    def __abs__(self) -> float                   # length
    def dot(self, o: Point) -> float
    def perp(self) -> Vec                        # (-y, x): a quarter turn clockwise on screen
    def unit(self) -> Vec                        # ValueError for the zero vector
    @overload
    def rotate(self, *, deg: Num, about: Point = (0.0, 0.0)) -> Vec: ...
    @overload
    def rotate(self, *, rad: Num, about: Point = (0.0, 0.0)) -> Vec: ...
```

- `Num` is the parameter type for numbers throughout (Conventions). It has no `Any` in it, so it passes Pyrefly `all`, and it rejects arrays and complex numbers statically; `bool` still passes the checker, and the runtime checks reject it.
- `Vec` unpacks like a tuple (`x, y = v`, `*v`) and is accepted wherever a `Point` is. Plain tuples are accepted everywhere; `(N, 2)` arrays wherever a signature says `ArrayLike`.
- Operators, so that runtime results match what Pyrefly infers:
  - With a `Point` (`+`, `-`) or a number (`*`, `/`; numpy scalars included, `bool` excluded) the result is a `Vec`, component-wise or scaled. Operands go through `float()`, so a Vec holds Python floats.
  - With an ndarray on either side of `+`, `-`, `*` or `/` the result is the ndarray of the same operation on `np.asarray(self)`, in the same operand order: `s.center + offsets` with offsets of shape `(N, 2)` is an `(N, 2)` array, as Pyrefly infers. `__rtruediv__` exists only for this; a number divided by a Vec is a `TypeError`.
  - Anything else returns `NotImplemented`, so Python raises its own `TypeError` (`unsupported operand type(s) for +: 'Vec' and 'int'`); a pair of numbers holding NaN or infinity raises `ValueError`.
  - `__array_priority__` makes numpy arrays and scalars hand their operators to Vec's reflected ones, so `np.float64(2) * vec`, `np.int64(2) * vec` and `t * (b - a)` with `t` from `np.linspace` are Vecs at runtime too (without it numpy returns an ndarray and `.x` fails). The cost: an ndarray on the left of an operator Vec does not define (`**`, `@`, comparisons) raises `TypeError` where Pyrefly infers an ndarray; write `np.asarray(vec)` there. Ufuncs such as `np.cos(vec)` still treat a Vec as a sequence.
  - `tuple + Vec` works at runtime through `__radd__`, but type checkers read it as tuple concatenation, so write `vec + tuple`.
- `__add__`, `__mul__` and `__rmul__` override `tuple`'s; they carry `@override` and `# pyrefly: ignore[bad-override]`, which with `s.data`'s `Any` are the only sanctioned ignores in the library (§15.3).
- Evidence: the vector-math cluster spans 17 designs; `polar` has 133 calls in 22 designs.

```python
class Rect(NamedTuple):
    x: float
    y: float
    w: float
    h: float
    @property
    def x1(self) -> float                        # x + w; also y1
    @property
    def center(self) -> Vec
    def frac(self, fx: float, fy: float) -> Vec  # (x + fx * w, y + fy * h)
    def contains(self, p: Point, margin: float = 0.0) -> bool   # inclusive, grown by margin
```

`P().rect(*r)` draws it. 11 designs test on-canvas visibility by hand; `s.inset(-m).contains(p)` covers them.

### Angles

Every API that takes an angle takes it as exactly one keyword naming the unit:
- `deg=` or `rad=`: 0 points east (+x) and angles grow clockwise on screen, as in SVG (y points down).
- `bearing=`: degrees, 0 points north (up) and bearings grow clockwise, as on a compass. `bearing=b` equals `deg=b - 90`.

Ranges take a pair under the same keyword: `deg=(a0, a1)`. Passing none, or more than one, raises `TypeError`; each API has one overload per unit, so the checker catches it too. The one exception is the x-axis rotation of `Path.A`: SVG degrees, positional, as in the path command it writes (§6). Evidence: 156 `math.radians` calls in 74 files, and three angle conventions in use.

`walldye._vec.angle(deg, rad, bearing) -> float` turns the keyword triple into screen radians for the library's own use, raising the `TypeError` above.

```python
@overload
def polar(c: Point, r: float, *, deg: float) -> Vec: ...
@overload
def polar(c: Point, r: float, *, rad: float) -> Vec: ...
@overload
def polar(c: Point, r: float, *, bearing: float) -> Vec: ...
```

The point at distance `r` from `c` in the given direction: `(cx + r cos a, cy + r sin a)` in screen radians.

### Ufunc-safe maths

Each has a scalar overload (`float` in, `float` out, bit-identical to the old scalar functions) and an array overload (`ArrayLike` in, `NDArray[np.float64]` out, element-wise, the same arithmetic). Evidence: 14 designs reimplement `smoothstep` in numpy because the old one called a scalar `clamp`.

| Function | Scalar definition |
|---|---|
| `lerp(a, b, t)` | `a + (b - a) * t` |
| `clamp(v, lo=0.0, hi=1.0)` | `lo if v < lo else min(v, hi)`; arrays use `np.clip` |
| `smoothstep(e0, e1, x)` | `t = clamp((x - e0) / (e1 - e0))`, then `t * t * (3 - 2 * t)`; works with `e0 > e1`; `ValueError` when `e0 == e1` |

## 6. Paths

```python
class Path:
    def __init__(self, nd: int = 1) -> None      # nd: decimals for coordinates, 0 to 4
    def __str__(self) -> str                      # the d attribute
    @property
    def empty(self) -> bool

def P(nd: int = 1) -> Path: ...
```

A fluent builder for SVG path data. Every method appends and returns `Self`. One builder holds any number of subpaths, so the usual pattern is one builder per paint and stroke style, drawn once. Evidence: `P` is used in 155 designs; `.M` 741 calls, `.poly` 280, `.A` 196.

Number format: `fmt(v, nd)` writes ints (Python or numpy) as they are, and floats (numpy scalars included) with `nd` decimals, trailing zeros and a trailing point stripped, and `-0` written as `0`. `bool` raises `TypeError`; NaN or infinity raises `ValueError` naming the command. Commands are concatenated without separators, as before.

### Commands

Absolute only. Each point-taking command accepts numbers or `Point`s (one overload each); arguments are positional-only.

| Method | Output |
|---|---|
| `M(x, y)` / `M(p)` | `M{x} {y}` |
| `L(x, y)` / `L(p)` | `L{x} {y}` |
| `H(x)`, `V(y)` | `H{x}`, `V{y}` |
| `C(x1, y1, x2, y2, x, y)` / `C(c1, c2, p)` | `C{x1} {y1} {x2} {y2} {x} {y}` |
| `Q(x1, y1, x, y)` / `Q(c, p)` | `Q{x1} {y1} {x} {y}` |
| `A(rx, ry, rot, large, sweep, x, y)` / `A(rx, ry, rot, large, sweep, p)` | `A{rx} {ry} {rot} {int(large)} {int(sweep)} {x} {y}`; `rot` is in degrees (§5, Angles); `large` and `sweep` are `Flag` (below) |
| `Z()` | `Z` |

`type Flag = bool | np.bool | Literal[0, 1]`. Of the 184 `.A()` calls in the nixos designs, 168 pass literal `0`/`1` and the rest compute a comparison, `int(...)` or `1 - s`; Pyrefly rejects `Literal[0]` for a `bool` parameter, so a `bool`-only type would fail every ported arc. At runtime a flag is a `bool`, an `np.bool`, or an int or numpy integer equal to 0 or 1; another int raises `ValueError` and any other type `TypeError`. `int(cond)` and `1 - s` type as `int`, so the port writes `cond` and `not s` (§16).

### Primitives

Each starts a new subpath with `M` (so any number merge into one element) and returns `Self`. `c` is a centre `Point`; `p(r, a)` below means `c + r (cos a, sin a)` in screen radians.

| Method | Output | Evidence |
|---|---|---|
| `rect(x, y, w, h)` | `M x y H x+w V y+h H x Z`; `ValueError` for negative `w` or `h` | `s.rect` 176 calls in 59 files |
| `rrect(x, y, w, h, r)` | with `q = min(r, w/2, h/2)`: `M x+q y H x+w-q A q q 0 0 1 x+w y+q V y+h-q A q q 0 0 1 x+w-q y+h H x+q A q q 0 0 1 x y+h-q V y+q A q q 0 0 1 x+q y Z`; `q == 0` gives `rect` | 10 designs, 4 signatures |
| `circle(c, r)` | `M cx+r cy A r r 0 1 1 cx-r cy A r r 0 1 1 cx+r cy Z`; nothing for `r == 0`; `ValueError` for `r < 0` | two-arc idiom 55 times in 41 files, plus 17 designs with a helper |
| `ellipse(c, rx, ry)` | as `circle` with `rx ry` | 9 `s.ellipse` calls |
| `ring(c, r0, r1)` | `circle(c, r1)`, then the inner circle with both sweep flags 0, so the default fill rule leaves the hole; `ValueError` unless `0 <= r0 < r1` | 8 `ring` helpers |
| `arc(c, r, *, deg=(a0, a1) \| rad=... \| bearing=...)` | `M p(r, a0) A r r 0 {large} {sweep} p(r, a1)`, with `sweep = a1 > a0` and `large = abs(a1 - a0) > pi`; `ValueError` when `a0 == a1` or `abs(a1 - a0) >= 2 pi` | 8 designs |
| `arc_band(c, r0, r1, *, deg=(a0, a1) \| ...)` | closed annular sector: `M p(r1, a0) A r1 r1 0 {large} {sweep} p(r1, a1) L p(r0, a1) A r0 r0 0 {large} {not sweep} p(r0, a0) Z`, with `large` and `sweep` as for `arc`; when `r0 == 0` a pie wedge, `M c L p(r1, a0) A r1 r1 0 {large} {sweep} p(r1, a1) Z`; `ValueError` unless `0 <= r0 < r1`, and for the spans `arc` rejects | kept from v1 |
| `ngon(c, r, n, *, deg= \| rad= \| bearing=, inner=None)` | `M v0 L v1 ... Z` through `ngon_vertices` (below); `ValueError` for `n < 3` | 7 designs |
| `dots(pts: ArrayLike, r)` | one `circle(p, r)` per point | 12 designs |
| `arrowhead(tip, size, *, deg= \| rad= \| bearing=, width=None)` | a triangle pointing along the angle: with `base = tip - size (cos a, sin a)`, `w = width if width is not None else 0.3 * size` and `n = w (-sin a, cos a)`: `M tip L base+n L base-n Z` | 10 designs with near-identical bodies |
| `poly(pts: ArrayLike, *, closed=False)` | `M p0 L p1 ...`, then `Z` when closed; nothing for 0 points; `ValueError` unless the shape is `(N, 2)` | 280 calls in 93 files |
| `spline(pts: ArrayLike, *, closed=False, tension=1.0)` | the v1 `smooth()`, renamed: a Catmull-Rom curve through the points as cubic Béziers with control offsets `tension / 6`; the first and last segments of an open curve duplicate their end point; fewer than 3 points give `poly` | 33 `.smooth` calls in 17 files |
| `shape(geom)` | any shapely geometry: a Polygon's exterior and each interior ring as closed subpaths, oriented opposite ways (`shapely.geometry.polygon.orient(g, 1.0)`), so holes show under the default fill rule; a LinearRing closed; a LineString open; Multi* and GeometryCollection part by part in order; Points and empties draw nothing. A ring's repeated closing coordinate becomes `Z` | 44 designs convert geometry by hand; 28 of the 31 that read `.exterior` drop holes |

`walldye._path.ngon_vertices(c: Point, r: float, n: int, a: float, inner: float | None) -> NDArray[np.float64]` returns the vertices `P().ngon` and `geom.ngon` share: vertex `k` of `n` at `p(r, a + 2 pi k / n)`; with `inner`, `2n` vertices alternating `r` and `inner`, the inner ones at `a + pi (2k + 1) / n`.

## 7. Canvas

`draw` receives a `Canvas[Pm]`. It is created by `Design.draw` (§9), lives for one draw, and raises `RuntimeError("the canvas is closed")` if used after `draw` returns. The type parameter is covariant (it appears only in the read-only `params` property), so a `Canvas[Radar]` is a `Canvas`, and helpers can take a plain `Canvas`.

```python
class Canvas[Pm: Params = Params]:
    @property
    def w(self) -> int
    @property
    def h(self) -> int
    @property
    def landscape(self) -> bool          # w >= h
    @property
    def light(self) -> bool              # the regime of this draw
    @property
    def params(self) -> Pm
    @property
    def center(self) -> Vec              # (w / 2, h / 2)
```

`s.light` is the only theme fact a design can read, and branching on it is light ladder step 3 (a light template per aspect). There is deliberately no `s.variant` or `s.aspect`: designs branch on params and on `w`, `h` and `landscape`, never on names.

### 7.1 Layout

```python
def frac(self, fx: float, fy: float) -> Vec
def pick(self, *, landscape: Point, portrait: Point, snap: float | None = None) -> Vec
def inset(self, margin: float) -> Rect
```

- `frac(fx, fy)` is `Vec(fx * w, fy * h)`.
- `pick` takes the `landscape` fractions when `s.landscape`, else the `portrait` ones, scales them like `frac`, and with `snap` rounds each coordinate to a multiple of it (`round(x / snap) * snap`, Python's half-to-even `round`), so a pixel grid anchored there has a whole-cell origin. 6 of the 10 aspect-aware files hand-roll this, each with its own constants.
- `inset(margin)` is `Rect(margin, margin, w - 2 * margin, h - 2 * margin)`; a negative margin grows it. `ValueError` when the result has no area.

### 7.2 Random streams

```python
def rng(self, key: int | str) -> random.Random
def np_rng(self, key: int | str) -> np.random.Generator
def noise(self, key: int | str) -> Noise
```

The only randomness a design may use. The lint bans the sources it can see (§15.1): `random`, `numpy.random`, `scipy.stats.qmc`, `Noise()`, and library samplers (`rvs`, `random_noise`, `scipy.sparse.random`, any `random_state=`) unless they are handed `s.np_rng(key)`. The in-process repeat and the `PYTHONHASHSEED` subprocess catch unseeded randomness the lint misses; a library call seeded by a constant through a name it cannot see is left to review. Each call returns a fresh generator in the stream's initial state, so two calls with one key give two identical, independent generators, as two `rng(5)` calls did before.

Derivation, with `seed = s.params.seed`:

| Case | `rng` | `np_rng` | `noise` |
|---|---|---|---|
| `seed is None` and `key` is an int | `random.Random(key)` | `np.random.default_rng(key)` | `Noise(key)` |
| otherwise | `random.Random(name)` | `np.random.default_rng(int.from_bytes(hashlib.sha256(name.encode()).digest()[:16], "big"))` | `Noise(name)` |

- `name = f"{'' if seed is None else seed}:{key!r}"`, so seed 11 with key 5 is `"11:5"`, and key `"coast"` with no seed is `":'coast'"`. `repr` keeps the int 5 and the string `"5"` apart.
- The first row reproduces the v1 generators exactly, so the literal seeds tuned into the 208 designs survive the port. Setting `seed` in a variant moves every stream at once.
- String seeding of `random.Random` and the sha256 are independent of `PYTHONHASHSEED`.
- `key`: a `bool` raises `TypeError`; a negative int raises `ValueError`.
- Evidence: 136 designs are seeded, 223 of their 259 seed arguments are literals, 41 designs run 2 to 7 generators, and 19 mix the four generator families.

### 7.3 Data files

```python
def data(self, name: str) -> Any
```

Reads `wallpapers/<slug>/data/<name>` beside the design's file. `name` must match `[A-Za-z0-9][A-Za-z0-9._-]*\.(json|txt|npy)` in full (a trailing newline fails), else `ValueError`. `.json` returns `json.loads` of the UTF-8 text, `.txt` the text, `.npy` `np.load(path, allow_pickle=False)`. A missing file raises `FileNotFoundError`. Every call reads the file again, so nothing is shared between renders. The result is `Any`, the one unchecked value a design gets, so annotate it where it is read (`coast: list[list[float]] = s.data("coast.json")`); the port requires this. Data files are part of `design_sha` (§13.2). Evidence: 8 designs embed more than 3 kB of data (paradox-province-dither 53 kB, bg3-nautiloid 30 kB, star-chart 15 kB).

### 7.4 Drawing

```python
def fill(self, d: Path, paint: Paint, *, rule: FillRule | None = None,
         opacity: float | None = None) -> None
def stroke(self, d: Path, paint: Paint, width: float, *, cap: LineCap | None = None,
           join: LineJoin | None = None, dash: Sequence[float] | None = None,
           opacity: float | None = None) -> None
def path(self, d: Path, *, fill: Paint, **style: Unpack[Style]) -> None
```

- `fill` emits `<path d fill [fill-rule] [opacity]/>`.
- `stroke` emits `<path d fill="none" stroke stroke-width [stroke-linecap] [stroke-linejoin] [stroke-dasharray] [opacity]/>`. The explicit `fill="none"` replaces SVG's default black fill, which 60 old calls relied on without meaning to.
- `path` is the typed escape hatch for everything else. `fill` is a required keyword; pass `"none"` for an outline.
- An empty path draws nothing and records nothing.
- Evidence: 401 of the 814 nixos `s.path` calls are `fill="none"` plus stroke plus width; `fill="none"` appears 552 times; `stroke_linecap` has 131 uses and `stroke_linejoin` 137.

### 7.5 Style

```python
type LineCap = Literal["butt", "round", "square"]
type LineJoin = Literal["miter", "round", "bevel"]
type FillRule = Literal["nonzero", "evenodd"]


class Style(TypedDict, total=False):
    stroke: Paint
    stroke_width: float
    stroke_linecap: LineCap
    stroke_linejoin: LineJoin
    stroke_dasharray: Sequence[float]
    stroke_dashoffset: float
    stroke_opacity: float
    fill_opacity: float
    fill_rule: FillRule
    opacity: float
    transform: Affine
    clip_path: Ref
    mask: Ref
```

Style has no `fill` key: the methods that allow a fill take it as their own keyword (`path`, `pixel_path`), so `path` can require it. These 13 keys plus `fill` cover every attribute the 219 files pass (the old `rx` becomes `P().rrect`). A shared style is a typed dict: `THIN: Style = {"stroke": UI, "stroke_width": 1.0}`, then `s.path(d, fill="none", **THIN)`.

Runtime validation, applied to every value that becomes an attribute (Style keys, verb arguments and `fill`):

| Value | Rule |
|---|---|
| any key | unknown keys raise `TypeError` (`**kwargs` accept anything at runtime) |
| numbers | int, float and numpy scalars; `bool` raises `TypeError`; NaN, infinity and `""` raise `ValueError` |
| `stroke_width`, `width` | at least 0 |
| `opacity`, `fill_opacity`, `stroke_opacity` | within [0, 1] |
| `stroke_dasharray`, `dash` | a non-empty sequence of finite numbers, each at least 0, not all 0 |
| literals | one of the listed values, else `ValueError` |
| paints and refs | §4.5 |

Attributes are written in one fixed order, whatever order the call used: `fill`, `fill-rule`, `fill-opacity`, `stroke`, `stroke-width`, `stroke-linecap`, `stroke-linejoin`, `stroke-dasharray`, `stroke-dashoffset`, `stroke-opacity`, `opacity`, `transform`, `clip-path`, `mask`. Numbers use `fmt(v, 2)`; `stroke-dasharray` joins its numbers with spaces; `transform` is `matrix(a b c d e f)` with a to d at 6 decimals and e, f at 2; refs are `url(#id)`.

### 7.6 Groups and buckets

```python
def group(self, **style: Unpack[Style]) -> AbstractContextManager[None]
def buckets(self, paints: Sequence[Paint], kind: Literal["fill", "stroke"], /,
            **style: Unpack[Style]) -> AbstractContextManager[Buckets]

@final
class Buckets:
    def __getitem__(self, i: SupportsIndex) -> Path   # IndexError outside range(len(paints))
    def __len__(self) -> int
```

- `with s.group(**style):` wraps what is drawn inside in `<g ...>` and `</g>`. 43 `s.g` calls in 31 files. It takes no `fill`: every element the API emits sets its own fill (`stroke` writes `fill="none"`), so a group fill would never be inherited. Its other keys still matter: children that leave `stroke`, `stroke_width` or `fill_rule` unset inherit them (a stroked group outlines its `s.fill` children), and `opacity`, `transform`, `clip_path` and `mask` apply to the group as a whole.
- `with s.buckets(paints, kind, **style) as b:` gives one `Path` per paint, filled through `b[i]`, and emits one element per non-empty bucket, in index order, at the position where the `with` statement opened. Anything else drawn inside the block therefore lands above the buckets.
- `kind="fill"`: each element is `fill=paints[i]` plus `style`, which may set a shared `stroke`.
- `kind="stroke"`: each element is `fill="none"`, `stroke=paints[i]` plus `style`, which must set `stroke_width` (`ValueError` otherwise) and must not set `stroke` (`TypeError`).
- Buckets are keyed by index, never by colour. Two equal paints in `paints` give two elements. `b[i]` takes numpy integers too (`b[rng.integers(len(TONES))]`).
- After the block closes the paths are emitted, so using the `Buckets` object again raises `RuntimeError("the buckets block is closed")`.
- Evidence: 53 files build parallel builders, 29 build dict or list comprehensions of paths, 14 use `setdefault`, and 38 keyed paths by hex, which is what changed their geometry with the theme.

### 7.7 Clips, masks and patterns

Sub-surfaces are context managers. Each allocates its id on creation, collects its content inside the block, and appends its element to `<defs>` when the block closes. Evidence: 28 raw-markup `clip`/`mask`/`pattern` calls, and 63 `:.1f` f-strings in 19 files that existed only to feed them.

Sequencing:
- While a sub-surface is open, drawing on the canvas, or opening another sub-surface or a canvas group, raises `RuntimeError("close the clip block first")`.
- Canvas gradients may be made while a sub-surface is open; they go to `<defs>` at once, so a pattern can use one made inside its own block.
- A sub-surface may open inside a canvas `group` or `buckets` block: defs are document-global, so its element lands in `<defs>`, not in the group.
- After its block closes, a surface's `ref` stays usable and every other method raises `RuntimeError("the clip block is closed")` (naming the surface).

```python
def clip(self) -> AbstractContextManager[ClipSurface]
def mask(self) -> AbstractContextManager[MaskSurface]
def pattern(self, w: float, h: float, *,
            transform: Affine | None = None) -> AbstractContextManager[PatternSurface]

@final
class ClipSurface:
    ref: Ref                                            # kind "clip"
    def add(self, d: Path, *, rule: FillRule = "nonzero",
            transform: Affine | None = None) -> None

@final
class MaskSurface:
    ref: Ref                                            # kind "mask"
    def fill(self, d: Path, paint: MaskPaint, *, rule: FillRule | None = None,
             opacity: float | None = None) -> None
    def stroke(self, d: Path, paint: MaskPaint, width: float, *, cap: LineCap | None = None,
               join: LineJoin | None = None, dash: Sequence[float] | None = None,
               opacity: float | None = None) -> None
    def group(self, *, opacity: float | None = None,
              transform: Affine | None = None) -> AbstractContextManager[None]
    def linear_gradient(self, stops: Sequence[MaskStop], p0: Point, p1: Point, *,
                        units: Literal["user", "bbox"] = "user") -> Ref   # kind "mask_paint"
    def radial_gradient(self, stops: Sequence[MaskStop], center: Point, r: float, *,
                        focus: Point | None = None,
                        units: Literal["user", "bbox"] = "user") -> Ref

@final
class PatternSurface:
    ref: Ref                                            # kind "paint"
    # fill, stroke, path and group, with the same signatures and rules as Canvas
```

- Clip content is geometry only, so `add` takes no paint.
- Mask content takes only mask colours, so a theme colour in a mask is a type error and a `TypeError`. Greys are `mix(MASK_BLACK, MASK_WHITE, t)`. The site recolours nothing inside masks: mask colours are the constant slots that check allows there (design.md, Recolouring pipeline).
- Pattern content is drawn in pattern-local coordinates (0 to `w`, 0 to `h`) with theme paints.
- Use a ref after its block: `with s.group(clip_path=clip.ref):`, `mask=m.ref`, `s.fill(d, pat.ref)`.

Emitted elements (ids come from one counter per document, starting at 1, with prefixes `lg`, `rg`, `cp`, `m`, `p`):
- `<clipPath id="cp1"><path d="..."[ clip-rule="evenodd"][ transform="..."]/>...</clipPath>`
- `<mask id="m2" maskUnits="userSpaceOnUse" x="0" y="0" width="W" height="H">...</mask>`
- `<pattern id="p3" width="w" height="h" patternUnits="userSpaceOnUse"[ patternTransform="..."]>...</pattern>`, with `w` and `h` at 3 decimals.

### 7.8 Gradients

```python
def linear_gradient(self, stops: Sequence[Stop], p0: Point, p1: Point, *,
                    units: Literal["user", "bbox"] = "user") -> Ref      # kind "paint"
def radial_gradient(self, stops: Sequence[Stop], center: Point, r: float, *,
                    focus: Point | None = None,
                    units: Literal["user", "bbox"] = "user") -> Ref
```

- `units="user"` (the default) writes `gradientUnits="userSpaceOnUse"`, so coordinates are canvas pixels; `"bbox"` omits the attribute (objectBoundingBox, coordinates 0 to 1). 29 of the 35 v1 calls passed userSpaceOnUse; the port gives the other 6 `units="bbox"`.
- At least one stop; offsets within [0, 1] and non-decreasing; stop opacity within [0, 1]. `ValueError` otherwise.
- Output: `<linearGradient id="lg1" x1 y1 x2 y2[ gradientUnits="userSpaceOnUse"]>` and `<radialGradient id="rg2" cx cy r[ fx fy][ gradientUnits=...]>`, coordinates at 3 decimals, each stop `<stop offset="o" stop-color="#..."[ stop-opacity="a"]/>` with offset and opacity at 3 decimals. The element goes to `<defs>` at once.
- A gradient made on the canvas can be used inside a pattern; mask content needs the mask surface's own gradients.

### 7.9 Pixel paths

```python
def pixel_path(self, d: Path, fill: Paint, *, cell: float, origins: Sequence[Point],
               **style: Unpack[Style]) -> None
```

For `walldye.pixel`; designs normally draw pixel work through those helpers. It emits `<path d class="px" fill .../>` and, when `d` is not empty, records `(cell, x, y)` for each of `origins`, in order, in the document's pixel grids; `ValueError` when `origins` is empty. A path can span several grids: a `glyphs` group covers several lines, and with `anchor="middle"` or `"end"` each line has its own x origin, so glyphs passes one origin per line the path holds cells of; `grid_runs`, `sprite` and `Pixels` pass one. The class tells the exporter to add `shape-rendering="crispEdges"` to these paths only; the grids give slots.json its `cells` and feed the whole-origin warning.

## 8. Params and knob

```python
@dataclass_transform(frozen_default=True, kw_only_default=True, field_specifiers=(knob,))
class ParamsMeta(type): ...


class Params(metaclass=ParamsMeta):
    seed: int | None = None
```

A design's parameters are a frozen, typed `Params` subclass. The metaclass turns every subclass, and `Params` itself, into `dataclasses.dataclass(frozen=True, kw_only=True)`. The transform sits on the metaclass so that the inherited `seed` field is visible to the type checker; on a base class it is not (checked with Pyrefly 1.3.1).

```python
class Moon(Params):
    phase: float = knob(default=58, lo=-150, hi=150, unit="deg", doc="sun angle from the viewer")
    method: Literal["bayer", "bluenoise"] = knob(default="bluenoise", doc="dither method")
    cells: int = knob(default=3, choices=(2, 3, 4))
    earthshine: bool = True
```

```python
@overload
def knob(*, default: bool, doc: str = "") -> bool: ...
@overload
def knob(
    *, default: int, lo: int | None = None, hi: int | None = None, doc: str = "", unit: str = ""
) -> int: ...
@overload
def knob(
    *,
    default: float,
    lo: float | None = None,
    hi: float | None = None,
    doc: str = "",
    unit: str = "",
) -> float: ...
@overload
def knob[T: (str, int)](
    *, default: T, choices: Sequence[T], doc: str = "", unit: str = ""
) -> T: ...
@overload
def knob[T](*, default: T, doc: str = "") -> T: ...  # str and Literal fields
```

- Every argument is keyword-only. PEP 681 type checkers recognise a field's default only when it is passed as `default=`; with a positional default, Pyrefly 1.3.1 and pyright 1.1.414 both treat the field as required and flag every `Moon()`.
- At runtime `knob` returns `dataclasses.field(default=default, metadata={"walldye": Knob(lo, hi, choices, doc, unit)})`. A field without `knob` is a plain default with no range, choices or doc.
- `lo` and `hi` are soft: they bound `sheet --wedge`, and `--set` warns outside them. Variants may go outside them; check warns. `choices`, and the members of a `Literal` annotation, are hard: any other value raises `ValueError` when the params are built.
- `unit` is display only (`walldye params`); nothing converts it.

Class creation (the metaclass) raises `TypeError` when:
- a field has no default (the default variant is `Moon()`);
- an annotation is anything but `int`, `float`, `bool`, `str` or `Literal[...]` of str or int values (colour params are not allowed; a `Literal` field chosen in `draw` covers role choices);
- a name starts with `_`, or a subclass redeclares `seed`;
- `lo` or `hi` is given for a non-numeric field, or `choices` together with `lo` or `hi`.

It raises `ValueError` when `lo > hi`, the default is outside `[lo, hi]`, or `choices` does not include the default.

Instances (`__post_init__`, and so also `dataclasses.replace`):
- `bool` fields take only `bool`. `int` fields take int or a numpy integer, not `bool`. `float` fields take int, float or a numpy number (not `bool`), must be finite, and are stored as `float`, so `Moon(phase=90) == Moon(phase=90.0)`. `str` fields take `str`. `seed` takes `None` or an int of at least 0. Anything else raises `TypeError`.
- Hard choices raise `ValueError`.
- Instances are hashable and compare by value.

For the tools:

```python
@final
@dataclass(frozen=True, slots=True)
class KnobInfo:
    name: str
    kind: Literal["int", "float", "bool", "str", "seed"]
    default: int | float | bool | str | None
    lo: float | None
    hi: float | None
    choices: tuple[int | str, ...] | None     # from choices= or a Literal annotation
    doc: str
    unit: str

def describe(params_type: type[Params]) -> tuple[KnobInfo, ...]   # declaration order, seed last
```

## 9. design and Design

```python
def design[Pm: Params](
    *,
    aspects: Literal["any"] | tuple[Aspect, ...] = ("16:9",),
    variants: Mapping[str, Pm] | None = None,
    bg: Colour = BG,
) -> Callable[[Callable[[Canvas[Pm]], None]], Design[Pm]]: ...
```

Decorates the one function `draw(s: Canvas[Pm]) -> None` and replaces it with a `Design`. The type checker ties `variants` to the params type in `draw`'s annotation: passing another class's instances is an error.

- `aspects`: `"any"` (every aspect in `SITE_ASPECTS`) or a non-empty tuple of them; a design composing only for 16:9 omits it. `type Aspect = Literal["16:9", "16:10", "21:9", "32:9", "9:19.5", "10:16"]` (in `_aspect.py`, which types `SITE_ASPECTS` as `tuple[Aspect, ...]`), so the checker rejects a bare `"16:9"`, a list and a typo such as `("16:10 ",)`. At runtime any other string raises `ValueError`, a non-tuple `TypeError`, and an empty tuple or one holding anything but site aspects `ValueError`. 16:9 is always native: the site, the OG image and nixos need it.
- `variants`: at most 4 named variants, so at most 5 versions with the default; more raise `ValueError("at most 4 named variants (5 versions with the default), got 5")`. Each is an instance of exactly the draw's params type. Names match `[a-z0-9]+(-[a-z0-9]+)*` in full (`fullmatch`, so `"late\n"` fails), are at most 24 characters and are not `default`. A variant equal to `Pm()` or to another variant raises `ValueError`. The default variant is implicit and unnamed in code; tools call it `default`.
- `bg`: the colour of the full-canvas rectangle drawn before `draw` runs. A `by_regime` colour is fine. A mask colour or a str raises `TypeError`. It replaces v1's module-level `BG`.
- The params type comes from `draw`'s annotation, `Canvas[X]` giving `X`, read with `typing.get_type_hints`. A bare `Canvas`, or no annotation, gives `Params`; with `variants` given, a missing annotation raises `TypeError("annotate draw(s: Canvas[YourParams])")`, and a bare `Canvas` with variants of a subclass raises `TypeError("variant 'late' is an instance of Radar; annotate draw(s: Canvas[Radar])")` (Pyrefly accepts that decorator, since `Canvas` is covariant, and complains only where `draw` reads a field). `draw` must take exactly one positional parameter.
- Labels, descriptions and draft flags for variants live in meta.yaml (§13.4), never in code.

```python
@final
class Design[Pm: Params]:
    fn: Callable[[Canvas[Pm]], None]
    params_type: type[Pm]
    declared_aspects: Literal["any"] | tuple[Aspect, ...]
    aspects: tuple[Aspect, ...]          # native: SITE_ASPECTS order, always including "16:9"
    variants: Mapping[str, Pm]           # named only, declaration order, read-only
    bg: Colour
    source: pathlib.Path                 # design.py, from fn.__code__.co_filename
    def variant_names(self) -> tuple[str, ...]              # ("default", *variants)
    def params(self, variant: str = "default") -> Pm        # KeyError for unknown names
    def draw(self, spec: RenderSpec) -> Document
```

## 10. Documents and the render model

### 10.1 RenderSpec and drawing

```python
@final
@dataclass(frozen=True, slots=True)
class RenderSpec:
    variant: str  # "default" or a named variant; a label for keys
    params: Params  # the values drawn (a variant's, or with --set overrides)
    aspect: str  # anything _aspect.canvas_size accepts
    regime: Literal["dark", "light"]
```

`Design.draw(spec)` creates a `Canvas` of `canvas_size(spec.aspect)` with `light = spec.regime == "light"` and `params = spec.params`, starts a document with the `bg` rectangle, calls `fn`, closes the canvas and returns the `Document`. It raises `TypeError` if `type(spec.params) is not params_type`; whatever the design raises propagates. Drawing an aspect the design does not declare is allowed (preview warns).

### 10.2 Document

```python
@final
class Document:
    def __init__(self, parts: Sequence[str], colours: Sequence[Colour | MaskColour], *,
                 w: int, h: int, regime: Literal["dark", "light"],
                 pixel_grids: Sequence[tuple[float, float, float]] = ()) -> None
    w: int
    h: int
    regime: Literal["dark", "light"]
    pixel_grids: tuple[tuple[float, float, float], ...]   # (cell, x, y) in draw order
    def colours(self) -> tuple[Colour | MaskColour, ...]  # one per slot, in text order
    def skeleton(self) -> str
    def hexes(self, tokens: Mapping[str, str]) -> list[str]
    def to_svg(self, tokens: Mapping[str, str]) -> str
```

- A document is its serialised text cut at every colour: `parts` has one more entry than `colours`, and `to_svg` is `parts[0] + hex(colours[0]) + parts[1] + ...`. `ValueError` if the lengths do not fit. The serialiser builds documents this way, and C builds legacy documents directly from `source.svg` (§12.4).
- `to_svg(tokens)` resolves each colour under the 21-token dict (§4.4) and returns the SVG text. It raises `ValueError` when the tokens belong to the other regime than the document; build never serialises a dark document under light seeds.
- `hexes(tokens)` is the list of resolved `#RRGGBB` values. Invariant, tested: it equals `[c for _, _, c in tokenize.find_colours(doc.to_svg(tokens))]`, so the fit can skip re-tokenising.
- `skeleton()` is `"#".join(parts)`, and equals `tokenize.skeleton(doc.to_svg(t))` for every theme `t`.
- The output is already normalised (uppercase `#RRGGBB`), so `tokenize.normalise(svg) == svg`.
- Exact slot coefficients from the formulas are possible but deferred; the least-squares fit stays.

### 10.3 SVG format

```
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 W H" width="W" height="H">
<defs>...every def element, in the order it was appended, on one line...</defs>
<rect x="0" y="0" width="W" height="H" fill="#1C1B1A"/>
<path d="M960 540..." fill="none" stroke="#343331" stroke-width="1.5"/>
<g opacity="0.5">
<path d="..." fill="#CF6A4C"/>
</g>
</svg>
```

One element per line, a trailing newline, no XML declaration. `<defs>` appears only when something was defined. Gradients are appended when made, and clips, masks and patterns when their block closes. The only elements are `svg`, `defs`, `rect` (the background), `path`, `g`, `clipPath`, `mask`, `pattern`, `linearGradient`, `radialGradient` and `stop`. Colours appear only in `fill`, `stroke` and `stop-color`, which the slot tokenizer reads.

### 10.4 The render model

A design is drawn once per (variant, aspect, regime), and each document is serialised under every theme that needs it: the template theme, the 8 basis themes, the 2 probes and the held-out set of that regime. `walldye check` of a two-regime piece therefore draws 6 times per aspect and variant (a draw, an in-process repeat and a subprocess repeat per regime) instead of v1's 52 fresh module runs, and serialises 48 times (27 dark, 21 light).

- The light regime shares the dark template when `light_doc.skeleton() == dark_doc.skeleton()`. That holds for tokens and `by_regime` (light ladder steps 1 and 2); a geometry branch on `s.light` (step 3) gives a `.light.svg` per aspect.
- Geometry can no longer vary with the theme, because nothing in `draw` can read a colour value. Probe themes keep testing the fit and the constant-slot rule; the skeleton comparison stays as a cheap assertion.
- `walldye check --paranoid` also imports design.py afresh and redraws for every serialisation, requiring byte-equal output. It is for library changes and occasional `--all` sweeps, and costs what v1's check did.
- A disk memo for heavy pure work is deferred until timings after this change show it is needed (reaction-diffusion and brain-coral are the candidates).

## 11. Helper modules

Only clusters that about 7 or more designs re-implement, each with its own tests (the port adopts them; the corpus does not exercise them before that). 3D and drafting kits beyond `arrowhead` are deferred. Randomness always comes in as a generator from `s.rng`, `s.np_rng` or `s.noise`; no helper takes an integer seed.

### 11.1 `walldye.geom`

| Name | Signature and semantics | Evidence |
|---|---|---|
| `Affine` | see below | 15 designs rotate points by hand, about 20 define coordinate mappers, 17 files write transform strings |
| `Polyline` | see below | arc-length cluster 11 designs; `cumsum(hypot(diff))` 9; `np.interp` along a path 15 |
| `spline_points(pts: ArrayLike, n: int, *, closed: bool = False) -> NDArray` | points on the curve `P().spline(tension=1.0)` draws (uniform Catmull-Rom, the same end handling): `n` samples per segment at `t = k / n`, `k = 0 .. n-1`, plus the last point of an open curve; fewer than 3 points come back unchanged; `ValueError` for `n < 1` | 9 designs (plus 4 CubicSpline) |
| `bezier_points(ctrl: ArrayLike, n: int) -> NDArray` | `n + 1` points at `t = linspace(0, 1, n + 1)` on the quadratic (3 control points) or cubic (4) Bézier; `ValueError` otherwise | 8 designs |
| `ribbon(pts: ArrayLike, width: float \| ArrayLike) -> NDArray` | the closed outline of a stroke of varying width along `pts`: the vertices offset by `+width/2` along the normals `Polyline.offset` uses, in order, then the vertices offset by `-width/2`, in reverse, `(2N, 2)`; `width` is a scalar or one value per vertex. Draw with `P().poly(out, closed=True)` | about 9 designs |
| `hatch(region: BaseGeometry, pitch: float, *, deg= \| rad= \| bearing=, offset: float = 0.0) -> list[NDArray]` | parallel lines in the given direction, `pitch` apart measured across them, through the centre of `region.bounds` shifted by `offset + k * pitch` for every `k` that reaches the region, clipped to it; each piece a `(2, 2)` segment, ordered by `k`, then along the line | 7 designs |
| `ngon(c: Point, r: float, n: int, *, deg= \| rad= \| bearing=, inner: float \| None = None) -> NDArray` | `ngon_vertices` (§6) with the angle resolved | 7 designs |
| `scatter(n: int, rect: Rect, rng: random.Random, *, min_dist: float = 0.0, accept: Callable[[Vec], bool] \| None = None, tries: int = 30) -> NDArray` | dart throwing: up to `n * tries` candidates `(rng.uniform(x, x1), rng.uniform(y, y1))`, x drawn first, each kept unless `accept` rejects it or a kept point lies within `min_dist`; stops at `n` points, so it may return fewer | 13 files with rejection loops |
| `poisson_disk(rect: Rect, radius: float, rng: random.Random, *, k: int = 30) -> NDArray` | Bridson sampling, the v1 algorithm and draw order unchanged, so `poisson_disk(Rect(x0, y0, w, h), radius, s.rng(n), k=k)` returns v1's points for `poisson_disk(rng(n), w, h, radius, k, x0, y0)` | 12 designs |
| `parts(g: BaseGeometry) -> list[BaseGeometry]` | Multi* and GeometryCollection flattened recursively, empties dropped, order kept | `getattr(g, "geoms", [g])` 41 times in 30 files |

All return `NDArray[np.float64]` of shape `(N, 2)` unless stated.

```python
@final
@dataclass(frozen=True, slots=True)
class Affine:                       # SVG matrix(a b c d e f): x' = a x + c y + e, y' = b x + d y + f
    a: float
    b: float
    c: float
    d: float
    e: float
    f: float
    @classmethod
    def identity(cls) -> Affine
    @classmethod
    def translate(cls, dx: float, dy: float) -> Affine
    @classmethod
    def scale(cls, sx: float, sy: float | None = None, *, about: Point = (0.0, 0.0)) -> Affine
    @classmethod                    # one overload each for deg= and rad=
    def rotate(cls, *, deg: float, about: Point = (0.0, 0.0)) -> Affine
    @classmethod                    # one overload each for deg=, rad= and bearing=
    def frame(cls, origin: Point, *, deg: float, scale: float = 1.0) -> Affine
    def __matmul__(self, other: Affine) -> Affine      # (m @ n)(p) == m(n(p))
    def __call__(self, p: Point) -> Vec
    def apply(self, pts: ArrayLike) -> NDArray[np.float64]
    def inverse(self) -> Affine                         # ValueError when singular
```

`frame` maps local coordinates to the canvas: local +x points in the given direction, local +y a quarter turn clockwise from it, both scaled by `scale`, and local (0, 0) lands on `origin`. An `Affine` is also the type of `transform=` (§7.5). It is implemented in `walldye/_affine.py` (part A) and re-exported here.

```python
@final
class Polyline:
    def __init__(self, pts: ArrayLike, *, closed: bool = False) -> None
    pts: NDArray[np.float64]        # (N, 2), consecutive duplicates removed; ValueError if N < 2
    closed: bool
    @property
    def length(self) -> float
    @overload
    def at(self, d: float) -> Vec: ...
    @overload
    def at(self, d: NDArray[np.float64]) -> NDArray[np.float64]: ...
    def tangent(self, d: float) -> Vec
    def resample(self, step: float) -> Polyline
    def offset(self, dist: float) -> Polyline
```

- `at(d)` is the point at arc length `d`, clamped to `[0, length]`; on a closed line `d` wraps. `tangent(d)` is the unit direction of the segment there (the outgoing one at a vertex).
- `resample(step)` puts points every `step` along the line from its start, keeping the end point of an open line; `ValueError` unless `step > 0`.
- `offset(dist)` moves each vertex by `dist` along the unit bisector of its two segment normals (an end vertex along its one segment's normal), keeping the point count. The normal of direction `(tx, ty)` is `(-ty, tx)`, so a positive `dist` moves to the right of the direction of travel as seen on screen.

### 11.2 `walldye.field`

| Name | Signature and semantics | Evidence |
|---|---|---|
| `Noise` | see below | 21 files loop over scalar `fbm`, 4 use `np.vectorize`, 6 carry their own value noise |
| `noise_grid(cols: int, rows: int, scale: float, rng: np.random.Generator, *, octaves: int = 1, gain: float = 0.5) -> NDArray` | the v1 numpy fBm Perlin field, `(rows, cols)`, drawing from `rng` in v1's order, so `noise_grid(c, r, s, s_.np_rng(4))` equals v1's `noise_grid(c, r, s, seed=4)`; the v1 lattice fix stays, so the `ng` padding wrappers go | 23 designs; `ng` wrappers in 13 |
| `cells(rect: Rect, cell: float) -> tuple[NDArray, NDArray]` | cell centres covering `rect`: `cols = int(rect.w // cell)`, `rows = int(rect.h // cell)`, `xs[j, i] = rect.x + (i + 0.5) * cell`, `ys[j, i] = rect.y + (j + 0.5) * cell`, both `(rows, cols)`; x first, unlike `np.mgrid` | 35 files use mgrid or meshgrid, 20 compute centres |
| `falloff(d, r: float, power: float = 1.0)` | `clip(1 - d / r, 0, 1) ** power`, ufunc-safe like `clamp` | 7 files |
| `gauss(d, sigma: float)` | `exp(-(d / sigma) ** 2)`, ufunc-safe; the corpus convention, without the usual factor of 2 | 33 files |
| `iso_lines(field: ArrayLike, level: float, *, cell: float = 1.0, origin: Point = (0.0, 0.0), simplify: float = 0.0) -> list[NDArray]` | `skimage.measure.find_contours`, converted from (row, col) to canvas `(x, y) = origin + (col, row) * cell`, then with `simplify > 0` `approximate_polygon(line, simplify)` in canvas units; closed lines repeat their first point at the end. `approximate_polygon` is a Python loop, about 0.7 ms per line per draw: on a 5,000-line field it was 3.7 s of a 4.3 s draw, and check draws each (aspect, regime) three times, so dense fields want a coarser cell or fewer levels rather than `simplify`. Replaces v1's `contours` | 7 designs use find_contours, 3 `contours` |
| `runs(mask: ArrayLike) -> list[tuple[int, int]]` | the half-open `(start, stop)` index ranges of consecutive true values in a 1-D boolean array, in order | 7 designs |
| `sample_field(fn: Callable[[NDArray, NDArray], ArrayLike], cols: int, rows: int) -> NDArray` | one vectorised call `fn(i, j)` with the integer lattice index arrays of shape `(rows + 1, cols + 1)` (column index `i`, row index `j`), returned as float64 of that shape; the corner lattice `iso_lines` expects | 2 designs; kept by decision |

```python
@final
class Noise:
    def __init__(self, seed: int | str) -> None
    @overload
    def __call__(self, x: float, y: float) -> float: ...
    @overload
    def __call__(self, x: ArrayLike, y: ArrayLike) -> NDArray[np.float64]: ...
    # n3(x, y, z) and fbm(x, y, octaves=4, lacunarity=2.0, gain=0.5): the same two overloads
```

- v1's seeded 2D and 3D Perlin noise, roughly within [-1, 1]. The permutation is `list(range(256))` shuffled by `random.Random(seed)` and doubled, exactly as in v1.
- Scalar inputs (Python or numpy scalars) return a float identical to v1. Array inputs broadcast and return float64 arrays computed with the same operations in the same order, so each element equals the scalar result exactly (tested).
- Implemented in `walldye/_noise.py` (part A, because `s.noise` returns it) and re-exported here. Designs get it only from `s.noise(key)`.

### 11.3 `walldye.pixel`

```python
type Font = Literal["5x8", "8x16"]
type DitherMethod = Literal[
    "bayer",
    "clustered",
    "bluenoise",
    "lines",
    "random",
    "fs",
    "atkinson",
    "jarvis",
    "stucki",
    "burkes",
    "sierra",
    "sierra-lite",
    "riemersma",
]
```

| Name | Signature and semantics | Evidence |
|---|---|---|
| `grid_runs(s: Canvas, grid: ArrayLike, palette: Sequence[Paint \| None], cell: float, origin: Point = (0.0, 0.0), *, skip: int \| None = 0, **style: Unpack[Style]) -> None` | an index grid `(rows, cols)` as merged horizontal runs, one `s.pixel_path` per palette index in ascending order; cells equal to `skip`, and indices whose palette entry is `None`, are not drawn; `skip=None` draws index 0 too; indices outside the palette raise `IndexError`. Takes ndarrays directly | 51 designs; 34 `.tolist()` calls |
| `Pixels` | see below | pixel-stamping cluster 21 designs; 16 `[None, ...]` palettes; 9 stamp helpers; 6 line helpers |
| `dither(field: ArrayLike, levels: int, *, method: DitherMethod = "bayer", matrix: int = 4, rng: np.random.Generator \| None = None, serpentine: bool = False) -> NDArray[np.int64]` | v1's `dither`, taking a `(rows, cols)` array of values (clamped to [0, 1]) instead of a callback, returning indices `0 .. levels-1` of the same shape. Ordered methods are vectorised with v1's per-cell arithmetic; error diffusion and riemersma keep v1's loops. `"bluenoise"` and `"random"` need `rng` (`ValueError` without it) | 31 designs; 27 lambda adapters; 20 `np.array(dither(...))` wraps |
| `bayer(n: int) -> NDArray` | the `(n, n)` Bayer threshold matrix, values `(v + 0.5) / n**2`; `n` a power of two of at least 2 | 5 designs |
| `blue_noise(n: int, rng: np.random.Generator, *, sigma: float = 1.5) -> NDArray` | v1's void-and-cluster mask, drawing from `rng` exactly as v1 drew from `default_rng(seed)`. Cached by `(n, sigma, rng.bit_generator.state on entry)`; a cache hit also sets the generator to the state an uncached call would leave, so later draws do not depend on the cache | 2 designs |
| `threshold_matrix(method: Literal["bayer", "clustered", "bluenoise", "lines", "random"], size: int = 4, rng: np.random.Generator \| None = None) -> NDArray` | v1's ordered masks; `"random"` is now `rng.random((k, k))` with `k = max(size, 64)` (a v1 `random.Random` stream before, so its output changes) | 3 designs |
| `sprite(s: Canvas, art: str \| Sequence[str], palette: Mapping[str, Paint], cell: float, origin: Point = (0.0, 0.0), **style: Unpack[Style]) -> None` | v1's `sprite`: one character per pixel, a multi-line string stripped of leading and trailing newlines, or a list of rows; characters missing from `palette` are transparent; drawn through `grid_runs` with the palette keys in sorted order | 7 designs |
| `glyph(ch: str, font: Font = "8x16") -> NDArray[np.bool_]` | the character's bitmap, `(fh, fw)`; unknown characters are blank | 1 design |
| `glyphs(...)` | see below | 37 designs, 78 calls |
| `text_width(text: str, *, font: Font = "8x16", px: float = 2, gap: int = 0) -> float` | the drawn width of one line: `(len(text) * (fw + gap) - gap) * px`, 0 for an empty string | 17 designs measure text by hand |

```python
@final
class Pixels:
    def __init__(self, cols: int, rows: int, palette: Sequence[Paint | None]) -> None
    cols: int
    rows: int
    palette: tuple[Paint | None, ...]
    grid: NDArray[np.int64]              # (rows, cols), all 0 at first; assign to it with numpy
    def stamp(self, art: str | Sequence[str], x: int, y: int, key: Mapping[str, int], *,
              flip: bool = False) -> None
    def line(self, x0: int, y0: int, x1: int, y1: int, index: int) -> None
    def dither(self, field: ArrayLike, levels: Sequence[int], *, method: DitherMethod = "bayer",
               matrix: int = 4, rng: np.random.Generator | None = None,
               where: ArrayLike | None = None) -> None
    def draw(self, s: Canvas, cell: float, origin: Point = (0.0, 0.0), *, skip: int | None = 0,
             **style: Unpack[Style]) -> None
```

- Palette index 0 is the background by convention and is skipped by `draw` unless `skip` says otherwise.
- `stamp` writes `key[ch]` for every character of `art` found in `key` (others are transparent), with the art's top-left at column `x`, row `y`, mirrored left to right when `flip`, clipped to the grid.
- `line` sets the cells of a Bresenham line, both ends included, clipped to the grid.
- `dither` quantises `field` (`(rows, cols)`, clamped to [0, 1]) into `len(levels)` levels with `walldye.pixel.dither` and writes `levels[q]` into the grid, only where the boolean `where` is true when given.
- `draw` is `grid_runs(s, self.grid, self.palette, cell, origin, skip=skip, **style)`.

```python
def glyphs(
    s: Canvas,
    lines: str | Sequence[str],  # a str is split on "\n"
    paint: Paint | Callable[[int, int, str], Paint | None],
    *,
    at: Point,
    font: Font = "8x16",
    px: float = 2,
    gap: int = 0,
    anchor: Literal["start", "middle", "end"] = "start",
    flip: bool = False,
    key: Callable[[int, int, str], Hashable] | None = None,
    **style: Unpack[Style],
) -> None: ...
```

- Bitmap text as crisp pixel paths from the bundled Spleen fonts: each font pixel is `px` by `px`, a character cell `(fw + gap) * px` wide and `(fh + gap) * px` tall. Spaces are never drawn.
- `paint` is one paint, or `paint(col, row, ch)` per cell, where `None` skips the cell.
- `anchor` places each line on its own: `"start"` puts its left edge at `at[0]`, `"middle"` centres it there and `"end"` puts its right edge there, using `text_width`. Line `r` starts at `at[1] + r * (fh + gap) * px`.
- `flip` mirrors each character's bitmap left to right; the character order is unchanged.
- Cells group into one path per paint (formula equality, so grouping no longer changes with the theme), or per `key(col, row, ch)` when given. Every cell in one group must get the same paint (`ValueError` otherwise). Paths come out in first-seen group order through `s.pixel_path`, whose `origins` are the origins of the lines that have cells in that path, in line order.

## 12. Tool contracts

Part C implements these in `walldye/tools/`; the batch workflow and tests call some of them directly, so the names are stable.

### 12.1 Loading and rendering

```python
# walldye/tools/common.py
def load(slug: str) -> Design[Params] | LegacyPiece
def render(slug: str, theme: str | Mapping[str, str], aspect: str = "16:9",
           variant: str = "default", overrides: Sequence[str] = ()) -> str
```

- `load` imports `wallpapers/<slug>/design.py` once per process as module `_walldye_<slug with - replaced by _>`, registered in `sys.modules` for as long as the process lives, and returns its module attribute `draw`. `ValueError("design.py must define @design(...) def draw(s: Canvas[...]) -> None")` when that is not a `Design`. Import errors propagate. stdout is redirected to stderr while the module runs and while it draws.
- `render` parses the theme, derives the regime from its seeds, builds the spec (`overrides` are `--set` items, §14.2), draws, and serialises. Tools cache documents by spec within a process.
- `rasterise`, `crop_svg`, `viewbox`, `ink_map`, `focus` and `check.near_clones(slugs)` keep their v1 signatures (the batch workflow calls `rasterise` and `near_clones`).

### 12.2 Keys and the determinism subprocess

- Every cache, file and subprocess key comes from `(slug, variant, aspect, regime)`: `f"{slug}@{variant}@{aspect}@{regime}"`.
- `python -m walldye _hashes <wallpapers dir> <key>...` prints a JSON object mapping each key to the sha256 of `draw(spec).to_svg(tokens of BASIS[regime][0])`, made in that process. Check runs it once per (piece, variant) task with `PYTHONHASHSEED=4242`.

### 12.3 Process pool

`check`, `build` and `build --verify` run their tasks in a `concurrent.futures.ProcessPoolExecutor` with the `forkserver` context and `--jobs` workers (default `os.cpu_count()`; `--jobs 1`, or a single task, runs in-process). A task is one (slug, variant), so the versions of a single piece check in parallel too. Workers return plain data (templates, slots entries, cells, probes, a 64 by 36 ink map of the 16:9 dark template, errors, warnings, seconds) and never write files. The parent runs the static steps first (ruff and Pyrefly once over every target design file), then gathers results, runs the variant-sibling comparison, prints reports in slug order and does all writing.

### 12.4 Legacy pieces

`LegacyPiece` (source.svg plus palette.yaml) has the same `draw(spec) -> Document` and only the default variant at 16:9. It builds `Document(parts, colours, ...)` by cutting `source.svg` at `tokenize.find_colours` and mapping each slot's colour through palette.yaml (a token name, or `[token, token, t]` for `mix`), turning names into colours with `walldye._colour.token` (§4.1). A colour palette.yaml does not map is an error naming it (v1 left it in place, where check then failed it as hardcoded).

## 13. Build layout, hashes and metadata

### 13.1 Layout

```
wallpapers/<slug>/
  design.py
  data/                       # optional; flat; .json, .txt and .npy files only
  meta.yaml
  build/                      # only `walldye build` writes here
    16x9.svg                  # default variant, unchanged from v1
    16x9.light.svg            # when light geometry differs
    <aspect>[.light].svg      # the other native aspects
    slots.json                # default variant
    <variant>/                # one directory per named variant
      <aspect>[.light].svg
      slots.json
```

- Every variant is built for every native aspect and every regime of the piece (a rectangular matrix).
- Build removes template files it did not write and `build/<name>/` directories whose name is not a declared variant, and touches nothing else. A `build --variant` run removes nothing outside that variant.
- nixos keeps reading `build/16x9.svg`, the default variant.

### 13.2 Hashes

- A hash is sha256 over `<key>\t<value>` lines, sorted, each ending in a newline; unchanged from v1.
- `design_lines(slug)` are v1's lines (design.py, or source.svg and palette.yaml, and `themes\t<sorted regimes>`) plus `wallpapers/<slug>/data/<name>\t<sha256>` for every file in `data/`.
- `design_sha(slug, variant)` is the digest of `design_lines(slug)`, plus the line `variant\t<name>` for a named variant. The default variant's `design_sha` has no variant line, so v1's definition is its special case. Variant values live in design.py, which the design line already covers.
- The render-lib hash is unchanged in definition and picks up the new files under `walldye/` by itself.
- `src/lib/__fixtures__/hash-vector.json` (C's `regen.py` generates it; C's pytest and D's vitest read it) becomes `{"definition": ..., "vectors": [...]}`. Each vector is `{name, files, lines, text, sha256}`, where `files` maps repo paths to contents, `lines` are the non-file lines, `text` the exact digested text and `sha256` its digest. The two vectors: `"design"`, the current one unchanged, and `"variant-with-data"`, with `wallpapers/example/design.py` and `wallpapers/example/data/points.json`, and the lines `themes\tdark,light` and `variant\tlate`.

### 13.3 slots.json

Per variant directory, as in v1: `design_sha`, `focus`, `cells`, `probes` and `checked`, then one `"<aspect>/<regime>"` entry per template (`{file, sha256, n, coefs, occ}`, `file` relative to the slots.json's own directory). A named variant's slots.json adds `"variant": "<name>"` right after `design_sha`; the default's has no such key. `probes` hold that variant's renders. `checked` is the walldye version, bumped to `0.2.0` for this API.

### 13.4 meta.yaml `variants`

```yaml
variants:                       # only when design.py declares named variants
  default: {label: Early in the turn}
  late:
    label: Late in the turn     # required
    description: ...            # optional
    draft: true                 # optional, default false
  open-sea: {label: Open water, draft: true}
```

- The keys are exactly `default` plus the names declared in `@design(variants=...)`, in any order; missing or extra keys are errors. A piece without named variants has no `variants:` key.
- `label`: required, one to four plain words, unique within the piece, following the Copy rules (no internal terms: not "variant", "preset" or "seed"). It names the version in the detail page's switcher.
- `description`: optional, named variants only. When that version is shown it replaces the piece's description, as alt text and on the page. The description rules apply.
- `draft`: named variants only; a draft variant is built but hidden from the production site and from nixos. Agents always write `draft: true`; `walldye review` approves each variant.

### 13.5 index.json

```json
"radar-sweep": {
  "aspects": [
    "16:9",
    "16:10",
    "21:9",
    "32:9",
    "9:19.5",
    "10:16"
  ],
  "draft": false,
  "license": "CC0-1.0",
  "title": "Radar sweep",
  "variants": {
    "late": {
      "draft": true,
      "label": "Late in the turn"
    }
  }
}
```

Written with `json.dumps(index, indent=2, ensure_ascii=False)` plus a newline, as in v1. `aspects` now come from the default variant's slots.json entries, in `SITE_ASPECTS` order, so writing the index never imports designs. A piece without `build/slots.json` (after `walldye new`, or a draft not built yet when `review` or `drop` rewrites the index) is left out until it is built; check-artifacts expects exactly the pieces that have one. `variants` lists the named variants in meta.yaml order, each with `draft` and `label`; it is `{}` for a piece without them. The default variant is not listed.

## 14. CLI

### 14.1 Commands

| Command | v2 changes |
|---|---|
| `new <slug>` | writes the v2 template (§14.3) |
| `preview <slug>` | `--variant NAME` (default `default`), `--set k=v` (repeatable); the PNG name gains `--<variant>` for a named variant and `-set-<k>-<v>` per override in key order; prints the regime and whether the light document's skeleton differs from the dark one; runs the AST lint (§15.1) but not ruff or Pyrefly; the palette-distance hint is gone |
| `render <slug>` | `--variant`, `--set`; the default output is `<slug>[--<variant>]-<token>-<aspect>[-crop].svg` |
| `check [<slug>... \| --all]` | `--variant NAME` (default: all variants), `--paranoid`, `--jobs N`, and `--similar`, which is v1's `--set` renamed so it cannot be confused with `--set k=v`; runs ruff and Pyrefly on the design files (§15); warns for each named variant value outside its knob's soft range. The sibling rule compares only pairs with a fresh side, ink maps measured from each template's own background: with `--variant`, that variant's fresh 16:9 dark template with the committed `16x9.svg` of each other variant, skipping, with a note, those that have none yet, as `--similar` does |
| `build [<slug>... \| --all]` | `--variant NAME` (default: all), `--jobs N`; `--verify` covers every variant's templates; `--set` is refused with `error: --set is for exploring; give the values a named variant in design.py` |
| `params <slug>` | new: prints the params schema and the variants; `--json` for scripts |
| `sheet` | `--variant`, `--set`, `--wedge k=SPEC` (repeatable), `--seeds A..B`, `--aspect` |
| `review` | a strip of variants per card; approving a variant sets its `draft: false` in meta.yaml; review never edits design.py |
| `list` | adds a sixth tab-separated column: the named variants, comma-joined, empty when none |
| `drop`, `themes` | unchanged |

`--variant` accepts `default` or a declared name; anything else exits 2 listing the names.

### 14.2 `--set`, `params`, `--wedge` and `--seeds`

- `--set k=v` sets one field of the variant's params. `k` must be a field of the params class (else exit 2). `v` is parsed by the field's kind from `describe`: `int` by `int()`, `float` by `float()`, `bool` from `true`/`false`/`1`/`0`, `str` as given, `seed` as an int or `none`. The params are rebuilt with `dataclasses.replace`, so type errors and hard-choice violations exit 2 with the message. A numeric value outside the soft range prints `warning: sweep=400 is outside 0..360`.
- `walldye params <slug>` prints the class name, then one line per field (name, kind, default, `lo..hi` or the choices, unit, doc), then one line per named variant with the fields that differ from the default and its meta.yaml label (marked `(draft)` when so). `--json` prints `{"slug", "class", "knobs": [KnobInfo as an object...], "variants": {name: {field: value}}}` with only the fields that differ.
- `sheet <slug> --wedge k=SPEC --seeds A..B` renders one slug afresh (not from build/) for every combination and writes a labelled grid, `--theme` and `--aspect` applying to all cells. `SPEC` is `a..b..step` (numeric, inclusive of `b` when it lands on a step within 1e-9, ints when all three are ints) or `v1,v2,...` (any kind). `--seeds A..B` sets `seed` to each int from A to B inclusive. Wedges vary in flag order, the first slowest, and seeds fastest. More than 64 cells exits 2. Values outside a soft range warn. Without `--wedge`, `--seeds` or `--set`, `sheet` works as in v1 on committed templates, and `--variant` picks `build/<variant>/`, skipping pieces that lack it.

### 14.3 The `walldye new` template

```python
"""TODO: one theme-neutral line, concept + technique."""

from walldye import ACCENT, UI, Canvas, P, design


@design()  # aspects="any" once the composition follows s.w and s.h
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(0.62, 0.5), portrait=(0.5, 0.4))
    s.stroke(P().circle(c, 240), UI, 2)
    s.fill(P().circle(c, 10), ACCENT)
```

It passes ruff and Pyrefly as written.

## 15. Lint, typing and formatting

### 15.1 Design lint (`walldye/tools/lint.py`)

Errors, each naming the line:

| Rule | Detail |
|---|---|
| imports | an allowlist. Standard library: `math`, `cmath`, `itertools`, `functools`, `collections`, `heapq`, `bisect`, `operator`, `dataclasses`, `typing`, `enum`, `fractions`, `statistics`, `string`, `re`, `textwrap`, `json`, `base64`, `zlib` and `copy`, with their submodules. Besides those, `walldye`, `walldye.geom`, `walldye.field`, `walldye.pixel`, `numpy`, `scipy`, `shapely` and `skimage` with their submodules, except `numpy.random`. Everything else fails, `random`, `colorsys` and `decimal` (whose context is process-global) included, as do relative imports, `walldye._*`, `walldye.tools` and `from __future__ import annotations` |
| randomness | any use of `numpy.random` or `scipy.stats.qmc`, annotations included (annotate with `Rng` and `NpRng` from `walldye`); a call whose name, bare or as the last attribute, is `Noise`, `default_rng`, `RandomState` or `SeedSequence`, so `field.Noise(3)` fails; a call named `rvs` or `random_noise`, or of `scipy.sparse.random`, `random_array` or `rand`, and any call passing `random_state=`, unless it passes `random_state=` or `rng=` as a direct `s.np_rng(key)` call. Use `s.rng`, `s.np_rng`, `s.noise` |
| constructors | a call whose name, bare or as the last attribute, is `Colour`, `MaskColour`, `Ref`, `Canvas`, `Document` or `Design`; using these names in annotations is fine |
| process state | calls of the builtins `hash`, `id`, `open`, `exec`, `eval`, `compile`, `globals` and `__import__`, matched as bare names only, so `re.compile(...)` passes; `global` statements |
| entry point | exactly one module-level function named `draw`, decorated with `@design(...)`; no other use of `design` |
| module level | the statement and expression rules below |
| mutation | inside any function, no mutation of a module-level name that the function does not bind itself: calls of `append`, `extend`, `insert`, `pop`, `remove`, `clear`, `update`, `setdefault`, `add`, `discard`, `sort`, `reverse` on it, and assignment, augmented assignment or `del` through a subscript or attribute of it |
| data | `data/` holds only files matching the `s.data` name pattern (the whole name: a trailing newline fails); no subdirectories |
| type escapes | `# type: ignore` and `# pyrefly: ignore` comments, and any use of `typing.cast` or `typing.Any`: designs are type-checked as written |

Warnings: colour words in docstrings and comments (v1's list); a pixel-grid origin that is not a whole unit (from `Document.pixel_grids`); a variant whose check took more than 120 seconds. v1's warnings for `luminance(`, `hex_to_rgb(` and `colorsys` are gone: the first two cannot be imported any more, and `colorsys` is not on the allowlist.

#### Module level

The corpus has 233 module-level constants in 111 designs that are neither literals nor colours (`math.radians(6)` 43 times, `np.array([...])` 18, comprehensions, `X1 = X0 + BAYS * BAY`); this rule lets them stay where they are.

A module-level statement is one of:
- the docstring, an import, or a `type` alias;
- an assignment, annotated assignment or augmented assignment to names (or tuples of names) whose value is a constant expression, or an `assert` of one;
- a `def`, undecorated except `draw` with `@design(...)`;
- a `class`, undecorated or decorated with `@dataclass(...)`.

Anything else fails, including `if`, `for`, `while`, `with` and `try`.

A constant expression uses only:
- literals, f-strings, tuple, list, dict and set displays, comprehensions and lambdas;
- names bound earlier at module level, imported names, the comprehension's own variables, and attributes of these (`math.pi`, `np.pi`);
- operators: arithmetic, bitwise, comparison, boolean, unary, conditional expressions, subscripts and slices;
- calls of:
  - the builtins `abs`, `min`, `max`, `round`, `sum`, `len`, `range`, `tuple`, `list`, `dict`, `set`, `frozenset`, `zip`, `enumerate`, `sorted`, `reversed`, `int`, `float`, `str`, `bool`, `complex`, `divmod`, `pow`, `any` and `all`;
  - any function in `math` or `cmath`;
  - `np.array`, `np.asarray`, `np.arange`, `np.linspace`, `np.zeros`, `np.ones`, `np.full`, `np.radians`, `np.deg2rad`, `np.degrees`, `np.sin`, `np.cos`, `np.tan`, `np.sqrt`, `np.hypot`, `np.arctan2` and `np.linalg.norm`;
  - `mix`, `ramp`, `ladder`, `by_regime`, `Vec`, `Rect`, `polar`, `lerp`, `clamp`, `smoothstep`, and the design's own `Params` subclasses;
  - functions defined earlier in the same module (6 designs build constants with their own pure helpers);
  - methods named `split`, `splitlines`, `strip`, `lstrip`, `rstrip`, `join`, `replace`, `ljust`, `rjust`, `center`, `upper`, `lower`, `format` or `zfill`, on any receiver.

Any other call fails: `P()` and `Path()`, anything on `s` (which does not exist at import), `numpy.random`, and library calls such as shapely, scipy or skimage, which move into `draw`.

These pass:

```python
TILT = math.radians(6)
X1 = X0 + BAYS * BAY
SPOKES = np.array([(math.cos(a), math.sin(a)) for a in np.radians(range(0, 360, 30))])
```

These fail:

```python
RING = P().circle((0, 0), 40)  # P() at module level
HULL = shapely.Polygon(OUTLINE)  # not an allowed call: build it in draw
for k in range(8):  # a module-level loop
    TABLE.append(k * k)
```

### 15.2 Formatting

Ruff, configured in pyproject.toml: line length 100, target py313, `extend-select = ["I"]` for import sorting, `known-first-party = ["walldye"]`, and `TRY004` off for `walldye/tools/**`, which reports a malformed file as `ValueError` whatever the test. All Python passes `uv run ruff format --check .` and `uv run ruff check .`; fix findings, never add blanket `noqa`. `walldye check` runs `ruff format --check` and `ruff check` on each design file (errors block the build), calling the `ruff` next to `sys.executable`, else the one on `PATH` (under `uv run --with`, `sys.executable` is an overlay environment without the dev tools). CI keeps checking formatting with ruff's standalone binary over the whole repo, and ruff formats Markdown too: every ` ```python ` block that parses (in this file, the skill's references, README.md, AGENTS.md) must pass `ruff format --check`; blocks that do not parse, such as signature listings, are skipped. `uv run ruff format .` fixes them.

### 15.3 Typing

Pyrefly is a dev dependency (`uv add --dev pyrefly`, 1.3.1 or later), with stubs for the untyped runtime libraries: `scipy-stubs`, `types-shapely`, `types-pyyaml` (skimage and resvg-py ship their own). CI stays Python-free.

```toml
# pyproject.toml
[tool.pyrefly]
project-includes = ["walldye"]
python-version = "3.13"
preset = "all"

[tool.pyrefly.errors]
# Fluent Path builders and argparse return values that statement calls discard by design.
unused-call-result = false
```

```toml
# wallpapers/pyrefly.toml
python-version = "3.13"
preset = "default"
```

- The library, `walldye/` including `tools/`, is checked at the strictest preset, `all`: every error kind at error severity, including `explicit-any`, `implicit-bool`, `missing-override-decorator`, `implicit-reexport` and `unknown-*`, with one exception, `unused-call-result` (§19). It reports every fluent call used as a statement (`d.M(1, 2)`, `self.M(...)` inside the primitives, `d.circle(...).M(...)`), which is how `_path.py` and B's `grid_runs`, `glyphs` and `Pixels` build paths, and every `parser.add_argument(...)`: 60 of today's errors under `all`, 30 of them in `cli.py`. Designs are unaffected, since `default` does not enable it. `tests/python/tools/test_typing.py` runs `pyrefly check` (project mode) and requires 0 errors. Untyped values (numpy's `mgrid`, `json.loads`) are cast or annotated at the boundary; `s.data()` returns `Any` by design and is the one explicit `Any`, with a targeted ignore. The only other sanctioned ignores are Vec's three `bad-override`s (§5). Context-manager methods are annotated `-> Generator[T]` (typeshed deprecates `Iterator` for `@contextmanager`).
- `test_typing.py` also counts the suppression comments in `walldye/` and requires exactly the sanctioned four, because Pyrefly exits 0 with a bare `# type: ignore`.
- Designs are checked at the standard level, preset `default`. Pyrefly uses the nearest config above a file, so `wallpapers/pyrefly.toml` applies to every design without flags, in editors too. `walldye check` runs `pyrefly check` on the design files (all targets in one run) and any error blocks the build; a design that fails to import still gets its lint, ruff and Pyrefly findings, so one round shows every layer. Each finding prints Pyrefly's full description on one line (for an overload error, the closest overload and the reason, such as `Expected at most 2 positional arguments, got 3`), with walldye's private modules named by the public one (`walldye.polar`, not `walldye._vec.polar`). `test_typing.py` checks the 8 skill examples with `-c wallpapers/pyrefly.toml`, and the planted-mistakes and helper tests use the same file.
- `f(*x, y)`: Pyrefly 1.3.1 reports `bad-argument-count` on a call that star-unpacks a value of unknown length (a `list`, an ndarray, an untyped helper's result) and then passes more positional arguments, although the call is valid; `def f(d, x0, y0, x1, y1, r)` called as `f(None, *p, 2.0)` with `p: list[float]` gives "Expected 6 positional arguments, got 7". A `tuple[float, float]` or `Vec` passes. So type helpers that return points as `tuple[float, float]` or `Vec`, or index explicitly (`f(d, p[0], p[1], r)`); 22 of the 208 nixos designs have such calls, and the codemod marks each with `# TODO(port): star-args`.
- What the types catch, verified on a prototype with Pyrefly 1.3.1: a raw hex where a paint goes, a misspelt style key, a bad line cap, `s.path` without `fill`, a theme colour on a mask surface, a mask colour on the canvas, `mix` of the two, assigning to a params field, an unknown params field, a variant of the wrong params class, a positional angle, and a wrong-typed or out-of-choice `Literal` variant value. Sorting colours still fails only at runtime.

## 16. Removed names

| v1 | v2 |
|---|---|
| `from walldye import W, H`; `U = min(W, H) / 1080` | `s.w`, `s.h`; drop `U` (always 1) |
| `ASPECTS = [...]` | `@design(aspects=...)` |
| module-level `BG = X` | `@design(bg=X)` |
| `def draw(s)` | `@design(...)` `def draw(s: Canvas[P]) -> None` |
| `is_light()` in control flow | `s.light` |
| `X if is_light() else Y` for a colour | `by_regime(Y, X)` (dark first) |
| `THEME[...]`, `GREYS`, `ACCENTS`, `ORANGE_DARK` | tokens; a local tuple where a list is needed |
| `accent_ramp(n, lo=BG, hi=ACCENT)` | `ladder((lo, ACCENT_4, hi), n)` |
| `hex_to_rgb`, `rgb_to_hex`, `luminance`, `palette_distance`, `on_palette` | gone from designs; the tools use `walldye._theme` |
| `rng(k)`, `random.Random(k)` | `s.rng(k)` |
| `np.random.default_rng(k)` | `s.np_rng(k)` |
| `Noise(k)` | `s.noise(k)` |
| `noise_grid(c, r, scale, seed=k, ...)` | `field.noise_grid(c, r, scale, s.np_rng(k), ...)` |
| `s.path(d, fill="none", stroke=X, stroke_width=w, ...)` | `s.stroke(d, X, w, cap=..., join=..., dash=...)` |
| `s.path(d, fill=X)` | `s.fill(d, X)` |
| `s.path(d, stroke=X)` without `fill` | `s.stroke(...)`, or `s.path(d, fill="none", stroke=X, ...)` |
| `s.rect(x, y, w, h, rx=r)` | `s.fill(P().rect(x, y, w, h), ...)`, `P().rrect(x, y, w, h, r)` |
| `s.circle(cx, cy, r)`, `s.ellipse(...)` | `P().circle((cx, cy), r)`, `P().ellipse(...)` |
| `s.line(x1, y1, x2, y2)` | `s.stroke(P().M(x1, y1).L(x2, y2), ...)` |
| `s.polyline(pts)`, `s.polygon(pts)` | `P().poly(pts)`, `P().poly(pts, closed=True)` |
| `s.g(**kw)` | `s.group(**style)` |
| `s.clip(markup)` | `with s.clip() as c: c.add(path)`, then `clip_path=c.ref` |
| `s.mask(markup)` | `with s.mask() as m: m.fill(path, MASK_WHITE)`, then `mask=m.ref` |
| `s.pattern(w, h, markup, transform)` | `with s.pattern(w, h, transform=...) as pat:`, then `pat.ref` |
| `s.linear_gradient(stops, x1, y1, x2, y2, units)` | `s.linear_gradient(stops, p0, p1, units="user" \| "bbox")`, user space by default |
| `s.radial_gradient(stops, cx, cy, r, units)` | `s.radial_gradient(stops, center, r, focus=..., units=...)` |
| `s.text`, `s.raw`, `s.el`, `s.defs`, `s.uid`, `Svg` | gone |
| `P().smooth(...)` | `P().spline(...)` |
| `P().arc_band(cx, cy, r0, r1, a0, a1)` | `P().arc_band((cx, cy), r0, r1, rad=(a0, a1))` when `a0 < a1 < a0 + 2π`; see the notes below |
| `polar(cx, cy, r, a)` | `polar((cx, cy), r, rad=a)` |
| `fmt`, `pts` | gone (internal) |
| `grid_runs(s, grid, colors, cell, ox, oy, skip)` | `pixel.grid_runs(s, grid, palette, cell, (ox, oy), skip=...)` |
| `dither(fn, cols, rows, levels, method, matrix, seed, serpentine)` | `pixel.dither(array, levels, method=..., matrix=..., rng=s.np_rng(seed), serpentine=...)` |
| `bayer`, `blue_noise(n, seed)`, `threshold_matrix(m, size, seed)` | `pixel.bayer`, `pixel.blue_noise(n, rng)`, `pixel.threshold_matrix(m, size, rng)` |
| `glyph`, `glyphs(s, lines, color, font, px, x, y, gap, key)` | `pixel.glyph`, `pixel.glyphs(s, lines, paint, at=(x, y), font=, px=, gap=, key=)` |
| `sprite(s, art, palette, cell, x, y)` | `pixel.sprite(s, art, palette, cell, (x, y))` |
| `SHADES`, `DENSITY`, `BAYER2`, `CLUSTERED8`, `DIFFUSION`, `DIFFUSION_DIV` | gone from the public API |
| `contours(field, level, cell, ox, oy)` | `field.iso_lines(field, level, cell=, origin=)` |
| `sample_field(fn, cols, rows)` (scalar `fn`) | `field.sample_field(fn, cols, rows)` (vectorised `fn`) |
| `poisson_disk(r, w, h, radius, k, x0, y0)` | `geom.poisson_disk(Rect(x0, y0, w, h), radius, s.rng(n), k=k)` |
| `canvas_size`, `SITE_ASPECTS`, `set_canvas`, `set_theme`, `supports`, `native_aspects`, `aspect_label`, `template_name`, `parse_template_name`, `TEMPLATE_NAME`, `pixel_grids`, `reset_pixel_grids` | tools only: `walldye._aspect`; the grids are `Document.pixel_grids` |
| `DEFAULT_THEME`, `PRESETS`, `SEEDS`, `TOKENS`, `derive_theme`, `parse_seeds`, `parse_theme`, `theme_token`, `theme_tokens` | tools only: `walldye._theme` |
| `check --set` | `check --similar` |

Notes for the port, where a row above is more than a rename:
- `arc_band`: v1 always drew clockwise (sweep 1) and took `large` from `(a1 - a0) % 2π`, so `a1 < a0` meant the clockwise sector from `a0` round to `a1`. v2 draws from `a0` towards `a1` (`sweep = a1 > a0`) and rejects spans of 2π or more. For a v1 call with `a1 < a0`, write `rad=(a0, a1 + 2π)`; swapping the ends would draw the other sector. Check the result visually.
- String path data: 14 designs pass a string to `s.path` (`"".join(f"M{x} {y}h2v2h-2z" ...)`, f-strings), often with relative commands. v2 takes only a `Path` of absolute commands, so rebuild these with `P()`: `rect` for the little squares, absolute `H`/`V` for the rest.
- Arc flags (§6): `int(cond)` becomes `cond`, and `1 - s` becomes `not s`; literal `0`/`1` and comparisons stay.
- numpy scalars need no `float()`: every numeric parameter takes `Num` (Conventions).

## 17. Worked example

radar-sweep as ported to v2, with one variant proposed as a draft (`wallpapers/radar-sweep/design.py`).

```python
"""A radar scope mid-rotation: stepped wedges trail the sweep arm as an afterglow over noise-masked arc grains of coastline."""

from walldye import (
    ACCENT,
    ACCENT_4,
    ACCENT_6,
    BG,
    BG_ALT,
    UI,
    Canvas,
    P,
    Params,
    Vec,
    design,
    knob,
    ladder,
    mix,
    polar,
    smoothstep,
)


class Radar(Params):
    sweep: float = knob(default=60, lo=0, hi=360, unit="deg", doc="arm bearing from north")
    glow: float = knob(default=70, lo=20, hi=180, unit="deg", doc="afterglow length")


VARIANTS = {"late": Radar(sweep=210, glow=120)}

R, STEPS = 420, 36  # scope radius; afterglow wedges
LAND = (38, 175)  # coastline bearings
ISLANDS = ((151, 0.66, 26), (160, 0.8, 18), (170, 0.56, 15))  # bearing, range (x R), radius
CONTACTS = ((-11, 0.66), (-27, 0.34), (-44, 0.7))  # bearing behind the arm, range (x R)
DB, DR, MAX_RUN = 0.6, 6, 3  # grain grid: bearing step, ring step, longest grain in steps
# Grain tones by age: ACCENT_4 fading to UI under the afterglow (0-4), then UI to BG_ALT (5-7).
TONES = (*ladder((ACCENT_4, UI), 5), *ladder((UI, BG_ALT), 4)[1:])


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Radar]) -> None:
    p = s.params
    # landscape: right of centre, leaving the left for windows; portrait: low, under the clock
    c = s.pick(landscape=(0.71875, 5 / 9), portrait=(0.5, 0.6))

    def at(r: float, b: float) -> Vec:
        return polar(c, r, bearing=b)

    def tone(b: float) -> int:
        """Index into TONES for a grain at bearing `b`: the afterglow behind the arm, then a
        35-degree fade from UI to BG_ALT, which also runs 45 to 80 degrees ahead of the arm."""
        age = (p.sweep - b) % 360  # degrees since the arm passed
        if age <= p.glow:
            return round(age / p.glow * 4)
        return 4 + round(smoothstep(0, 35, min(age - p.glow, 315 - age)) * 3)

    with s.clip() as scope:
        scope.add(P().circle(c, R))
    with s.group(clip_path=scope.ref):
        for i in range(STEPS):
            end = p.sweep - p.glow * i / STEPS
            # a 0.3 degree overlap hides anti-aliasing seams between wedges
            wedge = P().arc_band(c, 0, R + 2, bearing=(end - p.glow / STEPS - 0.3, end))
            s.fill(wedge, mix(BG, ACCENT_6, (1 - i / STEPS) ** 1.6))

    # Coastline returns: a low-frequency land mask plus a few islands, cut into short arc grains.
    noise, rng = s.noise(5), s.rng(5)
    isles = [(at(R * rr, b), rad) for b, rr, rad in ISLANDS]
    b0, b1 = LAND
    with s.buckets(TONES, "stroke", stroke_width=1.4, stroke_linecap="butt") as grains:

        def emit(rr: float, run: list[float]) -> None:
            grains[tone((run[0] + run[-1]) / 2)].arc(c, rr, bearing=(run[0] - 0.2, run[-1] + 0.2))

        for ring in range(int(R * 0.4 / DR), int(R * 0.93 / DR)):
            rr = ring * DR
            run: list[float] = []
            for k in range(int((b1 - b0) / DB) + 1):
                b = b0 + k * DB
                # scope-relative, so the coast is the same wherever the scope sits
                q = at(rr, b) - c
                edge = smoothstep(b0, b0 + 25, b) * (1 - smoothstep(b1 - 50, b1 - 25, b))
                mass = noise.fbm(q.x / 220 + 6.27, q.y / 220 + 2.73, 4) + 0.7 * (rr / R - 0.55)
                land = edge > 0.3 and mass > 0.17
                wobble = 1 + 0.35 * noise(q.x / 40, q.y / 40)
                isle = any(abs(at(rr, b) - ic) < rad * wobble for ic, rad in isles)
                dense = 0.62 if isle else min(0.6, 0.3 + 2.5 * (mass - 0.17))
                # the sweep line always breaks a run
                hit = (land or isle) and rng.random() < dense and abs(b - p.sweep) > DB / 2
                if hit:
                    run.append(b)
                if run and (not hit or len(run) == MAX_RUN):
                    emit(rr, run)
                    run = []
            if run:
                emit(rr, run)

    rings = P()
    for k in range(1, 5):
        rings.circle(c, R * k / 5)
    s.stroke(rings, BG_ALT, 1.2)
    ticks, major = P(), P()
    for b in range(0, 360, 5):
        long = b % 30 == 0
        (major if long else ticks).M(at(R, b)).L(at(R - (18 if long else 6), b))
    s.stroke(ticks, UI, 1.2)
    s.stroke(major, UI, 1.6)
    s.stroke(P().M(c.x - R, c.y).H(c.x + R).M(c.x, c.y - R).V(c.y + R), UI, 1)
    s.stroke(P().circle(c, R), UI, 2)
    # fresh contacts under the afterglow, and one fading behind the arm
    s.fill(P().dots([at(R * rr, p.sweep + db) for db, rr in CONTACTS], 5), ACCENT)
    s.fill(P().circle(at(R * 0.55, p.sweep + 190), 5), ACCENT_4)
    s.stroke(P().M(c).L(at(R, p.sweep)), ACCENT, 1.6, cap="round")
```

What the example shows:
- `TONES` is a tuple of colour formulas at module level; the grains are bucketed by index, so no colour is ever a key.
- `s.noise(5)` and `s.rng(5)` with no seed are v1's `Noise(5)` and `rng(5)`, so the default coastline is the one the M1 piece was tuned on, and the default version draws what v1 drew.
- `tone` fades returns past the afterglow over 35 degrees, and those just ahead of the arm the same way. The default never shows the first fade (its coast starts 22 degrees behind the arm), `late` does.
- `late` changes what the scope shows, which is what a variant must do: the arm has swung past the coast and most of the coastline sits in the afterglow.
- The variant moves the arm, and it has to. The afterglow wedges and the rings dominate the ink map, so a variant that keeps the arm and changes only the coast (`Radar(seed=11)`, which moves both random streams to `"11:5"`) measures an ink-map cosine of 0.98 against the default, over the 0.93 limit, and check rejects it. `late` measures 0.20 (16:9 dark, as check measures it).

meta.yaml, the relevant lines:

```yaml
title: Radar sweep
description: A radar scope mid-rotation. Its sweep arm trails a stepped afterglow across range rings, a stippled coastline and three contacts.
variants:
  default: {label: Early in the turn}
  late:
    label: Late in the turn
    description: A radar scope later in its turn. The arm has swept past the coastline, leaving most of it under a long afterglow while its far end fades.
    draft: true
```

The commands around it:

```sh
uv run walldye params radar-sweep
uv run walldye preview radar-sweep --variant late --theme nord
uv run walldye preview radar-sweep --set sweep=120 --set seed=3      # exploring only
uv run walldye sheet radar-sweep --wedge sweep=0..360..45 --seeds 0..3
uv run walldye check radar-sweep                                     # every variant
uv run walldye build radar-sweep     # build/16x9.svg ... and build/late/16x9.svg ...
```

On the site: `/radar-sweep?v=late` once review approves it, exported as `radar-sweep--late-nord-2560x1440.png`, and in index.json `"variants": {"late": {"draft": true, "label": "Late in the turn"}}`.

## 18. Tests

Each part lands with its tests; every test file passes ruff and the library passes Pyrefly `all`.

The comparisons with v1 read pinned outputs, never v1 code, because A deletes it. Each part pins what its own tests compare, once, with a script beside the JSON it writes: A `tests/python/fixtures/v1_pins/noise.py` (Noise scalar outputs), B `tests/python/fixtures/v1_pins/helpers.py` (`poisson_disk`, `noise_grid`, `blue_noise`, `dither` and `threshold_matrix`). Each script loads `git show ad9da3d:walldye/__init__.py` as a throwaway module with `__package__ = "walldye"`, so its relative imports resolve to `_theme`, whose behaviour does not change. The JSON is committed; the scripts are kept to show where the pins came from.

- A, core:
  - Colour equality, hashing (the same hash in a subprocess with another `PYTHONHASHSEED`), ordering and `str`/`format` errors, canonical forms, `mix` range and type errors, the `Colour`/`MaskColour` separation.
  - `resolve` equals `_theme.mix` chains for every preset and random themes; `by_regime` picks by regime; `ladder((lo, ACCENT_4, hi), n)` resolves like v1's `accent_ramp` for n = 2..12; `Ladder.rung` for scalars and arrays; `token` for all 21 names and the `ValueError`.
  - `Vec` arithmetic and `__radd__`; with numpy: `vec + arr`, `arr + vec`, `arr - vec` and `arr / vec` are ndarrays, and `np.float64(2) * vec` and `np.int64(2) * vec` are Vecs of Python floats. `Rect`, angle keywords and their `TypeError`, `polar`, ufunc-safe maths (scalar bit-identical to v1, arrays element-wise equal).
  - Path goldens for every command and primitive, `fmt` edge cases (bool, NaN, `np.float32`, `-0`), `A` flags (bool, `np.bool`, 0 and 1 pass; 2 raises `ValueError`, 0.5 `TypeError`), `shape` with holes, Multi* and collections.
  - Params: class-creation errors, instance validation, int to float, `describe`, and a Pyrefly run over a planted-mistakes fixture proving the type errors of §15.3.
  - Canvas: every Style validation error, attribute order, buckets position and ordering, the sub-surface sequencing rules (§7.7) and ids, the closed-buckets and closed-surface errors, gradient output, `pixel_path` recording one grid per origin, the closed-canvas error, `data()` names and types, and the stream table in §7.2 (int keys equal the stdlib and numpy generators; named streams stable across processes).
  - Document: `hexes` equals the tokenizer on `to_svg`, `skeleton` equals `tokenize.skeleton`, the regime mismatch error, and draw-once equivalence: one document serialised under N themes equals N fresh draws, for the 3 M1 pieces and the 8 examples once D has ported them.
  - Noise: scalar outputs equal the pins in `noise.json`; arrays equal scalars element by element.
- B, helpers: each helper in §11 against hand-computed cases; `poisson_disk`, `noise_grid` and `blue_noise` equal the pins in `helpers.json` for the same seeds; `dither` equals the pinned v1 output (made with a callback reading the same field) for every method except `"random"`; `blue_noise`'s cache leaves the generator where an uncached call would; `glyphs` anchoring, flip and grouping, and the origins it records for a multi-line group; `text_width`.
- C, tools: the loader (import once, module name, errors), `--set` parsing and warnings, `params` output, wedge and seed ranges, the variant build layout and stale cleanup, per-variant `design_sha` against the hash vector `regen.py` generates, `index.json` variants and unbuilt pieces left out, `check --variant` against committed siblings, meta.yaml variants rules, every lint rule in §15.1 on fixture designs, the `_hashes` subprocess keys, `--paranoid` catching a design that leaks module state, the process pool giving the same output as `--jobs 1`, `test_typing.py` (§15.3), and the skill examples passing the design lint. The fixture designs in `tests/python/fixtures/designs/` are ported to v2.
- D, site: vitest for the hash vectors (read from C's fixture), meta.yaml variants in the zod schema, the copy lint on variant labels and descriptions, the check-artifacts rules for `build/<variant>/`, and Playwright for `?v=` switching, variant export names and the index's "N versions" caption.

## 19. Departures to confirm

Where this file departs from what the owner decided in the interview. Each stands until the owner confirms or overturns it:
- `knob` takes every argument by keyword (`knob(default=60, lo=0, hi=360)`), not `knob(default, lo, hi, *, ...)`: PEP 681 checkers see a field's default only through `default=` (§8).
- `dataclass_transform` sits on a `Params` metaclass rather than the base class, so the checker sees the inherited `seed` (§8).
- `s.buckets(paints, kind, /, **style)` takes a required `kind`, `"fill"` or `"stroke"`, that the interview's `s.buckets(paints, **style)` did not have (§7.6).
- `check --set`, the near-clone report, is renamed `check --similar`, so it cannot be confused with `--set k=v` (§14.1).
- The library runs at Pyrefly's strictest preset except `unused-call-result`, which is off (§15.3).
- "At most 4 per design" is read as 4 named variants plus the default, 5 versions in all, as the interview synthesis worded it ("named variants ... at most 4 per design"); agents propose at most 3 (§9).
