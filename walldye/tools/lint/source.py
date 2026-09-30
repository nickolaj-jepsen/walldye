"""The design lint: what design.py may import, call and keep at module level, read from its
source without running it."""

import ast
import io
import re
import tokenize as py_tokenize
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from walldye.tools.lint.templates import Lints
from walldye.tools.lint.words import color_words, docstring

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


CONSTRUCTORS: Final = frozenset({"Color", "MaskColor", "Ref", "Canvas", "Document", "Design"})


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


COLORS: Final = frozenset(
    f"walldye.{n}"
    for n in (
        "BLACK", "BG_DEEP", "BG", "BG_ALT", "UI", "UI_ALT", "UI_HI", "MUTED", "FG_ALT", "FG",
        "ACCENT_HI", "ACCENT", "ACCENT_1", "ACCENT_2", "ACCENT_3", "ACCENT_4", "ACCENT_5",
        "ACCENT_6", "ACCENT_7", "ACCENT_8", "MASK_WHITE", "MASK_BLACK",
    )
)  # fmt: skip


COLOR_CALLS: Final = frozenset({"walldye.mix", "walldye.by_regime"})


_HEX_STRING: Final = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


_SUPPRESSION: Final = re.compile(r"#\s*(type|pyrefly)\s*:\s*ignore\b")


_ALLOWLIST: Final = (
    "designs import walldye, walldye.geom, walldye.field, walldye.pixel, numpy (not"
    " numpy.random), scipy, shapely, skimage and a few pure standard-library modules"
)


_RANDOM: Final = "draw randomness from s.rng(key), s.np_rng(key) or s.noise(key)"


_SAMPLER: Final = "library samplers take random_state=s.np_rng(key) or rng=s.np_rng(key)"


_UNCHECKED: Final = "designs are type-checked as written; fix what Pyrefly reports instead"


_NO_TEXT: Final = "a color has no text form; pass it to a drawing call"


_ENTRY: Final = "a design has exactly one module-level @design(...) def draw(s: Canvas[...])"


type Function = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda


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


def _is_color(d: _Design, node: ast.expr) -> bool:
    """Whether `node` is certainly a color: a token name or a mix()/by_regime() call."""
    if isinstance(node, ast.Name):
        return d.aliases.get(node.id) in COLORS
    return isinstance(node, ast.Call) and d.dotted(node.func) in COLOR_CALLS


def _color_strings(d: _Design, docstrings: set[int]) -> None:
    for node in ast.walk(d.tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings and _HEX_STRING.fullmatch(node.value.strip()) is not None:
                d.error(node, f"raw color {node.value!r}; paints are tokens, mix() and by_regime()")
        elif isinstance(node, ast.JoinedStr):
            first = node.values[0] if len(node.values) > 0 else None
            if isinstance(first, ast.Constant) and first.value == "#" and len(node.values) > 1:
                d.error(node, "builds a hex color; paints are tokens, mix() and by_regime()")
            if any(
                isinstance(v, ast.FormattedValue) and _is_color(d, v.value) for v in node.values
            ):
                d.error(node, _NO_TEXT)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            text = node.func.id in ("str", "format", "repr")
            if text and len(node.args) > 0 and _is_color(d, node.args[0]):
                d.error(node, _NO_TEXT)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            parts = node.right.elts if isinstance(node.right, ast.Tuple) else [node.right]
            if isinstance(node.left, ast.Constant) and any(_is_color(d, p) for p in parts):
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
    """Report whatever in `node` is not a constant expression."""
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
    """(errors, warnings) of the design lint for one design.py, each
    naming its line. SyntaxError propagates."""
    text = path.read_text()
    d = _Design(ast.parse(text, str(path)))
    docstrings = _docstrings(d.tree)
    _imports(d)
    _process(d)
    _entry_point(d)
    _module_level(d)
    _mutation(d)
    _color_strings(d, docstrings)
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
    if len(words := color_words("\n".join(docs + [t.string for t in comments]))) > 0:
        warnings.append(
            f"color words in docstrings or comments: {', '.join(sorted(words))} (name tokens or roles, never hues)"
        )
    if (module_doc := ast.get_docstring(d.tree)) is not None:
        warnings += [f"docstring: {w}" for w in docstring(module_doc)]
    return errors, warnings
