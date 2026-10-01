"""Theme presets, the theme token grammar, and the themes the build's checks draw under.

Theme token grammar (parse_seeds): a preset name, `bg-fg-accent`, `bg,fg,accent` or
`bg=..,fg=..,accent=..`, each seed 3 or 6 hex digits with an optional `#`.

The check themes map a regime to Seeds; fireproof appears in none of them.
"""

import random
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from walldye._theme import (
    FIREPROOF,
    REGIMES,
    SEEDS,
    Regime,
    Seeds,
    normalize_seed,
    regime,
    theme_tokens,
)

PRESETS: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {
        "fireproof": FIREPROOF,
        "flexoki-light": {"bg": "#FFFCF0", "fg": "#100F0F", "accent": "#BC5215"},
        "ayu-dark": {"bg": "#0B0E14", "fg": "#BFBDB6", "accent": "#E6B450"},
        # ayu's keyword orange: its #FFAA33 accent all but vanishes on the light ground.
        "ayu-light": {"bg": "#FCFCFC", "fg": "#5C6166", "accent": "#FA8D3E"},
        "catppuccin-mocha": {"bg": "#1E1E2E", "fg": "#CDD6F4", "accent": "#CBA6F7"},
        "catppuccin-latte": {"bg": "#EFF1F5", "fg": "#4C4F69", "accent": "#8839EF"},
        "dracula": {"bg": "#282A36", "fg": "#F8F8F2", "accent": "#FF79C6"},
        # The scheme's orange: its green sits too close to fg for a highlight to stand out.
        "everforest-dark": {"bg": "#2D353B", "fg": "#D3C6AA", "accent": "#E69875"},
        "everforest-light": {"bg": "#FDF6E3", "fg": "#5C6A72", "accent": "#F57D26"},
        "gruvbox-dark": {"bg": "#282828", "fg": "#EBDBB2", "accent": "#FE8019"},
        "gruvbox-light": {"bg": "#FBF1C7", "fg": "#3C3836", "accent": "#AF3A03"},
        "nord": {"bg": "#2E3440", "fg": "#ECEFF4", "accent": "#88C0D0"},
        # "love", not the usual "rose", which sits too close to fg for a highlight to stand out.
        "rose-pine": {"bg": "#191724", "fg": "#E0DEF4", "accent": "#EB6F92"},
        "rose-pine-dawn": {"bg": "#FAF4ED", "fg": "#575279", "accent": "#B4637A"},
        "solarized-dark": {"bg": "#002B36", "fg": "#93A1A1", "accent": "#CB4B16"},
        "solarized-light": {"bg": "#FDF6E3", "fg": "#586E75", "accent": "#CB4B16"},
        "tokyo-night": {"bg": "#1A1B26", "fg": "#C0CAF5", "accent": "#7AA2F7"},
        "tokyo-night-day": {"bg": "#E1E2E7", "fg": "#3760BF", "accent": "#9854F1"},
    }
)
DEFAULT_THEME: Final = "fireproof"

# A theme token, a seed mapping or a (bg, fg, accent) triple.
type Theme = str | Mapping[str, str] | tuple[str, str, str]


def preset_seeds(name: str) -> Seeds:
    """The seeds of preset `name`; KeyError for an unknown name."""
    p = PRESETS[name]
    return Seeds(p["bg"], p["fg"], p["accent"])


def parse_seeds(spec: str | None) -> dict[str, str]:
    """Seeds {bg, fg, accent} (uppercase #RRGGBB) for a theme token; None or "" means DEFAULT_THEME.

    Raises ValueError for anything outside the grammar: unknown names, a wrong seed count,
    keys other than bg/fg/accent (per-token overrides), or a preset combined with overrides.
    """
    spec = (DEFAULT_THEME if spec is None or spec == "" else spec).strip()
    if spec in PRESETS:
        return preset_seeds(spec)._asdict()
    if "=" in spec:
        pairs = [p.split("=", 1) for p in spec.split(",")]
        values = {p[0].strip(): p[1] for p in pairs if len(p) == 2}
        if len(values) != len(pairs) or values.keys() != set(SEEDS):
            raise ValueError(
                f"theme {spec!r}: keyed form takes exactly bg=, fg= and accent=,"
                " no preset or other tokens"
            )
        return {k: normalize_seed(values[k]) for k in SEEDS}
    parts = spec.split("," if "," in spec else "-")
    if len(parts) != 3:
        raise ValueError(
            f"unknown theme {spec!r}: use a preset ({', '.join(PRESETS)}) or bg-fg-accent hex seeds"
        )
    return {k: normalize_seed(v) for k, v in zip(SEEDS, parts)}


def parse_theme(spec: str | None) -> dict[str, str]:
    """All 21 tokens for a theme token (see parse_seeds)."""
    return theme_tokens(parse_seeds(spec))


