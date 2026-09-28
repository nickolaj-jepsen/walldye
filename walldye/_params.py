"""Typed, frozen design parameters: Params subclasses, knob() fields and their schema."""

import dataclasses
import inspect
import math
import typing
import weakref
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, dataclass_transform, final, overload

import numpy as np

from ._vec import NUM_TYPES

type Kind = Literal["int", "float", "bool", "str", "seed"]
type Value = int | float | bool | str | None


@final
@dataclass(frozen=True, slots=True)
class Knob:
    """knob()'s arguments, recorded in the field's metadata under "walldye"; the class that
    owns the field validates them."""

    lo: object
    hi: object
    choices: object
    doc: object
    unit: object


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
def knob[T](*, default: T, doc: str = "") -> T: ...
def knob(
    *,
    default: object,
    lo: float | None = None,
    hi: float | None = None,
    choices: Sequence[object] | None = None,
    doc: str = "",
    unit: str = "",
) -> object:
    """A Params field with a default, an optional soft range [lo, hi] (bounds sweeps; --set
    warns outside it), optional hard `choices`, a one-line `doc` and a display `unit`.

    Every argument is keyword-only, so type checkers see the default. The class creating the
    field validates the arguments (see ParamsMeta).
    """
    return dataclasses.field(
        default=default,
        metadata={"walldye": Knob(lo, hi, choices, doc, unit)},
    )


@final
@dataclass(frozen=True, slots=True)
class _Field:
    """One validated field of a Params class."""

    name: str
    kind: Kind
    default: Value
    literal: tuple[int | str, ...] | None
    lo: int | float | None = None
    hi: int | float | None = None
    choices: tuple[int | str, ...] | None = None
    doc: str = ""
    unit: str = ""

    def check(self, owner: str, v: object) -> Value:
        """`v` converted for this field (numpy numbers to int or float, ints to float).

        Raises TypeError for the wrong type and ValueError for a value outside the choices,
        a non-finite float or a negative seed.
        """
        what = f"{owner}.{self.name}"
        if self.kind == "seed":
            if v is None:
                return None
            n = _int(v, what)
            if n < 0:
                raise ValueError(f"{what} takes None or an int >= 0, got {v!r}")
            return n
        if self.kind == "bool":
            if not isinstance(v, bool):
                raise TypeError(f"{what} takes a bool, got {v!r}")
            return v
        out: Value
        if self.kind == "int":
            out = _int(v, what)
        elif self.kind == "float":
            if isinstance(v, bool) or not isinstance(v, NUM_TYPES):
                raise TypeError(f"{what} takes a float, got {v!r}")
            out = float(v)
            if not math.isfinite(out):
                raise ValueError(f"{what} takes a finite float, got {v!r}")
        elif isinstance(v, str):
            out = v
        else:
            raise TypeError(f"{what} takes a str, got {v!r}")
        for allowed in (self.literal, self.choices):
            if allowed is not None and out not in allowed:
                raise ValueError(f"{what} takes one of {', '.join(map(repr, allowed))}, got {v!r}")
        return out


def _int(v: object, what: str) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, np.integer)):
        raise TypeError(f"{what} takes an int, got {v!r}")
    return int(v)


_FIELDS: Final[weakref.WeakKeyDictionary[type, tuple[_Field, ...]]] = weakref.WeakKeyDictionary()

_SEED: Final = _Field("seed", "seed", None, None, doc="moves every random stream")


def _kind(owner: str, name: str, ann: object) -> tuple[Kind, tuple[int | str, ...] | None]:
    """The kind and Literal members of an annotation; TypeError for anything unsupported."""
    for t, kind in ((bool, "bool"), (int, "int"), (float, "float"), (str, "str")):
        if ann is t:
            return kind, None
    if typing.get_origin(ann) is Literal:
        members: tuple[object, ...] = typing.get_args(ann)
        if all(isinstance(m, str) for m in members):
            return "str", tuple(str(m) for m in members)
        if all(isinstance(m, int) and not isinstance(m, bool) for m in members):
            return "int", tuple(m for m in members if isinstance(m, int))
    raise TypeError(
        f"{owner}.{name}: a param is int, float, bool, str or a Literal of str or of int values,"
        f" got {ann!r}"
    )


def _num_or_none(v: object, what: str) -> int | float | None:
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, NUM_TYPES):
        raise TypeError(f"{what} takes a number, got {v!r}")
    return int(v) if isinstance(v, (int, np.integer)) else float(v)


