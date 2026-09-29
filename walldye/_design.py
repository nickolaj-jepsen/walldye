"""The @design decorator and the Design it makes: variants, aspects and drawing to a Document."""

import inspect
import pathlib
import re
import typing
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal, cast, final

from ._aspect import SITE_ASPECTS, Aspect, canvas_size, native_aspects
from ._canvas import Canvas
from ._color import BG, Color
from ._document import Builder, Document
from ._params import Params

MAX_VARIANTS: Final = 4
_VARIANT_NAME: Final = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


@final
@dataclass(frozen=True, slots=True)
class RenderSpec:
    """One render: which version, with which params, at which aspect, in which regime."""

    variant: str  # "default" or a named variant; a label for keys
    params: Params  # the values drawn (a variant's, or with --set overrides)
    aspect: str  # anything _aspect.canvas_size accepts
    regime: Literal["dark", "light"]


@final
class Design[Pm: Params]:
    """A decorated draw function with its params type, variants, aspects and background."""

    def __init__(
        self,
        fn: Callable[[Canvas[Pm]], None],
        params_type: type[Pm],
        declared_aspects: Literal["any"] | tuple[Aspect, ...],
        variants: Mapping[str, Pm],
        bg: Color,
    ) -> None:
        """Internal: @design(...) makes Designs."""
        self.fn: Final = fn
        self.params_type: Final = params_type
        self.declared_aspects: Final = declared_aspects
        self.aspects: Final = native_aspects(declared_aspects)
        self.variants: Final[Mapping[str, Pm]] = MappingProxyType(dict(variants))
        self.bg: Final = bg
        self.source: Final = pathlib.Path(fn.__code__.co_filename)

    def variant_names(self) -> tuple[str, ...]:
        """("default", *variants), in declaration order."""
        return ("default", *self.variants)

    def params(self, variant: str = "default") -> Pm:
        """The params of a version: params_type() for "default". Raises KeyError for an
        unknown name."""
        if variant == "default":
            return self.params_type()
        if variant not in self.variants:
            raise KeyError(f"no variant {variant!r} (have: {', '.join(self.variant_names())})")
        return self.variants[variant]

    def draw(self, spec: RenderSpec) -> Document:
        """Draw one render: a canvas of canvas_size(spec.aspect), the bg rectangle, then fn.

        Raises TypeError unless type(spec.params) is params_type, ValueError for an unknown
        regime or aspect; whatever the design raises propagates.
        """
        params = spec.params
        if type(params) is not self.params_type or not isinstance(params, self.params_type):
            raise TypeError(
                f"{self.source.parent.name} draws {self.params_type.__name__},"
                f" got {type(params).__name__}"
            )
        if spec.regime not in ("dark", "light"):
            raise ValueError(f"regime is 'dark' or 'light', got {spec.regime!r}")
        w, h = canvas_size(spec.aspect)
        doc = Builder(w, h, spec.regime)
        doc.body.append([f'<rect x="0" y="0" width="{w}" height="{h}" fill="', self.bg, '"/>'])
        canvas = Canvas(params, w=w, h=h, light=spec.regime == "light", doc=doc, source=self.source)
        try:
            self.fn(canvas)
        finally:
            canvas._close()
        return doc.finish()


def _aspects(aspects: object) -> Literal["any"] | tuple[Aspect, ...]:
    if aspects == "any":
        return "any"
    if not isinstance(aspects, tuple):
        # A lone aspect string is a wrong value of the right kind: aspects=("16:9",) was meant.
        error = ValueError if isinstance(aspects, str) else TypeError
        raise error(f'aspects is "any" or a tuple of {", ".join(SITE_ASPECTS)}; got {aspects!r}')
    items: tuple[object, ...] = aspects
    out = tuple(a for a in SITE_ASPECTS if a in items)
    if len(items) == 0 or len(out) != len(items):
        raise ValueError(f"aspects are one or more of {', '.join(SITE_ASPECTS)}; got {aspects!r}")
    return out


