"""Theme model: three seeds (bg, fg, accent) derive the 21 tokens; pure functions only.

Tokens are relative to the seeds, so light themes invert on their own: BG_DEEP and BLACK sit
beyond bg, the greys step from bg to fg and ACCENT_1..8 from accent to bg. `fireproof` pins all
21 tokens by hand; its exact seeds resolve to that table, any other seeds are derived.

Theme token grammar (parse_seeds): a preset name, `bg-fg-accent`, `bg,fg,accent` or
`bg=..,fg=..,accent=..`, each seed 3 or 6 hex digits with an optional `#`.
"""

from __future__ import annotations

import re

SEEDS = ("bg", "fg", "accent")
TOKENS = (
    "black", "bg_deep", "bg", "bg_alt", "ui", "ui_alt", "ui_hi", "muted", "fg_alt", "fg",
    "accent_hi", "accent", "accent_1", "accent_2", "accent_3", "accent_4",
    "accent_5", "accent_6", "accent_7", "accent_8", "orange_dark",
)  # fmt: skip
# Fractions fitted to the hand-picked Flexoki/terracotta values of the default theme.
_GREY_T = {
    "bg_alt": 0.063,
    "ui": 0.126,
    "ui_alt": 0.189,
    "ui_hi": 0.31,
    "muted": 0.563,
    "fg_alt": 0.816,
}
_ACCENT_T = {
    "accent_1": 0.17, "accent_2": 0.26, "accent_3": 0.5, "accent_4": 0.56,
    "accent_5": 0.68, "accent_6": 0.8, "accent_7": 0.9, "accent_8": 0.955,
}  # fmt: skip

PRESETS: dict[str, dict[str, str]] = {
    # Pinned so the hand-picked greys and terracotta ramp render exactly.
    "fireproof": {
        "black": "#100F0F",
        "bg_deep": "#181716",
        "bg": "#1C1B1A",
        "bg_alt": "#282726",
        "ui": "#343331",
        "ui_alt": "#403E3C",
        "ui_hi": "#575653",
        "muted": "#878580",
        "fg_alt": "#B7B5AC",
        "fg": "#DAD8CE",
        "accent_hi": "#E08A6E",
        "accent": "#CF6A4C",
        "accent_1": "#B14D2F",
        "accent_2": "#A1462B",
        "accent_3": "#71311E",
        "accent_4": "#6B3528",
        "accent_5": "#55291F",
        "accent_6": "#40211B",
        "accent_7": "#2E1C19",
        "accent_8": "#241B19",
        "orange_dark": "#BC5215",
    },
    "flexoki-light": {"bg": "#FFFCF0", "fg": "#100F0F", "accent": "#BC5215"},
    "gruvbox-dark": {"bg": "#282828", "fg": "#EBDBB2", "accent": "#FE8019"},
    "nord": {"bg": "#2E3440", "fg": "#ECEFF4", "accent": "#88C0D0"},
    "catppuccin-mocha": {"bg": "#1E1E2E", "fg": "#CDD6F4", "accent": "#CBA6F7"},
    "tokyo-night": {"bg": "#1A1B26", "fg": "#C0CAF5", "accent": "#7AA2F7"},
    "rose-pine": {"bg": "#191724", "fg": "#E0DEF4", "accent": "#EBBCBA"},
    "everforest-dark": {"bg": "#2D353B", "fg": "#D3C6AA", "accent": "#A7C080"},
    "ayu-dark": {"bg": "#0B0E14", "fg": "#BFBDB6", "accent": "#E6B450"},
    "dracula": {"bg": "#282A36", "fg": "#F8F8F2", "accent": "#FF79C6"},
    "solarized-light": {"bg": "#FDF6E3", "fg": "#586E75", "accent": "#CB4B16"},
}
DEFAULT_THEME = "fireproof"

_SEED = re.compile(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def hex_to_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def rgb_to_hex(r: float, g: float, b: float) -> str:
    """Uppercase #RRGGBB; channels are clamped to 0..255 and rounded half to even."""
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, round(v))) for v in (r, g, b)))


def mix(a: str, b: str, t: float) -> str:
    """Linear RGB blend from `a` (t=0) to `b` (t=1)."""
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    return rgb_to_hex(ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t)


