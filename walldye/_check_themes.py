"""Themes for the build's checks: the held-out set the slot coefficients must predict, the
skeleton probes, and a sample theme per regime to hash draws under.

A theme here is a (bg, fg, accent) triple of uppercase #RRGGBB seeds; each dict maps a regime
("dark" or "light", per _theme.is_light) to its themes. Fireproof appears in none of them.
"""

from __future__ import annotations

import random

from ._theme import PRESETS, is_light

Theme = tuple[str, str, str]
HELD_OUT_SEED = 2026


def regime(theme: Theme) -> str:
    """Regime name of a theme: "light" when bg is brighter than fg, else "dark"."""
    return "light" if is_light(theme[0], theme[1]) else "dark"


def generate(seed: int, n: int) -> dict[str, list[Theme]]:
    """`n` random themes per regime from random.Random(`seed`): each draw is three
    getrandbits(24) colors, filed under its regime or discarded once that regime is full."""
    r = random.Random(seed)
    out: dict[str, list[Theme]] = {"dark": [], "light": []}
    while any(len(v) < n for v in out.values()):
        theme = (
            f"#{r.getrandbits(24):06X}",
            f"#{r.getrandbits(24):06X}",
            f"#{r.getrandbits(24):06X}",
        )
        themes = out[regime(theme)]
        if len(themes) < n:
            themes.append(theme)
    return out


# == generate(HELD_OUT_SEED, 4). Kept literal so the checks never move with random or
# generate(); a test checks it still holds.
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
_PRESET_SEEDS: list[Theme] = [
    (PRESETS[name]["bg"], PRESETS[name]["fg"], PRESETS[name]["accent"])
    for name in PRESETS
    if name != "fireproof"
]

# Slot coefficients must predict these within 2 RGB units: every preset but fireproof, corners,
# random.
HELD_OUT: dict[str, list[Theme]] = {
    r: [t for t in _PRESET_SEEDS if regime(t) == r] + _CORNERS[r] + _HELD_OUT_RANDOM[r]
    for r in ("dark", "light")
}

# Skeleton check only. Collapse: every token lands on (nearly) one hex, so
# color-keyed dicts merge; an exact tie is dark, so light's bg sits one unit above fg.
# Order: bg/fg/accent chosen so token hex strings sort roughly opposite to the regime's
# template theme (fireproof, flexoki-light), so anything sorted by hex reorders.
PROBES: dict[str, list[Theme]] = {
    "dark": [("#808080", "#808080", "#808080"), ("#3F0000", "#00C0C0", "#0000FF")],
    "light": [("#818181", "#808080", "#808080"), ("#00C0C0", "#3F0000", "#FF0000")],
}

# An ordinary theme per regime that determinism checks and slots.json `probes` hash draws under.
SAMPLE: dict[str, Theme] = {r: _HELD_OUT_RANDOM[r][0] for r in ("dark", "light")}
