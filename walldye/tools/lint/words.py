"""Words visitors read: the copy rules for meta.yaml's title, description, notes and version
labels and descriptions, and the color words design.py's comments may not use either."""

import re
from collections.abc import Mapping
from typing import Final

from walldye.tools import metadata

# Hues and named shades; copy says what is picked out, never its color. Token names (ALL CAPS) are fine.
COLOR_WORDS: Final = frozenset({
    "red", "orange", "yellow", "green", "blue", "purple", "violet", "pink", "brown", "black",
    "white", "grey", "gray", "cyan", "magenta", "teal", "turquoise", "indigo", "crimson",
    "scarlet", "maroon", "amber", "golden", "beige", "cream", "ivory", "terracotta", "ochre",
    "umber", "sepia", "navy", "lavender", "lilac", "mauve", "azure", "cobalt", "vermilion",
    "burgundy", "charcoal", "khaki", "sienna", "cerulean", "ultramarine", "chartreuse", "fuchsia"
})  # fmt: skip
# Words visitors never read, singular; a version label with one of them is an error.
INTERNAL_TERMS: Final = frozenset({
    "regime", "seed", "token", "native", "hand-tuned", "light-ready", "preset", "variant",
    "param", "slot", "template", "derived", "guard",
})  # fmt: skip
MAX_DESCRIPTION_WORDS: Final = 30
MAX_DESCRIPTION_SENTENCES: Final = 2
_WORDS: Final = re.IGNORECASE | re.ASCII
# Phrases visible copy never uses, each with the reason copy() gives; matched as whole words.
BANNED: Final = (
    (
        re.compile(r"\b(stunning|mesmeri[sz]ing|elegant|timeless|beautiful(ly)?|breathtaking|captivating|gorgeous|exquisite|hypnotic|vibrant|evocative|sublime|majestic|iconic|dazzling|striking)\b", _WORDS),
        "evaluative adjective",
    ),
    (
        re.compile(r"\b(delve[sd]?|delving|tapestry|testament|quietly|seamless(ly)?|serves as|stands as)\b", _WORDS),
        "stock phrase",
    ),
    (
        re.compile(r"\b(regimes?|seeds?|tokens?|native|hand-tuned|light-ready|presets?|variants?|params?|slots?|templates?|derived|guards?|has script|AI-generated|generator lost|appendix)\b", _WORDS),
        "internal term",
    ),
    (re.compile(r"\b(CC0(-1\.0)?|GPL(-[\w.-]+)?|SPDX|OFL|LicenseRef-[\w.-]*)(?![\w-])", _WORDS), "license identifier"),
    (re.compile(r"\bRGB units?\b|\b\d+(\.\d+)?:1\b|\b\d+\s?px\b", _WORDS), "machinery number"),
    (re.compile(r"\bthe accent\b|\baccent colou?r\b|\b(bg|fg)(_alt)?\b", _WORDS), "theme role as a noun"),
)  # fmt: skip


def color_words(text: str) -> set[str]:
    """Color words in `text` as written, lowercased, plurals included ("greys" matches via
    "grey"); ALL-CAPS words (token names like ACCENT_HI) are not prose."""
    found: set[str] = set()
    words: list[str] = re.findall(r"(?<!\w)[A-Za-z]+(?!\w)", text)
    for w in words:
        lower = w.lower()
        stems = {lower, lower.removesuffix("s"), lower.removesuffix("es")}
        if w != w.upper() and not COLOR_WORDS.isdisjoint(stems):
            found.add(lower)
    return found


def sentences(text: str) -> int:
    """Sentences in `text`: one ends at . ! or ? before whitespace and a capital, a quote or a
    parenthesis, or at the end, so "Fig. 1" does not end one."""
    t = text.strip()
    if t == "":
        return 0
    ends = 0
    for m in re.finditer(r"[.!?]+", t):
        after = re.match(r"\s+(.)", t[m.end() :])
        if m.end() == len(t) or (after is not None and (after[1].isupper() or after[1] in '"“‘(')):
            ends += 1
    return ends if t[-1] in ".!?" else ends + 1


def copy(meta: Mapping[str, object]) -> list[str]:
    """Copy problems in the title, description and notes of `meta` and in each version's label
    and description, each as "<field>: <problem>" (a version field as
    `variants.<name>.label`): color words and BANNED phrases in any of them, and a description
    over MAX_DESCRIPTION_WORDS words or MAX_DESCRIPTION_SENTENCES sentences. [] when the copy
    follows the rules."""
    fields: list[tuple[str, object, bool]] = [
        ("title", meta.get("title"), False),
        ("description", meta.get("description"), True),
        ("notes", meta.get("notes"), False),
    ]
    variants = metadata.as_dict(meta.get("variants"))
    for name, value in (dict[str, object]() if variants is None else variants).items():
        if (e := metadata.as_dict(value)) is not None:
            fields += [
                (f"variants.{name}.label", e.get("label"), False),
                (f"variants.{name}.description", e.get("description"), True),
            ]
    out: list[str] = []
    for field, value, is_description in fields:
        text = "" if value is None or value is False or value == "" else str(value)
        if text == "":
            continue
        if len(colors := color_words(text)) > 0:
            out.append(f"{field}: color words {', '.join(sorted(colors))}")
        for pattern, why in BANNED:
            if (m := pattern.search(text)) is not None:
                out.append(f'{field}: {why} "{m[0]}"')
        if is_description:
            if (n := len(text.split())) > MAX_DESCRIPTION_WORDS:
                out.append(f"{field}: {n} words, over {MAX_DESCRIPTION_WORDS}")
            if (s := sentences(text)) > MAX_DESCRIPTION_SENTENCES:
                out.append(f"{field}: {s} sentences, over {MAX_DESCRIPTION_SENTENCES}")
    return out
