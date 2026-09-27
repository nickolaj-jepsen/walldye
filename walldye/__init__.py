"""walldye: procedural SVG wallpaper library.

A design is `wallpapers/<slug>/design.py` exposing `draw(s: Svg)`. The tools call
set_theme() and set_canvas() before loading it fresh, so the theme tokens and W/H a design
imports with `from walldye import ...` reflect the requested theme and aspect ratio.

Helpers: theme tokens (BG, UI*, FG*, ACCENT*, ACCENTS, GREYS) + mix/ramp/accent_ramp +
is_light(); Svg element/gradient/clip/mask/pattern builders; P() path builder with
smooth()/arc_band(); Noise (pure-Python Perlin) and noise_grid (numpy fBm);
dither() (ordered/blue-noise/halftone/error-diffusion/Riemersma) + grid_runs() + sprite()
for pixel art; glyph()/glyphs() + SHADES/DENSITY for ASCII/TUI/braille art (Spleen
bitmap font, font.py); contours() marching squares; poisson_disk().
numpy, scipy, shapely and scikit-image are importable from designs.
"""

from __future__ import annotations

import math
import random
import re
from contextlib import contextmanager

from . import _theme
from ._theme import (  # re-exported: designs and tools import these from walldye
    DEFAULT_THEME,
    PRESETS,
    SEEDS,
    TOKENS,
    derive_theme,
    hex_to_rgb,
    luminance,
    mix,
    parse_seeds,
    parse_theme,
    rgb_to_hex,
    theme_token,
    theme_tokens,
)

# --- canvas ------------------------------------------------------------------
# The short side is always 1080 units; the long side follows the aspect ratio, so
# stroke weights read the same on every screen shape.
SHORT = 1080
W, H = 1920, 1080
SITE_ASPECTS = ["16:9", "16:10", "21:9", "32:9", "9:19.5", "10:16"]
TEMPLATE_NAME = re.compile(r"^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(\.light)?\.svg$")


def canvas_size(aspect: str | float = "16:9") -> tuple[int, int]:
    """(W, H) for an aspect like '16:9', '21:9', '9:19.5', '3440x1440' or a float w/h ratio."""
    if isinstance(aspect, str):
        a, b = (float(v) for v in aspect.lower().replace("x", ":").split(":"))
        ratio = a / b
    else:
        ratio = float(aspect)
    return (round(SHORT * ratio), SHORT) if ratio >= 1 else (SHORT, round(SHORT / ratio))


def set_canvas(aspect: str | float = "16:9") -> tuple[int, int]:
    """Set module-level W/H and clear the pixel-grid registry; call before loading a design module."""
    global W, H
    W, H = canvas_size(aspect)
    reset_pixel_grids()
    return W, H


def _ratio(aspect: str) -> float:
    w, h = canvas_size(aspect)
    return w / h


def supports(declared: list[str], aspect: str) -> bool:
    """True if a design declaring ASPECTS=`declared` renders `aspect` natively: "any", or a ratio within 1%."""
    if "any" in declared:
        return True
    want = _ratio(aspect)
    return any(abs(_ratio(a) - want) / want < 0.01 for a in declared)


def native_aspects(declared: list[str]) -> list[str]:
    """The SITE_ASPECTS a design declaring ASPECTS=`declared` renders natively, in SITE_ASPECTS order."""
    return [a for a in SITE_ASPECTS if supports(declared, a)]


def aspect_label(aspect: str) -> str:
    """File label of an aspect: '9:19.5' -> '9x19.5'."""
    a, b = aspect.lower().replace("x", ":").split(":")
    return f"{float(a):g}x{float(b):g}"


def template_name(aspect: str, light: bool = False) -> str:
    """Template file name: '16:9' -> '16x9.svg'; '9:19.5' with `light` -> '9x19.5.light.svg'."""
    return f"{aspect_label(aspect)}{'.light' if light else ''}.svg"


def parse_template_name(name: str) -> tuple[str, bool]:
    """(aspect, light) of a template file name: '9x19.5.light.svg' -> ('9:19.5', True); ValueError if not one."""
    m = TEMPLATE_NAME.match(name)
    if not m:
        raise ValueError(f"not a template name: {name!r}")
    return f"{m.group(1)}:{m.group(2)}", bool(m.group(3))


def ramp(a: str, b: str, n: int) -> list[str]:
    """`n` evenly spaced colors from `a` to `b` inclusive."""
    return [mix(a, b, i / (n - 1)) if n > 1 else a for i in range(n)]


# --- pixel grids ---------------------------------------------------------------

_PIXEL_GRIDS: list[tuple[float, float, float]] = []


def pixel_grids() -> list[tuple[float, float, float]]:
    """(cell, origin x, origin y) of each grid_runs/glyphs/sprite call that drew something since
    the last reset, in draw order. set_theme() and set_canvas() reset it, so after a fresh load
    and draw() it describes exactly that render."""
    return list(_PIXEL_GRIDS)


