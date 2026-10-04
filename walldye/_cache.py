"""@cached: memoized pure functions for designs, in memory always and on disk once a tool
turns the disk on with use_disk()."""

import ast
import collections
import contextlib
import dataclasses
import functools
import hashlib
import inspect
import json
import os
import random
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import numpy as np
from numpy.typing import NDArray

from ._noise import Noise
from ._params import Params
from ._vec import Vec

MEMORY_BYTES: Final = 256 * 2**20  # per process, by array bytes
DISK_BYTES: Final = 2**30  # past this, a write prunes the least recently used files to 3/4

type _Array = NDArray[np.generic]
type _Generator = np.random.Generator | random.Random


@dataclass(frozen=True)
class _Packed:
    """A value split into a JSON skeleton and the arrays it points at by index."""

    skeleton: str
    arrays: tuple[_Array, ...]

    @property
    def nbytes(self) -> int:
        return sum(a.nbytes for a in self.arrays) + len(self.skeleton)


@dataclass
class _Disk:
    root: Path
    salt: Callable[[], str]
    _salt: str | None = None

    def path(self, key: str) -> Path:
        if self._salt is None:
            self._salt = self.salt()
        name = hashlib.sha256(f"{self._salt}\n{key}".encode()).hexdigest()
        return self.root / name[:2] / f"{name}.npz"


# key -> the packed (value, generator states on exit), most recently used last
_MEMORY: Final[collections.OrderedDict[str, _Packed]] = collections.OrderedDict()
_disk: _Disk | None = None


def use_disk(root: Path | None, salt: Callable[[], str] = lambda: "") -> None:
    """Keep results under `root` as well as in memory, or only in memory when `root` is None.
    `salt` is called once, on the first disk access, and goes into every file's key: pass
    something that changes whenever the library or its dependencies could compute differently.
    A file that cannot be read is treated as missing and removed."""
    global _disk
    _disk = None if root is None else _Disk(root, salt)


def clear_memory() -> None:
    """Forget every result held in memory."""
    _MEMORY.clear()


def cached[**A, R](fn: Callable[A, R]) -> Callable[A, R]:
    """`fn` memoized, for a module-level function of a design that does heavy, pure work.

    The key is the source of `fn` and of every module-level definition, constant and import it
    reaches by name, plus its arguments: None, bools, numbers, strings, bytes, tuples (Vec
    included), lists, dicts with string keys, numpy arrays and scalars, Params, Noise, and
    numpy or `random` generators by their state. Array arguments reach `fn` read-only. A hit
    returns a fresh copy and leaves each generator argument in the state a call would have.
    Results may be built from the same types, apart from Params, Noise and generators.

    Raises TypeError when `fn` is not a module-level function with a readable source file,
    and on a call with an argument or result outside those types.
    """
    if not inspect.isfunction(fn) or fn.__qualname__ != fn.__name__:
        raise TypeError("@cached takes a module-level def")
    code = _code_digest(fn)

    @functools.wraps(fn)
    def memoized(*args: A.args, **kwargs: A.kwargs) -> R:
        h = hashlib.sha256(code.encode())
        generators: list[_Generator] = []
        _feed(h.update, (args, kwargs), generators)
        key = h.hexdigest()
        packed = _recall(key)
        if packed is None:
            frozen = cast("tuple[object, ...]", _read_only(args))
            call = cast("Callable[..., R]", fn)
            value = call(*frozen, **cast("dict[str, object]", _read_only(kwargs)))
            packed = _pack((value, [_state(g) for g in generators]))
            _remember(key, packed)
            if _disk is not None:
                _write(_disk.path(key), packed)
        value, states = cast("tuple[R, list[object]]", _unpack(packed))
        for g, state in zip(generators, states, strict=True):
            _restore(g, state)
        return value

    return memoized


def _recall(key: str) -> _Packed | None:
    packed = _MEMORY.get(key)
    if packed is not None:
        _MEMORY.move_to_end(key)
        return packed
    if _disk is None:
        return None
    packed = _read(_disk.path(key))
    if packed is not None:
        _remember(key, packed)
    return packed


