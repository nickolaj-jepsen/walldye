"""Static lints: the design lint (docs/api.md, Design lint), template limits, the data/ rules
and the meta.yaml rules."""

import ast
import io
import re
import tokenize as py_tokenize
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import yaml

from walldye.tools import common

MAX_BYTES, WARN_BYTES = 1_000_000, 600_000
MAX_ELEMENTS, WARN_ELEMENTS = 20_000, 15_000
STDLIB: Final = frozenset({
    "math", "cmath", "itertools", "functools", "collections", "heapq", "bisect", "operator",
    "dataclasses", "typing", "enum", "fractions", "statistics", "string", "re", "textwrap",
    "json", "base64", "zlib", "copy",
})  # fmt: skip
LIBRARIES: Final = frozenset({"numpy", "scipy", "shapely", "skimage"})
WALLDYE_MODULES: Final = frozenset({"walldye", "walldye.geom", "walldye.field", "walldye.pixel"})
RANDOM_CALLS: Final = frozenset({"Noise", "default_rng", "RandomState", "SeedSequence"})
# Modules whose every use is randomness; designs may not import or name them.
RANDOM_MODULES: Final = ("numpy.random", "scipy.stats.qmc")
# Library samplers: allowed only when handed a generator from s.np_rng(key).
SAMPLER_CALLS: Final = frozenset({"rvs", "random_noise"})
SAMPLER_ORIGINS: Final = frozenset({
    "scipy.sparse.random", "scipy.sparse.random_array", "scipy.sparse.rand",
    "skimage.util.random_noise",
})  # fmt: skip
TYPE_ESCAPES: Final = frozenset({"typing.cast", "typing.Any"})
CONSTRUCTORS: Final = frozenset({"Colour", "MaskColour", "Ref", "Canvas", "Document", "Design"})
PROCESS_CALLS: Final = frozenset({
    "hash", "id", "open", "exec", "eval", "compile", "globals", "__import__",
})  # fmt: skip
MUTATORS: Final = frozenset({
    "append", "extend", "insert", "pop", "remove", "clear", "update", "setdefault", "add",
    "discard", "sort", "reverse",
})  # fmt: skip
CONST_BUILTINS: Final = frozenset({
    "abs", "min", "max", "round", "sum", "len", "range", "tuple", "list", "dict", "set",
    "frozenset", "zip", "enumerate", "sorted", "reversed", "int", "float", "str", "bool",
    "complex", "divmod", "pow", "any", "all",
})  # fmt: skip
CONST_NUMPY: Final = frozenset(
    f"numpy.{n}"
    for n in (
        "array", "asarray", "arange", "linspace", "zeros", "ones", "full", "radians", "deg2rad",
        "degrees", "sin", "cos", "tan", "sqrt", "hypot", "arctan2", "linalg.norm",
    )
)  # fmt: skip
CONST_WALLDYE: Final = frozenset(
    f"walldye.{n}"
    for n in (
        "mix", "ramp", "ladder", "by_regime", "Vec", "Rect", "polar", "lerp", "clamp",
        "smoothstep",
    )
)  # fmt: skip
STR_METHODS: Final = frozenset({
    "split", "splitlines", "strip", "lstrip", "rstrip", "join", "replace", "ljust", "rjust",
    "center", "upper", "lower", "format", "zfill",
})  # fmt: skip
COLOURS: Final = frozenset(
    f"walldye.{n}"
    for n in (
        "BLACK", "BG_DEEP", "BG", "BG_ALT", "UI", "UI_ALT", "UI_HI", "MUTED", "FG_ALT", "FG",
        "ACCENT_HI", "ACCENT", "ACCENT_1", "ACCENT_2", "ACCENT_3", "ACCENT_4", "ACCENT_5",
        "ACCENT_6", "ACCENT_7", "ACCENT_8", "MASK_WHITE", "MASK_BLACK",
    )
)  # fmt: skip
COLOUR_CALLS: Final = frozenset({"walldye.mix", "walldye.by_regime"})
# Hues and named shades; copy must say "accent", "bg", roles. Token names (ALL CAPS) are fine.
COLOUR_WORDS: Final = frozenset({
    "red", "orange", "yellow", "green", "blue", "purple", "violet", "pink", "brown", "black",
    "white", "grey", "gray", "cyan", "magenta", "teal", "turquoise", "indigo", "crimson",
    "scarlet", "maroon", "amber", "golden", "beige", "cream", "ivory", "terracotta", "ochre",
    "umber", "sepia", "navy", "lavender", "lilac", "mauve", "azure", "cobalt", "vermilion",
    "burgundy", "charcoal", "khaki", "sienna", "cerulean", "ultramarine", "chartreuse", "fuchsia"
})  # fmt: skip
# Words visitors never read (docs/design.md, Copy rules); variant labels may not use them.
INTERNAL_TERMS: Final = frozenset({
    "regime", "seed", "token", "native", "hand-tuned", "light-ready", "preset", "variant",
    "param",
})  # fmt: skip
RESERVED_SLUGS: Final = frozenset(
    {"about", "index", "t", "og", "fonts", "404", "robots", "favicon"}
)
SOURCE_KINDS: Final = ("recreation", "inspiration", "reference", "data")
FAN_WORK: Final = "LicenseRef-fan-work"
DEFAULT_LICENSE: Final = "CC0-1.0"
LICENSES = common.ROOT / "LICENSES"
DATA_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.(json|txt|npy)")
_HEX_STRING: Final = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
_SUPPRESSION: Final = re.compile(r"#\s*(type|pyrefly)\s*:\s*ignore\b")
_ALLOWLIST: Final = (
    "designs import walldye, walldye.geom, walldye.field, walldye.pixel, numpy (not"
    " numpy.random), scipy, shapely, skimage and a few pure standard-library modules"
)
_RANDOM: Final = "draw randomness from s.rng(key), s.np_rng(key) or s.noise(key)"
_SAMPLER: Final = "library samplers take random_state=s.np_rng(key) or rng=s.np_rng(key)"
_UNCHECKED: Final = "designs are type-checked as written; fix what Pyrefly reports instead"
_NO_TEXT: Final = "a colour has no text form; pass it to a drawing call"
_ENTRY: Final = "a design has exactly one module-level @design(...) def draw(s: Canvas[...])"

