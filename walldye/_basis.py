"""Themes for the slot fit: the committed basis, the held-out set and the skeleton probes.

A theme here is a (bg, fg, accent) triple of uppercase #RRGGBB seeds; each dict maps a regime
("dark" or "light", per _theme.is_light) to its themes. Fireproof appears in none of them.
"""

from __future__ import annotations

import random

import numpy as np

from ._theme import PRESETS, SEEDS, hex_to_rgb, is_light

Theme = tuple[str, str, str]
MAX_COND = 15
BASIS_SEED = 0
HELD_OUT_SEED = 2026


def regime(theme: Theme) -> str:
    """Regime name of a theme: "light" when bg is brighter than fg, else "dark"."""
    return "light" if is_light(theme[0], theme[1]) else "dark"


def generate(seed: int, n: int) -> dict[str, list[Theme]]:
    """`n` random themes per regime from random.Random(`seed`).

    Each draw is three uniform 24-bit colours (bg, fg, accent via getrandbits(24)) filed under
    its regime; draws for a regime that is already full are discarded.
    """
    r = random.Random(seed)
    out: dict[str, list[Theme]] = {"dark": [], "light": []}
    while any(len(v) < n for v in out.values()):
        theme = tuple(f"#{r.getrandbits(24):06X}" for _ in range(3))
        themes = out[regime(theme)]
        if len(themes) < n:
            themes.append(theme)
    return out


def seed_matrix(themes: list[Theme]) -> np.ndarray:
    """The least-squares matrix of one slot's fit over `themes`, shape (3 * len(themes), 6).

    Row (theme, channel ch) is [bg_ch, fg_ch, accent_ch, ch==R, ch==G, ch==B] with seeds scaled
    to 0..1, so its unknowns are (a, b, c, dr, dg, db) of out = a*bg + b*fg + c*accent + d with d
    in 0..1 units, and the seed columns stay commensurate with the constant ones.
    """
    rgb = np.array([[hex_to_rgb(c) for c in t] for t in themes], float) / 255
    return np.concatenate([np.hstack([seeds.T, np.eye(3)]) for seeds in rgb])


def condition_number(themes: list[Theme]) -> float:
    """2-norm condition number of seed_matrix(themes); a basis needs <= MAX_COND."""
    return float(np.linalg.cond(seed_matrix(themes)))


# == generate(BASIS_SEED, 8), where BASIS_SEED is the first seed from 0 up giving
# condition_number <= MAX_COND in both regimes. Kept literal so the fit never moves with
# random or generate(); the tests check both still hold.
BASIS: dict[str, list[Theme]] = {
    "dark": [
        ("#D82C07", "#629F6F", "#C2094C"),
        ("#42485E", "#F728B4", "#82E2E6"),
        ("#7C65C1", "#67A9C3", "#EB1167"),
        ("#955886", "#E443DF", "#E87A16"),
        ("#482686", "#23C661", "#C17C62"),
        ("#1846D4", "#9E4D6E", "#CCA5A5"),
        ("#40212E", "#FCBD04", "#E8E521"),
        ("#885617", "#FB97D4", "#B4862B"),
    ],
    "light": [
        ("#E3E706", "#6BAA94", "#0A5D2F"),
        ("#C8A706", "#D4713D", "#4DA5E7"),
        ("#F7C1BD", "#7A0242", "#5BA91F"),
        ("#37EBDC", "#813328", "#23A771"),
        ("#CF6A65", "#9A1641", "#E6F459"),
        ("#259F43", "#4F65D4", "#19488D"),
        ("#BAD640", "#12E0C8", "#E61A44"),
        ("#D9B8A7", "#AF1992", "#5487CE"),
    ],
}

# == generate(HELD_OUT_SEED, 4), literal for the same reason.
_HELD_OUT_RANDOM: dict[str, list[Theme]] = {
    "dark": [
        ("#1E7EA4", "#51C9BC", "#80A4DF"),
        ("#DC28FF", "#F3F492", "#1A4668"),
        ("#8C3D5F", "#D7A7A3", "#BB049A"),
        ("#C0433C", "#C5E818", "#96263A"),
    ],
    "light": [
        ("#F38B2F", "#8306D0", "#A5AEC7"),
        ("#E255AC", "#39292D", "#E51214"),
        ("#99DD25", "#9F1995", "#8E7AA6"),
        ("#6BAD6B", "#C88B28", "#9293DE"),
    ],
}
_CORNERS: dict[str, list[Theme]] = {
    "dark": [
        ("#000000", "#FFFFFF", "#FF0000"),
        ("#10141C", "#D8E0E8", "#D8E0E8"),  # accent == fg
        ("#10141C", "#D8E0E8", "#10141C"),  # accent == bg
        ("#404850", "#58606A", "#C07850"),  # luminance gap 0.052
    ],
    "light": [
        ("#FFFFFF", "#000000", "#0000FF"),
        ("#F4EEE0", "#2A2622", "#2A2622"),
        ("#F4EEE0", "#2A2622", "#F4EEE0"),
        ("#58606A", "#404850", "#C07850"),
    ],
}
_PRESET_SEEDS = [tuple(PRESETS[name][k] for k in SEEDS) for name in PRESETS if name != "fireproof"]

# Predicted within 2 RGB units or build fails: every preset but fireproof, corners, random.
HELD_OUT: dict[str, list[Theme]] = {
    r: [t for t in _PRESET_SEEDS if regime(t) == r] + _CORNERS[r] + _HELD_OUT_RANDOM[r] for r in ("dark", "light")
}

# Skeleton check only, never fitted. Collapse: every token lands on (nearly) one hex, so
# colour-keyed dicts merge; an exact tie is dark, so light's bg sits one unit above fg.
# Order: bg/fg/accent chosen so token hex strings sort roughly opposite to the regime's
# template theme (fireproof, flexoki-light), so anything sorted by hex reorders.
PROBES: dict[str, list[Theme]] = {
    "dark": [("#808080", "#808080", "#808080"), ("#3F0000", "#00C0C0", "#0000FF")],
    "light": [("#818181", "#808080", "#808080"), ("#00C0C0", "#3F0000", "#FF0000")],
}
