"""Documents: a drawn SVG cut at every colour, serialised under any theme of its regime."""

from collections.abc import Mapping, Sequence
from typing import Final, Literal, final

from ._colour import Colour, MaskColour, coefs, resolve
from ._theme import Coefs, is_light

type Regime = Literal["dark", "light"]
type Fragment = str | Colour | MaskColour
type Line = list[Fragment]


@final
class Document:
    """An SVG template whose colours are still formulas.

    The text is parts[0] + colour 0 + parts[1] + ... + parts[-1], so `parts` has one more
    entry than `colours`. Every colour sits in a fill, stroke or stop-color value, so the slot
    tokenizer finds exactly these slots, in this order.
    """

    def __init__(
        self,
        parts: Sequence[str],
        colours: Sequence[Colour | MaskColour],
        *,
        w: int,
        h: int,
        regime: Regime,
        pixel_grids: Sequence[tuple[float, float, float]] = (),
    ) -> None:
        """Raises ValueError unless len(parts) == len(colours) + 1 and `regime` is "dark" or
        "light"."""
        if len(parts) != len(colours) + 1:
            raise ValueError(f"a document needs one more part than colours, got {len(parts)} parts")
        if regime not in ("dark", "light"):
            raise ValueError(f"regime is 'dark' or 'light', got {regime!r}")
        self._parts: Final = tuple(parts)
        self._colours: Final = tuple(colours)
        self.w: Final = w
        self.h: Final = h
        self.regime: Final = regime
        self.pixel_grids: Final = tuple(pixel_grids)

    def colours(self) -> tuple[Colour | MaskColour, ...]:
        """One colour per slot, in text order."""
        return self._colours

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
            raise ValueError(f"a {self.regime} document cannot be serialised under a {theme} theme")
        memo: dict[Colour | MaskColour, str] = {}
        out: list[str] = []
        for c in self._colours:
            h = memo.get(c)
            if h is None:
                h = memo[c] = resolve(c, tokens)
            out.append(h)
        return out

    def coefs(self) -> list[Coefs]:
        """Each slot's Coefs in the document's regime (see _colour.coefs), in text order."""
        light = self.regime == "light"
        memo: dict[Colour | MaskColour, Coefs] = {}
        out: list[Coefs] = []
        for c in self._colours:
            k = memo.get(c)
            if k is None:
                k = memo[c] = coefs(c, light)
            out.append(k)
        return out

    def to_svg(self, tokens: Mapping[str, str]) -> str:
        """The SVG text under the 21-token dict `tokens`, already normalised.

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
        """The document of everything drawn, in the SVG layout of api.md (one element per line,
        defs first, trailing newline)."""
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
        colours: list[Colour | MaskColour] = []
        text: list[str] = []
        for frag in stream:
            if isinstance(frag, str):
                text.append(frag)
            else:
                parts.append("".join(text))
                colours.append(frag)
                text = []
        parts.append("".join(text))
        return Document(
            parts, colours, w=self.w, h=self.h, regime=self.regime, pixel_grids=self.grids
        )
