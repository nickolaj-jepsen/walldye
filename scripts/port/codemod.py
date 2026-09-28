# /// script
# requires-python = ">=3.13"
# dependencies = ["libcst>=1.8"]
# ///
"""Rewrite v1 designs (`from wallgen import ...` or v1 `from walldye import ...`) as API v2 skeletons.

    uv run scripts/port/codemod.py SRC... (--out DIR | --in-place) [--report FILE] [--no-format]

SRC is a design file or a directory of them (`*.py`, or `*/design.py`). A file's slug is its stem,
or its folder's name for `design.py`; `--out DIR` writes `DIR/<slug>/design.py`. The rewrite is
mechanical and follows docs/api.md: imports, the `@design(...)` decorator and typed `draw`
signature, W/H and the generator families inside the canvas's reach to `s.w`/`s.h` and
`s.rng`/`s.np_rng`/`s.noise` (helpers that need the canvas get an `s` parameter), `is_light()`
to `s.light` or `by_regime`, `s.g` to `s.group`, element methods to `P()` primitives, `s.path`
to `s.stroke`/`s.fill` where the style allows, gradients, transforms, dash patterns, the moved
helpers and a module-level `BG` to `@design(bg=...)`. What it cannot do is marked in the output
with `# TODO(port): <kind>: <what to do>` on the line above the statement. Running it on its own
output changes nothing.

Unless `--no-format`, the output goes through the repo's ruff: `ruff check --fix` (its safe fixes,
which sort imports and drop unused ones), then `ruff format`. The report (stdout, and JSON with `--report`) lists per file what changed
and which TODOs remain.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst
from libcst.metadata import (
    ExpressionContext,
    ExpressionContextProvider,
    MetadataWrapper,
    ParentNodeProvider,
)

ROOT = Path(__file__).resolve().parents[2]
OLD_MODULES = ("wallgen", "walldye")
NEW_MODULES = ("walldye", "walldye.geom", "walldye.field", "walldye.pixel")

TOKENS = frozenset(
    {"BLACK", "BG_DEEP", "BG", "BG_ALT", "UI", "UI_ALT", "UI_HI", "MUTED", "FG_ALT", "FG"}
    | {"ACCENT_HI", "ACCENT"}
    | {f"ACCENT_{i}" for i in range(1, 9)}
)
CORE = TOKENS | frozenset(
    {"MASK_WHITE", "MASK_BLACK", "design", "Canvas", "Params", "knob", "Colour", "MaskColour"}
    | {"mix", "ramp", "ladder", "Ladder", "by_regime", "Paint", "MaskPaint", "Ref", "Style"}
    | {"Stop", "MaskStop", "LineCap", "LineJoin", "FillRule", "Buckets", "ClipSurface"}
    | {"MaskSurface", "PatternSurface", "Rng", "NpRng", "P", "Path", "Vec", "Rect", "Point"}
    | {"Num", "polar", "lerp", "clamp", "smoothstep"}
)
# v1 helpers that live on in a helper module (v1 name -> v2 module, v2 name).
MOVED = {
    "noise_grid": ("walldye.field", "noise_grid"),
    "sample_field": ("walldye.field", "sample_field"),
    "contours": ("walldye.field", "iso_lines"),
    "poisson_disk": ("walldye.geom", "poisson_disk"),
    **{n: ("walldye.pixel", n) for n in ("grid_runs", "dither", "bayer", "blue_noise")},
    **{n: ("walldye.pixel", n) for n in ("threshold_matrix", "glyph", "glyphs", "sprite")},
}
# v1 constants that v2 dropped from the API; the design gets its own copy.
CONSTANTS = {
    "SHADES": ('" ░▒▓█"', ()),
    "DENSITY": ('" .:-=+*#%@"', ()),
    "GREYS": (
        "[BLACK, BG_DEEP, BG, BG_ALT, UI, UI_ALT, UI_HI, MUTED]",
        ("BLACK", "BG_DEEP", "BG", "BG_ALT", "UI", "UI_ALT", "UI_HI", "MUTED"),
    ),
    "ACCENTS": (
        "[" + ", ".join([*(f"ACCENT_{i}" for i in range(8, 0, -1)), "ACCENT"]) + "]",
        (*(f"ACCENT_{i}" for i in range(8, 0, -1)), "ACCENT"),
    ),
}
CANVAS_NAMES = {"W", "H", "rng", "Noise", "is_light", "accent_ramp"}
V1_CANVAS_ATTRS = frozenset(
    {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "g", "defs"}
    | {"linear_gradient", "radial_gradient", "clip", "mask", "pattern", "uid", "raw", "el"}
)
V2_CANVAS_ATTRS = frozenset(
    {"w", "h", "landscape", "light", "params", "center", "frac", "pick", "inset", "rng"}
    | {"np_rng", "noise", "data", "fill", "stroke", "path", "pixel_path", "group", "buckets"}
    | {"clip", "mask", "pattern", "linear_gradient", "radial_gradient"}
)
PIXEL_TAKES_CANVAS = {"grid_runs", "glyphs", "sprite"}
STROKE_KEYS = {"stroke_linecap": "cap", "stroke_linejoin": "join", "stroke_dasharray": "dash"}
STYLE_KEYS = frozenset(
    {"stroke", "stroke_width", "stroke_linecap", "stroke_linejoin", "stroke_dasharray"}
    | {"stroke_dashoffset", "stroke_opacity", "fill_opacity", "fill_rule", "opacity"}
    | {"transform", "clip_path", "mask"}
)
NUMERIC_KEYS = {"stroke_width", "stroke_dashoffset", "stroke_opacity", "fill_opacity", "opacity"}
HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
LINT_CALLS = {"hash", "id", "open", "exec", "eval", "compile", "globals", "__import__"}
WH = {"W": "w", "H": "h"}

TODO = {
    "module-wh": "W and H are v1's 16:9 canvas; move what uses them into draw (s.w, s.h)",
    "reads-wh": "reads the module-level W/H; move into draw or pass s",
    "generator": "no canvas in reach: take a generator from s.rng/s.np_rng/s.noise instead",
    "unseeded": "unseeded generator: give it a key and use s.rng/s.np_rng",
    "raw-markup": "raw clip/mask/pattern markup: use `with s.clip() as c:` (docs/api.md 7.7)",
    "colour-order": "colours have no order: sort by an explicit key that skips the colour",
    "hex-literal": "raw colour string: use a token, mix() or by_regime()",
    "aspects": '16:9 only; declare aspects="any" once the layout follows s.w/s.h',
    "string-path": "string path data: rebuild it with P() and absolute commands",
    "transform": "transform string: build a walldye.geom.Affine",
    "dasharray": "dash pattern: pass a sequence of numbers",
    "fill-default": "v1 drew this with SVG's default black fill: choose a paint",
    "group-fill": "the group's fill moved onto its children; this helper must pass it",
    "splat-style": "**style into a drawing call: check the keys against Style",
    "arc-band": "v2 draws from a0 towards a1; for a1 < a0 write rad=(a0, a1 + 2 * math.pi)",
    "is-light": "is_light() outside draw: use s.light in draw, or by_regime()",
    "star-args": (
        "f(*x, y): Pyrefly counts the arguments wrong unless x has a known length; type x as"
        " tuple[float, float] or Vec, or pass x[0], x[1] (docs/api.md 15.3)"
    ),
}


@dataclass
class Report:
    """What the rewrite of one file did: counts of changes by kind, and the TODOs left."""

    slug: str
    source: str
    output: str = ""
    compiles: bool = False
    changes: Counter[str] = field(default_factory=Counter)
    todos: list[dict[str, object]] = field(default_factory=list)
    error: str = ""

    def as_json(self) -> dict[str, object]:
        return {
            "slug": self.slug,
            "source": self.source,
            "output": self.output,
            "compiles": self.compiles,
            "changes": dict(sorted(self.changes.items())),
            "todos": self.todos,
            **({"error": self.error} if self.error else {}),
        }


_EMPTY = cst.Module(body=[])


def code(node: cst.CSTNode) -> str:
    return _EMPTY.code_for_node(node)


def parse(text: str) -> cst.BaseExpression:
    return cst.parse_expression(text)


def star_then_positional(call: cst.Call) -> bool:
    """Whether `call` passes a positional argument after a `*x` one."""
    starred = False
    for arg in call.args:
        if arg.keyword is not None or arg.star == "**":
            break
        if arg.star == "*":
            starred = True
        elif starred:
            return True
    return False


def dotted(node: cst.BaseExpression) -> str:
    """`a.b.c` for a Name/Attribute chain, else ""."""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        head = dotted(node.value)
        return f"{head}.{node.attr.value}" if head else ""
    return ""


def string_value(node: cst.CSTNode) -> str | None:
    if isinstance(node, cst.SimpleString):
        v = node.evaluated_value
        return v if isinstance(v, str) else None
    if isinstance(node, cst.ConcatenatedString):
        left, right = string_value(node.left), string_value(node.right)
        return None if left is None or right is None else left + right
    return None


def number_text(node: cst.CSTNode) -> str | None:
    if isinstance(node, (cst.Integer, cst.Float)):
        return node.value
    if isinstance(node, cst.UnaryOperation) and isinstance(node.operator, cst.Minus):
        inner = number_text(node.expression)
        return None if inner is None else "-" + inner
    return None


def number_literal(text: str) -> str | None:
    """`text` as a Python number literal when it is one, e.g. "1.50" -> "1.5"."""
    try:
        v = float(text)
    except ValueError:
        return None
    if not math.isfinite(v):
        return None
    return str(int(v)) if v == int(v) and "." not in text and "e" not in text.lower() else repr(v)


def call_parts(call: cst.Call) -> tuple[list[cst.Arg], dict[str, cst.Arg], list[cst.Arg]]:
    """(positional, keyword by name, ** splats) of `call`; *args count as positional."""
    pos, kw, splat = [], {}, []
    for a in call.args:
        if a.keyword is not None:
            kw[a.keyword.value] = a
        elif a.star == "**":
            splat.append(a)
        else:
            pos.append(a)
    return pos, kw, splat


def arg_code(a: cst.Arg) -> str:
    return code(a.value)


def unwrap_fmt(node: cst.BaseExpression) -> cst.BaseExpression:
    """`fmt(x)` / `fmt(x, nd)` / `str(x)` -> x; v2 formats numbers itself."""
    if isinstance(node, cst.Call) and dotted(node.func) in ("fmt", "str") and node.args:
        return node.args[0].value
    return node


def fstring_items(node: cst.BaseExpression) -> list[str | cst.BaseExpression] | None:
    """A str or f-string as literal text and expressions (format specs dropped), or None."""
    text = string_value(node)
    if text is not None:
        return [text]
    if not isinstance(node, cst.FormattedString):
        return None
    out: list[str | cst.BaseExpression] = []
    for part in node.parts:
        if isinstance(part, cst.FormattedStringText):
            out.append(part.value)
        elif isinstance(part, cst.FormattedStringExpression) and part.conversion is None:
            out.append(unwrap_fmt(part.expression))
        else:
            return None
    return out


def split_args(items: Sequence[str | cst.BaseExpression]) -> list[str] | None:
    """Space/comma separated values of a transform or dash list, each as Python code."""
    values: list[str] = []
    pending = ""  # literal text glued to the next expression, like the "-" in "-{x}"
    for item in items:
        if isinstance(item, str):
            tokens = re.split(r"[\s,]+", item)
            for i, tok in enumerate(tokens):
                if not tok:
                    continue
                last = i == len(tokens) - 1 and not re.search(r"[\s,]$", item)
                if last and tok == "-":
                    pending = "-"
                    continue
                lit = number_literal(tok)
                if lit is None:
                    return None
                values.append(lit)
        else:
            text = code(item)
            if pending:
                text, pending = f"-({text})", ""
            values.append(text)
    return None if pending else values


def degrees_arg(text: str) -> tuple[str, str]:
    """("rad", x) for `math.degrees(x)` / `np.degrees(x)`, else ("deg", text)."""
    m = re.fullmatch(r"(?:math|np|numpy)\.(?:degrees|rad2deg)\((.*)\)", text, re.DOTALL)
    return ("rad", m.group(1)) if m else ("deg", text)


def affine_code(node: cst.BaseExpression) -> str | None:
    """A v1 transform string (str or f-string) as `Affine...` code, or None."""
    items = fstring_items(node)
    if items is None:
        return None
    # Re-tokenise into function names and argument groups over the mixed items.
    ops: list[tuple[str, list[str | cst.BaseExpression]]] = []
    current: list[str | cst.BaseExpression] | None = None
    name = ""
    for item in items:
        if not isinstance(item, str):
            if current is None:
                return None
            current.append(item)
            continue
        rest = item
        while rest:
            if current is None:
                m = re.match(r"\s*([A-Za-z]+)\s*\(", rest)
                if not m:
                    if rest.strip():
                        return None
                    break
                name, current, rest = m.group(1), [], rest[m.end() :]
            else:
                close = rest.find(")")
                if close < 0:
                    current.append(rest)
                    break
                current.append(rest[:close])
                ops.append((name, current))
                current, rest = None, rest[close + 1 :]
    if current is not None or not ops:
        return None
    parts = []
    for name, args in ops:
        vals = split_args(args)
        if vals is None:
            return None
        if name == "translate" and len(vals) in (1, 2):
            parts.append(f"Affine.translate({vals[0]}, {vals[1] if len(vals) == 2 else 0})")
        elif name == "scale" and len(vals) in (1, 2):
            parts.append(f"Affine.scale({', '.join(vals)})")
        elif name == "rotate" and len(vals) in (1, 3):
            unit, angle = degrees_arg(vals[0])
            about = f", about=({vals[1]}, {vals[2]})" if len(vals) == 3 else ""
            parts.append(f"Affine.rotate({unit}={angle}{about})")
        elif name == "matrix" and len(vals) == 6:
            parts.append(f"Affine({', '.join(vals)})")
        else:
            return None
    return " @ ".join(parts)


def dash_code(node: cst.BaseExpression) -> str | None:
    """A v1 dash string (str or f-string) as a tuple literal, or None."""
    items = fstring_items(node)
    if items is None:
        return None
    vals = split_args(items)
    if not vals:
        return None
    return f"({', '.join(vals)},)" if len(vals) == 1 else f"({', '.join(vals)})"


def numeric_code(node: cst.BaseExpression) -> str | None:
    """A numeric style value written as a string, `fmt(x)` or `f"{x}"`, as number code."""
    node = unwrap_fmt(node)
    text = string_value(node)
    if text is not None:
        return number_literal(text.strip())
    items = fstring_items(node)
    if items is not None and len(items) == 1 and not isinstance(items[0], str):
        return code(items[0])
    return None if isinstance(node, (cst.SimpleString, cst.FormattedString)) else code(node)


# --- scope analysis ---------------------------------------------------------------------------


def bound_names(fn: cst.FunctionDef | cst.Lambda) -> set[str]:
    """Names `fn` binds in its own scope: parameters and assignment targets in its body."""
    names = {p.name.value for p in _params(fn.params)}
    if isinstance(fn, cst.Lambda):
        return names
    collector = _Binder()
    fn.body.visit(collector)
    return names | collector.names


def _params(params: cst.Parameters) -> Iterator[cst.Param]:
    yield from params.posonly_params
    yield from params.params
    if isinstance(params.star_arg, cst.Param):
        yield params.star_arg
    yield from params.kwonly_params
    if params.star_kwarg is not None:
        yield params.star_kwarg


def _targets(node: cst.CSTNode) -> Iterator[str]:
    if isinstance(node, cst.Name):
        yield node.value
    elif isinstance(node, (cst.Tuple, cst.List)):
        for el in node.elements:
            yield from _targets(el.value)
    elif isinstance(node, cst.StarredElement):
        yield from _targets(node.value)


class _Binder(cst.CSTVisitor):
    """Collects the names a function body binds, skipping nested scopes."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self.names.add(node.name.value)
        return False

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self.names.add(node.name.value)
        return False

    def visit_Lambda(self, node: cst.Lambda) -> bool:
        return False

    def visit_ListComp(self, node: cst.ListComp) -> bool:
        return False

    def visit_SetComp(self, node: cst.SetComp) -> bool:
        return False

    def visit_DictComp(self, node: cst.DictComp) -> bool:
        return False

    def visit_GeneratorExp(self, node: cst.GeneratorExp) -> bool:
        return False

    def visit_AssignTarget(self, node: cst.AssignTarget) -> None:
        self.names.update(_targets(node.target))

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        self.names.update(_targets(node.target))

    def visit_AugAssign(self, node: cst.AugAssign) -> None:
        self.names.update(_targets(node.target))

    def visit_For(self, node: cst.For) -> None:
        self.names.update(_targets(node.target))

    def visit_AsName(self, node: cst.AsName) -> None:
        self.names.update(_targets(node.name))

    def visit_NamedExpr(self, node: cst.NamedExpr) -> None:
        self.names.update(_targets(node.target))

    def visit_ImportAlias(self, node: cst.ImportAlias) -> None:
        if node.asname is None:
            self.names.add(code(node.name).split(".")[0])


