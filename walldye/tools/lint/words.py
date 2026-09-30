"""Words visitors read: the copy rules for meta.yaml's title, description, alt text, notes and
version labels, descriptions and alt texts, and what design.py's docstring and comments may not
say either."""

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
# field kind: (words, sentences) at most
LIMITS: Final = {"description": (20, 1), "alt": (25, 1)}
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
        re.compile(r"\b(a take on|nods? to|nodding to|love letter|homage|evok(e|es|ed|ing)|in the spirit of|invit(e|es|ing)|meditation|ode to|reminiscent of|pays? tribute)\b", _WORDS),
        "gesture phrase",
    ),
    (
        re.compile(r"\b(regimes?|seeds?|tokens?|native|hand-tuned|light-ready|presets?|variants?|params?|slots?|templates?|derived|guards?|has script|AI-generated|generator lost|appendix)\b", _WORDS),
        "internal term",
    ),
    (re.compile(r"\b(CC0(-1\.0)?|GPL(-[\w.-]+)?|SPDX|OFL|LicenseRef-[\w.-]*)(?![\w-])", _WORDS), "license identifier"),
    (re.compile(r"\bRGB units?\b|\b\d+(\.\d+)?:1\b|\b\d+\s?px\b", _WORDS), "machinery number"),
    (re.compile(r"\bthe accent\b|\baccent colou?r\b|\b(bg|fg)(_alt)?\b", _WORDS), "theme role as a noun"),
)  # fmt: skip


# Only in a description: the highlight is the alt text's to describe.
HIGHLIGHT: Final = re.compile(
    r"\b(lit|picked out|filled in|stands? out|highlighted|singled out)\b", _WORDS
)
# Only in a description: credit belongs in sources and notes.
CREDIT: Final = re.compile(r"\bafter [A-Z]\w*|\bafter the\b", re.ASCII)
# Only in an alt text: say what the set-apart thing is or shows instead.
SET_APART: Final = re.compile(r"\b(picked[- ]out|filled[- ]in|highlighted)\b", _WORDS)
# Only in a title: imagery words stand in for the subject's name.
IMAGERY: Final = re.compile(
    r"\b(veils?|whirl(s|ing)?|struck|danc(e|es|ing)|whispers?|symphony|reverie|dreams?|ballet|lullaby|requiem)\b",
    _WORDS,
)


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
    """Copy problems in the title, description, alt text and notes of `meta` and in each
    version's label, description and alt text, each as "<field>: <problem>" (a version field as
    `variants.<name>.label`): color words and BANNED phrases in any of them, IMAGERY in the
    title, HIGHLIGHT and CREDIT in a description, SET_APART in an alt text, and a description or alt text over its LIMITS. [] when
    the copy follows the rules."""
    fields: list[tuple[str, object, str]] = [
        ("title", meta.get("title"), "title"),
        ("description", meta.get("description"), "description"),
        ("alt", meta.get("alt"), "alt"),
        ("notes", meta.get("notes"), "notes"),
    ]
    variants = metadata.as_dict(meta.get("variants"))
    for name, value in (dict[str, object]() if variants is None else variants).items():
        if (e := metadata.as_dict(value)) is not None:
            fields += [
                (f"variants.{name}.{key}", e.get(key), key)
                for key in ("label", "description", "alt")
            ]
    out: list[str] = []
    for field, value, kind in fields:
        text = "" if value is None or value is False or value == "" else str(value)
        if text == "":
            continue
        if len(colors := color_words(text)) > 0:
            out.append(f"{field}: color words {', '.join(sorted(colors))}")
        for pattern, why in BANNED:
            if (m := pattern.search(text)) is not None:
                out.append(f'{field}: {why} "{m[0]}"')
        if kind == "title" and (m := IMAGERY.search(text)) is not None:
            out.append(f'{field}: imagery "{m[0]}" (name the subject)')
        if kind == "description" and (m := HIGHLIGHT.search(text)) is not None:
            out.append(f'{field}: describes the picture "{m[0]}" (the alt text does)')
        if kind == "description" and (m := CREDIT.search(text)) is not None:
            out.append(f'{field}: credit "{m[0]}" (sources and notes carry it)')
        if kind == "alt" and (m := SET_APART.search(text)) is not None:
            out.append(f'{field}: "{m[0]}" (say what the set-apart thing is or shows)')
        if kind in LIMITS:
            most_words, most_sentences = LIMITS[kind]
            if (n := len(text.split())) > most_words:
                out.append(f"{field}: {n} words, over {most_words}")
            if (n := sentences(text)) > most_sentences:
                out.append(f"{field}: {n} sentences, over {most_sentences}")
    return out


def docstring(text: str) -> list[str]:
    """Copy problems in a design.py module docstring: more than one line, and BANNED phrases."""
    out = [f'{why} "{m[0]}"' for pattern, why in BANNED if (m := pattern.search(text)) is not None]
    if len(text.strip().splitlines()) > 1:
        out.insert(0, "more than one line (the subject and the technique)")
    return out