def _remember(key: str, packed: _Packed) -> None:
    _MEMORY[key] = packed
    total = sum(p.nbytes for p in _MEMORY.values())
    while total > MEMORY_BYTES and len(_MEMORY) > 1:
        total -= _MEMORY.popitem(last=False)[1].nbytes


# Keys


def _code_digest(fn: Callable[..., object]) -> str:
    """The module-level statements `fn` reaches by name in its source file, dumped in order."""
    path = None
    try:
        path = inspect.getsourcefile(fn)
        source = None if path is None else Path(path).read_text()
    except (OSError, TypeError):
        source = None
    if source is None:
        raise TypeError(f"@cached needs the source file of {fn.__qualname__}")
    body = ast.parse(source).body
    bound: dict[str, list[int]] = {}
    for i, node in enumerate(body):
        for name in _binds(node):
            bound.setdefault(name, []).append(i)
    if fn.__name__ not in bound:
        raise TypeError(f"@cached cannot find def {fn.__name__} in {path}")
    todo, seen = [fn.__name__], {fn.__name__}
    picked: set[int] = set()
    while len(todo) > 0:
        for i in bound.get(todo.pop(), ()):
            if i in picked:
                continue
            picked.add(i)
            for n in ast.walk(body[i]):
                if isinstance(n, ast.Name) and n.id not in seen:
                    seen.add(n.id)
                    todo.append(n.id)
    return "\n".join(ast.dump(body[i], include_attributes=False) for i in sorted(picked))


def _binds(node: ast.stmt) -> Iterator[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        yield node.name
    elif isinstance(node, ast.TypeAlias):
        yield node.name.id
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        for a in node.names:
            yield a.name.split(".")[0] if a.asname is None else a.asname
    else:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, (ast.AnnAssign, ast.AugAssign))
            else []
        )
        for t in targets:
            yield from (n.id for n in ast.walk(t) if isinstance(n, ast.Name))


def _feed(update: Callable[[bytes], None], v: object, generators: list[_Generator]) -> None:
    """Feed `v` to a hash's `update`, collecting its generators in order."""

    def put(*parts: object) -> None:
        update(f"{'|'.join(map(str, parts))};".encode())

    if v is None or isinstance(v, (bool, int, float, str, bytes)):
        put(type(v).__name__, repr(v))
    elif isinstance(v, (tuple, list)):
        put(type(v).__qualname__, len(v))
        for x in cast("tuple[object, ...] | list[object]", v):
            _feed(update, x, generators)
    elif isinstance(v, dict):
        d = cast("dict[object, object]", v)
        put("dict", len(d))
        for k in sorted(d, key=str):
            if not isinstance(k, str):
                raise TypeError(f"@cached takes dicts with string keys, got {k!r}")
            put(repr(k))
            _feed(update, d[k], generators)
    elif isinstance(v, np.ndarray):
        a = cast("_Array", v)
        if a.dtype.hasobject:
            raise TypeError("@cached takes numpy arrays of numbers, not objects")
        put("ndarray", a.dtype.str, a.shape)
        update(np.ascontiguousarray(a).tobytes())
    elif isinstance(v, np.generic):
        put("scalar", v.dtype.str)
        update(v.tobytes())
    elif isinstance(v, Params):
        put("params", type(v).__qualname__)
        _feed(update, {f.name: getattr(v, f.name) for f in dataclasses.fields(v)}, generators)
    elif isinstance(v, Noise):
        put("noise")
        _feed(update, v._pa, generators)
    elif isinstance(v, (np.random.Generator, random.Random)):
        put(type(v).__qualname__)
        _feed(update, _state(v), generators)
        generators.append(v)
    else:
        raise TypeError(f"@cached cannot key an argument of type {type(v).__qualname__}")


def _read_only(v: object) -> object:
    """`v` with every array in it replaced by a read-only view."""
    if isinstance(v, np.ndarray):
        view = cast("_Array", v).view()
        view.flags.writeable = False
        return view
    if type(v) is tuple:
        return tuple(_read_only(x) for x in cast("tuple[object, ...]", v))
    if type(v) is list:
        return [_read_only(x) for x in cast("list[object]", v)]
    if type(v) is dict:
        return {k: _read_only(x) for k, x in cast("dict[object, object]", v).items()}
    return v