type Lints = tuple[list[str], list[str]]
type Function = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda


def reserved(slug: str) -> bool:
    """Whether `slug` collides with a site route or file (RESERVED_SLUGS, sitemap*, _*)."""
    return slug in RESERVED_SLUGS or slug.startswith(("sitemap", "_"))


def svg(text: str) -> Lints:
    """(errors, warnings) for one template: invalid XML, <text>, <filter>, <image>, size and
    element count over MAX_* are errors; over WARN_* warnings."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return [f"invalid XML: {e}"], []
    errors: list[str] = []
    warnings: list[str] = []
    tags = [el.tag.rpartition("}")[2] for el in root.iter()]
    if "text" in tags:
        errors.append("<text> depends on installed fonts; draw glyphs as paths (walldye.pixel)")
    if "filter" in tags:
        errors.append("<filter> is not allowed: slow at 4K, soft, and renderers disagree")
    if "image" in tags:
        errors.append("<image> is not allowed: templates are self-contained vectors")
    size = len(text.encode())
    for value, hard, soft, what in (
        (size, MAX_BYTES, WARN_BYTES, f"{size:,} bytes"),
        (len(tags), MAX_ELEMENTS, WARN_ELEMENTS, f"{len(tags)} elements"),
    ):
        if value > hard:
            errors.append(
                f"{what} is over the limit of {hard:,}; merge shapes into one <path> per colour"
            )
        elif value > soft:
            warnings.append(
                f"{what} is heavy (over {soft:,}); merge shapes into one <path> per colour"
            )
    return errors, warnings


def colour_words(text: str) -> set[str]:
    """Colour words in `text`, lowercased; ALL-CAPS words (token names like ACCENT_HI) are
    not prose."""
    words: list[str] = re.findall(r"\b[A-Za-z]+\b", text)
    return {w.lower() for w in words if w.lower() in COLOUR_WORDS and not w.isupper()}


def random_module(name: str) -> str | None:
    """The module of RANDOM_MODULES that dotted name `name` is or lies inside, else None."""
    return next((m for m in RANDOM_MODULES if name == m or name.startswith(f"{m}.")), None)


def allowed_module(name: str) -> bool:
    """Whether a design may import module `name` (the import allowlist)."""
    top = name.split(".")[0]
    if random_module(name) is not None:
        return False
    if top == "walldye":
        return name in WALLDYE_MODULES
    return top in STDLIB or top in LIBRARIES


@dataclass
class _Design:
    """What the design lint knows about a module while it walks it."""

    tree: ast.Module
    aliases: dict[str, str] = field(default_factory=dict[str, str])  # local name -> origin
    errors: list[tuple[int, str]] = field(default_factory=list[tuple[int, str]])

    def error(self, node: ast.AST, message: str) -> None:
        line: int = getattr(node, "lineno", 0)
        if (line, message) not in self.errors:
            self.errors.append((line, message))

    def dotted(self, node: ast.expr) -> str | None:
        """The imported origin of a Name or Attribute chain ("numpy.random.default_rng")."""
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id)
        if isinstance(node, ast.Attribute):
            base = self.dotted(node.value)
            return None if base is None else f"{base}.{node.attr}"
        return None


def _called_name(node: ast.Call) -> str | None:
    """The bare name or last attribute a call goes through (`Noise` for `field.Noise(3)`)."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _imports(d: _Design) -> None:
    for node in ast.walk(d.tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if not allowed_module(a.name):
                    d.error(node, f"imports {a.name}; {_ALLOWLIST}")
                top = a.name.split(".")[0]
                d.aliases[top if a.asname is None else a.asname] = (
                    top if a.asname is None else a.name
                )
        elif isinstance(node, ast.ImportFrom):
            module = "" if node.module is None else node.module
            if node.level > 0:
                d.error(node, "relative import; designs are single files")
                continue
            if module == "__future__":
                d.error(node, "from __future__ imports change how annotations evaluate")
                continue
            if not allowed_module(module):
                d.error(node, f"imports {module}; {_ALLOWLIST}")
            for a in node.names:
                full = f"{module}.{a.name}"
                private = module == "walldye" and (
                    a.name.startswith("_") or a.name in ("tools", "font")
                )
                if private or random_module(full) is not None:
                    d.error(node, f"imports {full}; {_ALLOWLIST}")
                d.aliases[a.name if a.asname is None else a.asname] = full


def _process(d: _Design) -> None:
    for node in ast.walk(d.tree):
        if isinstance(node, ast.Global):
            d.error(node, "global statements change module state; pass values through s")
        elif isinstance(node, ast.Call):
            name = _called_name(node)
            if isinstance(node.func, ast.Name) and name in PROCESS_CALLS:
                d.error(
                    node, f"calls {name}(), which depends on the process or the files around it"
                )
            if name in RANDOM_CALLS:
                d.error(node, f"calls {name}(); {_RANDOM}")
            if not _streamed(node):
                if name in SAMPLER_CALLS or d.dotted(node.func) in SAMPLER_ORIGINS:
                    d.error(node, f"calls {name}() without a stream; {_SAMPLER}")
                elif any(kw.arg == "random_state" for kw in node.keywords):
                    d.error(node, f"passes random_state= without a stream; {_SAMPLER}")
            if name in CONSTRUCTORS:
                d.error(node, f"calls {name}(); the drawing API makes these")
        elif isinstance(node, (ast.Name, ast.Attribute)):
            origin = d.dotted(node)
            module = None if origin is None else random_module(origin)
            if module is not None:
                d.error(node, f"uses {module}; {_RANDOM}")
            elif origin in TYPE_ESCAPES:
                d.error(node, f"uses {origin}; {_UNCHECKED}")


def _streamed(node: ast.Call) -> bool:
    """Whether a call passes random_state= or rng= as a direct s.np_rng(...) call."""
    return any(
        kw.arg in ("random_state", "rng")
        and isinstance(kw.value, ast.Call)
        and _called_name(kw.value) == "np_rng"
        for kw in node.keywords
    )


def _is_colour(d: _Design, node: ast.expr) -> bool:
    """Whether `node` is certainly a colour: a token name or a mix()/by_regime() call."""
    if isinstance(node, ast.Name):
        return d.aliases.get(node.id) in COLOURS
    return isinstance(node, ast.Call) and d.dotted(node.func) in COLOUR_CALLS


def _colour_strings(d: _Design, docstrings: set[int]) -> None:
    for node in ast.walk(d.tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings and _HEX_STRING.fullmatch(node.value.strip()) is not None:
                d.error(
                    node, f"raw colour {node.value!r}; paints are tokens, mix() and by_regime()"
                )
        elif isinstance(node, ast.JoinedStr):
            first = node.values[0] if len(node.values) > 0 else None
            if isinstance(first, ast.Constant) and first.value == "#" and len(node.values) > 1:
                d.error(node, "builds a hex colour; paints are tokens, mix() and by_regime()")
            if any(
                isinstance(v, ast.FormattedValue) and _is_colour(d, v.value) for v in node.values
            ):
                d.error(node, _NO_TEXT)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            text = node.func.id in ("str", "format", "repr")
            if text and len(node.args) > 0 and _is_colour(d, node.args[0]):
                d.error(node, _NO_TEXT)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            parts = node.right.elts if isinstance(node.right, ast.Tuple) else [node.right]
            if isinstance(node.left, ast.Constant) and any(_is_colour(d, p) for p in parts):
                d.error(node, _NO_TEXT)


def _docstrings(tree: ast.Module) -> set[int]:
    """ids of the docstring constants of the module, its classes and its functions."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if len(node.body) > 0 else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                out.add(id(first.value))
    return out


def _bound_names(node: ast.stmt) -> list[str]:
    """Names a module-level statement binds."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.TypeAlias):
        return [node.name.id]
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return [a.name.split(".")[0] if a.asname is None else a.asname for a in node.names]
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    return [n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)]


def _entry_point(d: _Design) -> None:
    draws = [
        n for n in d.tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "draw"
    ]  # fmt: skip
    rebound = [
        n for n in d.tree.body
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and "draw" in _bound_names(n)
    ]  # fmt: skip
    if len(draws) != 1 or len(rebound) > 0:
        d.error(d.tree if len(draws) == 0 else draws[-1], _ENTRY)
    decorators: set[int] = set()
    for fn in draws:
        decs = fn.decorator_list
        good = len(decs) == 1 and isinstance(decs[0], ast.Call)
        if not isinstance(fn, ast.FunctionDef) or not good:
            d.error(fn, _ENTRY)
        for dec in decs:
            if isinstance(dec, ast.Call) and d.dotted(dec.func) == "walldye.design":
                decorators.add(id(dec.func))
            else:
                d.error(fn, _ENTRY)
    for node in ast.walk(d.tree):
        if (
            isinstance(node, (ast.Name, ast.Attribute))
            and id(node) not in decorators
            and d.dotted(node) == "walldye.design"
            and not isinstance(node.ctx, ast.Store)
        ):
            d.error(node, "design is only used as the @design(...) decorator on draw")


def _plain_target(t: ast.expr) -> bool:
    if isinstance(t, ast.Name):
        return True
    if isinstance(t, ast.Starred):
        return _plain_target(t.value)
    if isinstance(t, (ast.Tuple, ast.List)):
        return all(_plain_target(e) for e in t.elts)
    return False


@dataclass
class _Scope:
    """Module-level names bound so far, and which of them are functions or Params classes."""

    names: set[str] = field(default_factory=set[str])
    functions: set[str] = field(default_factory=set[str])
    params: set[str] = field(default_factory=set[str])


def _module_level(d: _Design) -> None:
    scope = _Scope()
    for i, node in enumerate(d.tree.body):
        docstring = i == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        if docstring or isinstance(node, (ast.Import, ast.ImportFrom, ast.TypeAlias)):
            pass
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not all(_plain_target(t) for t in targets):
                d.error(node, "module-level assignments bind names; change values inside draw")
            if node.value is not None:
                _constant(d, node.value, scope, set())
        elif isinstance(node, ast.Assert):
            _constant(d, node.test, scope, set())
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "draw":
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call):
                        for arg in [*dec.args, *(k.value for k in dec.keywords)]:
                            _constant(d, arg, scope, set())
            elif len(node.decorator_list) > 0:
                d.error(node, "module-level functions are undecorated, except @design on draw")
            else:
                scope.functions.add(node.name)
        elif isinstance(node, ast.ClassDef):
            if not all(_is_dataclass(d, dec) for dec in node.decorator_list):
                d.error(node, "module-level classes are undecorated or @dataclass(...)")
            for b in node.bases:
                if d.dotted(b) == "walldye.Params" or (
                    isinstance(b, ast.Name) and b.id in scope.params
                ):
                    scope.params.add(node.name)
        else:
            kind = type(node).__name__.lower()
            d.error(
                node,
                f"a module-level {kind} statement; module level only declares, so move the work into draw",
            )
        scope.names.update(_bound_names(node))