type Fn = cst.FunctionDef | cst.Lambda


class Analysis(cst.CSTVisitor):
    """Everything the transformer needs to know about the original tree, keyed by node."""

    METADATA_DEPENDENCIES = (ParentNodeProvider, ExpressionContextProvider)

    def __init__(self) -> None:
        self.stack: list[Fn] = []
        self.chain: dict[cst.CSTNode, tuple[Fn, ...]] = {}
        self.bound: dict[Fn, set[str]] = {}
        self.old: dict[str, str] = {}  # local name -> v1 name, for names from the old modules
        self.np_names: set[str] = set()  # local names of numpy
        self.random_names: set[str] = set()  # local names of the random module
        self.default_rng_names: set[str] = set()  # `from numpy.random import default_rng`
        self.module_funcs: dict[str, cst.FunctionDef] = {}
        self.module_bound: set[str] = set()
        self.module_assigns: dict[str, list[cst.CSTNode]] = {}
        self.names: list[cst.Name] = []
        self.calls: list[cst.Call] = []
        self.loads: set[cst.Name] = set()
        self.parents: dict[cst.CSTNode, cst.CSTNode] = {}
        self.funcs: list[cst.FunctionDef] = []
        self.assigns: list[tuple[cst.CSTNode, cst.BaseExpression | None]] = []  # target, value
        self.fors: list[tuple[cst.CSTNode, cst.BaseExpression]] = []
        self.in_import = False

    # traversal bookkeeping

    def on_visit(self, node: cst.CSTNode) -> bool:
        parent = self.get_metadata(ParentNodeProvider, node, None)
        if parent is not None:
            self.parents[node] = parent
        if isinstance(node, (cst.Name, cst.Call, cst.IfExp, cst.Attribute)):
            self.chain[node] = tuple(self.stack)
        if isinstance(node, (cst.Import, cst.ImportFrom)):
            self.in_import = True
        if isinstance(node, cst.Name) and not self.in_import:
            self.names.append(node)
            if self.get_metadata(ExpressionContextProvider, node, None) == ExpressionContext.LOAD:
                self.loads.add(node)
        if isinstance(node, cst.Call):
            self.calls.append(node)
        if isinstance(node, (cst.FunctionDef, cst.Lambda)):
            self.bound[node] = bound_names(node)
            if isinstance(node, cst.FunctionDef):
                self.funcs.append(node)
            self.stack.append(node)
        return super().on_visit(node)

    def on_leave(self, original_node: cst.CSTNode) -> None:
        super().on_leave(original_node)
        if isinstance(original_node, (cst.Import, cst.ImportFrom)):
            self.in_import = False
        if isinstance(original_node, (cst.FunctionDef, cst.Lambda)):
            self.stack.pop()

    def visit_Module(self, node: cst.Module) -> None:
        for stmt in node.body:
            if isinstance(stmt, cst.FunctionDef):
                self.module_funcs[stmt.name.value] = stmt
                self.module_bound.add(stmt.name.value)
            elif isinstance(stmt, cst.ClassDef):
                self.module_bound.add(stmt.name.value)
            elif isinstance(stmt, cst.SimpleStatementLine):
                for small in stmt.body:
                    targets: list[cst.CSTNode] = []
                    if isinstance(small, cst.Assign):
                        targets = [t.target for t in small.targets]
                    elif isinstance(small, (cst.AnnAssign, cst.AugAssign)):
                        targets = [small.target]
                    for t in targets:
                        for name in _targets(t):
                            self.module_bound.add(name)
                            self.module_assigns.setdefault(name, []).append(small)
                    if isinstance(small, cst.ImportFrom) and not isinstance(
                        small.names, cst.ImportStar
                    ):
                        self._import_from(small)
                    elif isinstance(small, cst.Import):
                        for alias in small.names:
                            full = code(alias.name)
                            asname = alias.asname
                            local = code(asname.name) if isinstance(asname, cst.AsName) else full
                            if full == "numpy":
                                self.np_names.add(local)
                            elif full == "random":
                                self.random_names.add(local)

    def _import_from(self, node: cst.ImportFrom) -> None:
        module = code(node.module) if node.module else ""
        assert not isinstance(node.names, cst.ImportStar)
        for alias in node.names:
            name = code(alias.name)
            local = code(alias.asname.name) if isinstance(alias.asname, cst.AsName) else name
            if module == "numpy.random" and name == "default_rng":
                self.default_rng_names.add(local)
            if module in OLD_MODULES and name not in CORE:
                self.old[local] = name

    def visit_Assign(self, node: cst.Assign) -> None:
        for t in node.targets:
            self.assigns.append((t.target, node.value))

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        self.assigns.append((node.target, node.value))

    def visit_For(self, node: cst.For) -> None:
        self.fors.append((node.target, node.iter))

    def visit_CompFor(self, node: cst.CompFor) -> None:
        self.fors.append((node.target, node.iter))


@dataclass
class Scope:
    """Canvas reach: where the canvas is in scope, and under which name."""

    a: Analysis
    canvas_fns: set[Fn] = field(default_factory=set)
    threaded: dict[str, str] = field(default_factory=dict)  # module function -> its parameter
    draw: cst.FunctionDef | None = None

    def is_local(self, node: cst.CSTNode, name: str) -> bool:
        return any(name in self.a.bound[f] for f in self.a.chain.get(node, ()))

    def param(self, fn: Fn) -> str | None:
        """The name `fn` has (or, once threaded, will have) the canvas under."""
        if fn in self.canvas_fns:
            return "s"
        if isinstance(fn, cst.FunctionDef) and self.a.module_funcs.get(fn.name.value) is fn:
            return self.threaded.get(fn.name.value)
        return None

    def name(self, node: cst.CSTNode) -> str | None:
        """The canvas's name at `node`, None when it is out of reach."""
        chain = self.a.chain.get(node, ())
        for i in range(len(chain) - 1, -1, -1):
            param = self.param(chain[i])
            if param is not None:
                shadowed = any(param in self.a.bound[f] for f in chain[i + 1 :])
                return None if shadowed else param
        return None


def first_param(fn: Fn) -> str | None:
    params = list(fn.params.posonly_params) + list(fn.params.params)
    return params[0].name.value if params else None


class _Evidence(cst.CSTVisitor):
    """Whether a function body uses its `s` as a canvas (not descending into rebinding scopes)."""

    def __init__(self, bound: dict[Fn, set[str]], helpers: set[str]) -> None:
        self.bound, self.helpers, self.found = bound, helpers, False

    def _enter(self, node: Fn) -> bool:
        return "s" not in self.bound.get(node, set())

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        return self._enter(node)

    def visit_Lambda(self, node: cst.Lambda) -> bool:
        return self._enter(node)

    def visit_Attribute(self, node: cst.Attribute) -> None:
        if dotted(node.value) == "s" and node.attr.value in V1_CANVAS_ATTRS | V2_CANVAS_ATTRS:
            self.found = True

    def visit_Call(self, node: cst.Call) -> None:
        name = dotted(node.func).rsplit(".", 1)[-1]
        if node.args and dotted(node.args[0].value) == "s" and name in self.helpers:
            self.found = True


