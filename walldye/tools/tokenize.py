"""Paint-context colour tokenizer: the one definition of a colour occurrence ("slot").

A slot is a colour value in a paint context: the attributes fill, stroke, stop-color,
flood-color, lighting-color and color, and the same properties inside `style="..."` and
`<style>` elements. The value (surrounding whitespace and a CSS `!important` aside) must be
exactly hex3, hex6 or a CSS named colour; anything else (none, currentColor, url(#id),
rgb(), hex with alpha) is not a slot. Attribute and property names are case-sensitive,
hex digits and colour names are not. Comments are skipped. Offsets are str indices, so the
shared fixture keeps its inputs ASCII (JS indices are UTF-16 units).

src/lib/__fixtures__/tokenize.json is the spec; the TS port runs the same fixture.
"""

import re
from collections.abc import Sequence

type Span = tuple[int, int, str]

PAINT = ("fill", "stroke", "stop-color", "flood-color", "lighting-color", "color")

# CSS Color 4 named colours.
NAMED = {
    "aliceblue": "#F0F8FF", "antiquewhite": "#FAEBD7", "aqua": "#00FFFF", "aquamarine": "#7FFFD4",
    "azure": "#F0FFFF", "beige": "#F5F5DC", "bisque": "#FFE4C4", "black": "#000000",
    "blanchedalmond": "#FFEBCD", "blue": "#0000FF", "blueviolet": "#8A2BE2", "brown": "#A52A2A",
    "burlywood": "#DEB887", "cadetblue": "#5F9EA0", "chartreuse": "#7FFF00", "chocolate": "#D2691E",
    "coral": "#FF7F50", "cornflowerblue": "#6495ED", "cornsilk": "#FFF8DC", "crimson": "#DC143C",
    "cyan": "#00FFFF", "darkblue": "#00008B", "darkcyan": "#008B8B", "darkgoldenrod": "#B8860B",
    "darkgray": "#A9A9A9", "darkgreen": "#006400", "darkgrey": "#A9A9A9", "darkkhaki": "#BDB76B",
    "darkmagenta": "#8B008B", "darkolivegreen": "#556B2F", "darkorange": "#FF8C00", "darkorchid": "#9932CC",
    "darkred": "#8B0000", "darksalmon": "#E9967A", "darkseagreen": "#8FBC8F", "darkslateblue": "#483D8B",
    "darkslategray": "#2F4F4F", "darkslategrey": "#2F4F4F", "darkturquoise": "#00CED1", "darkviolet": "#9400D3",
    "deeppink": "#FF1493", "deepskyblue": "#00BFFF", "dimgray": "#696969", "dimgrey": "#696969",
    "dodgerblue": "#1E90FF", "firebrick": "#B22222", "floralwhite": "#FFFAF0", "forestgreen": "#228B22",
    "fuchsia": "#FF00FF", "gainsboro": "#DCDCDC", "ghostwhite": "#F8F8FF", "gold": "#FFD700",
    "goldenrod": "#DAA520", "gray": "#808080", "green": "#008000", "greenyellow": "#ADFF2F",
    "grey": "#808080", "honeydew": "#F0FFF0", "hotpink": "#FF69B4", "indianred": "#CD5C5C",
    "indigo": "#4B0082", "ivory": "#FFFFF0", "khaki": "#F0E68C", "lavender": "#E6E6FA",
    "lavenderblush": "#FFF0F5", "lawngreen": "#7CFC00", "lemonchiffon": "#FFFACD", "lightblue": "#ADD8E6",
    "lightcoral": "#F08080", "lightcyan": "#E0FFFF", "lightgoldenrodyellow": "#FAFAD2", "lightgray": "#D3D3D3",
    "lightgreen": "#90EE90", "lightgrey": "#D3D3D3", "lightpink": "#FFB6C1", "lightsalmon": "#FFA07A",
    "lightseagreen": "#20B2AA", "lightskyblue": "#87CEFA", "lightslategray": "#778899", "lightslategrey": "#778899",
    "lightsteelblue": "#B0C4DE", "lightyellow": "#FFFFE0", "lime": "#00FF00", "limegreen": "#32CD32",
    "linen": "#FAF0E6", "magenta": "#FF00FF", "maroon": "#800000", "mediumaquamarine": "#66CDAA",
    "mediumblue": "#0000CD", "mediumorchid": "#BA55D3", "mediumpurple": "#9370DB", "mediumseagreen": "#3CB371",
    "mediumslateblue": "#7B68EE", "mediumspringgreen": "#00FA9A", "mediumturquoise": "#48D1CC", "mediumvioletred": "#C71585",
    "midnightblue": "#191970", "mintcream": "#F5FFFA", "mistyrose": "#FFE4E1", "moccasin": "#FFE4B5",
    "navajowhite": "#FFDEAD", "navy": "#000080", "oldlace": "#FDF5E6", "olive": "#808000",
    "olivedrab": "#6B8E23", "orange": "#FFA500", "orangered": "#FF4500", "orchid": "#DA70D6",
    "palegoldenrod": "#EEE8AA", "palegreen": "#98FB98", "paleturquoise": "#AFEEEE", "palevioletred": "#DB7093",
    "papayawhip": "#FFEFD5", "peachpuff": "#FFDAB9", "peru": "#CD853F", "pink": "#FFC0CB",
    "plum": "#DDA0DD", "powderblue": "#B0E0E6", "purple": "#800080", "rebeccapurple": "#663399",
    "red": "#FF0000", "rosybrown": "#BC8F8F", "royalblue": "#4169E1", "saddlebrown": "#8B4513",
    "salmon": "#FA8072", "sandybrown": "#F4A460", "seagreen": "#2E8B57", "seashell": "#FFF5EE",
    "sienna": "#A0522D", "silver": "#C0C0C0", "skyblue": "#87CEEB", "slateblue": "#6A5ACD",
    "slategray": "#708090", "slategrey": "#708090", "snow": "#FFFAFA", "springgreen": "#00FF7F",
    "steelblue": "#4682B4", "tan": "#D2B48C", "teal": "#008080", "thistle": "#D8BFD8",
    "tomato": "#FF6347", "turquoise": "#40E0D0", "violet": "#EE82EE", "wheat": "#F5DEB3",
    "white": "#FFFFFF", "whitesmoke": "#F5F5F5", "yellow": "#FFFF00", "yellowgreen": "#9ACD32",
}  # fmt: skip

