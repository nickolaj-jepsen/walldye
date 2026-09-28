"""Helpers for the core tests: loading the fixture designs and the themes to serialise under."""

import importlib.util
import itertools
import sys
from pathlib import Path

from walldye import _basis, _theme
from walldye._design import Design, RenderSpec
from walldye._params import Params

DESIGNS = Path(__file__).parent / "designs"
_fresh = itertools.count()


def load(slug: str) -> Design[Params]:
    """A fresh import of the fixture design `slug`, under a module name never used before."""
    return load_file(DESIGNS / slug / "design.py")


def load_file(path: Path) -> Design[Params]:
    """A fresh import of the design file `path`, under a module name never used before.

    Raises AssertionError when the module has no @design draw.
    """
    name = f"_walldye_core_test_{path.parent.name.replace('-', '_')}_{next(_fresh)}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        del sys.modules[name]
    d = mod.draw
    assert isinstance(d, Design)
    return d


def tokens(theme: tuple[str, str, str]) -> dict[str, str]:
    """The 21-token dict of a (bg, fg, accent) seed triple."""
    return _theme.theme_tokens(dict(zip(_theme.SEEDS, theme, strict=True)))


def themes(regime: str) -> list[dict[str, str]]:
    """Every theme the tools serialise a document of `regime` under: its template preset, the
    basis, the held-out set and the probes."""
    template = _theme.parse_theme("fireproof" if regime == "dark" else "flexoki-light")
    rest = _basis.BASIS[regime] + _basis.HELD_OUT[regime] + _basis.PROBES[regime]
    return [template, *(tokens(t) for t in rest)]


def spec(design: Design[Params], variant: str, aspect: str, regime: str) -> RenderSpec:
    """The RenderSpec of one render of `design`."""
    assert regime in ("dark", "light")
    return RenderSpec(
        variant, design.params(variant), aspect, "light" if regime == "light" else "dark"
    )