def _is_dataclass(d: _Design, node: ast.expr) -> bool:
    return d.dotted(node.func if isinstance(node, ast.Call) else node) == "dataclasses.dataclass"


_CONTAINERS: Final = (
    ast.Tuple, ast.List, ast.Set, ast.Dict, ast.JoinedStr, ast.FormattedValue, ast.BinOp,
    ast.BoolOp, ast.Compare, ast.UnaryOp, ast.IfExp, ast.Subscript, ast.Slice, ast.Starred,
)  # fmt: skip


def _constant(d: _Design, node: ast.expr, scope: _Scope, local: set[str]) -> None:
    """Report whatever in `node` is not a constant expression (docs/api.md, Module level)."""
    if isinstance(node, ast.Constant):
        return
    if isinstance(node, ast.Name):
        if node.id not in scope.names and node.id not in local and node.id not in CONST_BUILTINS:
            d.error(node, f"{node.id} is not bound before this module-level line")
    elif isinstance(node, ast.Attribute):
        _constant(d, node.value, scope, local)
    elif isinstance(node, ast.Lambda):
        defaults = [*node.args.defaults, *(k for k in node.args.kw_defaults if k is not None)]
        for default in defaults:
            _constant(d, default, scope, local)
    elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        _constant(d, node.elt, scope, _comprehension(d, node.generators, scope, local))
    elif isinstance(node, ast.DictComp):
        inner = _comprehension(d, node.generators, scope, local)
        _constant(d, node.key, scope, inner)
        _constant(d, node.value, scope, inner)
    elif isinstance(node, ast.Call):
        _call(d, node, scope, local)
    elif isinstance(node, _CONTAINERS):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                _constant(d, child, scope, local)
    else:
        d.error(node, f"{type(node).__name__} is not allowed in a module-level constant")