def reset_pixel_grids() -> None:
    _PIXEL_GRIDS.clear()


# --- theme -------------------------------------------------------------------
# The model lives in _theme; set_theme() binds the current tokens as module globals
# (BG, ACCENT_3, ...) for designs to import by name.

THEME: dict[str, str] = {}
GREYS: list[str] = []
ACCENTS: list[str] = []


def set_theme(spec: str | dict[str, str] | None = None) -> dict[str, str]:
    """Resolve a theme (theme token, or a {bg, fg, accent} seed dict) into the module-level tokens.

    Call before loading a design module: designs bind BG/ACCENT/... at import time. Also
    resets the pixel-grid registry. Raises ValueError for anything parse_seeds or theme_tokens reject.
    """
    global THEME, GREYS, ACCENTS
    THEME = theme_tokens(spec) if isinstance(spec, dict) else parse_theme(spec)
    globals().update({k.upper(): v for k, v in THEME.items()})
    GREYS = [THEME[k] for k in ("black", "bg_deep", "bg", "bg_alt", "ui", "ui_alt", "ui_hi", "muted")]
    # bg-ward → accent: the ramp most designs step through.
    ACCENTS = [THEME[f"accent_{i}"] for i in range(8, 0, -1)] + [THEME["accent"]]
    reset_pixel_grids()
    return THEME


set_theme()


def is_light() -> bool:
    """True when the current theme is in the light regime (bg brighter than fg; ties are dark).

    The one theme test designs may branch on.
    """
    return _theme.is_light(THEME["bg"], THEME["fg"])


def accent_ramp(n: int, lo: str | None = None, hi: str | None = None) -> list[str]:
    """`n` tones from background-ish (`lo`, default BG) to `hi` (default ACCENT) via ACCENT_4."""
    lo, hi = lo or THEME["bg"], hi or THEME["accent"]
    mid = THEME["accent_4"]
    out = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 1.0
        out.append(mix(lo, mid, t / 0.5) if t < 0.5 else mix(mid, hi, (t - 0.5) / 0.5))
    return out


def palette_distance(c: str, anchors: list[str] | None = None) -> float:
    """RGB distance (0..441) from `c` to the convex hull of the theme tokens (or `anchors`).

    Every mix() of theme colours lies inside the hull, so ~0 means the colour re-themes
    cleanly; a large distance means a hardcoded off-theme colour.
    """
    import numpy as np
    from scipy.optimize import nnls

    pts_ = np.array([hex_to_rgb(a) for a in (anchors or list(THEME.values()))], float).T
    target = np.array(hex_to_rgb(c), float)
    k = 1000.0  # heavily weighted sum-to-one row: NNLS then solves hull membership
    wts, _ = nnls(np.vstack([pts_, k * np.ones(pts_.shape[1])]), np.append(target, k))
    return float(np.linalg.norm(pts_ @ wts - target))


def on_palette(c: str, tol: float = 8.0) -> bool:
    """True if `c` is, within `tol` RGB units, a blend of the current theme's tokens."""
    return palette_distance(c) <= tol


# --- numbers & geometry ---------------------------------------------------


def fmt(v: float, nd: int = 1) -> str:
    """Compact number: fixed `nd` decimals with trailing zeros stripped."""
    if isinstance(v, int):
        return str(v)
    s = f"{v:.{nd}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def pts(points, nd: int = 1) -> str:
    return " ".join(f"{fmt(x, nd)},{fmt(y, nd)}" for x, y in points)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def smoothstep(e0: float, e1: float, x: float) -> float:
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def polar(cx: float, cy: float, r: float, a: float) -> tuple[float, float]:
    """Point at radius `r`, angle `a` radians (0 = +x, clockwise on screen)."""
    return cx + r * math.cos(a), cy + r * math.sin(a)