def canvas_scope(a: Analysis) -> Scope:
    """Where the canvas is: draw, the helpers that use their `s` as one, and those that get it."""
    scope = Scope(a)
    draw = a.module_funcs.get("draw")
    if draw is not None and first_param(draw) == "s":
        scope.draw = draw
        scope.canvas_fns.add(draw)
    helpers = set(PIXEL_TAKES_CANVAS)
    candidates = [f for f in a.funcs if first_param(f) == "s" and f is not draw]
    changed = True
    while changed:
        changed = False
        for fn in candidates:
            if fn in scope.canvas_fns:
                continue
            known = {f.name.value for f in scope.canvas_fns if isinstance(f, cst.FunctionDef)}
            ev = _Evidence(a.bound, helpers | known)
            fn.body.visit(ev)
            if ev.found:
                scope.canvas_fns.add(fn)
                changed = True
    scope.threaded = _threadable(a, scope)
    return scope


def _needs_canvas(a: Analysis, call: cst.Call) -> bool:
    """Whether converting `call` needs the canvas (a generator, is_light, a seeded helper)."""
    name = dotted(call.func)
    v1 = a.old.get(name, "")
    if v1 in ("rng", "Noise", "is_light", "noise_grid", "blue_noise"):
        return True
    if v1 in ("dither", "threshold_matrix"):
        return _rng_method(call, v1) is not False
    last = name.rsplit(".", 1)
    if name in a.default_rng_names or (
        len(last) == 2 and last[1] == "default_rng" and _np_random(a, last[0])
    ):
        return bool(call.args)
    if len(last) == 2 and last[1] == "Random" and last[0] in a.random_names:
        return bool(call.args)
    return False


def _np_random(a: Analysis, head: str) -> bool:
    parts = head.split(".")
    return len(parts) == 2 and parts[0] in a.np_names and parts[1] == "random"


def _rng_method(call: cst.Call, v1: str) -> bool | None:
    """For dither/threshold_matrix: True if the method needs a generator, None if unknown."""
    pos, kw, _ = call_parts(call)
    index = 4 if v1 == "dither" else 0
    arg = kw.get("method") or (pos[index] if len(pos) > index else None)
    if arg is None:
        return False
    method = string_value(arg.value)
    if method is None:
        return None
    return method in ("bluenoise", "random")


def _threadable(a: Analysis, scope: Scope) -> dict[str, str]:
    """Module-level functions that get a canvas parameter (named `s`, or `canvas` where `s` is
    taken): those that need the canvas, and the helpers that call them, when every reference
    is a call with the canvas in reach."""

    def top(node: cst.CSTNode) -> str | None:
        chain = a.chain.get(node, ())
        fn = chain[0] if chain else None
        if isinstance(fn, cst.FunctionDef) and a.module_funcs.get(fn.name.value) is fn:
            return fn.name.value
        return None

    def free(nodes: list[cst.CSTNode]) -> str | None:
        taken = {n for node in nodes for f in a.chain.get(node, ()) for n in a.bound[f]}
        return next((p for p in ("s", "canvas") if p not in taken), None)

    seeds: dict[str, list[cst.CSTNode]] = {}
    for call in a.calls:
        name = top(call)
        if name and _needs_canvas(a, call) and scope.name(call) is None:
            seeds.setdefault(name, []).append(call)
    rejected: set[str] = set()
    while True:
        sites = {f: list(nodes) for f, nodes in seeds.items() if f not in rejected}
        before = len(rejected)
        grown = True
        while grown and len(rejected) == before:
            grown = False
            scope.threaded = {}
            for f, nodes in sites.items():
                param = free(nodes)
                if param is None:
                    rejected.add(f)
                else:
                    scope.threaded[f] = param
            for f in list(scope.threaded):
                for ref in a.names:
                    if ref.value != f or ref not in a.loads or scope.is_local(ref, f):
                        continue
                    parent = a.parents.get(ref)
                    if not (isinstance(parent, cst.Call) and parent.func is ref):
                        rejected.add(f)
                    elif scope.name(ref) is None:
                        caller = top(ref)
                        if caller is None or caller in rejected:
                            rejected.add(f)
                        elif ref not in sites.setdefault(caller, []):
                            sites[caller].append(ref)
                            grown = True
        if len(rejected) == before:
            return scope.threaded


# --- colour heuristics ------------------------------------------------------------------------


@dataclass(frozen=True)
class Seq:
    """A sequence whose items are of kind `of`."""

    of: Kind


@dataclass(frozen=True)
class Tup:
    """A tuple with positional kinds."""

    parts: tuple[Kind, ...]


COLOUR = "C"
type Kind = str | Seq | Tup | None  # COLOUR, a container, or None for anything else


def _merge(a: Kind, b: Kind) -> Kind:
    if a is None or a == b:
        return b
    if b is None:
        return a
    if isinstance(a, Seq) and isinstance(b, Seq):
        return Seq(_merge(a.of, b.of))
    return a


def _elem(k: Kind) -> Kind:
    if isinstance(k, Seq):
        return k.of
    if isinstance(k, Tup):
        out: Kind = None
        for x in k.parts:
            out = _merge(out, x)
        return out
    return None


def _has_colour(k: Kind) -> bool:
    if isinstance(k, Seq):
        return _has_colour(k.of)
    if isinstance(k, Tup):
        return any(_has_colour(x) for x in k.parts)
    return k == COLOUR


class Colours:
    """A small flow-insensitive inference of which values are colours, per function scope,
    for the colour-order check and by_regime: colours have no order in v2."""

    def __init__(self, a: Analysis, scope: Scope) -> None:
        self.a, self.scope = a, scope
        self.env: dict[tuple[Fn | None, str], Kind] = {}
        self.keys: dict[tuple[Fn | None, str], Kind] = {}
        for _ in range(4):
            before = (dict(self.env), dict(self.keys))
            for target, value in a.assigns:
                if value is not None:
                    self._bind(target, self.kind(value))
            for target, it in a.fors:
                self._bind(target, _elem(self.kind(it)))
            for call in a.calls:
                f = call.func
                if (
                    isinstance(f, cst.Attribute)
                    and f.attr.value in ("setdefault", "get")
                    and call.args
                    and isinstance(f.value, cst.Name)
                ):
                    self._key(f.value, self.kind(call.args[0].value))
            for node in a.parents:
                if (
                    isinstance(node, cst.Subscript)
                    and isinstance(node.value, cst.Name)
                    and len(node.slice) == 1
                    and isinstance(node.slice[0].slice, cst.Index)
                ):
                    self._key(node.value, self.kind(node.slice[0].slice.value))
            if (dict(self.env), dict(self.keys)) == before:
                break

    def _where(self, name: cst.Name) -> Fn | None:
        chain = self.a.chain.get(name, ())
        for fn in reversed(chain):
            if name.value in self.a.bound[fn]:
                return fn
        return None

    def _lookup(self, table: dict[tuple[Fn | None, str], Kind], name: cst.Name) -> Kind:
        return table.get((self._where(name), name.value))

    def _bind(self, target: cst.CSTNode, kind: Kind) -> None:
        if isinstance(target, cst.Name):
            key = (self._where(target), target.value)
            self.env[key] = _merge(self.env.get(key), kind)
        elif isinstance(target, (cst.Tuple, cst.List)):
            for i, el in enumerate(target.elements):
                if isinstance(el, cst.StarredElement):
                    self._bind(el.value, Seq(_elem(kind)))
                elif isinstance(kind, Tup):
                    self._bind(el.value, kind.parts[i] if i < len(kind.parts) else None)
                else:
                    self._bind(el.value, _elem(kind))

    def _key(self, dict_name: cst.Name, kind: Kind) -> None:
        if kind is None:
            return
        key = (self._where(dict_name), dict_name.value)
        self.keys[key] = _merge(self.keys.get(key), kind)

    def kind(self, node: cst.BaseExpression) -> Kind:
        if isinstance(node, cst.Name):
            found = self._lookup(self.env, node)
            if found is None and node.value in TOKENS and not self.scope.is_local(node, node.value):
                return COLOUR
            return found
        if isinstance(node, cst.Call):
            return self._call_kind(node)
        if isinstance(node, cst.Subscript):
            outer = self.kind(node.value)
            if len(node.slice) != 1:
                return None
            index = node.slice[0].slice
            if isinstance(index, cst.Slice):
                return outer if isinstance(outer, Seq) else None
            if isinstance(outer, Tup):
                n = number_text(index.value) if isinstance(index, cst.Index) else None
                if n is None or not n.lstrip("-").isdigit():
                    return None
                i = int(n)
                return outer.parts[i] if -len(outer.parts) <= i < len(outer.parts) else None
            return outer.of if isinstance(outer, Seq) else None
        if isinstance(node, cst.Tuple):
            if any(isinstance(e, cst.StarredElement) for e in node.elements):
                return Seq(self._merged(node.elements))
            return Tup(tuple(self.kind(e.value) for e in node.elements))
        if isinstance(node, (cst.List, cst.Set)):
            return Seq(self._merged(node.elements))
        if isinstance(node, (cst.ListComp, cst.GeneratorExp, cst.SetComp)):
            return Seq(self.kind(node.elt))
        if isinstance(node, cst.IfExp):
            return _merge(self.kind(node.body), self.kind(node.orelse))
        if isinstance(node, cst.BinaryOperation) and isinstance(node.operator, cst.Add):
            return _merge(self.kind(node.left), self.kind(node.right))
        return None

    def _merged(self, elements: Sequence[cst.BaseElement]) -> Kind:
        out: Kind = None
        for e in elements:
            k = self.kind(e.value)
            out = _merge(out, _elem(k) if isinstance(e, cst.StarredElement) else k)
        return out

    def _call_kind(self, node: cst.Call) -> Kind:
        name = dotted(node.func)
        last = name.rsplit(".", 1)[-1]
        args = [a.value for a in node.args]
        if last in ("mix", "by_regime"):
            return COLOUR
        if last in ("ramp", "ladder", "accent_ramp"):
            return Seq(COLOUR)
        if last == "choice" and args:
            return _elem(self.kind(args[0]))
        if name in ("list", "tuple", "sorted", "reversed", "set", "frozenset") and args:
            return Seq(_elem(self.kind(args[0])))
        if name == "zip":
            return Seq(Tup(tuple(_elem(self.kind(a)) for a in args)))
        if name == "enumerate" and args:
            return Seq(Tup((None, _elem(self.kind(args[0])))))
        f = node.func
        if isinstance(f, cst.Attribute) and isinstance(f.value, cst.Name):
            key = self._lookup(self.keys, f.value)
            if f.attr.value == "items":
                return Seq(Tup((key, None)))
            if f.attr.value == "keys":
                return Seq(key)
        return None

    def colour(self, node: cst.BaseExpression) -> bool:
        return self.kind(node) == COLOUR

    def sorts_colours(self, node: cst.BaseExpression) -> bool:
        """Whether sorting the items of `node` (without a key) may compare colours."""
        kind = self.kind(node)
        if isinstance(node, cst.Name) and kind is None:
            kind = Seq(self._lookup(self.keys, node))  # iterating a dict gives its keys
        return _has_colour(_elem(kind))

    def compares_colours(self, nodes: Sequence[cst.BaseExpression]) -> bool:
        """For min/max/sorted arguments: one iterable, or several values compared directly."""
        if len(nodes) == 1:
            return self.sorts_colours(nodes[0])
        return any(_has_colour(self.kind(n)) for n in nodes)


# --- the rewrite -----------------------------------------------------------------------------


@dataclass
class Frame:
    """TODOs collected for one statement."""

    todos: list[tuple[str, str, str]] = field(default_factory=list)  # kind, text, name


@dataclass
class GroupCtx:
    """What an enclosing `with s.g(...)` / `with s.group(...)` block sets for its children."""

    fill: str | None = None
    stroke: bool = False
    width: bool = False
    v1_fill: bool = False  # the fill was moved off a v1 group onto its children