def theme_token(seeds: Mapping[str, str]) -> str:
    """Canonical token for {bg, fg, accent}: the preset name when the seeds equal a preset's,
    else lowercase `bg-fg-accent` without `#`."""
    s = Seeds(*(normalize_seed(seeds[k]) for k in SEEDS))
    for name in PRESETS:
        if s == preset_seeds(name):
            return name
    return "-".join(v[1:].lower() for v in s)


def seeds_of(theme: Theme) -> dict[str, str]:
    """{bg, fg, accent} of a theme token, a seed mapping or a (bg, fg, accent) triple."""
    if isinstance(theme, str):
        return parse_seeds(theme)
    if isinstance(theme, tuple):
        return dict(zip(SEEDS, theme, strict=True))
    return {k: normalize_seed(theme[k]) for k in SEEDS}


def tokens_of(theme: Theme) -> dict[str, str]:
    """The 21 tokens of a theme token, seed mapping or seed triple."""
    return theme_tokens(seeds_of(theme))


def regime_of(theme: Theme) -> Regime:
    """The regime a theme's seeds select."""
    s = seeds_of(theme)
    return regime(s["bg"], s["fg"])


HELD_OUT_SEED = 2026


def generate(seed: int, n: int) -> dict[Regime, list[Seeds]]:
    """`n` random themes per regime from random.Random(`seed`): each draw is three
    getrandbits(24) colors, filed under its regime or discarded once that regime is full."""
    r = random.Random(seed)
    out: dict[Regime, list[Seeds]] = {"dark": [], "light": []}
    while any(len(v) < n for v in out.values()):
        theme = Seeds(
            f"#{r.getrandbits(24):06X}",
            f"#{r.getrandbits(24):06X}",
            f"#{r.getrandbits(24):06X}",
        )
        themes = out[regime(theme.bg, theme.fg)]
        if len(themes) < n:
            themes.append(theme)
    return out


# == generate(HELD_OUT_SEED, 4). Kept literal so the checks never move with random or
# generate(); a test checks it still holds.
_HELD_OUT_RANDOM: dict[Regime, list[Seeds]] = {
    "dark": [
        Seeds("#1E7EA4", "#51C9BC", "#80A4DF"),
        Seeds("#DC28FF", "#F3F492", "#1A4668"),
        Seeds("#8C3D5F", "#D7A7A3", "#BB049A"),
        Seeds("#C0433C", "#C5E818", "#96263A"),
    ],
    "light": [
        Seeds("#F38B2F", "#8306D0", "#A5AEC7"),
        Seeds("#E255AC", "#39292D", "#E51214"),
        Seeds("#99DD25", "#9F1995", "#8E7AA6"),
        Seeds("#6BAD6B", "#C88B28", "#9293DE"),
    ],
}
_CORNERS: dict[Regime, list[Seeds]] = {
    "dark": [
        Seeds("#000000", "#FFFFFF", "#FF0000"),
        Seeds("#10141C", "#D8E0E8", "#D8E0E8"),  # accent == fg
        Seeds("#10141C", "#D8E0E8", "#10141C"),  # accent == bg
        Seeds("#404850", "#58606A", "#C07850"),  # luminance gap 0.052
    ],
    "light": [
        Seeds("#FFFFFF", "#000000", "#0000FF"),
        Seeds("#F4EEE0", "#2A2622", "#2A2622"),
        Seeds("#F4EEE0", "#2A2622", "#F4EEE0"),
        Seeds("#58606A", "#404850", "#C07850"),
    ],
}
_PRESET_SEEDS: list[Seeds] = [preset_seeds(name) for name in PRESETS if name != "fireproof"]

# Slot coefficients must predict these within 2 RGB units: every preset but fireproof, corners,
# random.
HELD_OUT: dict[Regime, list[Seeds]] = {
    r: [t for t in _PRESET_SEEDS if regime(t.bg, t.fg) == r] + _CORNERS[r] + _HELD_OUT_RANDOM[r]
    for r in REGIMES
}

# Skeleton check only. Collapse: every token lands on (nearly) one hex, so
# color-keyed dicts merge; an exact tie is dark, so light's bg sits one unit above fg.
# Order: bg/fg/accent chosen so token hex strings sort roughly opposite to the regime's
# template theme (fireproof, flexoki-light), so anything sorted by hex reorders.
PROBES: dict[Regime, list[Seeds]] = {
    "dark": [Seeds("#808080", "#808080", "#808080"), Seeds("#3F0000", "#00C0C0", "#0000FF")],
    "light": [Seeds("#818181", "#808080", "#808080"), Seeds("#00C0C0", "#3F0000", "#FF0000")],
}

# An ordinary theme per regime that the determinism check hashes draws under.
SAMPLE: dict[Regime, Seeds] = {r: _HELD_OUT_RANDOM[r][0] for r in REGIMES}