def _comprehension(
    d: _Design, gens: Sequence[ast.comprehension], scope: _Scope, local: set[str]
) -> set[str]:
    inner = set(local)
    for g in gens:
        _constant(d, g.iter, scope, inner)
        inner |= {n.id for n in ast.walk(g.target) if isinstance(n, ast.Name)}
        for cond in g.ifs:
            _constant(d, cond, scope, inner)
    return inner


def _call(d: _Design, node: ast.Call, scope: _Scope, local: set[str]) -> None:
    func = node.func
    origin = d.dotted(func)
    ok = False
    if isinstance(func, ast.Name) and origin is None:
        builtin = func.id in CONST_BUILTINS and func.id not in scope.names
        ok = builtin or func.id in scope.functions or func.id in scope.params
    elif origin is not None:
        top = origin.split(".")[0]
        ok = top in ("math", "cmath") or origin in CONST_NUMPY or origin in CONST_WALLDYE
    if not ok and isinstance(func, ast.Attribute) and origin is None and func.attr in STR_METHODS:
        _constant(d, func.value, scope, local)
        ok = True
    if not ok:
        name = ast.unparse(func)
        d.error(
            node,
            f"calls {name}() at module level; only pure calls build constants, so do this in draw",
        )
    for arg in [*node.args, *(k.value for k in node.keywords)]:
        _constant(d, arg, scope, local)