class Path_:
    """Fluent SVG path-data builder; str() gives the `d` attribute."""

    def __init__(self, nd: int = 1):
        self.parts: list[str] = []
        self.nd = nd

    def _f(self, *vs):
        return " ".join(fmt(v, self.nd) for v in vs)

    def M(self, x, y):
        self.parts.append("M" + self._f(x, y))
        return self

    def L(self, x, y):
        self.parts.append("L" + self._f(x, y))
        return self

    def H(self, x):
        self.parts.append("H" + self._f(x))
        return self

    def V(self, y):
        self.parts.append("V" + self._f(y))
        return self

    def C(self, x1, y1, x2, y2, x, y):
        self.parts.append("C" + self._f(x1, y1, x2, y2, x, y))
        return self

    def Q(self, x1, y1, x, y):
        self.parts.append("Q" + self._f(x1, y1, x, y))
        return self

    def A(self, rx, ry, rot, large, sweep, x, y):
        self.parts.append(f"A{self._f(rx, ry, rot)} {int(large)} {int(sweep)} {self._f(x, y)}")
        return self

    def Z(self):
        self.parts.append("Z")
        return self

    def poly(self, points, closed: bool = False):
        for i, (x, y) in enumerate(points):
            (self.M if i == 0 else self.L)(x, y)
        return self.Z() if closed else self

    def smooth(self, points, closed: bool = False, tension: float = 1.0):
        """Catmull-Rom spline through `points`, as cubic Béziers."""
        p = list(points)
        if len(p) < 3:
            return self.poly(p, closed)
        n = len(p)
        self.M(*p[0])
        segs = n if closed else n - 1
        for i in range(segs):
            p0 = p[(i - 1) % n] if (closed or i > 0) else p[0]
            p1, p2 = p[i], p[(i + 1) % n]
            p3 = p[(i + 2) % n] if (closed or i + 2 < n) else p2
            k = tension / 6
            self.C(
                p1[0] + (p2[0] - p0[0]) * k,
                p1[1] + (p2[1] - p0[1]) * k,
                p2[0] - (p3[0] - p1[0]) * k,
                p2[1] - (p3[1] - p1[1]) * k,
                *p2,
            )
        return self.Z() if closed else self

    def arc_band(self, cx, cy, r0, r1, a0, a1):
        """Closed annular sector between radii r0<r1 and angles a0→a1 (radians)."""
        large = 1 if (a1 - a0) % (2 * math.pi) > math.pi else 0
        self.M(*polar(cx, cy, r1, a0)).A(r1, r1, 0, large, 1, *polar(cx, cy, r1, a1))
        self.L(*polar(cx, cy, r0, a1)).A(r0, r0, 0, large, 0, *polar(cx, cy, r0, a0))
        return self.Z()

    def __str__(self):
        return "".join(self.parts)


def P(nd: int = 1) -> Path_:
    return Path_(nd)


# --- SVG document ---------------------------------------------------------


def _attrs(kw: dict) -> str:
    out = []
    for k, v in kw.items():
        if v is None:
            continue
        k = k.rstrip("_").replace("_", "-")
        if k == "href":
            k = "href"
        if isinstance(v, float):
            v = fmt(v, 2)
        out.append(f'{k}="{v}"')
    return (" " + " ".join(out)) if out else ""


class Svg:
    """In-memory SVG canvas (default W×H, filled with the theme BG; bg=None for none).

    Element helpers append and return the markup.
    """

    def __init__(self, bg: str | None = ..., width: int | None = None, height: int | None = None):
        bg = THEME["bg"] if bg is ... else bg
        width, height = width or W, height or H
        self.w, self.h = width, height
        self.body: list[str] = []
        self._defs: list[str] = []
        self._ids = 0
        if bg:
            self.rect(0, 0, width, height, fill=bg)

    def uid(self, prefix: str = "i") -> str:
        self._ids += 1
        return f"{prefix}{self._ids}"

    def raw(self, markup: str) -> str:
        self.body.append(markup)
        return markup

    def el(self, tag: str, _content: str | None = None, **kw) -> str:
        m = f"<{tag}{_attrs(kw)}/>" if _content is None else f"<{tag}{_attrs(kw)}>{_content}</{tag}>"
        return self.raw(m)

    def rect(self, x, y, w, h, **kw):
        return self.el("rect", x=fmt(x), y=fmt(y), width=fmt(w), height=fmt(h), **kw)

    def circle(self, cx, cy, r, **kw):
        return self.el("circle", cx=fmt(cx), cy=fmt(cy), r=fmt(r, 2), **kw)

    def ellipse(self, cx, cy, rx, ry, **kw):
        return self.el("ellipse", cx=fmt(cx), cy=fmt(cy), rx=fmt(rx), ry=fmt(ry), **kw)

    def line(self, x1, y1, x2, y2, **kw):
        return self.el("line", x1=fmt(x1), y1=fmt(y1), x2=fmt(x2), y2=fmt(y2), **kw)

    def path(self, d, **kw):
        return self.el("path", d=str(d), **kw)

    def polyline(self, points, nd: int = 1, **kw):
        kw.setdefault("fill", "none")
        return self.el("polyline", points=pts(points, nd), **kw)

    def polygon(self, points, nd: int = 1, **kw):
        return self.el("polygon", points=pts(points, nd), **kw)

    def text(self, x, y, content: str, **kw):
        return self.el("text", content, x=fmt(x), y=fmt(y), **kw)

    @contextmanager
    def g(self, **kw):
        self.raw(f"<g{_attrs(kw)}>")
        yield self
        self.raw("</g>")

    def defs(self, markup: str) -> None:
        self._defs.append(markup)

    def linear_gradient(self, stops, x1=0, y1=0, x2=0, y2=1, units: str | None = None) -> str:
        """`stops`: [(offset, color[, opacity])]. Returns a `url(#id)` paint."""
        gid = self.uid("lg")
        s = "".join(
            f'<stop offset="{fmt(o, 3)}" stop-color="{c}"' + (f' stop-opacity="{fmt(rest[0], 3)}"' if rest else "") + "/>"
            for o, c, *rest in stops
        )
        u = f' gradientUnits="{units}"' if units else ""
        self.defs(f'<linearGradient id="{gid}" x1="{fmt(x1, 3)}" y1="{fmt(y1, 3)}" x2="{fmt(x2, 3)}" y2="{fmt(y2, 3)}"{u}>{s}</linearGradient>')
        return f"url(#{gid})"

    def radial_gradient(self, stops, cx=0.5, cy=0.5, r=0.5, units: str | None = None) -> str:
        gid = self.uid("rg")
        s = "".join(
            f'<stop offset="{fmt(o, 3)}" stop-color="{c}"' + (f' stop-opacity="{fmt(rest[0], 3)}"' if rest else "") + "/>"
            for o, c, *rest in stops
        )
        u = f' gradientUnits="{units}"' if units else ""
        self.defs(f'<radialGradient id="{gid}" cx="{fmt(cx, 3)}" cy="{fmt(cy, 3)}" r="{fmt(r, 3)}"{u}>{s}</radialGradient>')
        return f"url(#{gid})"

    def clip(self, markup: str) -> str:
        """Define a clipPath from raw shape markup; returns `url(#id)`."""
        cid = self.uid("cp")
        self.defs(f'<clipPath id="{cid}">{markup}</clipPath>')
        return f"url(#{cid})"

    def mask(self, markup: str) -> str:
        """Define a mask (white = visible) from raw markup; returns `url(#id)`."""
        mid = self.uid("m")
        self.defs(f'<mask id="{mid}" maskUnits="userSpaceOnUse" x="0" y="0" width="{self.w}" height="{self.h}">{markup}</mask>')
        return f"url(#{mid})"

    def pattern(self, w, h, markup: str, transform: str | None = None) -> str:
        """Tile `markup` on a w×h userSpace grid; returns `url(#id)`."""
        pid = self.uid("p")
        t = f' patternTransform="{transform}"' if transform else ""
        self.defs(f'<pattern id="{pid}" width="{fmt(w, 3)}" height="{fmt(h, 3)}" patternUnits="userSpaceOnUse"{t}>{markup}</pattern>')
        return f"url(#{pid})"

    def to_string(self) -> str:
        head = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}">'
        defs = ["<defs>" + "".join(self._defs) + "</defs>"] if self._defs else []
        return "\n".join([head, *defs, *self.body, "</svg>"]) + "\n"


