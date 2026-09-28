"""Slot fitting: every colour occurrence ("slot") of a template as out = a*bg + b*fg + c*accent + d.

Per regime, the design's document is serialised under that regime's basis themes
(walldye._basis); each slot's six coefficients [a, b, c, dr, dg, db] are fitted by least
squares over the basis, with seeds and d in 0..255 channel units. The browser evaluates
`((a*bg + b*fg) + c*accent) + d` per channel, rounds half to even and clamps to 0..255.
"""

import bisect
import os
import re
from collections.abc import Mapping, Sequence
from typing import Final, TypedDict

import numpy as np
from numpy.typing import NDArray

from walldye import _basis
from walldye._aspect import template_name
from walldye._basis import Theme
from walldye._document import Document
from walldye._theme import SEEDS, hex_to_rgb, rgb_to_hex, theme_token
from walldye.tools.common import Regime, tokens_of
from walldye.tools.tokenize import TAG, find_colours, skeleton

TEMPLATE_THEMES: Final[dict[Regime, str]] = {"dark": "fireproof", "light": "flexoki-light"}
MAX_ERROR = 2
DECIMALS = 5
# A slot the seeds can move by less than one RGB unit in total is constant (hardcoded).
CONSTANT_SPAN = 1 / 255
MASKING = ("mask", "clipPath")

type Floats = NDArray[np.float64]
type Chain = tuple[tuple[str, str | None], ...]


class Entry(TypedDict):
    """One template's fit, as slots.json stores it (minus the sha256 build adds)."""

    file: str
    n: int
    coefs: list[list[float]]
    occ: list[int]


def label(theme: str | Theme) -> str:
    """A theme's name in messages: the preset name or the bg-fg-accent token."""
    return theme if isinstance(theme, str) else theme_token(dict(zip(SEEDS, theme, strict=True)))


def rgb(hexes: Sequence[str]) -> Floats:
    """(n, 3) float RGB of `hexes`."""
    return np.array([hex_to_rgb(c) for c in hexes], dtype=np.float64).reshape(-1, 3)


def colours(svg: str) -> Floats:
    """(n, 3) float RGB of the slots of `svg`, in document order."""
    return rgb([c for _, _, c in find_colours(svg)])


def fit(themes: Sequence[Theme], renders: Sequence[Floats]) -> Floats:
    """Least-squares coefficients, shape (n, 6), of the n slots whose colours under
    `themes[i]` are `renders[i]` (n, 3); rows are [a, b, c, dr, dg, db], d in 0..255 units."""
    a = _basis.seed_matrix(list(themes))
    # Row (theme, channel) of the stacked outputs lines up with the same row of seed_matrix.
    y: Floats = np.concatenate([r.T for r in renders]) / 255
    x: Floats = np.linalg.lstsq(a, y, rcond=None)[0]
    return np.hstack([x[:3].T, x[3:].T * 255])


def compact(coefs: Floats) -> tuple[list[list[float]], list[int]]:
    """(rows, occ): `coefs` rounded to DECIMALS and deduplicated in first-seen order, with
    occ[i] the row of slot i."""
    rows: dict[tuple[float, ...], int] = {}
    occ: list[int] = []
    for row in coefs:
        key = tuple(round(float(v), DECIMALS) + 0.0 for v in row)  # + 0.0 turns -0.0 into 0.0
        occ.append(rows.setdefault(key, len(rows)))
    return [list(r) for r in rows], occ


def predict(coefs: Floats, theme: Theme) -> Floats:
    """(n, 3) RGB the browser computes from `coefs` (n, 6) under `theme`."""
    bg, fg, accent = (np.array(hex_to_rgb(c), dtype=np.float64) for c in theme)
    v: Floats = coefs[:, [0]] * bg + coefs[:, [1]] * fg + coefs[:, [2]] * accent + coefs[:, 3:]
    return np.clip(np.rint(v), 0, 255)


