"""Where the tools find the repo and a piece's files, and what they name the templates."""

import os
import re
from pathlib import Path
from typing import Final

from walldye._aspect import canvas_size

# An editable install sits in a checkout two levels up; an installed package (the Nix one) is
# pointed at a folder holding wallpapers/ by $WALLDYE_ROOT.
_ROOT_ENV: Final = os.environ.get("WALLDYE_ROOT", "")


ROOT: Final = Path(_ROOT_ENV) if _ROOT_ENV != "" else Path(__file__).resolve().parents[2]


WALLPAPERS = ROOT / "wallpapers"


TAXONOMY = WALLPAPERS / "taxonomy.yaml"


FEATURED = WALLPAPERS / "featured.yaml"  # the site's featured pieces, one `- <slug>` line each


_SLUG: Final = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def cache_dir() -> Path | None:
    """Where preview, render and sheet keep @cached results: $WALLDYE_CACHE, else
    .cache/cached/ in the checkout; None when $WALLDYE_CACHE is `off`."""
    env = os.environ.get("WALLDYE_CACHE", "")
    if env == "off":
        return None
    return Path(env) if env != "" else ROOT / ".cache" / "cached"


def piece_dir(slug: str) -> Path:
    """wallpapers/<slug>/, whether or not it exists; ValueError unless `slug` is lowercase
    words joined by single hyphens."""
    if _SLUG.fullmatch(slug) is None:
        raise ValueError(f"bad slug {slug!r} (lowercase letters and digits, single hyphens)")
    return WALLPAPERS / slug


def build_dir(slug: str, variant: str = "default") -> Path:
    """build/ for the default variant, build/<variant>/ for a named one."""
    b = piece_dir(slug) / "build"
    return b if variant == "default" else b / variant


def slugs() -> list[str]:
    """Sorted slugs of every wallpapers/<slug>/ holding a meta.yaml."""
    return sorted(p.parent.name for p in WALLPAPERS.glob("*/meta.yaml"))


def is_legacy(slug: str) -> bool:
    """True for a script-less piece (source.svg + palette.yaml); FileNotFoundError if it is
    neither kind."""
    d = piece_dir(slug)
    if (d / "design.py").exists():
        return False
    if (d / "source.svg").exists():
        return True
    raise FileNotFoundError(f"{d} has neither design.py nor source.svg")


def is_aspect(value: str) -> bool:
    """Whether `value` names an aspect canvas_size() accepts ('16:9', '3440x1440')."""
    try:
        w, h = canvas_size(value)
    except (ValueError, ZeroDivisionError, OverflowError):
        return False
    return w > 0 and h > 0


def key(slug: str, variant: str, aspect: str, regime: str) -> str:
    """The cache, file and subprocess key of one render."""
    return f"{slug}@{variant}@{aspect}@{regime}"


TEMPLATE_NAME: Final = re.compile(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(\.light)?\.svg")


def aspect_label(aspect: str) -> str:
    """File label of an aspect: '9:19.5' -> '9x19.5'."""
    a, b = aspect.lower().replace("x", ":").split(":")
    return f"{float(a):g}x{float(b):g}"


def template_name(aspect: str, light: bool = False) -> str:
    """Template file name: '16:9' -> '16x9.svg'; '9:19.5' with `light` -> '9x19.5.light.svg'."""
    return f"{aspect_label(aspect)}{'.light' if light else ''}.svg"


def parse_template_name(name: str) -> tuple[str, bool]:
    """(aspect, light) of a template file name: '9x19.5.light.svg' -> ('9:19.5', True).

    Raises ValueError when `name` is not a template name.
    """
    m = TEMPLATE_NAME.fullmatch(name)
    if m is None:
        raise ValueError(f"not a template name: {name!r}")
    return f"{m.group(1)}:{m.group(2)}", m.group(3) is not None
