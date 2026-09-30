"""Words visitors read: finding color words in prose."""

import re
from typing import Final

# Hues and named shades; copy must say "accent", "bg", roles. Token names (ALL CAPS) are fine.
COLOR_WORDS: Final = frozenset({
    "red", "orange", "yellow", "green", "blue", "purple", "violet", "pink", "brown", "black",
    "white", "grey", "gray", "cyan", "magenta", "teal", "turquoise", "indigo", "crimson",
    "scarlet", "maroon", "amber", "golden", "beige", "cream", "ivory", "terracotta", "ochre",
    "umber", "sepia", "navy", "lavender", "lilac", "mauve", "azure", "cobalt", "vermilion",
    "burgundy", "charcoal", "khaki", "sienna", "cerulean", "ultramarine", "chartreuse", "fuchsia"
})  # fmt: skip


def color_words(text: str) -> set[str]:
    """Color words in `text` as written, lowercased, plurals included ("greys" matches via
    "grey"); ALL-CAPS words (token names like ACCENT_HI) are not prose."""
    words: list[str] = re.findall(r"\b[A-Za-z]+\b", text)
    prose = {w.lower() for w in words if not w.isupper()}
    return {
        w
        for w in prose
        if not COLOR_WORDS.isdisjoint({w, w.removesuffix("s"), w.removesuffix("es")})
    }