def _params_type(fn: Callable[..., object], variants: bool) -> type[Params]:
    """The params class from draw's annotation Canvas[X]: X, or Params for a bare Canvas or
    no annotation."""
    sig = inspect.signature(fn)
    ps = list(sig.parameters.values())
    positional = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if len(ps) != 1 or ps[0].kind not in positional:
        raise TypeError(f"draw takes exactly one positional parameter, got {sig}")
    ann: object = typing.get_type_hints(fn).get(ps[0].name)
    if ann is None:
        if variants:
            raise TypeError("annotate draw(s: Canvas[YourParams])")
        return Params
    if ann is Canvas:
        return Params
    if typing.get_origin(ann) is Canvas:
        (arg,) = typing.get_args(ann)
        if isinstance(arg, type) and issubclass(arg, Params):
            return arg
    raise TypeError(f"annotate draw(s: Canvas[YourParams]), got {ann!r}")


def _variants[P: Params](variants: Mapping[str, P] | None, params_type: type[P]) -> dict[str, P]:
    if variants is None:
        return {}
    if not isinstance(variants, Mapping):
        raise TypeError(f"variants is a mapping of name to params, got {variants!r}")
    if len(variants) > MAX_VARIANTS:
        raise ValueError(
            f"at most {MAX_VARIANTS} named variants ({MAX_VARIANTS + 1} versions with the"
            f" default), got {len(variants)}"
        )
    default = params_type()
    out: dict[str, P] = {}
    for name, value in variants.items():
        if not isinstance(name, str) or _VARIANT_NAME.fullmatch(name) is None or len(name) > 24:
            raise ValueError(
                "variant names are lowercase words joined by '-', up to 24 characters;"
                f" got {name!r}"
            )
        if name == "default":
            raise ValueError("'default' names the unnamed version; pick another variant name")
        if type(value) is not params_type:
            cls = type(value).__name__
            if params_type is Params:
                raise TypeError(
                    f"variant {name!r} is an instance of {cls}; annotate draw(s: Canvas[{cls}])"
                )
            raise TypeError(
                f"variant {name!r} is an instance of {cls}; draw takes {params_type.__name__}"
            )
        if value == default:
            raise ValueError(f"variant {name!r} equals the default {params_type.__name__}()")
        for other, seen in out.items():
            if value == seen:
                raise ValueError(f"variants {other!r} and {name!r} are equal")
        out[name] = value
    return out


def design[Pm: Params](
    *,
    aspects: Literal["any"] | tuple[Aspect, ...] = ("16:9",),
    variants: Mapping[str, Pm] | None = None,
    bg: Color = BG,
) -> Callable[[Callable[[Canvas[Pm]], None]], Design[Pm]]:
    """Declare a design: decorates the one function draw(s: Canvas[P]) -> None.

    `aspects` is "any" (every site aspect) or a tuple of the site aspects the composition
    follows; 16:9 is always built. `variants` names up to 4 params instances of draw's params
    class besides the implicit default, each different from the default and from each other,
    named like "late" or "open-sea" (at most 24 characters, not "default"). `bg` is the color
    of the full-canvas rectangle drawn before draw runs.

    Raises TypeError for a non-tuple `aspects`, a bg that is not a theme color, a variant of
    another class, or a draw without exactly one positional parameter (or without a Canvas[P]
    annotation when there are variants); ValueError for unknown aspects, too many variants,
    bad variant names and equal variants.
    """
    declared = _aspects(aspects)
    if not isinstance(bg, Color):
        raise TypeError(f"bg takes a theme color, got {bg!r}")

    def wrap(fn: Callable[[Canvas[Pm]], None]) -> Design[Pm]:
        # The annotation is Canvas[Pm], so the class read from it is Pm.
        params_type = cast("type[Pm]", _params_type(fn, variants is not None))
        return Design(fn, params_type, declared, _variants(variants, params_type), bg)

    return wrap
