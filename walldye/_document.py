"""Documents: a drawn SVG cut at every color, serialized under any theme of its regime."""

from collections.abc import Mapping, Sequence
from typing import Final, Literal, final

from ._color import Color, MaskColor, coefs, resolve
from ._theme import Coefs, is_light

type Regime = Literal["dark", "light"]
type Fragment = str | Color | MaskColor
type Line = list[Fragment]


@final
class Document:
    """An SVG template whose colors are still formulas.

    The text is parts[0] + color 0 + parts[1] + ... + parts[-1], so `parts` has one more
    entry than `colors`. Every color sits in a fill, stroke or stop-color value, so the slot
    tokenizer finds exactly these slots, in this order.
    """

    def __init__(
        self,
        parts: Sequence[str],
        colors: Sequence[Color | MaskColor],
        *,
        w: int,
        h: int,
        regime: Regime,
        pixel_grids: Sequence[tuple[float, float, float]] = (),
    ) -> None:
        """Raises ValueError unless len(parts) == len(colors) + 1 and `regime` is "dark" or
        "light"."""
        if len(parts) != len(colors) + 1:
            raise ValueError(f"a document needs one more part than colors, got {len(parts)} parts")
        if regime not in ("dark", "light"):
            raise ValueError(f"regime is 'dark' or 'light', got {regime!r}")
        self._parts: Final = tuple(parts)
        self._colors: Final = tuple(colors)
        self.w: Final = w
        self.h: Final = h
        self.regime: Final = regime
        self.pixel_grids: Final = tuple(pixel_grids)

    def colors(self) -> tuple[Color | MaskColor, ...]:
        """One color per slot, in text order."""
        return self._colors

    def skeleton(self) -> str:
        """The text with every slot replaced by "#"; equals tokenize.skeleton(self.to_svg(t))
        for every theme t."""
        return "#".join(self._parts)

    def hexes(self, tokens: Mapping[str, str]) -> list[str]:
        """Each slot resolved to uppercase #RRGGBB under the 21-token dict `tokens`.

        Raises ValueError when the tokens belong to the other regime.
        """
        light = is_light(tokens["bg"], tokens["fg"])
        if light != (self.regime == "light"):
            theme = "light" if light else "dark"
            raise ValueError(f"a {self.regime} document cannot be serialized under a {theme} theme")
        memo: dict[Color | MaskColor, str] = {}
        out: list[str] = []
        for c in self._colors:
            h = memo.get(c)
            if h is None:
                h = memo[c] = resolve(c, tokens)
            out.append(h)
        return out

    def coefs(self) -> list[Coefs]:
        """Each slot's Coefs in the document's regime (see _color.coefs), in text order."""
        light = self.regime == "light"
        memo: dict[Color | MaskColor, Coefs] = {}
        out: list[Coefs] = []
        for c in self._colors:
            k = memo.get(c)
            if k is None:
                k = memo[c] = coefs(c, light)
            out.append(k)
        return out

    def to_svg(self, tokens: Mapping[str, str]) -> str:
        """The SVG text under the 21-token dict `tokens`, already normalized.

        Raises ValueError when the tokens belong to the other regime.
        """
        hexes = self.hexes(tokens)
        out = [self._parts[0]]
        for h, part in zip(hexes, self._parts[1:], strict=True):
            out += (h, part)
        return "".join(out)


@final
class Pending:
    """Lines reserved at one position in the body and filled in later (a buckets block)."""

    def __init__(self) -> None:
        self.lines: list[Line] = []


@final
class Builder:
    """The mutable state of one draw: defs, body lines, ids and pixel grids."""

    def __init__(self, w: int, h: int, regime: Regime) -> None:
        self.w: Final = w
        self.h: Final = h
        self.regime: Final = regime
        self.defs: list[Fragment] = []
        self.body: list[Line | Pending] = []
        self.grids: list[tuple[float, float, float]] = []
        self._ids = 0

    def new_id(self, prefix: str) -> str:
        """The next id of the document's one counter, with `prefix` ("lg", "cp", ...)."""
        self._ids += 1
        return f"{prefix}{self._ids}"

    def finish(self) -> Document:
        """The document of everything drawn, one element per line."""
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}"'
            f' width="{self.w}" height="{self.h}">\n'
        )
        stream: list[Fragment] = [head]
        if len(self.defs) > 0:
            stream += ["<defs>", *self.defs, "</defs>\n"]
        for item in self.body:
            for line in item.lines if isinstance(item, Pending) else (item,):
                stream += line
                stream.append("\n")
        stream.append("</svg>\n")
        parts: list[str] = []
        colors: list[Color | MaskColor] = []
        text: list[str] = []
        for frag in stream:
            if isinstance(frag, str):
                text.append(frag)
            else:
                parts.append("".join(text))
                colors.append(frag)
                text = []
        parts.append("".join(text))
        return Document(
            parts, colors, w=self.w, h=self.h, regime=self.regime, pixel_grids=self.grids
        )
