"""Bitmap text: the bundled Spleen glyphs as arrays and as runs of set pixels."""

import functools
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from ._font import FONTS
from ._vec import Num, count, positive
from .field import runs

type Font = Literal["5x8", "8x16"]


def font_table(font: object) -> tuple[int, int, dict[int, str]]:
    if not isinstance(font, str) or font not in FONTS:
        raise ValueError(f"font is one of {', '.join(FONTS)}, got {font!r}")
    return FONTS[font]


@functools.cache
def _bitmap(font: str, ch: str) -> NDArray[np.bool_]:
    """The cached bitmap of glyph(); callers must not modify it."""
    fw, fh, table = font_table(font)
    rows = table.get(ord(ch))
    if rows is None:
        return np.zeros((fh, fw), dtype=np.bool_)
    vals = np.array([int(rows[2 * j : 2 * j + 2], 16) for j in range(fh)], dtype=np.int64)
    return ((vals[:, None] >> (fw - 1 - np.arange(fw))[None, :]) & 1).astype(np.bool_)


def glyph(ch: str, font: Font = "8x16") -> NDArray[np.bool_]:
    """The (height, width) bitmap of the character `ch` in a bundled Spleen font: "5x8" has
    ASCII and light box drawing, "8x16" adds heavy box drawing, blocks, shades, geometric
    shapes and braille. Unknown characters are blank.

    Raises ValueError for anything but one character or an unknown font.
    """
    if not isinstance(ch, str) or len(ch) != 1:
        raise ValueError(f"glyph takes one character, got {ch!r}")
    return _bitmap(font, ch).copy()


@functools.cache
def glyph_runs(font: str, ch: str, flip: bool) -> tuple[tuple[int, int, int], ...]:
    """The (row, start, stop) runs of set pixels in a glyph, left to right per row; `flip`
    mirrors the bitmap first."""
    bitmap = _bitmap(font, ch)
    bits: NDArray[np.bool_] = bitmap[:, ::-1] if flip else bitmap
    return tuple((j, i, k) for j in range(bits.shape[0]) for i, k in runs(bits[j]))


def text_width(text: str, *, font: Font = "8x16", px: Num = 2, gap: int = 0) -> float:
    """The drawn width of one line of glyphs: (len(text) * (width + gap) - gap) * px, and 0 for
    an empty string.

    Raises ValueError for an unknown font, a px not above 0 or a negative gap.
    """
    fw, _, _ = font_table(font)
    p = positive(px, "text_width px")
    g = count(gap, "text_width gap", 0)
    return 0.0 if len(text) == 0 else (len(text) * (fw + g) - g) * p