def constant(coefs: Floats) -> NDArray[np.bool_]:
    """Per row of `coefs`, whether it ignores the seeds (a, b, c all but zero)."""
    return np.abs(coefs[:, :3]).sum(axis=1) < CONSTANT_SPAN


_ID = re.compile(r"""(?:^|\s)id\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_REF = re.compile(r"""url\(\s*['"]?#([^)'"\s]+)['"]?\s*\)|href\s*=\s*["']#([^"']+)["']""")


def _regions(svg: str) -> list[tuple[int, int, Chain]]:
    """(start, end, element chain) for each start tag and each <style> body, in order; the
    chain runs from the root to the element the tag (or style body) belongs to."""
    out: list[tuple[int, int, Chain]] = []
    stack: list[tuple[str, str | None]] = []
    for m in TAG.finditer(svg):
        name: str | None = m.group("name")
        if name is None:
            continue
        if m.group("end") != "":
            while len(stack) > 0 and stack.pop()[0] != name:
                pass
            continue
        ident = _ID.search(m.group("attrs"))
        value = (
            None
            if ident is None
            else ident.group(1)
            if ident.group(1) is not None
            else ident.group(2)
        )
        chain: Chain = (*stack, (name, value))
        out.append((m.start(), m.end(), chain))
        if m.group("empty") == "":
            stack.append(chain[-1])
            if name == "style":
                end = svg.find("</style", m.end())
                out.append((m.end(), len(svg) if end < 0 else end, chain))
    return out


def mask_bound(svg: str, positions: Sequence[int]) -> list[bool]:
    """For each offset in `positions`, whether it paints only mask or clip content: inside a
    <mask>/<clipPath>, or inside an element (gradient, pattern, symbol...) whose id is only
    referenced from such content, transitively. Offsets outside any tag are not bound."""
    regions = _regions(svg)
    starts = [r[0] for r in regions]

    def chain_at(pos: int) -> Chain | None:
        i = bisect.bisect_right(starts, pos) - 1
        return regions[i][2] if i >= 0 and pos < regions[i][1] else None

    refs: dict[str, list[Chain]] = {}
    for m in _REF.finditer(svg):
        chain = chain_at(m.start())
        if chain is not None:
            ident: str = m.group(1) if m.group(1) is not None else m.group(2)
            refs.setdefault(ident, []).append(chain)

    only: set[str] = set()

    def bound(chain: Chain) -> bool:
        return any(name in MASKING or ident in only for name, ident in chain)

    changed = True
    while changed:
        changed = False
        for ident, chains in refs.items():
            if ident not in only and all(bound(c) for c in chains):
                only.add(ident)
                changed = True
    return [c is not None and len(c) > 0 and bound(c) for c in map(chain_at, positions)]


def _line(svg: str, pos: int) -> int:
    return svg.count("\n", 0, pos) + 1


def first_diff(a: str, b: str) -> str:
    """Where two different strings first part, as `line N: '<a context>' vs '<b context>'`."""
    k = len(os.path.commonprefix([a, b]))
    return f"line {_line(a, k)}: {a[max(0, k - 30) : k + 30]!r} vs {b[max(0, k - 30) : k + 30]!r}"


def slot_rule(svg: str, rows: Sequence[Sequence[float]], occ: Sequence[int]) -> list[str]:
    """Constant-slot rule errors for template `svg` with fitted `rows`/`occ`: a constant slot
    is allowed only in mask content (see mask_bound), a theme-dependent one never is."""
    spans = find_colours(svg)
    table = np.array(rows, dtype=np.float64).reshape(-1, 6)
    const = constant(table)[list(occ)] if len(occ) > 0 else np.zeros(0, dtype=np.bool_)
    masked = mask_bound(svg, [s for s, _, _ in spans])
    hard: dict[str, list[int]] = {}
    themed: dict[str, list[int]] = {}
    for (start, _, colour), c, m in zip(spans, const.tolist(), masked, strict=True):
        if c and not m:
            hard.setdefault(colour, []).append(start)
        elif not c and m:
            themed.setdefault(colour, []).append(start)
    return [
        *(
            f"hardcoded {c} ×{len(at)} (line {_line(svg, at[0])}): use a token or mix(); constant colours belong only in <mask>/<clipPath>"
            for c, at in hard.items()
        ),
        *(
            f"theme-dependent {c} ×{len(at)} in mask content (line {_line(svg, at[0])}): masks take MASK_WHITE, MASK_BLACK and their mixes only"
            for c, at in themed.items()
        ),
    ]


def fit_aspect(
    docs: Mapping[Regime, Document], aspect: str
) -> tuple[dict[str, str], dict[str, Entry], list[str]]:
    """Fit one native aspect of a design, given its document per regime ("dark", optionally
    "light").

    The dark template is the dark document under fireproof; the light regime shares it when
    the two documents' skeletons match, else gets its own template under flexoki-light. Each
    regime's slots are fitted over its basis and must predict every held-out theme within
    MAX_ERROR units; the template and probe serialisations must tokenize to the document's
    own slots. Returns (templates {file name: svg}, entries {"<aspect>/<regime>": Entry},
    errors); a regime whose serialisations disagree with its document gets no entry.
    """
    templates: dict[str, str] = {}
    entries: dict[str, Entry] = {}
    errors: list[str] = []
    dark = docs["dark"]
    for regime, doc in docs.items():
        ref_theme = TEMPLATE_THEMES[regime]
        own = doc.skeleton()
        differ = [
            (label(t), s) for t in (ref_theme, *_basis.PROBES[regime])
            if (s := skeleton(doc.to_svg(tokens_of(t)))) != own
        ]  # fmt: skip
        if len(differ) > 0:
            name, s = differ[0]
            errors.append(
                f"{aspect} {regime}: the slots found under {name} are not the document's, {first_diff(own, s)}"
            )
            continue
        if regime == "dark" or own == dark.skeleton():
            name = template_name(aspect)
            if name not in templates:
                templates[name] = dark.to_svg(tokens_of(TEMPLATE_THEMES["dark"]))
        else:
            name = template_name(aspect, light=True)
            templates[name] = doc.to_svg(tokens_of(ref_theme))

        basis = _basis.BASIS[regime]
        rows, occ = compact(fit(basis, [rgb(doc.hexes(tokens_of(t))) for t in basis]))
        table = (
            np.array(rows, dtype=np.float64).reshape(-1, 6)[occ]
            if len(occ) > 0
            else np.zeros((0, 6))
        )
        # (error, theme, slot, actual, predicted) per held-out theme off by more than MAX_ERROR
        misses: list[tuple[float, Theme, int, str, str]] = []
        for t in _basis.HELD_OUT[regime]:
            actual, predicted = rgb(doc.hexes(tokens_of(t))), predict(table, t)
            err: Floats = np.abs(predicted - actual).max(axis=1, initial=0)
            if float(err.max(initial=0)) > MAX_ERROR:
                i = int(err.argmax())
                a = rgb_to_hex(*(float(v) for v in actual[i]))
                p = rgb_to_hex(*(float(v) for v in predicted[i]))
                misses.append((float(err[i]), t, i, a, p))
        if len(misses) > 0:
            worst, t, i, a_hex, p_hex = max(misses, key=lambda m: m[0])
            line = _line(templates[name], find_colours(templates[name])[i][0])
            errors.append(
                f"{aspect} {regime}: {len(misses)} of {len(_basis.HELD_OUT[regime])} held-out themes miss by more than {MAX_ERROR} units; "
                f"worst {label(t)}, off by {worst:.0f} at the slot on line {line} of {name} ({a_hex}, predicted {p_hex}): "
                "colour arithmetic that is not a linear mix of tokens?"
            )
        errors += [f"{aspect} {regime}: {e}" for e in slot_rule(templates[name], rows, occ)]
        entries[f"{aspect}/{regime}"] = {"file": name, "n": len(occ), "coefs": rows, "occ": occ}
    return templates, entries, errors