def _state(g: _Generator) -> object:
    return g.bit_generator.state if isinstance(g, np.random.Generator) else g.getstate()


def _restore(g: _Generator, state: object) -> None:
    if isinstance(g, np.random.Generator):
        g.bit_generator.state = cast("dict[str, object]", state)
    else:
        g.setstate(cast("tuple[object, ...]", state))


# Values


def _pack(value: object) -> _Packed:
    arrays: list[_Array] = []

    def go(v: object) -> object:
        if v is None or isinstance(v, (bool, int, float, str)):
            return v
        if isinstance(v, Vec):
            return {"vec": [go(v.x), go(v.y)]}
        if isinstance(v, (tuple, list)):
            tag = "tuple" if isinstance(v, tuple) else "list"
            if type(v) not in (tuple, list):
                raise TypeError(f"@cached cannot return a {type(v).__qualname__}")
            return {tag: [go(x) for x in cast("list[object]", v)]}
        if isinstance(v, dict):
            d = cast("dict[object, object]", v)
            if not all(isinstance(k, str) for k in d):
                raise TypeError("@cached returns dicts with string keys only")
            return {"dict": {cast("str", k): go(x) for k, x in d.items()}}
        if isinstance(v, bytes):
            arrays.append(np.frombuffer(v, np.uint8).copy())
            return {"bytes": len(arrays) - 1}
        if isinstance(v, (np.ndarray, np.generic)):
            a = np.array(v)
            if a.dtype.hasobject:
                raise TypeError("@cached cannot return numpy arrays of objects")
            arrays.append(a)
            return {"array" if isinstance(v, np.ndarray) else "scalar": len(arrays) - 1}
        raise TypeError(f"@cached cannot return a {type(v).__qualname__}")

    skeleton = json.dumps(go(value))
    return _Packed(skeleton, tuple(arrays))


def _unpack(packed: _Packed) -> object:
    def go(v: object) -> object:
        if not isinstance(v, dict):
            return v
        ((tag, x),) = cast("dict[str, object]", v).items()
        match tag:
            case "vec":
                vx, vy = cast("list[float]", go({"list": x}))
                return Vec(vx, vy)
            case "tuple":
                return tuple(go(i) for i in cast("list[object]", x))
            case "list":
                return [go(i) for i in cast("list[object]", x)]
            case "dict":
                return {k: go(i) for k, i in cast("dict[str, object]", x).items()}
            case "bytes":
                return packed.arrays[cast("int", x)].tobytes()
            case "array":
                return packed.arrays[cast("int", x)].copy()
            case "scalar":
                return packed.arrays[cast("int", x)][()]
            case _:
                raise ValueError(f"unknown tag {tag!r}")

    return go(json.loads(packed.skeleton))


# Disk


def _read(path: Path) -> _Packed | None:
    try:
        with np.load(path, allow_pickle=False) as f:
            # arr_0 is the skeleton, then the arrays in order
            names = cast("list[str]", f.files)
            got = [cast("_Array", f[f"arr_{i}"]) for i in range(len(names))]
        packed = _Packed(str(got[0]), tuple(got[1:]))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile):
        with contextlib.suppress(OSError):
            path.unlink()
        return None
    with contextlib.suppress(OSError):
        os.utime(path)  # pruning goes by mtime, oldest first
    return packed


def _write(path: Path, packed: _Packed) -> None:
    """Write `packed` atomically, then prune; a disk that refuses only loses the cache."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.stem}.{os.getpid()}.tmp")
        with tmp.open("wb") as f:
            np.savez(f, np.array(packed.skeleton), *packed.arrays)
        tmp.replace(path)
        _prune(path.parent.parent)
    except OSError:
        pass


def _prune(root: Path) -> None:
    files: list[tuple[float, int, Path]] = []
    for d in root.iterdir():
        if d.is_dir():
            for p in d.glob("*.npz"):
                with contextlib.suppress(OSError):
                    st = p.stat()
                    files.append((st.st_mtime, st.st_size, p))
    total = sum(size for _, size, _ in files)
    if total <= DISK_BYTES:
        return
    for _, size, p in sorted(files):
        if total <= DISK_BYTES * 3 // 4:
            break
        with contextlib.suppress(OSError):
            p.unlink()
            total -= size