def _functions(
    node: ast.AST, outer: tuple[set[str], ...] = ()
) -> Iterator[tuple[Function, set[str]]]:
    """Every function under `node`, with the names it and the functions around it bind."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            chain = (*outer, _locals(child))
            yield child, set[str]().union(*chain)
            yield from _functions(child, chain)
        else:
            yield from _functions(child, outer)


def _body(fn: Function) -> list[ast.AST]:
    return [fn.body] if isinstance(fn, ast.Lambda) else list(fn.body)


def _locals(fn: Function) -> set[str]:
    """The names `fn` binds: parameters, assignment and loop targets, imports, nested defs,
    nonlocals and exception names."""
    a = fn.args
    names = {x.arg for x in [*a.posonlyargs, *a.args, *a.kwonlyargs]}
    names |= {x.arg for x in (a.vararg, a.kwarg) if x is not None}
    stack = _body(fn)
    while len(stack) > 0:
        node = stack.pop()
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            continue
        elif isinstance(node, ast.Lambda):
            continue
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {x.name.split(".")[0] if x.asname is None else x.asname for x in node.names}
        elif isinstance(node, ast.Nonlocal):
            names |= set(node.names)
        elif isinstance(node, ast.ExceptHandler) and node.name is not None:
            names.add(node.name)
        stack.extend(ast.iter_child_nodes(node))
    return names


def _base(node: ast.expr) -> ast.Name | None:
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node if isinstance(node, ast.Name) else None


def _is_item(t: ast.expr) -> bool:
    return isinstance(t, (ast.Attribute, ast.Subscript))


def _unpack(t: ast.expr) -> list[ast.expr]:
    if isinstance(t, (ast.Tuple, ast.List)):
        return [x for e in t.elts for x in _unpack(e)]
    if isinstance(t, ast.Starred):
        return _unpack(t.value)
    return [t]


def _mutation(d: _Design) -> None:
    module = {
        n for stmt in d.tree.body
        if not isinstance(stmt, (ast.Import, ast.ImportFrom))
        for n in _bound_names(stmt)
    }  # fmt: skip
    for fn, bound in _functions(d.tree):
        stack = _body(fn)
        while len(stack) > 0:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue  # _functions visits it with its own names
            sites: list[ast.expr] = []
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in MUTATORS:
                    sites.append(node.func.value)
            elif isinstance(node, (ast.Assign, ast.Delete)):
                sites += [x for t in node.targets for x in _unpack(t) if _is_item(x)]
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)) and _is_item(node.target):
                sites.append(node.target)
            for site in sites:
                name = _base(site)
                if name is not None and name.id in module and name.id not in bound:
                    d.error(
                        node,
                        f"changes module-level {name.id} while drawing; every render must start from the same state",
                    )
            stack.extend(ast.iter_child_nodes(node))


def design(path: Path) -> Lints:
    """(errors, warnings) of the design lint for one design.py: imports, randomness,
    constructors, process state, the entry point, module-level statements, mutation of
    module-level names, raw colour strings, text forms of colours and type-check escapes
    (`# type: ignore`, `# pyrefly: ignore`, typing.cast, typing.Any) are errors, each naming
    its line; colour words in docstrings or comments are warnings. SyntaxError propagates."""
    text = path.read_text()
    d = _Design(ast.parse(text, str(path)))
    docstrings = _docstrings(d.tree)
    _imports(d)
    _process(d)
    _entry_point(d)
    _module_level(d)
    _mutation(d)
    _colour_strings(d, docstrings)
    comments = [
        t
        for t in py_tokenize.generate_tokens(io.StringIO(text).readline)
        if t.type == py_tokenize.COMMENT
    ]
    for t in comments:
        if (m := _SUPPRESSION.search(t.string)) is not None:
            d.errors.append(
                (t.start[0], f"`# {m.group(1)}: ignore` silences Pyrefly; {_UNCHECKED}")
            )
    errors = [
        f"line {line}: {msg}" if line > 0 else msg
        for line, msg in sorted(d.errors, key=lambda e: e[0])
    ]
    docs = [
        n.value for n in ast.walk(d.tree)
        if isinstance(n, ast.Constant) and id(n) in docstrings and isinstance(n.value, str)
    ]  # fmt: skip
    warnings: list[str] = []
    if len(words := colour_words("\n".join(docs + [t.string for t in comments]))) > 0:
        warnings.append(
            f"colour words in docstrings or comments: {', '.join(sorted(words))} (name tokens or roles, never hues)"
        )
    return errors, warnings


def data(slug: str) -> list[str]:
    """Errors for wallpapers/<slug>/data/: only files named like `points.json`, `names.txt`
    or `grid.npy`, and no subdirectories."""
    d = common.piece_dir(slug) / "data"
    if not d.is_dir():
        return []
    errors: list[str] = []
    for p in sorted(d.iterdir()):
        if p.is_dir():
            errors.append(f"data/{p.name}/: data/ holds files only, no subdirectories")
        elif DATA_NAME.fullmatch(p.name) is None:
            errors.append(f"data/{p.name}: data files are .json, .txt or .npy with a plain name")
    return errors


def _text(m: common.Meta, key: str) -> str:
    value = m.get(key)
    return value if isinstance(value, str) else ""


def _mappings(value: object) -> list[dict[str, object]] | None:
    """The mappings of a YAML list, [] for None, and None when it is not a list of mappings."""
    if value is None:
        return []
    items = common.as_list(value)
    if items is None:
        return None
    out = [e for e in map(common.as_dict, items) if e is not None]
    return out if len(out) == len(items) else None


def license_of(meta: common.Meta) -> str | None:
    """The folder's licence: `license:`, else DEFAULT_LICENSE for an AI-generated piece with
    no recreation source, else None (no licence can be resolved)."""
    if (licence := _text(meta, "license")) != "":
        return licence
    sources = _mappings(meta.get("sources"))
    recreation = sources is not None and any(s.get("kind") == "recreation" for s in sources)
    return DEFAULT_LICENSE if meta.get("ai_generated") is True and not recreation else None


def load_taxonomy() -> dict[str, set[str]] | None:
    """Allowed values per facet from taxonomy.yaml (each facet a list of values, or a mapping
    keyed by value); None when the file does not exist."""
    if not common.TAXONOMY.exists():
        return None
    facets = common.as_dict(yaml.safe_load(common.TAXONOMY.read_text()))
    out: dict[str, set[str]] = {}
    for facet, values in (facets if facets is not None else dict[str, object]()).items():
        listed = common.as_list(values)
        keyed = common.as_dict(values)
        found = listed if listed is not None else list[object]() if keyed is None else list(keyed)
        out[facet] = {str(v) for v in found}
    return out


def meta(
    slug: str,
    m: common.Meta,
    taxonomy: dict[str, set[str]] | None,
    variants: Sequence[str] = ("default",),
) -> Lints:
    """(errors, warnings) for the meta.yaml `m` of `slug`, whose design declares `variants`
    ("default" first): required copy, reserved slugs, boolean draft and ai_generated, themes,
    source kinds, licence rules (a LICENSES/<licence>.txt for the resolved licence, and
    franchise for fan work), facets against `taxonomy` (skipped with a warning when None),
    proposed_facets outside drafts and the variants: rules; colour words in the copy warn."""
    errors: list[str] = []
    warnings: list[str] = []
    for key in ("title", "description"):
        if _text(m, key).strip() == "":
            errors.append(f"meta.yaml needs a {key}")
    for key in ("draft", "ai_generated"):
        if key in m and not isinstance(m[key], bool):
            errors.append(f"{key} must be true or false, not {m[key]!r}")
    if reserved(slug):
        errors.append(f"slug {slug!r} is reserved by the site")
    themes = m.get("themes")
    if themes is not None and themes not in (["dark", "light"], ["dark"]):
        errors.append(f"themes must be [dark, light] or [dark], not {themes!r}")
    if themes == ["dark"] and _text(m, "notes") == "":
        warnings.append("themes: [dark] needs the reason (light ladder steps 2-3 tried) in notes")
    sources = _mappings(m.get("sources"))
    if sources is None:
        errors.append("sources must be a list of mappings")
        sources = list[dict[str, object]]()
    for s in sources:
        if s.get("kind") not in SOURCE_KINDS:
            errors.append(f"source kind {s.get('kind')!r} is not one of {', '.join(SOURCE_KINDS)}")
    if _text(m, "license") == "":
        if any(s.get("kind") == "recreation" for s in sources):
            errors.append("a kind: recreation source needs an explicit license: (ask the owner)")
        elif m.get("ai_generated") is not True:
            errors.append("human-made pieces need an explicit license:")
    if (licence := license_of(m)) is not None and not (LICENSES / f"{licence}.txt").is_file():
        errors.append(
            f"license {licence!r} has no LICENSES/{licence}.txt; add the licence text or fix the id"
        )
    franchise = common.as_dict(m.get("franchise"))
    credited = franchise is not None and "" not in (
        _text(franchise, "title"),
        _text(franchise, "owner"),
    )
    if m.get("license") == FAN_WORK and not credited:
        errors.append(f"license {FAN_WORK} needs franchise: {{title, owner}}")
    if m.get("model") is not None and m.get("ai_generated") is not True:
        errors.append("model: is only for ai_generated pieces")
    if taxonomy is None:
        warnings.append("taxonomy.yaml not found; facets not checked")
    else:
        for facet, allowed in taxonomy.items():
            raw = m.get(facet)
            values = list[object]() if raw is None else common.as_list(raw)
            if values is None:
                errors.append(f"{facet} must be a list")
                continue
            for v in values:
                if v not in allowed:
                    errors.append(
                        f"{facet}: {v!r} is not in taxonomy.yaml (suggest it under proposed_facets)"
                    )
    if m.get("proposed_facets") not in (None, {}) and not common.is_draft(m):
        errors.append("proposed_facets are only allowed while draft: true")
    variant_errors, variant_warnings = _variants(m, variants)
    return errors + variant_errors, warnings + copy_words(m) + variant_warnings


def _variants(m: common.Meta, names: Sequence[str]) -> Lints:
    """The variants: rules: keys exactly the declared names, a unique plain label for each,
    and description and draft only on named variants."""
    if len(names) <= 1:
        if "variants" in m:
            return ["variants: is only for designs that declare named variants"], []
        return [], []
    entries = common.as_dict(m.get("variants"))
    if entries is None:
        return [f"meta.yaml needs variants: with a label for each of {', '.join(names)}"], []
    errors: list[str] = []
    warnings: list[str] = []
    if len(missing := [n for n in names if n not in entries]) > 0:
        errors.append(
            f"variants: missing {', '.join(missing)} (design.py declares {', '.join(names)})"
        )
    if len(extra := [n for n in entries if n not in names]) > 0:
        errors.append(
            f"variants: {', '.join(extra)} not declared in design.py (it declares {', '.join(names)})"
        )
    labels: dict[str, str] = {}
    for name, value in entries.items():
        entry = common.as_dict(value)
        if entry is None:
            errors.append(f"variants: {name} must be a mapping with a label")
            continue
        allowed = {"label"} if name == "default" else {"label", "description", "draft"}
        if len(unknown := sorted(set(entry) - allowed)) > 0:
            errors.append(
                f"variants: {name}: {', '.join(unknown)} not allowed (only {', '.join(sorted(allowed))})"
            )
        label = _text(entry, "label").strip()
        words = label.split()
        if not 1 <= len(words) <= 4:
            errors.append(f"variants: {name} needs a label of one to four plain words")
        stems = {w.lower().strip(".,;:!?").removesuffix("s") for w in words}
        if len(internal := sorted(stems & INTERNAL_TERMS)) > 0:
            errors.append(
                f"variants: {name}: the label says {', '.join(internal)}, a word visitors never see"
            )
        if (other := labels.get(label.lower())) is not None:
            errors.append(f"variants: {name} and {other} share the label {label!r}")
        labels[label.lower()] = name
        if "description" in entry and _text(entry, "description").strip() == "":
            errors.append(f"variants: {name}: description must be text")
        if "draft" in entry and not isinstance(entry["draft"], bool):
            errors.append(f"variants: {name}: draft must be true or false")
        if len(found := colour_words(f"{label}\n{_text(entry, 'description')}")) > 0:
            words_ = ", ".join(sorted(found))
            warnings.append(
                f"colour words in variants: {name}: {words_} (describe the shape, without naming colours)"
            )
    return errors, warnings


def copy_words(m: common.Meta) -> list[str]:
    """A warning naming the colour words in the title, description and notes of meta.yaml
    `m`, or []."""
    words = colour_words("\n".join(_text(m, k) for k in ("title", "description", "notes")))
    if len(words) == 0:
        return []
    return [
        f"colour words in meta.yaml copy: {', '.join(sorted(words))} (describe the shape or what it picks out, without naming colours)"
    ]


def pixel_origins(grids: Sequence[tuple[float, float, float]]) -> list[str]:
    """Warnings for pixel grids (cell, x, y) whose origin is not a whole unit."""
    off = sorted({(x, y, cell) for cell, x, y in grids if x % 1 != 0 or y % 1 != 0})
    return [
        f"pixel grid origin ({x:g}, {y:g}) is not a whole unit; snap it to the {cell:g}-unit cell grid"
        for x, y, cell in off
    ]