SKELETON_MARK = "#"

# A comment, or a start, end or empty-element tag with quoted attribute values (which may hold '>').
TAG = re.compile(
    r"<!--.*?-->"
    r"|<(?P<end>/?)(?P<name>[A-Za-z][\w:.-]*)(?P<attrs>(?:\s+[^\s=/>\"']+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*)\s*(?P<empty>/?)>",
    re.DOTALL,
)
_ATTR = re.compile(r"([^\s=/>\"']+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")
_DECL = re.compile(r"(?<![\w-])(" + "|".join(PAINT) + r")\s*:([^;{}]*)")
_ATTR_VALUE = re.compile(r"\s*(\S+?)\s*")
_CSS_VALUE = re.compile(r"\s*(\S+?)\s*(?:!\s*important\s*)?", re.IGNORECASE)
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
_STYLE_END = re.compile(r"</style\s*>")


def _colour(value: str) -> str | None:
    """Uppercase #RRGGBB for a hex3/hex6/named colour, else None."""
    if _HEX.fullmatch(value) is not None:
        h = value[1:]
        return "#" + (h if len(h) == 6 else "".join(c * 2 for c in h)).upper()
    return NAMED.get(value.lower())


def _match(out: list[Span], text: str, offset: int, value_re: re.Pattern[str]) -> None:
    m = value_re.fullmatch(text)
    if m is not None and (c := _colour(m.group(1))) is not None:
        out.append((offset + m.start(1), offset + m.end(1), c))


def _css(out: list[Span], text: str, offset: int) -> None:
    for d in _DECL.finditer(text):
        _match(out, d.group(2), offset + d.start(2), _CSS_VALUE)


def find_colours(svg: str) -> list[Span]:
    """Every slot in `svg` as (start, end, colour): svg[start:end] is the value as written,
    colour its uppercase #RRGGBB. Sorted by start."""
    out: list[Span] = []
    pos = 0
    while (m := TAG.search(svg, pos)) is not None:
        pos = m.end()
        name: str | None = m.group("name")
        if name is None or m.group("end") != "":
            continue
        attrs: str = m.group("attrs")
        base = m.start("attrs")
        for a in _ATTR.finditer(attrs):
            group = 2 if a.group(2) is not None else 3
            value: str = a.group(group)
            start = base + a.start(group)
            if a.group(1) == "style":
                _css(out, value, start)
            elif a.group(1) in PAINT:
                _match(out, value, start, _ATTR_VALUE)
        if name == "style" and m.group("empty") == "":
            end = _STYLE_END.search(svg, pos)
            stop = len(svg) if end is None else end.start()
            _css(out, svg[pos:stop], pos)
            pos = stop
    return out


def _replace(svg: str, spans: Sequence[Span], values: Sequence[str]) -> str:
    parts: list[str] = []
    last = 0
    for (start, end, _), value in zip(spans, values, strict=True):
        parts += [svg[last:start], value]
        last = end
    parts.append(svg[last:])
    return "".join(parts)


def substitute(svg: str, values: list[str]) -> str:
    """`svg` with slot i replaced by values[i]; ValueError unless there is one value per slot."""
    return _replace(svg, find_colours(svg), values)


def normalise(svg: str) -> str:
    """`svg` with every slot rewritten to uppercase #RRGGBB; idempotent, pixels unchanged."""
    spans = find_colours(svg)
    return _replace(svg, spans, [c for _, _, c in spans])


def skeleton(svg: str) -> str:
    """`svg` with every slot replaced by SKELETON_MARK: equal skeletons mean equal geometry
    and slot positions, whatever the colours."""
    spans = find_colours(svg)
    return _replace(svg, spans, [SKELETON_MARK] * len(spans))