def _field(owner: str, name: str, ann: object, value: object) -> _Field:
    """The validated field `name: ann = value` of class `owner`."""
    if name.startswith("_"):
        raise TypeError(f"{owner}.{name}: param names do not start with '_'")
    if name == "seed":
        raise TypeError(f"{owner}.seed: seed is declared by Params; set it in a variant instead")
    kind, literal = _kind(owner, name, ann)
    raw = Knob(None, None, None, "", "")
    if isinstance(value, dataclasses.Field):
        fld: dataclasses.Field[object] = value
        if fld.default is dataclasses.MISSING:
            raise TypeError(f"{owner}.{name} has no default; the default variant is {owner}()")
        meta = fld.metadata.get("walldye")
        if isinstance(meta, Knob):
            raw = meta
        value = fld.default
    lo, hi = _num_or_none(raw.lo, f"{owner}.{name} lo"), _num_or_none(raw.hi, f"{owner}.{name} hi")
    if (lo is not None or hi is not None) and (kind not in ("int", "float") or literal is not None):
        raise TypeError(f"{owner}.{name}: lo and hi are for int and float params")
    choices: tuple[int | str, ...] | None = None
    if raw.choices is not None:
        if lo is not None or hi is not None:
            raise TypeError(f"{owner}.{name}: give choices or lo and hi, not both")
        if kind not in ("int", "str") or isinstance(raw.choices, str):
            raise TypeError(f"{owner}.{name}: choices are a sequence of int or str values")
        if not isinstance(raw.choices, (tuple, list)):
            raise TypeError(f"{owner}.{name}: choices are a tuple or list, got {raw.choices!r}")
        seq: tuple[object, ...] | list[object] = raw.choices
        base = _Field(name, kind, None, literal)
        choices = tuple(c for c in (base.check(owner, c) for c in seq) if isinstance(c, (int, str)))
        if len(choices) == 0:
            raise ValueError(f"{owner}.{name}: choices are empty")
    if not isinstance(raw.doc, str) or not isinstance(raw.unit, str):
        raise TypeError(f"{owner}.{name}: doc and unit are str")
    field = _Field(name, kind, None, literal, lo, hi, choices, raw.doc, raw.unit)
    default = field.check(owner, value)
    if lo is not None and hi is not None and lo > hi:
        raise ValueError(f"{owner}.{name}: lo {lo} is above hi {hi}")
    if isinstance(default, (int, float)) and (
        (lo is not None and default < lo) or (hi is not None and default > hi)
    ):
        raise ValueError(f"{owner}.{name}: default {default} is outside {lo}..{hi}")
    return dataclasses.replace(field, default=default)


@dataclass_transform(frozen_default=True, kw_only_default=True, field_specifiers=(knob,))
class ParamsMeta(type):
    """Makes every Params class a frozen, keyword-only dataclass and validates its fields.

    Class creation raises TypeError for a field without a default, an unsupported annotation,
    a name starting with '_', a redeclared seed, lo/hi on a non-numeric field or choices with
    lo/hi; ValueError for lo > hi, or a default outside [lo, hi] or the choices.
    """

    def __new__(
        mcs, name: str, bases: tuple[type, ...], ns: dict[str, object], /, **kwargs: object
    ) -> "ParamsMeta":
        cls = super().__new__(mcs, name, bases, ns, **kwargs)
        parents = [b for b in bases if isinstance(b, ParamsMeta)]
        own: list[_Field] = []
        if len(parents) > 0:
            anns: dict[str, object] = inspect.get_annotations(cls, eval_str=True)
            for field_name, ann in anns.items():
                if field_name not in ns:
                    raise TypeError(
                        f"{name}.{field_name} has no default; the default variant is {name}()"
                    )
                own.append(_field(name, field_name, ann, ns[field_name]))
        inherited = [f for b in parents for f in _FIELDS.get(b, ()) if f.name != "seed"]
        klass: type = cls  # Pyrefly takes a ParamsMeta instance for a class only through `type`
        dataclasses.dataclass(frozen=True, kw_only=True)(klass)
        _FIELDS[cls] = (*inherited, *own, _SEED)
        return cls


class Params(metaclass=ParamsMeta):
    """The base of a design's parameters: a frozen, typed, keyword-only dataclass.

    `seed`, when set, moves every random stream (Canvas.rng and friends). Instances validate
    their values: TypeError for a wrong type, ValueError outside hard choices; numbers are
    stored as int or float, so Moon(phase=90) == Moon(phase=90.0).
    """

    seed: int | None = None

    def __post_init__(self) -> None:
        owner = type(self).__name__
        for f in _FIELDS[type(self)]:
            object.__setattr__(self, f.name, f.check(owner, getattr(self, f.name)))


@final
@dataclass(frozen=True, slots=True)
class KnobInfo:
    """One field of a params schema, for the tools."""

    name: str
    kind: Kind
    default: Value
    lo: float | None
    hi: float | None
    choices: tuple[int | str, ...] | None
    doc: str
    unit: str


def describe(params_type: type[Params]) -> tuple[KnobInfo, ...]:
    """The schema of `params_type`: its fields in declaration order, seed last.

    `choices` come from choices=, else from a Literal annotation. Raises TypeError for a class
    that is not a Params class.
    """
    fields = _FIELDS.get(params_type)
    if fields is None:
        raise TypeError(f"not a Params class: {params_type!r}")
    return tuple(
        KnobInfo(
            f.name,
            f.kind,
            f.default,
            None if f.lo is None else float(f.lo),
            None if f.hi is None else float(f.hi),
            f.choices if f.choices is not None else f.literal,
            f.doc,
            f.unit,
        )
        for f in fields
    )
