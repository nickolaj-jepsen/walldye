"""Content hashes that tell `walldye build` when templates are stale.

Every hash is the sha256 of UTF-8 lines `<key>\\t<value>\\n`, sorted by line; for a file the
key is its posix path relative to the repo root (for the package, relative to its parent) and
the value the sha256 of its bytes, or for a module the sha256 of its code (code_line).
"""

import ast
import hashlib
import importlib.metadata
import platform
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import walldye
from walldye.tools import paths


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(lines: Sequence[str]) -> str:
    """sha256 of `lines` sorted, each terminated by a newline."""
    return sha256("".join(f"{line}\n" for line in sorted(lines)).encode())


def file_line(key: str, path: Path) -> str:
    """`<key>\\t<sha256 of the bytes at path>`; `key` is the file's repo-relative posix path."""
    return f"{key}\t{sha256(path.read_bytes())}"


def _without_docstrings(tree: ast.Module) -> ast.Module:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            first = body[0].value if len(body) > 0 and isinstance(body[0], ast.Expr) else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                node.body = body[1:] if len(body) > 1 else [ast.Pass()]
    return tree


def code_line(key: str, path: Path) -> str:
    """file_line() for a .py file hashed by its code: the sha256 of its AST without docstrings
    or positions, so editing a comment, a docstring or the layout keeps the hash. Other files
    hash by their bytes."""
    if path.suffix != ".py":
        return file_line(key, path)
    tree = _without_docstrings(ast.parse(path.read_bytes(), str(path)))
    return f"{key}\t{sha256(ast.dump(tree, include_attributes=False).encode())}"


def data_files(slug: str) -> list[Path]:
    """The files in wallpapers/<slug>/data/, sorted by name ([] without the folder)."""
    d = paths.piece_dir(slug) / "data"
    return sorted(p for p in d.iterdir() if p.is_file()) if d.is_dir() else []


def design_lines(slug: str) -> list[str]:
    """Hash lines of a piece: design.py (or source.svg and palette.yaml) and every file in
    data/."""
    d = paths.piece_dir(slug)
    names = ["source.svg", "palette.yaml"] if paths.is_legacy(slug) else ["design.py"]
    return [
        *(file_line(f"wallpapers/{slug}/{n}", d / n) for n in names),
        *(file_line(f"wallpapers/{slug}/data/{p.name}", p) for p in data_files(slug)),
    ]


def design_sha(slug: str, variant: str = "default") -> str:
    """The digest of design_lines(slug), plus `variant\\t<name>` for a named variant."""
    lines = design_lines(slug)
    return digest(lines if variant == "default" else [*lines, f"variant\t{variant}"])


# Modules that cannot change what build writes: the CLI around it, and checks that either run
# on every build (the lints) or only on a redraw (determinism). Everything else is an input.
NEUTRAL: Final = (
    "walldye/__main__.py",
    "walldye/tools/cli.py",
    "walldye/tools/determinism.py",
    "walldye/tools/drop.py",
    "walldye/tools/index.py",
    "walldye/tools/lint/",
    "walldye/tools/listing.py",
    "walldye/tools/new.py",
    "walldye/tools/preview.py",
    "walldye/tools/recolor.py",
    "walldye/tools/render.py",
    "walldye/tools/review/",
    "walldye/tools/sheet.py",
    "walldye/tools/similar.py",
)


def _neutral(key: str) -> bool:
    return any(key == n or (n.endswith("/") and key.startswith(n)) for n in NEUTRAL)


def _requirement_name(requirement: str) -> str | None:
    """The distribution a Requires-Dist line names, None when only an extra asks for it."""
    spec, _, marker = requirement.partition(";")
    if re.search(r"\bextra\s*==", marker) is not None:
        return None
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
    return None if match is None else match[1]


def runtime_dists() -> dict[str, str]:
    """Name -> version of every installed distribution walldye needs at run time, found by
    following Requires-Dist from walldye (extras left out; walldye itself excluded, its code
    is hashed instead). Names are normalized as PEP 503 does."""
    found: dict[str, str] = {}
    requires = importlib.metadata.requires("walldye")
    todo: list[str] = [] if requires is None else list(requires)
    while len(todo) > 0:
        name = _requirement_name(todo.pop())
        if name is None:
            continue
        key = re.sub(r"[-_.]+", "-", name).lower()
        if key in found:
            continue
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue  # a marker excludes it here
        found[key] = dist.version
        if dist.requires is not None:
            todo += dist.requires
    return found


def toolchain_lines() -> list[str]:
    """Hash lines of what turns a design into build output: the code (code_line) of every file
    in the imported walldye package outside NEUTRAL, the runtime_dists() versions, and the
    Python version and machine."""
    package = Path(walldye.__file__).parent
    files = {
        f"walldye/{p.relative_to(package).as_posix()}": p
        for p in package.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }
    code = [code_line(k, p) for k, p in sorted(files.items()) if not _neutral(k)]
    deps = [f"dep\t{name}=={version}" for name, version in sorted(runtime_dists().items())]
    python = f"{sys.implementation.name} {platform.python_version()} {platform.machine()}"
    return [*code, *deps, f"python\t{python}"]


def toolchain_sha() -> str:
    """The digest of toolchain_lines(); slots.json records it as `toolchain`."""
    return digest(toolchain_lines())