# --- noise ----------------------------------------------------------------


class Noise:
    """Seeded 2D/3D Perlin gradient noise, roughly in [-1, 1]."""

    def __init__(self, seed: int = 0):
        r = random.Random(seed)
        p = list(range(256))
        r.shuffle(p)
        self.p = p + p

    @staticmethod
    def _fade(t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    @staticmethod
    def _grad2(h, x, y):
        h &= 7
        u, v = (x, y) if h < 4 else (y, x)
        return (u if h & 1 == 0 else -u) + (2 * v if h & 2 == 0 else -2 * v)

    def __call__(self, x: float, y: float) -> float:
        p = self.p
        xi, yi = math.floor(x), math.floor(y)
        xf, yf = x - xi, y - yi
        xi &= 255
        yi &= 255
        u, v = self._fade(xf), self._fade(yf)
        aa, ab = p[p[xi] + yi], p[p[xi] + yi + 1]
        ba, bb = p[p[xi + 1] + yi], p[p[xi + 1] + yi + 1]
        x1 = lerp(self._grad2(aa, xf, yf), self._grad2(ba, xf - 1, yf), u)
        x2 = lerp(self._grad2(ab, xf, yf - 1), self._grad2(bb, xf - 1, yf - 1), u)
        return lerp(x1, x2, v) * 0.5

    def n3(self, x: float, y: float, z: float) -> float:
        p = self.p
        xi, yi, zi = math.floor(x) & 255, math.floor(y) & 255, math.floor(z) & 255
        xf, yf, zf = x - math.floor(x), y - math.floor(y), z - math.floor(z)
        u, v, w = self._fade(xf), self._fade(yf), self._fade(zf)

        def g(h, x, y, z):
            h &= 15
            a = x if h < 8 else y
            b = y if h < 4 else (x if h in (12, 14) else z)
            return (a if h & 1 == 0 else -a) + (b if h & 2 == 0 else -b)

        A, B = p[xi] + yi, p[xi + 1] + yi
        AA, AB, BA, BB = p[A] + zi, p[A + 1] + zi, p[B] + zi, p[B + 1] + zi
        return lerp(
            lerp(lerp(g(p[AA], xf, yf, zf), g(p[BA], xf - 1, yf, zf), u), lerp(g(p[AB], xf, yf - 1, zf), g(p[BB], xf - 1, yf - 1, zf), u), v),
            lerp(
                lerp(g(p[AA + 1], xf, yf, zf - 1), g(p[BA + 1], xf - 1, yf, zf - 1), u),
                lerp(g(p[AB + 1], xf, yf - 1, zf - 1), g(p[BB + 1], xf - 1, yf - 1, zf - 1), u),
                v,
            ),
            w,
        )

    def fbm(self, x: float, y: float, octaves: int = 4, lacunarity: float = 2.0, gain: float = 0.5) -> float:
        amp, freq, total, norm = 1.0, 1.0, 0.0, 0.0
        for _ in range(octaves):
            total += amp * self(x * freq, y * freq)
            norm += amp
            amp *= gain
            freq *= lacunarity
        return total / norm


def noise_grid(cols: int, rows: int, scale: float, seed: int = 0, octaves: int = 1, gain: float = 0.5):
    """numpy (rows, cols) fBm Perlin field in ~[-1, 1]; `scale` is the base feature size in cells."""
    import numpy as np

    r = np.random.default_rng(seed)
    out = np.zeros((rows, cols))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        s = scale / (2**o)
        gx, gy = int(cols / s) + 2, int(rows / s) + 2
        ang = r.uniform(0, 2 * np.pi, (gy, gx))
        # The random offset can push x0 + 1 one past the lattice; wrap one extra cell.
        vx, vy = np.pad(np.cos(ang), ((0, 1), (0, 1)), mode="wrap"), np.pad(np.sin(ang), ((0, 1), (0, 1)), mode="wrap")
        x = np.arange(cols) / s + r.uniform(0, 1)
        y = np.arange(rows) / s + r.uniform(0, 1)
        X, Y = np.meshgrid(x, y)
        x0, y0 = X.astype(int), Y.astype(int)
        fx, fy = X - x0, Y - y0

        def dot(ix, iy, dx, dy):
            return vx[iy, ix] * dx + vy[iy, ix] * dy

        u = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
        v = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
        n0 = dot(x0, y0, fx, fy) + u * (dot(x0 + 1, y0, fx - 1, fy) - dot(x0, y0, fx, fy))
        n1 = dot(x0, y0 + 1, fx, fy - 1) + u * (dot(x0 + 1, y0 + 1, fx - 1, fy - 1) - dot(x0, y0 + 1, fx, fy - 1))
        out += amp * (n0 + v * (n1 - n0)) * 1.41
        norm += amp
        amp *= gain
    return out / norm


def rng(seed: int = 0) -> random.Random:
    return random.Random(seed)


# --- raster-ish helpers ---------------------------------------------------

BAYER2 = [[0, 2], [3, 1]]


def bayer(n: int) -> list[list[float]]:
    """n×n (power of two) ordered-dither threshold matrix in (0, 1)."""
    m = BAYER2
    while len(m) < n:
        k = len(m)
        m = [[4 * m[y % k][x % k] + BAYER2[y // k][x // k] for x in range(2 * k)] for y in range(2 * k)]
    size = len(m) ** 2
    return [[(v + 0.5) / size for v in row] for row in m]


def grid_runs(s: Svg, grid, colors, cell: float, ox: float = 0, oy: float = 0, skip: int | None = 0, **kw) -> None:
    """Emit a 2D index grid as one merged-run <path class="px"> per color index.

    `grid[row][col]` indexes `colors`; index `skip` (default 0 = background) is not drawn.
    Records (cell, ox, oy) in pixel_grids() when anything is drawn.
    """
    by_color: dict[int, list[str]] = {}
    for j, row in enumerate(grid):
        i = 0
        n = len(row)
        while i < n:
            c = row[i]
            k = i
            while k < n and row[k] == c:
                k += 1
            if c is not None and c != skip:
                x, y, w = ox + i * cell, oy + j * cell, (k - i) * cell
                by_color.setdefault(c, []).append(f"M{fmt(x)} {fmt(y)}h{fmt(w)}v{fmt(cell)}h{fmt(-w)}z")
            i = k
    if by_color:
        _PIXEL_GRIDS.append((cell, ox, oy))
    for c in sorted(by_color):
        s.path("".join(by_color[c]), fill=colors[c], class_="px", **kw)


DIFFUSION = {
    "fs": [(1, 0, 7), (-1, 1, 3), (0, 1, 5), (1, 1, 1)],
    "atkinson": [(1, 0, 1), (2, 0, 1), (-1, 1, 1), (0, 1, 1), (1, 1, 1), (0, 2, 1)],
    "jarvis": [(1, 0, 7), (2, 0, 5), (-2, 1, 3), (-1, 1, 5), (0, 1, 7), (1, 1, 5), (2, 1, 3),
               (-2, 2, 1), (-1, 2, 3), (0, 2, 5), (1, 2, 3), (2, 2, 1)],
    "stucki": [(1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4), (2, 1, 2),
               (-2, 2, 1), (-1, 2, 2), (0, 2, 4), (1, 2, 2), (2, 2, 1)],
    "burkes": [(1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4), (2, 1, 2)],
    "sierra": [(1, 0, 5), (2, 0, 3), (-2, 1, 2), (-1, 1, 4), (0, 1, 5), (1, 1, 4), (2, 1, 2),
               (-1, 2, 2), (0, 2, 3), (1, 2, 2)],
    "sierra-lite": [(1, 0, 2), (-1, 1, 1), (0, 1, 1)],
}
# Divisors per kernel; atkinson deliberately drops 1/4 of the error (its high-contrast look).
DIFFUSION_DIV = {"fs": 16, "atkinson": 8, "jarvis": 48, "stucki": 42, "burkes": 32, "sierra": 32, "sierra-lite": 4}

# 8x8 clustered-dot threshold order (dots grow from the centre, like a print halftone screen).
CLUSTERED8 = [
    [24, 10, 12, 26, 35, 47, 49, 37], [8, 0, 2, 14, 45, 59, 61, 51], [22, 6, 4, 16, 43, 57, 63, 53],
    [30, 20, 18, 28, 33, 41, 55, 39], [34, 46, 48, 36, 25, 11, 13, 27], [44, 58, 60, 50, 9, 1, 3, 15],
    [42, 56, 62, 52, 23, 7, 5, 17], [32, 40, 54, 38, 31, 21, 19, 29],
]


def threshold_matrix(method: str, size: int = 4, seed: int = 0) -> list[list[float]]:
    """Ordered-dither thresholds in (0, 1) for 'bayer' | 'clustered' | 'bluenoise' | 'lines' | 'random'."""
    if method == "bayer":
        return bayer(size)
    if method == "clustered":
        return [[(v + 0.5) / 64 for v in row] for row in CLUSTERED8]
    if method == "bluenoise":
        return [list(r) for r in blue_noise(max(size, 64), seed)]
    if method == "lines":
        return [[(j + 0.5) / size] * size for j in range(size)]
    if method == "random":
        r = random.Random(seed)
        return [[r.random() for _ in range(max(size, 64))] for _ in range(max(size, 64))]
    raise ValueError(method)


_BLUE: dict = {}


def blue_noise(n: int = 64, seed: int = 0, sigma: float = 1.5):
    """n×n void-and-cluster blue-noise threshold mask (tuple of rows, values in (0, 1)); cached."""
    if (n, seed) in _BLUE:
        return _BLUE[(n, seed)]
    import numpy as np

    r = np.random.default_rng(seed)
    d = np.minimum(np.arange(n), n - np.arange(n))
    kern = np.exp(-(d[:, None] ** 2 + d[None, :] ** 2) / (2 * sigma * sigma))

    def energy(b):
        return np.real(np.fft.ifft2(np.fft.fft2(b) * np.fft.fft2(kern)))

    def bump(e, idx, sign):
        y, x = divmod(int(idx), n)
        e += sign * np.roll(np.roll(kern, y, 0), x, 1)

    b = (r.random((n, n)) < 0.1).astype(float)
    e = energy(b)
    while True:
        c = np.argmax(np.where(b > 0, e, -np.inf))
        b.flat[c] = 0
        bump(e, c, -1)
        v = np.argmin(np.where(b > 0, np.inf, e))
        if v == c:
            b.flat[c] = 1
            bump(e, c, 1)
            break
        b.flat[v] = 1
        bump(e, v, 1)
    proto, ones = b.copy(), int(b.sum())
    rank = np.zeros(n * n)
    e = energy(b)
    for k in range(ones - 1, -1, -1):
        c = np.argmax(np.where(b > 0, e, -np.inf))
        b.flat[c] = 0
        bump(e, c, -1)
        rank[c] = k
    b = proto.copy()
    e = energy(b)
    for k in range(ones, n * n):
        v = np.argmin(np.where(b > 0, np.inf, e))
        b.flat[v] = 1
        bump(e, v, 1)
        rank[v] = k
    out = tuple(tuple(float(v) for v in row) for row in ((rank.reshape(n, n) + 0.5) / (n * n)))
    _BLUE[(n, seed)] = out
    return out


def _hilbert(order: int):
    n = 1 << order
    for d in range(n * n):
        x = y = 0
        t, s = d, 1
        while s < n:
            rx = 1 & (t // 2)
            ry = 1 & (t ^ rx)
            if ry == 0:
                if rx == 1:
                    x, y = s - 1 - x, s - 1 - y
                x, y = y, x
            x += s * rx
            y += s * ry
            t //= 4
            s *= 2
        yield x, y


def dither(value, cols: int, rows: int, levels: int, method: str = "bayer", matrix: int = 4, seed: int = 0, serpentine: bool = False) -> list[list[int]]:
    """Quantise `value(col, row) -> [0,1]` to indices 0..levels-1.

    Ordered (threshold mask): 'bayer' (crisp crosshatch, `matrix` = 2/4/8/16), 'clustered'
    (print halftone dots), 'bluenoise' (even organic grain, no pattern), 'lines' (horizontal
    line screen, `matrix` = line pitch in cells), 'random' (white-noise grain).
    Error diffusion: 'fs', 'atkinson' (1-bit Mac, loses 1/4 error → punchy), 'jarvis', 'stucki',
    'burkes', 'sierra', 'sierra-lite'; `serpentine` alternates row direction to break worms.
    'riemersma': error diffusion along a Hilbert curve (soft, curly texture).
    """
    n = levels - 1
    if method in ("bayer", "clustered", "bluenoise", "lines", "random"):
        m = threshold_matrix(method, matrix, seed)
        k = len(m)
        out = []
        for j in range(rows):
            row = []
            for i in range(cols):
                q = clamp(value(i, j)) * n
                b = int(q)
                row.append(min(n, b + (1 if (q - b) > m[j % k][i % k] else 0)))
            out.append(row)
        return out
    buf = [[clamp(value(i, j)) * n for i in range(cols)] for j in range(rows)]
    out = [[0] * cols for _ in range(rows)]
    if method == "riemersma":
        q, ratio = 16, 1 / 16
        weights = [ratio ** (1 - i / (q - 1)) for i in range(q)]
        hist = [0.0] * q
        order = max(cols, rows).bit_length()
        for x, y in _hilbert(order):
            if x >= cols or y >= rows:
                continue
            v = buf[y][x] + sum(h * w for h, w in zip(hist, weights)) / sum(weights) * 2
            new = max(0, min(n, round(v)))
            out[y][x] = new
            hist = hist[1:] + [buf[y][x] - new]
        return out
    if method not in DIFFUSION:
        raise ValueError(method)
    taps, div = DIFFUSION[method], DIFFUSION_DIV[method]
    for j in range(rows):
        rev = serpentine and j % 2 == 1
        for i in range(cols - 1, -1, -1) if rev else range(cols):
            old = buf[j][i]
            new = max(0, min(n, round(old)))
            out[j][i] = new
            err = old - new
            for dx, dy, wgt in taps:
                x, y = i + (-dx if rev else dx), j + dy
                if 0 <= x < cols and y < rows:
                    buf[y][x] += err * wgt / div
    return out


SHADES = " ░▒▓█"  # 8x16 block-element tones, light → full
DENSITY = " .:-=+*#%@"  # classic ASCII-art brightness ramp


def glyph(ch: str, font: str = "8x16") -> list[list[bool]]:
    """Pixel rows of `ch` in a baked Spleen font ('5x8' ASCII + light box drawing; '8x16'
    ASCII, box drawing, blocks ░▒▓█, geometric shapes, braille). Unknown chars → blank."""
    from .font import FONTS

    w, h, table = FONTS[font]
    rows = table.get(ord(ch))
    if rows is None:
        return [[False] * w for _ in range(h)]
    return [[bool(int(rows[2 * j : 2 * j + 2], 16) >> (w - 1 - i) & 1) for i in range(w)] for j in range(h)]


def glyphs(s: "Svg", lines, color, font: str = "8x16", px: int = 2, x: float = 0, y: float = 0, gap: int = 0, key=None, **kw) -> None:
    """Render a character grid as crisp pixels (one merged <path class="px"> per group).

    `lines`: list of strings (one per text row). `color`: a single colour, or
    `color(col, row, ch) -> colour | None` for per-cell colouring (None skips the cell).
    Cells group into paths by colour, or by `key(col, row, ch) -> hashable` when given: key by
    role so two roles that share a hex under some theme still get separate paths. Every cell of
    one key must get the same colour (ValueError otherwise). Paths come in first-seen group order.
    Each glyph pixel is `px`×`px`; cells are font-width×font-height pixels plus `gap`.
    Records (px, x, y) in pixel_grids() when anything is drawn.
    """
    from .font import FONTS

    fw, fh, _ = FONTS[font]
    cache: dict = {}
    paths: dict = {}
    for r, line in enumerate(lines):
        for c, ch in enumerate(line):
            if ch == " ":
                continue
            col = color(c, r, ch) if callable(color) else color
            if not col:
                continue
            bits = cache.get(ch) or cache.setdefault(ch, glyph(ch, font))
            ox, oy = x + c * (fw + gap) * px, y + r * (fh + gap) * px
            group = key(c, r, ch) if key else col
            fill, out = paths.setdefault(group, (col, []))
            if fill != col:
                raise ValueError(f"glyphs key {group!r} got two colours: {fill}, {col}")
            for j, row in enumerate(bits):
                i = 0
                while i < fw:
                    if row[i]:
                        k = i
                        while k < fw and row[k]:
                            k += 1
                        out.append(f"M{fmt(ox + i * px)} {fmt(oy + j * px)}h{fmt((k - i) * px)}v{fmt(px)}h{fmt(-(k - i) * px)}z")
                        i = k
                    else:
                        i += 1
    if paths:
        _PIXEL_GRIDS.append((px, x, y))
    for fill, d in paths.values():
        s.path("".join(d), fill=fill, class_="px", **kw)


def sprite(s: "Svg", art, palette: dict, cell: float, x: float = 0, y: float = 0, **kw) -> None:
    """Draw pixel art: `art` is a multi-line string (or list of rows), one char per pixel.

    `palette` maps chars to colors; unmapped chars ('.', ' ') are transparent. Drawn by
    grid_runs(), so the paths are tagged and the grid recorded the same way.
    """
    rows = art.strip("\n").split("\n") if isinstance(art, str) else list(art)
    keys = sorted(palette)
    idx = {c: i for i, c in enumerate(keys)}
    grid = [[idx.get(ch) for ch in row] for row in rows]
    grid_runs(s, grid, [palette[c] for c in keys], cell, x, y, skip=None, **kw)


def contours(field, level: float, cell: float = 1.0, ox: float = 0, oy: float = 0):
    """Marching squares over `field[row][col]`; returns joined polylines at `level`.

    Each polyline is a list of (x, y) in output units (grid index * cell + offset).
    """
    rows, cols = len(field), len(field[0])

    def pt(e):
        kind, i, j = e
        if kind == "h":
            a, b = field[j][i], field[j][i + 1]
            t = (level - a) / (b - a) if b != a else 0.5
            return ox + (i + t) * cell, oy + j * cell
        a, b = field[j][i], field[j + 1][i]
        t = (level - a) / (b - a) if b != a else 0.5
        return ox + i * cell, oy + (j + t) * cell

    adj: dict = {}

    def link(a, b):
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    for j in range(rows - 1):
        for i in range(cols - 1):
            tl, tr = field[j][i] > level, field[j][i + 1] > level
            br, bl = field[j + 1][i + 1] > level, field[j + 1][i] > level
            idx = tl << 3 | tr << 2 | br << 1 | bl
            if idx in (0, 15):
                continue
            top, right, bottom, left = ("h", i, j), ("v", i + 1, j), ("h", i, j + 1), ("v", i, j)
            table = {
                1: [(left, bottom)], 2: [(bottom, right)], 3: [(left, right)], 4: [(top, right)],
                6: [(top, bottom)], 7: [(left, top)], 8: [(left, top)], 9: [(top, bottom)],
                11: [(top, right)], 12: [(left, right)], 13: [(bottom, right)], 14: [(left, bottom)],
            }
            if idx in (5, 10):
                centre = (field[j][i] + field[j][i + 1] + field[j + 1][i] + field[j + 1][i + 1]) / 4 > level
                if (idx == 5) == centre:
                    segs = [(left, top), (bottom, right)]
                else:
                    segs = [(left, bottom), (top, right)]
            else:
                segs = table[idx]
            for a, b in segs:
                link(a, b)

    seen = set()
    lines = []
    for start in list(adj):
        if start in seen:
            continue
        # walk to an endpoint first so open chains come out whole
        cur, prev = start, None
        while True:
            nxt = [n for n in adj[cur] if n != prev]
            if len(adj[cur]) < 2 or not nxt or nxt[0] == start:
                break
            prev, cur = cur, nxt[0]
            if cur == start:
                break
        chain = [cur]
        seen.add(cur)
        prev = None
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                if len(adj[cur]) == 2 and chain[0] in adj[cur] and len(chain) > 2:
                    chain.append(chain[0])
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            chain.append(cur)
        lines.append([pt(e) for e in chain])
    return lines


def sample_field(fn, cols: int, rows: int):
    """`fn(col, row)` evaluated on a (rows+1)×(cols+1) lattice for contours()."""
    return [[fn(i, j) for i in range(cols + 1)] for j in range(rows + 1)]


def poisson_disk(r: random.Random, width: float, height: float, radius: float, k: int = 30, x0: float = 0, y0: float = 0):
    """Bridson Poisson-disk samples with min spacing `radius` inside the box."""
    cs = radius / math.sqrt(2)
    gw, gh = int(width / cs) + 1, int(height / cs) + 1
    grid = [[None] * gw for _ in range(gh)]
    first = (r.uniform(0, width), r.uniform(0, height))
    out, active = [first], [first]
    grid[int(first[1] / cs)][int(first[0] / cs)] = first
    while active:
        idx = r.randrange(len(active))
        px, py = active[idx]
        for _ in range(k):
            a, d = r.uniform(0, 2 * math.pi), r.uniform(radius, 2 * radius)
            x, y = px + d * math.cos(a), py + d * math.sin(a)
            if not (0 <= x < width and 0 <= y < height):
                continue
            gx, gy = int(x / cs), int(y / cs)
            ok = True
            for yy in range(max(0, gy - 2), min(gh, gy + 3)):
                for xx in range(max(0, gx - 2), min(gw, gx + 3)):
                    q = grid[yy][xx]
                    if q and (q[0] - x) ** 2 + (q[1] - y) ** 2 < radius * radius:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                grid[gy][gx] = (x, y)
                out.append((x, y))
                active.append((x, y))
                break
        else:
            active.pop(idx)
    return [(x + x0, y + y0) for x, y in out]