def luminance(c: str) -> float:
    """WCAG relative luminance of a hex colour, 0..1."""

    def lin(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(c)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def is_light(bg: str, fg: str) -> bool:
    """True for the light regime: bg strictly brighter than fg (equal luminance is dark)."""
    return luminance(bg) > luminance(fg)


def _recipe(light: bool) -> dict[str, tuple[str, str, float]]:
    """Every derived token as (x, y, t) for mix(x, y, t), where x and y name a seed or are the
    pole beyond bg (#000000 in the dark regime, #FFFFFF in the light one)."""
    beyond = "#FFFFFF" if light else "#000000"
    # Thin grey structure reads fainter on paper than on a dark ground; widen the low steps.
    boost = 1.6 if light else 1.0
    return {
        "bg_deep": ("bg", beyond, 0.15),
        "black": ("bg", beyond, 0.43),
        "accent_hi": ("accent", "fg", 0.28),
        **{
            k: ("bg", "fg", min(v * boost, 0.5) if k in ("bg_alt", "ui", "ui_alt", "ui_hi") else v)
            for k, v in _GREY_T.items()
        },
        **{k: ("accent", "bg", v) for k, v in _ACCENT_T.items()},
        "orange_dark": ("accent", "bg", _ACCENT_T["accent_1"]),
    }


def derive_theme(seeds: dict[str, str]) -> dict[str, str]:
    """Full token dict from `seeds`: needs bg, fg, accent; any other token is an override."""
    missing = {"bg", "fg", "accent"} - seeds.keys()
    if len(missing) > 0:
        raise ValueError(f"theme needs {', '.join(sorted(missing))}")
    unknown = seeds.keys() - set(TOKENS)
    if len(unknown) > 0:
        raise ValueError(
            f"unknown theme tokens: {', '.join(sorted(unknown))} (known: {', '.join(TOKENS)})"
        )
    recipe = _recipe(is_light(seeds["bg"], seeds["fg"]))
    t = {k: mix(seeds.get(x, x), seeds.get(y, y), v) for k, (x, y, v) in recipe.items()}
    t.update(seeds)
    return {k: t[k].upper() for k in TOKENS}


# (a, b, c, dr, dg, db): a colour equal to a*bg + b*fg + c*accent + d per channel, with the
# seeds and d in 0..255 channel units; a slots.json coefficient row.
type Coefs = tuple[float, float, float, float, float, float]


def blend_coefs(x: Coefs, y: Coefs, t: float) -> Coefs:
    """mix() from `x` (t=0) to `y` (t=1) on Coefs, without its rounding."""
    v = [p + (q - p) * t for p, q in zip(x, y, strict=True)]
    return (v[0], v[1], v[2], v[3], v[4], v[5])


def _end(name: str) -> Coefs:
    if name in SEEDS:
        a, b, c = (1.0 if name == s else 0.0 for s in SEEDS)
        return (a, b, c, 0.0, 0.0, 0.0)
    r, g, b = hex_to_rgb(name)
    return (0.0, 0.0, 0.0, float(r), float(g), float(b))


_COEFS: dict[bool, dict[str, Coefs]] = {
    light: {
        **{k: blend_coefs(_end(x), _end(y), v) for k, (x, y, v) in _recipe(light).items()},
        **{s: _end(s) for s in SEEDS},
    }
    for light in (False, True)
}


def token_coefs(name: str, light: bool) -> Coefs:
    """Token `name` of a derived theme in the light (or dark) regime as Coefs, exact before
    derive_theme rounds it. Fireproof's pinned tokens have no such form. KeyError for an
    unknown name."""
    return _COEFS[light][name]


def normalise_seed(c: str) -> str:
    """`c` (3 or 6 hex digits, optional `#`, any case) as uppercase #RRGGBB.

    Raises ValueError otherwise.
    """
    m = _SEED.fullmatch(c.strip())
    if m is None:
        raise ValueError(f"bad seed colour {c!r} (want 3 or 6 hex digits, optional #)")
    h = m.group(1)
    return "#" + (h if len(h) == 6 else "".join(ch * 2 for ch in h)).upper()


def _preset_seeds(name: str) -> dict[str, str]:
    return {k: PRESETS[name][k] for k in SEEDS}


def parse_seeds(spec: str | None) -> dict[str, str]:
    """Seeds {bg, fg, accent} (uppercase #RRGGBB) for a theme token; None or "" means DEFAULT_THEME.

    Raises ValueError for anything outside the grammar: unknown names, a wrong seed count,
    keys other than bg/fg/accent (per-token overrides), or a preset combined with overrides.
    """
    spec = (DEFAULT_THEME if spec is None or spec == "" else spec).strip()
    if spec in PRESETS:
        return _preset_seeds(spec)
    if "=" in spec:
        pairs = [p.split("=", 1) for p in spec.split(",")]
        values = {p[0].strip(): p[1] for p in pairs if len(p) == 2}
        if len(values) != len(pairs) or values.keys() != set(SEEDS):
            raise ValueError(
                f"theme {spec!r}: keyed form takes exactly bg=, fg= and accent=,"
                " no preset or other tokens"
            )
        return {k: normalise_seed(values[k]) for k in SEEDS}
    parts = spec.split("," if "," in spec else "-")
    if len(parts) != 3:
        raise ValueError(
            f"unknown theme {spec!r}: use a preset ({', '.join(PRESETS)}) or bg-fg-accent hex seeds"
        )
    return {k: normalise_seed(v) for k, v in zip(SEEDS, parts)}


def theme_tokens(seeds: dict[str, str]) -> dict[str, str]:
    """All 21 tokens for exactly {bg, fg, accent}: the pinned fireproof table for fireproof's
    exact seeds, derive_theme otherwise. Seeds are normalised first; ValueError on other keys."""
    if seeds.keys() != set(SEEDS):
        raise ValueError(
            f"theme seeds must be exactly bg, fg, accent (got {', '.join(sorted(seeds))})"
        )
    s = {k: normalise_seed(seeds[k]) for k in SEEDS}
    return derive_theme(PRESETS["fireproof"] if s == _preset_seeds("fireproof") else s)


def parse_theme(spec: str | None) -> dict[str, str]:
    """All 21 tokens for a theme token (see parse_seeds)."""
    return theme_tokens(parse_seeds(spec))


def theme_token(seeds: dict[str, str]) -> str:
    """Canonical token for {bg, fg, accent}: the preset name when the seeds equal a preset's,
    else lowercase `bg-fg-accent` without `#`."""
    s = {k: normalise_seed(seeds[k]) for k in SEEDS}
    for name in PRESETS:
        if s == _preset_seeds(name):
            return name
    return "-".join(s[k][1:].lower() for k in SEEDS)