class Rewrite(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (ParentNodeProvider,)

    def __init__(self, a: Analysis, scope: Scope, colours: Colours, report: Report) -> None:
        super().__init__()
        self.a, self.scope, self.colours, self.report = a, scope, colours, report
        self.frames: list[Frame] = []
        self.groups: list[GroupCtx | None] = []
        self.imports: dict[str, set[str]] = {m: set() for m in NEW_MODULES}
        self.need_numpy = False
        self.need_wh = False
        self.dash_consts: dict[str, str] = self._dash_consts()
        self.aspects: str | None = None
        self.bg: str | None = None
        self.drop_stmts: set[cst.CSTNode] = set()
        self.unit = False  # v1's `U = min(W, H) / 1080`, always 1 now
        self.module_todos: list[tuple[str, str]] = []  # marked on the first import line
        if scope.draw is None:
            self.module_todos.append(("lint", "no draw(s) function: the design needs one"))

    # bookkeeping

    def todo(self, kind: str, text: str = "", name: str = "") -> None:
        """Mark the current statement; with `name`, only if the name survives the rewrite."""
        if self.frames:
            self.frames[-1].todos.append((kind, text or TODO[kind], name))

    def change(self, kind: str) -> None:
        self.report.changes[kind] += 1

    def use(self, name: str, module: str = "walldye") -> None:
        self.imports[module].add(name)

    def canvas(self, node: cst.CSTNode) -> bool:
        return self.scope.name(node) is not None

    def cn(self, node: cst.CSTNode) -> str:
        """The canvas's name at `node` (call only where canvas() holds)."""
        return self.scope.name(node) or "s"

    def old(self, node: cst.CSTNode, name: str) -> str:
        """The v1 name `name` stands for at `node`, "" if it is not an old import there."""
        v1 = self.a.old.get(name, "")
        return "" if not v1 or self.scope.is_local(node, name) else v1

    def _push(self) -> None:
        self.frames.append(Frame())

    def _pop[N: cst.CSTNode](self, node: N) -> N:
        frame = self.frames.pop()
        if not frame.todos or not hasattr(node, "leading_lines"):
            return node
        existing = {ln.comment.value for ln in node.leading_lines if ln.comment is not None}
        lines = list(node.leading_lines)
        body = code(node)
        for kind, text, name in dict.fromkeys(frame.todos):
            if name and not re.search(rf"\b{re.escape(name)}\b", body):
                continue
            comment = f"# TODO(port): {kind}: {text}"
            if comment not in existing:
                lines.append(cst.EmptyLine(comment=cst.Comment(comment)))
                existing.add(comment)
        return node.with_changes(leading_lines=lines)

    def on_visit(self, node: cst.CSTNode) -> bool:
        if isinstance(node, (cst.SimpleStatementLine, cst.BaseCompoundStatement)):
            self._push()
            if isinstance(node, (cst.If, cst.For, cst.While, cst.With, cst.Try)) and isinstance(
                self.a.parents.get(node), cst.Module
            ):
                self.todo("lint", "module level holds only constants, functions and classes")
        return super().on_visit(node)

    def on_leave[N: cst.CSTNode](
        self, original_node: N, updated_node: N
    ) -> N | cst.RemovalSentinel | cst.FlattenSentinel[N]:
        result = super().on_leave(original_node, updated_node)
        if isinstance(original_node, (cst.SimpleStatementLine, cst.BaseCompoundStatement)):
            if isinstance(result, cst.CSTNode):
                return self._pop(result)
            self.frames.pop()
        return result

    def _dash_consts(self) -> dict[str, str]:
        """Module-level dash strings used only as stroke_dasharray values -> tuple code."""
        out = {}
        for name, assigns in self.a.module_assigns.items():
            if len(assigns) != 1 or not isinstance(assigns[0], cst.Assign):
                continue
            value = assigns[0].value
            text = string_value(value)
            if text is None or not re.fullmatch(r"[\d.\s,]+", text):
                continue
            uses = [n for n in self.a.names if n.value == name and n in self.a.loads]
            if uses and all(
                isinstance(p := self.a.parents.get(n), cst.Arg)
                and p.keyword is not None
                and p.keyword.value == "stroke_dasharray"
                for n in uses
            ):
                dash = dash_code(value)
                if dash:
                    out[name] = dash
        return out

    # module level

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        target = original_node.targets[0].target
        if (
            len(original_node.targets) == 1
            and isinstance(target, cst.Name)
            and target.value in self.dash_consts
            and not self.a.chain.get(target)
        ):
            self.change("dasharray")
            return updated_node.with_changes(value=parse(self.dash_consts[target.value]))
        return updated_node

    def leave_SimpleString(
        self, original_node: cst.SimpleString, updated_node: cst.SimpleString
    ) -> cst.SimpleString:
        value = string_value(original_node)
        if value is not None and HEX.fullmatch(value.strip()):
            self.todo("hex-literal")
        return updated_node

    def leave_FormattedString(
        self, original_node: cst.FormattedString, updated_node: cst.FormattedString
    ) -> cst.FormattedString:
        text = "".join(
            p.value for p in original_node.parts if isinstance(p, cst.FormattedStringText)
        )
        if HEX.search(text) and re.search(r"(fill|stroke|stop-color)=", text):
            self.todo("hex-literal")
        return updated_node

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.BaseExpression:
        name = original_node.value
        if original_node not in self.a.loads:
            return updated_node
        v1 = self.old(original_node, name)
        if v1 in WH and not self._dropped(original_node):
            if self.canvas(original_node):
                self.change("w-h")
                return parse(f"{self.cn(original_node)}.{WH[v1]}")
            self.need_wh = True
            self.todo("reads-wh")
            return updated_node.with_changes(value=v1)
        if v1 in CONSTANTS:
            return updated_node.with_changes(value=v1)
        if self.unit and name == "U" and not self.scope.is_local(original_node, name):
            return cst.Integer("1")
        if v1 and v1 not in MOVED and v1 not in CANVAS_NAMES and v1 != "polar":
            self.todo("removed-name", f"{v1} is gone in v2 (docs/api.md 16)", name)
        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        if original_node.attr.value != "parts" or original_node not in self.a.chain:
            return updated_node
        parent = self.a.parents.get(original_node)
        if (
            isinstance(parent, (cst.If, cst.While, cst.IfExp)) and parent.test is original_node
        ) or isinstance(parent, (cst.BooleanOperation, cst.UnaryOperation)):
            self.change("path-empty")
            return parse(f"(not {code(updated_node.value)}.empty)")
        self.todo("removed-name", "Path.parts is gone; build one P() and keep appending to it")
        return updated_node

    def _dropped(self, node: cst.CSTNode) -> bool:
        """Whether `node` sits in a module-level statement the rewrite deletes."""
        at: cst.CSTNode | None = node
        while at is not None and at not in self.drop_stmts:
            at = self.a.parents.get(at)
        return at is not None

    def leave_BinaryOperation(
        self, original_node: cst.BinaryOperation, updated_node: cst.BinaryOperation
    ) -> cst.BaseExpression:
        if not self.unit or not isinstance(original_node.operator, (cst.Multiply, cst.Divide)):
            return updated_node
        right_unit = self._is_unit(original_node.right)
        if right_unit:
            self.change("unit")
            return updated_node.left
        if isinstance(original_node.operator, cst.Multiply) and self._is_unit(original_node.left):
            self.change("unit")
            return updated_node.right
        return updated_node

    def _is_unit(self, node: cst.BaseExpression) -> bool:
        return (
            isinstance(node, cst.Name)
            and node.value == "U"
            and not node.lpar
            and not self.scope.is_local(node, "U")
        )

    # calls

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        out = self._call(original_node, updated_node)
        if isinstance(out, cst.Call) and star_then_positional(out):
            self.todo("star-args")
        return out

    def _call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        func = original_node.func
        name = dotted(func)
        if isinstance(func, cst.Name):
            if name in LINT_CALLS and not self.scope.is_local(original_node, name):
                self.todo("lint", f"{name}() is banned in designs (process state)")
            if name in ("sorted", "min", "max"):
                self._check_sort(original_node)
            if (
                name == "polar"
                and name not in self.a.module_bound
                and not self.scope.is_local(original_node, name)
            ):
                return self._polar(updated_node)
            self._helper_in_group(original_node)
            if name in self.scope.threaded and not self.scope.is_local(original_node, name):
                self.change("thread-s")
                canvas = cst.Arg(cst.Name(self.cn(original_node)))
                return updated_node.with_changes(args=[canvas, *updated_node.args])
            v1 = self.old(original_node, name)
            if v1:
                return self._v1_call(v1, original_node, updated_node)
            if name in self.a.default_rng_names:
                return self._generator("np_rng", original_node, updated_node)
            return updated_node
        if not isinstance(func, cst.Attribute):
            return updated_node
        attr, head = func.attr.value, dotted(func.value)
        if (
            attr == "sort"
            and not any(a.keyword for a in original_node.args)
            and self.colours.sorts_colours(func.value)
        ):
            self.todo("colour-order")
        if attr == "default_rng" and _np_random(self.a, head):
            return self._generator("np_rng", original_node, updated_node)
        if attr == "Random" and head in self.a.random_names:
            return self._generator("rng", original_node, updated_node)
        if head in self.a.random_names or (
            head.split(".")[0] in self.a.np_names and ".random" in f".{head}"
        ):
            self.todo("lint", f"{name}: randomness only from s.rng/s.np_rng/s.noise")
            return updated_node
        if head == "s" and self.scope.name(original_node) == "s":
            return self._canvas_call(attr, original_node, updated_node)
        if head.endswith(".s") and attr in V1_CANVAS_ATTRS - V2_CANVAS_ATTRS | {"path", "g"}:
            self.todo(
                "unknown-attr", f"{head}.{attr}(): canvas calls through an object are not converted"
            )
        return self._path_method(attr, updated_node)

    def _check_sort(self, call: cst.Call) -> None:
        pos, kw, _ = call_parts(call)
        if "key" in kw or not pos:
            return
        if self.colours.compares_colours([a.value for a in pos]):
            self.todo("colour-order")

    def _generator(self, kind: str, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, _ = call_parts(updated)
        seed = kw.get("seed") or (pos[0] if pos else None)
        if kind in ("rng", "noise") and seed is None and dotted(original.func) in self.a.old:
            key = "0"  # v1's rng() and Noise() default to seed 0
        elif seed is None:
            self.todo("unseeded")
            return updated
        else:
            key = arg_code(seed)
        if not self.canvas(original):
            self.todo("generator")
            return updated
        self.change("generator")
        return parse(f"{self.cn(original)}.{kind}({key})")

    def _v1_call(self, v1: str, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        if v1 == "rng":
            return self._generator("rng", original, updated)
        if v1 == "Noise":
            return self._generator("noise", original, updated)
        if v1 == "is_light":
            if self.canvas(original):
                self.change("is-light")
                return parse(f"{self.cn(original)}.light")
            self.todo("is-light")
            return updated
        if v1 == "accent_ramp":
            return self._accent_ramp(original, updated)
        if v1 == "polar":
            return self._polar(updated)
        if v1 in MOVED:
            module, new = MOVED[v1]
            self.use(new, module)
            self.change(f"{module.split('.')[1]}-helper")
            convert = getattr(self, f"_{v1}", None)
            if convert is None:
                return updated
            result = convert(original, updated)
            if result is updated:
                if not _needs_canvas(self.a, original):
                    self.todo("helper-change", f"{v1}() arguments changed (docs/api.md 16)")
                elif self.canvas(original):
                    self.todo("generator", f"{v1}() takes a generator from s.np_rng(key) now")
                else:
                    self.todo("generator")
            return result
        return updated

    def _polar(self, call: cst.Call) -> cst.BaseExpression:
        pos, kw, _ = call_parts(call)
        if kw:
            return call
        if len(pos) == 4 and not any(a.star for a in pos):
            centre, r, angle = f"({arg_code(pos[0])}, {arg_code(pos[1])})", pos[2], pos[3]
        elif len(pos) == 3 and pos[0].star == "*" and not any(a.star for a in pos[1:]):
            centre, r, angle = arg_code(pos[0]), pos[1], pos[2]
        else:
            return call
        self.change("polar")
        return parse(f"polar({centre}, {arg_code(r)}, {self._angle(angle.value)})")

    def _angle(self, node: cst.BaseExpression) -> str:
        """`deg=x` for math.radians(x) and friends, else `rad=<node>`."""
        degrees = ("math.radians", "np.radians", "np.deg2rad", "numpy.radians")
        if isinstance(node, cst.Call) and len(node.args) == 1 and dotted(node.func) in degrees:
            return f"deg={arg_code(node.args[0])}"
        return f"rad={code(node)}"

    def _accent_ramp(self, original: cst.Call, call: cst.Call) -> cst.BaseExpression:
        pos, kw, _ = call_parts(call)
        n = kw.get("n") or (pos[0] if pos else None)
        if n is None:
            return call
        lo = kw.get("lo") or (pos[1] if len(pos) > 1 else None)
        hi = kw.get("hi") or (pos[2] if len(pos) > 2 else None)
        lo_code, hi_code = (arg_code(lo) if lo else "BG"), (arg_code(hi) if hi else "ACCENT")
        for tok, given in (("BG", lo), ("ACCENT", hi), ("ACCENT_4", None)):
            if given is None:
                self.use(tok)
        self.use("ladder")
        self.change("accent-ramp")
        ladder = f"ladder(({lo_code}, ACCENT_4, {hi_code}), {arg_code(n)})"
        if self._list_operand(original):
            return parse(f"list({ladder})")  # v1 returned a list, and it is added to one here
        return parse(ladder)

    def _list_operand(self, node: cst.CSTNode) -> bool:
        """Whether `node` (or a slice of it) is an operand of `+`, where a tuple would fail."""
        parent = self.a.parents.get(node)
        while isinstance(parent, cst.Subscript):
            node, parent = parent, self.a.parents.get(parent)
        return isinstance(parent, cst.BinaryOperation) and isinstance(parent.operator, cst.Add)

    def _canvas_rng(self, original: cst.Call, seed: str) -> str | None:
        return f"{self.cn(original)}.np_rng({seed})" if self.canvas(original) else None

    def _noise_grid(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if len(pos) < 3 or any(a.star for a in pos):
            return updated
        seed = kw.pop("seed", None) or (pos[3] if len(pos) > 3 else None)
        if splat:
            # the v1 padding wrappers pass seed= through **kw; pull it out for the generator
            kwargs = self._star_kwarg(original)
            if seed or len(splat) != 1 or kwargs is None or arg_code(splat[0]) != kwargs:
                return updated
            rng = self._canvas_rng(original, f'{kwargs}.pop("seed", 0)')
            if rng is None:
                return updated
            args = [
                *(arg_code(a) for a in pos),
                rng,
                *(f"{k}={arg_code(v)}" for k, v in kw.items()),
            ]
            return parse(f"noise_grid({', '.join(args)}, **{kwargs})")
        rng = self._canvas_rng(original, arg_code(seed) if seed else "0")
        if rng is None:
            return updated
        args = [arg_code(a) for a in pos[:3]] + [rng]
        for i, key in ((4, "octaves"), (5, "gain")):
            value = kw.pop(key, None) or (pos[i] if len(pos) > i else None)
            if value is not None:
                args.append(f"{key}={arg_code(value)}")
        args += [f"{k}={arg_code(v)}" for k, v in kw.items()]
        return parse(f"noise_grid({', '.join(args)})")

    def _star_kwarg(self, node: cst.CSTNode) -> str | None:
        """The name of the **kwargs parameter of the function around `node`, if any."""
        chain = self.a.chain.get(node, ())
        star = chain[-1].params.star_kwarg if chain else None
        return star.name.value if star is not None else None

    def _blue_noise(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if splat or any(a.star for a in pos):
            return updated
        n = kw.pop("n", None) or (pos[0] if pos else None)
        seed = kw.pop("seed", None) or (pos[1] if len(pos) > 1 else None)
        sigma = kw.pop("sigma", None) or (pos[2] if len(pos) > 2 else None)
        rng = self._canvas_rng(original, arg_code(seed) if seed else "0")
        if rng is None:
            return updated
        args = [arg_code(n) if n else "64", rng] + ([f"sigma={arg_code(sigma)}"] if sigma else [])
        return parse(f"blue_noise({', '.join(args)})")

    def _threshold_matrix(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if splat or not pos or any(a.star for a in pos):
            return updated
        method = kw.pop("method", None) or pos[0]
        size = kw.pop("size", None) or (pos[1] if len(pos) > 1 else None)
        seed = kw.pop("seed", None) or (pos[2] if len(pos) > 2 else None)
        args = [arg_code(method), arg_code(size) if size else "4"]
        if _rng_method(original, "threshold_matrix") is not False:
            rng = self._canvas_rng(original, arg_code(seed) if seed else "0")
            if rng is None:
                return updated
            args.append(rng)
        return parse(f"threshold_matrix({', '.join(args)})")

    def _dither(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if splat or len(pos) + len(kw) < 4 or any(a.star for a in pos):
            return updated
        names = ["value", "cols", "rows", "levels", "method", "matrix", "seed", "serpentine"]
        got = {names[i]: a for i, a in enumerate(pos)} | kw
        if set(got) - set(names) or not {"value", "cols", "rows", "levels"} <= set(got):
            return updated
        field_code = self._dither_field(got["value"].value, got["cols"].value, got["rows"].value)
        args = [field_code, arg_code(got["levels"])]
        for key in ("method", "matrix"):
            if key in got:
                args.append(f"{key}={arg_code(got[key])}")
        if _rng_method(original, "dither") is not False:
            seed = got.get("seed")
            rng = self._canvas_rng(original, arg_code(seed) if seed else "0")
            if rng is None:
                return updated
            args.append(f"rng={rng}")
        if "serpentine" in got:
            args.append(f"serpentine={arg_code(got['serpentine'])}")
        return parse(f"dither({', '.join(args)})")

    def _dither_field(
        self, value: cst.BaseExpression, cols: cst.BaseExpression, rows: cst.BaseExpression
    ) -> str:
        """v1's value(col, row) callback as the (rows, cols) array v2 takes."""
        c, r = code(cols), code(rows)
        if isinstance(value, cst.Lambda) and len(value.params.params) == 2:
            i, j = (p.name.value for p in value.params.params)
            vector = _vectorise(value.body, i, j, r, c)
            if vector is not None:
                return vector
            self.need_numpy = True
            body = code(value.body)
            return f"np.array([[{body} for {i} in range({c})] for {j} in range({r})], dtype=float)"
        self.need_numpy = True
        fn = code(value)
        i, j = ("i", "j") if not re.search(r"\b[ij]\b", c + r + fn) else ("col", "row")
        return (
            f"np.array([[{fn}({i}, {j}) for {i} in range({c})] for {j} in range({r})], dtype=float)"
        )

    def _glyphs(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if "at" in kw or any(a.star for a in pos) or len(pos) < 3:
            return updated
        names = ["s", "lines", "color", "font", "px", "x", "y", "gap", "key"]
        got = {names[i]: a for i, a in enumerate(pos) if i < len(names)} | kw
        if len(pos) > len(names):
            return updated
        paint = got.pop("color", None) or got.pop("colour", None)
        if paint is None:
            return updated
        x, y = got.pop("x", None), got.pop("y", None)
        args = [arg_code(got.pop("s")), arg_code(got.pop("lines")), arg_code(paint)]
        args.append(f"at=({arg_code(x) if x else '0'}, {arg_code(y) if y else '0'})")
        args += [f"{k}={arg_code(v)}" for k, v in got.items()]
        args += [f"**{arg_code(a)}" for a in splat]
        return parse(f"glyphs({', '.join(args)})")

    def _sprite(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if "origin" in kw or any(a.star for a in pos) or len(pos) + len(kw) < 4 or len(pos) > 6:
            return updated
        names = ["s", "art", "palette", "cell", "x", "y"]
        got = {names[i]: a for i, a in enumerate(pos)} | kw
        x, y = got.pop("x", None), got.pop("y", None)
        args = [arg_code(got.pop(k)) for k in ("s", "art", "palette", "cell") if k in got]
        if len(args) < 4:
            return updated
        if x or y:
            args.append(f"({arg_code(x) if x else '0'}, {arg_code(y) if y else '0'})")
        args += [f"{k}={arg_code(v)}" for k, v in got.items()]
        args += [f"**{arg_code(a)}" for a in splat]
        return parse(f"sprite({', '.join(args)})")

    def _grid_runs(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if "origin" in kw or any(a.star for a in pos) or len(pos) > 7:
            return updated
        names = ["s", "grid", "colors", "cell", "ox", "oy", "skip"]
        got = {names[i]: a for i, a in enumerate(pos)} | kw
        if not {"s", "grid", "colors", "cell"} <= set(got):
            return updated
        grid = got.pop("grid").value
        if (
            isinstance(grid, cst.Call)
            and isinstance(grid.func, cst.Attribute)
            and grid.func.attr.value == "tolist"
            and not grid.args
        ):
            grid = grid.func.value  # v2 takes arrays
        ox, oy = got.pop("ox", None), got.pop("oy", None)
        args = [arg_code(got.pop("s")), code(grid), arg_code(got.pop("colors")), "cell="]
        args[-1] = arg_code(got.pop("cell"))
        if ox or oy:
            args.append(f"({arg_code(ox) if ox else '0'}, {arg_code(oy) if oy else '0'})")
        args += [f"{k}={arg_code(v)}" for k, v in got.items()]
        args += [f"**{arg_code(a)}" for a in splat]
        return parse(f"grid_runs({', '.join(args)})")

    def _contours(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if splat or any(a.star for a in pos) or len(pos) > 5:
            return updated
        names = ["field", "level", "cell", "ox", "oy"]
        got = {names[i]: a for i, a in enumerate(pos)} | kw
        if not {"field", "level"} <= set(got) or set(got) - set(names):
            return updated
        args = [arg_code(got["field"]), arg_code(got["level"])]
        if "cell" in got:
            args.append(f"cell={arg_code(got['cell'])}")
        if "ox" in got or "oy" in got:
            ox, oy = got.get("ox"), got.get("oy")
            args.append(f"origin=({arg_code(ox) if ox else '0'}, {arg_code(oy) if oy else '0'})")
        self.todo("helper-change", "iso_lines returns (N, 2) arrays; check how lines are used")
        return parse(f"iso_lines({', '.join(args)})")

    def _sample_field(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if kw or splat or len(pos) != 3 or any(a.star for a in pos):
            return updated
        self.need_numpy = True
        self.todo("helper-change", "sample_field calls fn once with index arrays; vectorise fn")
        return parse(
            f"sample_field(np.vectorize({arg_code(pos[0])}), {arg_code(pos[1])}, {arg_code(pos[2])})"
        )

    def _poisson_disk(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if splat or any(a.star for a in pos) or len(pos) > 7:
            return updated
        names = ["r", "width", "height", "radius", "k", "x0", "y0"]
        got = {names[i]: a for i, a in enumerate(pos)} | kw
        if not {"r", "width", "height", "radius"} <= set(got) or set(got) - set(names):
            return updated
        x0, y0 = got.get("x0"), got.get("y0")
        rect = (
            f"Rect({arg_code(x0) if x0 else '0'}, {arg_code(y0) if y0 else '0'}, "
            f"{arg_code(got['width'])}, {arg_code(got['height'])})"
        )
        args = [rect, arg_code(got["radius"]), arg_code(got["r"])]
        if "k" in got:
            args.append(f"k={arg_code(got['k'])}")
        self.use("Rect")
        call = f"poisson_disk({', '.join(args)})"
        if self._list_ops_on_result(original):
            # v1 returned a list of (x, y) tuples, and this design uses it as one
            return parse(f"[(x, y) for x, y in {call}.tolist()]")
        return parse(call)

    def _list_ops_on_result(self, call: cst.Call) -> bool:
        parent = self.a.parents.get(call)
        target = None
        if isinstance(parent, cst.Assign) and len(parent.targets) == 1:
            target = parent.targets[0].target
        if not isinstance(target, cst.Name):
            return False
        name = target.value
        chain = self.a.chain.get(call, ())
        scope_node: cst.CSTNode = chain[-1] if chain else cst.Module(body=[])
        found = False

        class Finder(cst.CSTVisitor):
            def visit_Call(self, node: cst.Call) -> None:
                nonlocal found
                f = node.func
                mutators = ("append", "extend", "insert", "pop", "remove", "sort")
                if (
                    isinstance(f, cst.Attribute)
                    and dotted(f.value) == name
                    and f.attr.value in mutators
                ):
                    found = True
                if (
                    dotted(f).endswith("shuffle")
                    and node.args
                    and dotted(node.args[0].value) == name
                ):
                    found = True

            def visit_BinaryOperation(self, node: cst.BinaryOperation) -> None:
                nonlocal found
                if isinstance(node.operator, cst.Add) and name in (
                    dotted(node.left),
                    dotted(node.right),
                ):
                    found = True

        scope_node.visit(Finder())
        return found

    # canvas methods

    def _canvas_call(self, attr: str, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        parent = self.a.parents.get(original)
        statement = isinstance(parent, cst.Expr)
        if attr == "g":
            return self._group(original, updated)
        if attr == "group":
            self._group_ctx(updated, v1=False)
            return updated
        if attr in ("clip", "mask") and original.args:
            self.todo("raw-markup")
            return updated
        if attr == "pattern" and len(original.args) >= 3:
            self.todo("raw-markup")
            return updated
        if attr in ("text", "raw", "el", "defs", "uid"):
            self.todo("removed-name", f"s.{attr}() is gone in v2 (docs/api.md 16)")
            return updated
        if attr in ("linear_gradient", "radial_gradient"):
            return self._gradient(attr, updated)
        if attr in ("rect", "circle", "ellipse", "line", "polygon", "polyline", "path"):
            if not statement:
                if attr != "path":
                    self.todo("raw-markup")
                return updated
            return self._draw(attr, original, updated)
        if attr not in V2_CANVAS_ATTRS:
            self.todo("removed-name", f"s.{attr}() is gone in v2 (docs/api.md 16)")
        return updated

    def _helper_in_group(self, call: cst.Call) -> None:
        ctx = self._ctx()
        if ctx.v1_fill:
            name = dotted(call.func)
            fn = self.a.module_funcs.get(name)
            if fn is not None and fn in self.scope.canvas_fns and fn is not self.scope.draw:
                self.todo("group-fill")

    def _ctx(self) -> GroupCtx:
        out = GroupCtx()
        for g in self.groups:
            if g is None:
                continue
            if g.fill is not None:
                out.fill, out.v1_fill = g.fill, g.v1_fill
            out.stroke |= g.stroke
            out.width |= g.width
        return out

    def visit_With(self, node: cst.With) -> None:
        is_group = any(
            isinstance(item.item, cst.Call)
            and dotted(item.item.func) in ("s.g", "s.group")
            and self.canvas(item.item)
            for item in node.items
        )
        self.groups.append(GroupCtx() if is_group else None)

    def leave_With(self, original_node: cst.With, updated_node: cst.With) -> cst.With:
        self.groups.pop()
        return updated_node

    def _group_ctx(self, call: cst.Call, *, v1: bool, fill: str | None = None) -> None:
        if self.groups and self.groups[-1] is not None:
            _, kw, _ = call_parts(call)
            ctx = self.groups[-1]
            ctx.fill, ctx.v1_fill = fill, v1 and fill is not None
            ctx.stroke, ctx.width = "stroke" in kw, "stroke_width" in kw

    def _group(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        parent = self.a.parents.get(original)
        if pos or not isinstance(parent, cst.WithItem):
            self.todo("removed-name", "s.g() outside a with block: use `with s.group(...)`")
            return updated
        fill = kw.pop("fill", None)
        args = self._style_args(kw)
        args += [f"**{arg_code(a)}" for a in splat]
        if splat:
            self.todo("splat-style")
        self._group_ctx(updated, v1=True, fill=arg_code(fill) if fill else None)
        if fill is not None:
            self.change("group-fill")
        self.change("group")
        return parse(f"s.group({', '.join(args)})")

    def _style_args(self, kw: dict[str, cst.Arg]) -> list[str]:
        """Style keyword arguments as v2 code, converting values v1 wrote as strings."""
        out = []
        for key, arg in kw.items():
            value = self._style_value(key, arg.value)
            if key not in STYLE_KEYS:
                self.todo("unknown-attr", f"{key}= has no v2 equivalent")
            out.append(f"{key}={value}")
        return out

    def _style_value(self, key: str, node: cst.BaseExpression) -> str:
        if key == "transform":
            if isinstance(node, (cst.SimpleString, cst.FormattedString, cst.ConcatenatedString)):
                affine = affine_code(node)
                if affine is not None:
                    self.use("Affine", "walldye.geom")
                    self.change("transform")
                    return affine
            if not _is_affine(node):
                self.todo("transform")
            return code(node)
        if key == "stroke_dasharray":
            if isinstance(node, cst.Name) and node.value in self.dash_consts:
                return code(node)
            dash = dash_code(node) if not isinstance(node, (cst.Tuple, cst.List)) else code(node)
            if dash is None:
                self.todo("dasharray")
                return code(node)
            if dash != code(node):
                self.change("dasharray")
            return dash
        if key in NUMERIC_KEYS:
            num = numeric_code(node)
            if num is None:
                self.todo("unknown-attr", f"{key}= is a string; v2 takes a number")
                return code(node)
            return num
        if key in ("stroke", "fill"):
            text = string_value(node)
            if text is not None and text != "none":
                self.todo("hex-literal")
        return code(node)

    def _gradient(self, attr: str, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if splat or not pos or pos[0].star:
            return updated
        linear = attr == "linear_gradient"
        names = ["x1", "y1", "x2", "y2"] if linear else ["cx", "cy", "r"]
        units = kw.pop("units", None)
        if len(pos) > 1 and string_value(pos[-1].value) is not None:
            units = pos.pop()  # v1 took units positionally after the geometry
        units_text = string_value(units.value) if units else None
        v2 = (
            len(pos) == 3
            and not any(a.star for a in pos)
            and not set(kw) & set(names)
            and units_text in (None, "user", "bbox")
        )
        if v2 or set(kw) - set(names):
            return updated
        if units is not None and units_text not in ("userSpaceOnUse", "objectBoundingBox"):
            self.todo("unknown-attr", "gradient units must be 'user' or 'bbox'")
            return updated
        values = [arg_code(a) for a in pos[1:]]
        stars = [a.star == "*" for a in pos[1:]]
        defaults = ["0", "0", "0", "1"] if linear else ["0.5", "0.5", "0.5"]
        if any(stars):
            geometry = _points(values, stars, "pp" if linear else "pn")
            if geometry is None or kw:
                return updated
        else:
            if len(values) > len(names):
                return updated
            got = dict(zip(names, values)) | {k: arg_code(v) for k, v in kw.items()}
            flat = [got.get(n, d) for n, d in zip(names, defaults)]
            geometry = [f"({flat[0]}, {flat[1]})"] + (
                [f"({flat[2]}, {flat[3]})"] if linear else [flat[2]]
            )
        args = [arg_code(pos[0]), *geometry]
        if units_text != "userSpaceOnUse":
            args.append('units="bbox"')
        self.change("gradient")
        return parse(f"s.{attr}({', '.join(args)})")

    def _draw(self, attr: str, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        pos, kw, splat = call_parts(updated)
        if attr == "path":
            if not pos:
                return updated
            d_node = unwrap_fmt(pos[0].value)
            if isinstance(
                d_node, (cst.SimpleString, cst.FormattedString, cst.ConcatenatedString)
            ) or (isinstance(d_node, (cst.BinaryOperation, cst.Call)) and _stringy(d_node)):
                self.todo("string-path")
            d = code(d_node)
            if len(pos) > 1:
                return updated
        else:
            d = self._element_path(attr, pos, kw)
            if d is None:
                self.todo("unknown-attr", f"s.{attr}() with these arguments; rebuild with P()")
                return updated
            self.use("P")
            self.change("element")
        default_fill = "none" if attr in ("line", "polyline") else None
        result = self._paint(d, kw, splat, default_fill, original)
        if _same(result, updated):
            return updated
        if dotted(result.func) == "s.path" if isinstance(result, cst.Call) else False:
            self.change("path")
        return result

    def _element_path(self, attr: str, pos: list[cst.Arg], kw: dict[str, cst.Arg]) -> str | None:
        """The P() builder for a v1 element call, consuming its geometry arguments."""
        geometry = {
            "rect": ["x", "y", "w", "h"],
            "circle": ["cx", "cy", "r"],
            "ellipse": ["cx", "cy", "rx", "ry"],
            "line": ["x1", "y1", "x2", "y2"],
            "polygon": ["points", "nd"],
            "polyline": ["points", "nd"],
        }[attr]
        if attr in ("polygon", "polyline"):
            points = kw.pop("points", None) or (pos[0] if pos else None)
            nd = kw.pop("nd", None) or (pos[1] if len(pos) > 1 else None)
            if points is None or len(pos) > 2 or points.star:
                return None
            closed = ", closed=True" if attr == "polygon" else ""
            return f"P({arg_code(nd) if nd else ''}).poly({arg_code(points)}{closed})"
        slots = [a.value if not a.star else a for a in pos]
        for name in geometry[len(pos) :]:
            if name in kw:
                slots.append(kw.pop(name).value)
        rx = kw.pop("rx", None) if attr == "rect" else None
        if attr == "rect" and "ry" in kw:
            return None
        values = [code(v.value) if isinstance(v, cst.Arg) else code(v) for v in slots]
        stars = [isinstance(v, cst.Arg) for v in slots]
        if attr == "rect":
            if sum(stars) > 1 or len(slots) > 4 or (not any(stars) and len(slots) != 4):
                return None
            args = ", ".join(("*" if st else "") + v for v, st in zip(values, stars))
            if rx is not None:
                return f"P().rrect({args}, {arg_code(rx)})"
            return f"P().rect({args})"
        if attr == "line" and len(values) == 4 and not any(stars):
            return f"P().M({values[0]}, {values[1]}).L({values[2]}, {values[3]})"
        shape = {"circle": "pn", "ellipse": "pnn", "line": "pp"}[attr]
        pts = _points(values, stars, shape)
        if pts is None:
            return None
        if attr == "line":
            return f"P().M({pts[0]}).L({pts[1]})"
        return f"P().{attr}({', '.join(pts)})"

    def _paint(
        self,
        d: str,
        kw: dict[str, cst.Arg],
        splat: list[cst.Arg],
        default_fill: str | None,
        original: cst.Call,
    ) -> cst.BaseExpression:
        """s.stroke / s.fill / s.path for path data `d` with v1 keyword arguments `kw`."""
        ctx = self._ctx()
        kw = {k: a for k, a in kw.items() if code(a.value) != "None"}  # v1 skipped None values
        fill_arg = kw.pop("fill", None)
        fill = self._style_value("fill", fill_arg.value) if fill_arg else None
        if fill is None and ctx.fill is not None:
            fill = ctx.fill
            self.change("group-fill")
        if fill is None and default_fill is not None and not splat:
            fill = f'"{default_fill}"'
        style = {k: self._style_value(k, a.value) for k, a in kw.items()}
        for k in style:
            if k not in STYLE_KEYS:
                self.todo("unknown-attr", f"{k}= has no v2 equivalent")
        if style.get("stroke") == '"none"' and not ctx.stroke:
            del style["stroke"]
        if splat:
            self.todo("splat-style")
            args = [d] + ([f"fill={fill}"] if fill else []) + [f"{k}={v}" for k, v in style.items()]
            args += [f"**{arg_code(a)}" for a in splat]
            return parse(f"s.path({', '.join(args)})")
        if fill is None:
            if "stroke" in style or ctx.stroke:
                self.change("implicit-fill-dropped")
            else:
                self.todo("fill-default")
            fill = '"none"'
        rest = set(style) - {"stroke", "stroke_width"}
        # Without a width v1 drew 1 px, unless a group set one: only draw's own body is sure
        # to be outside every group, since a helper can be called from inside one.
        direct = self.a.chain.get(original) == (self.scope.draw,)
        if (
            fill == '"none"'
            and "stroke" in style
            and ("stroke_width" in style or (direct and not ctx.width))
            and rest <= {*STROKE_KEYS, "opacity"}
        ):
            args = [d, style["stroke"], style.get("stroke_width", "1")]
            args += [f"{STROKE_KEYS.get(k, k)}={style[k]}" for k in style if k in rest]
            self.change("stroke")
            return parse(f"s.stroke({', '.join(args)})")
        if (
            fill != '"none"'
            and "stroke" not in style
            and "stroke_width" not in style
            and set(style) <= {"fill_rule", "opacity"}
        ):
            args = [d, fill]
            if "fill_rule" in style:
                args.append(f"rule={style['fill_rule']}")
            if "opacity" in style:
                args.append(f"opacity={style['opacity']}")
            self.change("fill")
            return parse(f"s.fill({', '.join(args)})")
        args = [d, f"fill={fill}"] + [f"{k}={v}" for k, v in style.items()]
        return parse(f"s.path({', '.join(args)})")

    # path builder methods

    def _path_method(self, attr: str, call: cst.Call) -> cst.BaseExpression:
        """P() builder calls, rewritten in place so the receiver keeps its layout."""
        if attr not in ("poly", "smooth", "spline", "dots", "arc_band", "M", "L", "A", "C", "Q"):
            return call
        pos, kw, splat = call_parts(call)
        before = list(pos)
        if attr in ("poly", "smooth", "spline", "dots") and pos and not pos[0].star:
            points = _listed(pos[0].value)
            if points is not None:
                # v2 reads points as an (N, 2) array; v1 iterated anything
                self.change("points-list")
                pos[0] = pos[0].with_changes(value=parse(points))
        if attr == "smooth" and not splat and len(pos) <= 3:
            self.change("spline")
            named = [_keyword(k, a) for k, a in zip(("closed", "tension"), pos[1:])]
            return _with_args(call, "spline", [*pos[:1], *named, *kw.values()])
        if attr == "poly" and len(pos) == 2 and not pos[1].star and not kw:
            self.change("poly-closed")
            return _with_args(call, "poly", [pos[0], _keyword("closed", pos[1])])
        if attr == "arc_band" and len(pos) == 6 and not kw and not any(a.star for a in pos):
            cx, cy, r0, r1, a0, a1 = (arg_code(a) for a in pos)
            self.todo("arc-band")
            self.change("arc-band")
            args = _args(f"({cx}, {cy}), {r0}, {r1}, rad=({a0}, {a1})")
            return _with_args(call, "arc_band", args)
        if attr in ("M", "L", "A", "C", "Q") and not kw and not splat:
            pos = self._path_command(attr, pos)
        if all(a is b for a, b in zip(pos, before, strict=True)):
            return call
        return _with_args(call, attr, [*pos, *kw.values(), *splat])

    def _path_command(self, attr: str, pos: list[cst.Arg]) -> list[cst.Arg]:
        """Starred points passed as points, and arc flags as v2 takes them."""
        stars = [a.star == "*" for a in pos]
        out = list(pos)
        if attr == "A" and len(pos) >= 5 and not any(stars[:5]):
            for i in (3, 4):
                flag = _flag(pos[i].value)
                if flag is not None:
                    out[i] = pos[i].with_changes(value=parse(flag))
            if len(pos) == 6 and stars[5]:
                out[5] = pos[5].with_changes(star="")
        elif attr in ("M", "L") and len(pos) == 1 and stars[0]:
            out[0] = pos[0].with_changes(star="")
        elif attr in ("C", "Q") and all(stars) and len(pos) == (3 if attr == "C" else 2):
            out = [a.with_changes(star="") for a in pos]
        if any(a is not b for a, b in zip(out, pos)):
            self.change("path-command")
        return out

    # statements

    def leave_IfExp(self, original_node: cst.IfExp, updated_node: cst.IfExp) -> cst.BaseExpression:
        test = original_node.test
        if (
            isinstance(test, cst.Call)
            and self.old(test, dotted(test.func)) == "is_light"
            and self.canvas(test)
            and self.colours.colour(original_node.body)
            and self.colours.colour(original_node.orelse)
        ):
            self.use("by_regime")
            self.change("by-regime")
            return parse(f"by_regime({code(updated_node.orelse)}, {code(updated_node.body)})")
        return updated_node

    def leave_Global(self, original_node: cst.Global, updated_node: cst.Global) -> cst.Global:
        self.todo("lint", "global statements are banned in designs")
        return updated_node

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        node = updated_node
        is_module = self.a.module_funcs.get(original_node.name.value) is original_node
        if original_node in self.scope.canvas_fns:
            node = _annotate_canvas(node)
        param = self.scope.threaded.get(original_node.name.value) if is_module else None
        if param is not None:
            canvas = cst.Param(cst.Name(param), annotation=cst.Annotation(cst.Name("Canvas")))
            params = node.params.with_changes(params=[canvas, *node.params.params])
            node = node.with_changes(params=params)
            self.change("thread-s-def")
        if is_module and original_node is self.scope.draw:
            node = self._decorate(node)
        if original_node in self.scope.canvas_fns or (
            is_module and original_node.name.value in self.scope.threaded
        ):
            self.use("Canvas")
        return node

    def _decorate(self, node: cst.FunctionDef) -> cst.FunctionDef:
        if any(dotted(_decorator_name(d)) == "design" for d in node.decorators):
            return node
        args = []
        if self.aspects is not None:
            args.append(f"aspects={self.aspects}")
        else:
            self.todo("aspects")
        if self.bg is not None:
            args.append(f"bg={self.bg}")
        self.use("design")
        self.change("decorator")
        deco = cst.Decorator(decorator=parse(f"design({', '.join(args)})"))
        if node.returns is None:
            node = node.with_changes(returns=cst.Annotation(cst.Name("None")))
        return node.with_changes(decorators=[deco, *node.decorators])

    def visit_Module(self, node: cst.Module) -> None:
        self._module_decisions(node)

    def _module_decisions(self, node: cst.Module) -> None:
        """ASPECTS, the v1 unit U and BG: what becomes decorator arguments or disappears."""
        for stmt in node.body:
            if not isinstance(stmt, cst.SimpleStatementLine) or len(stmt.body) != 1:
                continue
            small = stmt.body[0]
            if not (
                isinstance(small, cst.Assign)
                and len(small.targets) == 1
                and isinstance(small.targets[0].target, cst.Name)
            ):
                continue
            name = small.targets[0].target.value
            if name == "U" and re.sub(r"\s", "", code(small.value)) == "min(W,H)/1080":
                self.unit = True
                self.drop_stmts.add(stmt)
                self.change("unit")
            elif name == "ASPECTS" and len(self.a.module_assigns.get(name, [])) == 1:
                aspects = self._aspects(small.value)
                if aspects is not None and not self._referenced(name):
                    self.aspects = aspects
                    self.drop_stmts.add(stmt)
                    self.change("aspects")
            elif name == "BG" and self.scope.draw is not None:
                if any(dotted(_decorator_name(d)) == "design" for d in self.scope.draw.decorators):
                    continue
                if not self._referenced(name):
                    self.bg = code(small.value)
                    self.drop_stmts.add(stmt)
                elif isinstance(small.value, cst.Name) and small.value.value in TOKENS:
                    self.bg = small.value.value
                else:
                    self.bg = "BG"
                self.change("bg")

    def _aspects(self, value: cst.BaseExpression) -> str | None:
        if not isinstance(value, (cst.List, cst.Tuple)):
            return None
        items = [string_value(e.value) for e in value.elements]
        if any(i is None for i in items) or not items:
            return None
        if items == ["any"]:
            return '"any"'
        quoted = ", ".join(json.dumps(i) for i in items)
        return f"({quoted},)" if len(items) == 1 else f"({quoted})"

    def _referenced(self, name: str) -> bool:
        return any(n.value == name and n in self.a.loads for n in self.a.names)

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        body: list[cst.BaseStatement] = []
        carry: list[cst.EmptyLine] = []  # comments above deleted statements, kept for the next one
        import_at, import_lines = None, []
        for old, new in zip(original_node.body, updated_node.body, strict=True):
            if old in self.drop_stmts:
                carry += new.leading_lines
                continue
            if isinstance(new, cst.SimpleStatementLine) and isinstance(
                new.body[0], (cst.Import, cst.ImportFrom)
            ):
                kept = self._rewrite_imports(new)
                if kept is None:
                    import_lines += [*carry, *new.leading_lines]
                    carry = []
                    import_at = len(body) if import_at is None else import_at
                    continue
                new = kept
            if carry:
                new = new.with_changes(leading_lines=[*carry, *new.leading_lines])
                carry = []
            body.append(new)
        constants = self._constants()  # first: they add the tokens they need to the imports
        body[import_at or 0 : import_at or 0] = self._import_lines(import_lines)
        last = max((i for i, st in enumerate(body) if _is_import(st)), default=-1)
        body[last + 1 : last + 1] = constants
        return updated_node.with_changes(body=body)

    def _rewrite_imports(self, stmt: cst.SimpleStatementLine) -> cst.SimpleStatementLine | None:
        """None for `from __future__`, `from wallgen import ...` and `from walldye[.x] import
        ...` (their v2 names are collected to import again), else `stmt` unchanged."""
        small = stmt.body[0]
        if not isinstance(small, cst.ImportFrom) or isinstance(small.names, cst.ImportStar):
            return stmt
        module = code(small.module) if small.module else ""
        if module == "__future__":
            self.change("future-import")
            return None
        if module not in OLD_MODULES and module not in NEW_MODULES:
            return stmt
        if module == "wallgen" or any(code(a.name) in self.a.old.values() for a in small.names):
            self.change("imports")
        for alias in small.names:
            name = code(alias.name)
            if module in NEW_MODULES[1:]:
                self.imports[module].add(name)
            elif name in CORE:
                self.imports["walldye"].add(name)
            # v1-only names are imported again only if a converted call needs them
        return None

    def _constants(self) -> list[cst.SimpleStatementLine]:
        out = []
        if self.need_wh:
            stmt = cst.parse_statement("W, H = 1920, 1080\n")
            assert isinstance(stmt, cst.SimpleStatementLine)
            out.append(
                stmt.with_changes(
                    leading_lines=[
                        cst.EmptyLine(
                            comment=cst.Comment(f"# TODO(port): module-wh: {TODO['module-wh']}")
                        )
                    ]
                )
            )
        for name, (value, needs) in CONSTANTS.items():
            if name in self.a.old.values() and any(
                n.value == name and n in self.a.loads for n in self.a.names
            ):
                for tok in needs:
                    self.use(tok)
                self.change("constant")
                stmt = cst.parse_statement(f"{name} = {value}\n")
                assert isinstance(stmt, cst.SimpleStatementLine)
                out.append(stmt)
        return out

    def _import_lines(self, leading: list[cst.EmptyLine]) -> list[cst.SimpleStatementLine]:
        """The v2 imports, carrying `leading` (the comments above the old ones) and the
        module-level TODOs."""
        out = []
        if self.need_numpy and not self.a.np_names:
            out.append(cst.parse_statement("import numpy as np\n"))
        for module in NEW_MODULES:
            names = sorted(self.imports[module])
            for n in names:
                if n in self.a.module_bound and n not in self.a.old:
                    self.module_todos.append(("name-clash", f"{n} is imported and defined here"))
            if names:
                out.append(cst.parse_statement(f"from {module} import {', '.join(names)}\n"))
        lines = [st for st in out if isinstance(st, cst.SimpleStatementLine)]
        if not lines:
            return lines
        have = {ln.comment.value for ln in leading if ln.comment is not None}
        todos = [f"# TODO(port): {kind}: {text}" for kind, text in dict.fromkeys(self.module_todos)]
        comments = [cst.EmptyLine(comment=cst.Comment(c)) for c in todos if c not in have]
        lines[0] = lines[0].with_changes(leading_lines=[*leading, *comments])
        return lines


def _is_import(st: cst.BaseStatement) -> bool:
    return isinstance(st, cst.SimpleStatementLine) and isinstance(
        st.body[0], (cst.Import, cst.ImportFrom)
    )


def _same(a: cst.CSTNode, b: cst.CSTNode) -> bool:
    """Whether two nodes are the same code, up to layout (a trailing comma counts as layout)."""

    def bare(node: cst.CSTNode) -> str:
        return re.sub(r"\s+", "", code(node)).replace(",)", ")")

    return bare(a) == bare(b)


def _args(text: str) -> list[cst.Arg]:
    call = parse(f"f({text})")
    assert isinstance(call, cst.Call)
    return list(call.args)


def _keyword(name: str, arg: cst.Arg) -> cst.Arg:
    return _args(f"{name}={arg_code(arg)}")[0]


def _with_args(call: cst.Call, attr: str, args: list[cst.Arg]) -> cst.Call:
    """`call` with its method renamed to `attr` and new `args`, receiver untouched; commas are
    kept when the argument count is unchanged."""
    func = call.func
    assert isinstance(func, cst.Attribute)
    if len(args) == len(call.args):
        fixed = [a.with_changes(comma=old.comma) for a, old in zip(args, call.args)]
    else:
        comma = cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
        fixed = [a.with_changes(comma=comma) for a in args[:-1]] + args[-1:]
    return call.with_changes(func=func.with_changes(attr=cst.Name(attr)), args=fixed)


def _listed(node: cst.BaseExpression) -> str | None:
    """A one-shot iterable (zip, map, a generator) as list code, else None."""
    if isinstance(node, cst.GeneratorExp):
        return code(cst.ListComp(elt=node.elt, for_in=node.for_in))
    if isinstance(node, cst.Call) and dotted(node.func) in ("zip", "map", "reversed", "filter"):
        return f"list({code(node)})"
    return None


def _is_affine(node: cst.BaseExpression) -> bool:
    """Whether `node` is already v2 transform code: Affine calls composed with @."""
    if isinstance(node, cst.BinaryOperation) and isinstance(node.operator, cst.MatrixMultiply):
        return _is_affine(node.left) and _is_affine(node.right)
    return isinstance(node, cst.Call) and dotted(node.func).split(".")[0] == "Affine"


def _decorator_name(d: cst.Decorator) -> cst.BaseExpression:
    return d.decorator.func if isinstance(d.decorator, cst.Call) else d.decorator


def _annotate_canvas(fn: cst.FunctionDef) -> cst.FunctionDef:
    params = list(fn.params.params)
    if params and params[0].name.value == "s" and params[0].annotation is None:
        params[0] = params[0].with_changes(annotation=cst.Annotation(cst.Name("Canvas")))
        fn = fn.with_changes(params=fn.params.with_changes(params=params))
    return fn


def _stringy(node: cst.BaseExpression) -> bool:
    """Whether `node` builds a string: "".join(...), f-strings, or + with a string."""
    if isinstance(node, (cst.SimpleString, cst.FormattedString, cst.ConcatenatedString)):
        return True
    if isinstance(node, cst.Call):
        f = node.func
        return isinstance(f, cst.Attribute) and f.attr.value == "join"
    if isinstance(node, cst.BinaryOperation):
        return _stringy(node.left) or _stringy(node.right)
    return False


def _flag(node: cst.BaseExpression) -> str | None:
    """An arc flag v2 takes as bool: int(cond) -> cond, 1 - x -> not x; None to keep."""
    if isinstance(node, cst.Call) and dotted(node.func) == "int" and len(node.args) == 1:
        return code(node.args[0].value)
    if (
        isinstance(node, cst.BinaryOperation)
        and isinstance(node.operator, cst.Subtract)
        and number_text(node.left) == "1"
    ):
        return f"not {code(node.right)}"
    return None


def _points(values: list[str], stars: list[bool], shape: str) -> list[str] | None:
    """Positional geometry grouped by `shape` ("p" a point, "n" a number): a point is two
    numbers or one starred argument. None when the arguments do not fit the shape."""
    out, i = [], 0
    for slot in shape:
        if i >= len(values):
            return None
        if slot == "n":
            if stars[i]:
                return None
            out.append(values[i])
            i += 1
        elif stars[i]:
            out.append(values[i])
            i += 1
        elif i + 1 < len(values) and not stars[i + 1]:
            out.append(f"({values[i]}, {values[i + 1]})")
            i += 2
        else:
            return None
    return out if i == len(values) else None


def _vectorise(body: cst.BaseExpression, i: str, j: str, rows: str, cols: str) -> str | None:
    """`body` (a function of the cell indices i, j) over the whole grid, when every use of i
    and j is an `X[j, i]` lookup inside element-wise arithmetic; else None."""

    def walk(node: cst.BaseExpression) -> str | None:
        if isinstance(node, cst.Subscript) and len(node.slice) == 2:
            a, b = (s.slice for s in node.slice)
            if (
                isinstance(a, cst.Index)
                and isinstance(b, cst.Index)
                and dotted(a.value) == j
                and dotted(b.value) == i
                and not _mentions(node.value, {i, j})
            ):
                return f"{code(node.value)}[:{rows}, :{cols}]"
            return None
        if isinstance(node, cst.Call) and dotted(node.func) == "float" and len(node.args) == 1:
            return walk(node.args[0].value)
        if isinstance(node, cst.BinaryOperation) and not isinstance(
            node.operator, (cst.MatrixMultiply,)
        ):
            left, right = walk(node.left), walk(node.right)
            if left is None or right is None:
                return None
            op = code(node.operator).strip()
            return f"({left} {op} {right})"
        if isinstance(node, cst.UnaryOperation) and isinstance(node.operator, cst.Minus):
            inner = walk(node.expression)
            return None if inner is None else f"(-{inner})"
        if isinstance(node, cst.Comparison) and len(node.comparisons) == 1:
            left, right = walk(node.left), walk(node.comparisons[0].comparator)
            op = code(node.comparisons[0].operator).strip()
            if left is None or right is None or op not in ("<", ">", "<=", ">="):
                return None
            return f"({left} {op} {right})"
        if _mentions(node, {i, j}):
            return None
        if isinstance(node, (cst.Integer, cst.Float, cst.Name, cst.Attribute)):
            return code(node)
        return None

    out = walk(body)
    if out is None or "[:" not in out:
        return None
    return out[1:-1] if out.startswith("(") and out.endswith(")") and _balanced(out[1:-1]) else out


def _balanced(text: str) -> bool:
    depth = 0
    for ch in text:
        depth += ch in "([{"
        depth -= ch in ")]}"
        if depth < 0:
            return False
    return depth == 0


def _mentions(node: cst.CSTNode, names: set[str]) -> bool:
    found = False

    class V(cst.CSTVisitor):
        def visit_Name(self, node: cst.Name) -> None:
            nonlocal found
            found |= node.value in names

    node.visit(V())
    return found


# --- driver -----------------------------------------------------------------------------------


def transform(source: str, report: Report) -> str:
    """The v2 skeleton of v1 design `source`, recording changes and TODOs in `report`."""
    module = cst.parse_module(source)
    wrapper = MetadataWrapper(module)
    analysis = Analysis()
    wrapper.visit(analysis)
    scope = canvas_scope(analysis)
    colours = Colours(analysis, scope)
    rewrite = Rewrite(analysis, scope, colours, report)
    return wrapper.visit(rewrite).code


def ruff() -> str | None:
    for candidate in (ROOT / ".venv" / "bin" / "ruff", Path(sys.executable).parent / "ruff"):
        if candidate.exists():
            return str(candidate)
    return shutil.which("ruff")


def format_files(paths: Sequence[Path]) -> None:
    """Apply ruff's safe fixes, then format, with the repo's ruff settings."""
    exe = ruff()
    if exe is None:
        sys.exit("ruff not found: run `uv sync` in the repo, or pass --no-format")
    config = ["--config", str(ROOT / "pyproject.toml")]
    files = [str(p) for p in paths]
    subprocess.run([exe, "check", *config, "--fix", "--silent", "--exit-zero", *files], check=True)
    subprocess.run([exe, "format", *config, "--silent", *files], check=True)


def slug_of(path: Path) -> str:
    return path.parent.name if path.name == "design.py" else path.stem


def sources(paths: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            found = sorted(p.glob("*/design.py")) or sorted(
                q for q in p.glob("*.py") if not q.name.startswith("_")
            )
            out += found
        else:
            out.append(p)
    return out


def todos_in(text: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for n, line in enumerate(text.splitlines(), 1):
        m = re.search(r"# TODO\(port\): ([a-z-]+): (.*)$", line)
        if m:
            out.append({"kind": m.group(1), "line": n, "text": m.group(2)})
    return out


def run(srcs: Sequence[Path], out: Path | None, fmt: bool) -> list[Report]:
    reports: list[Report] = []
    written: list[tuple[Report, Path]] = []
    for src in srcs:
        slug = slug_of(src)
        report = Report(slug=slug, source=str(src))
        dest = src if out is None else out / slug / "design.py"
        try:
            text = transform(src.read_text(), report)
        except cst.ParserSyntaxError as exc:
            report.error = f"does not parse: {exc}"
            reports.append(report)
            continue
        except Exception as exc:  # a codemod bug: name the file, then fail loudly
            exc.add_note(f"while converting {src}")
            raise
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        report.output = str(dest)
        written.append((report, dest))
        reports.append(report)
    if fmt and written:
        format_files([d for _, d in written])
    for report, dest in written:
        text = dest.read_text()
        try:
            compile(text, str(dest), "exec")
            report.compiles = True
        except SyntaxError as exc:
            report.error = f"SyntaxError: {exc}"
        report.todos = todos_in(text)
    return reports


def summary(reports: Sequence[Report]) -> dict[str, object]:
    kinds: Counter[str] = Counter()
    files: Counter[str] = Counter()
    changes: Counter[str] = Counter()
    for r in reports:
        per = Counter(str(t["kind"]) for t in r.todos)
        kinds.update(per)
        files.update(per.keys())
        changes.update(r.changes)
    return {
        "files": len(reports),
        "compiles": sum(r.compiles for r in reports),
        "errors": sum(bool(r.error) for r in reports),
        "without_todos": sum(not r.todos and r.compiles for r in reports),
        "only_aspects_todo": sum({t["kind"] for t in r.todos} == {"aspects"} for r in reports),
        "todos": dict(kinds.most_common()),
        "todo_files": dict(files.most_common()),
        "changes": dict(changes.most_common()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("src", nargs="+", type=Path, help="design files or directories")
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--out", type=Path, help="write DIR/<slug>/design.py")
    where.add_argument("--in-place", action="store_true", help="rewrite the sources")
    parser.add_argument("--report", type=Path, help="write the JSON report here")
    parser.add_argument("--no-format", action="store_true", help="skip ruff")
    args = parser.parse_args(argv)
    reports = run(sources(args.src), None if args.in_place else args.out, not args.no_format)
    for r in reports:
        kinds = Counter(str(t["kind"]) for t in r.todos)
        status = r.error or ("ok" if r.compiles else "does not compile")
        todo = ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())) or "none"
        print(f"{r.slug}: {status}; {sum(r.changes.values())} changes; TODOs: {todo}")
    total = summary(reports)
    print(json.dumps(total, indent=2))
    if args.report:
        args.report.write_text(
            json.dumps({"summary": total, "files": [r.as_json() for r in reports]}, indent=2) + "\n"
        )
    return 1 if any(r.error for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
