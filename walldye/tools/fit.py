"""Slot fitting: every colour occurrence ("slot") of a template as out = a*bg + b*fg + c*accent + d.

Per regime, a design is rendered under that regime's basis themes (walldye._basis), which
must all share one skeleton with the template (and with the probe and held-out themes);
each slot's six coefficients [a, b, c, dr, dg, db] are then fitted by least squares over the
basis, with seeds and d in 0..255 channel units. The browser evaluates
`((a*bg + b*fg) + c*accent) + d` per channel, rounds half to even and clamps to 0..255.
"""

from __future__ import annotations

import bisect
import os
import re
from collections.abc import Callable

import numpy as np

from walldye import _basis, hex_to_rgb, rgb_to_hex, template_name, theme_token
from walldye._basis import Theme
from walldye._theme import SEEDS
from walldye.tools.tokenize import TAG, find_colours, normalise, skeleton

TEMPLATE_THEMES = {"dark": "fireproof", "light": "flexoki-light"}
MAX_ERROR = 2
DECIMALS = 5
# A slot the seeds can move by less than one RGB unit in total is constant (hardcoded).
CONSTANT_SPAN = 1 / 255
MASKING = ("mask", "clipPath")

Render = Callable[[str | Theme], str]


def label(theme: str | Theme) -> str:
    """A theme's name in messages: the preset name or the bg-fg-accent token."""
    return theme if isinstance(theme, str) else theme_token(dict(zip(SEEDS, theme)))


def colours(svg: str) -> np.ndarray:
    """(n, 3) float RGB of the slots of `svg`, in document order."""
    return np.array([hex_to_rgb(c) for _, _, c in find_colours(svg)], float).reshape(-1, 3)


def fit(themes: list[Theme], renders: list[np.ndarray]) -> np.ndarray:
    """Least-squares coefficients, shape (n, 6), of the n slots whose colours under
    `themes[i]` are `renders[i]` (n, 3); rows are [a, b, c, dr, dg, db], d in 0..255 units."""
    a = _basis.seed_matrix(themes)
    # Row (theme, channel) of the stacked outputs lines up with the same row of seed_matrix.
    y = np.concatenate([r.T for r in renders]) / 255
    x = np.linalg.lstsq(a, y, rcond=None)[0]
    return np.hstack([x[:3].T, x[3:].T * 255])


def compact(coefs: np.ndarray) -> tuple[list[list[float]], list[int]]:
    """(rows, occ): `coefs` rounded to DECIMALS and deduplicated in first-seen order, with
    occ[i] the row of slot i."""
    rows: dict[tuple[float, ...], int] = {}
    occ = []
    for row in coefs:
        key = tuple(round(float(v), DECIMALS) + 0.0 for v in row)  # + 0.0 turns -0.0 into 0.0
        occ.append(rows.setdefault(key, len(rows)))
    return [list(r) for r in rows], occ


def predict(coefs: np.ndarray, theme: Theme) -> np.ndarray:
    """(n, 3) RGB the browser computes from `coefs` (n, 6) under `theme`."""
    bg, fg, accent = (np.array(hex_to_rgb(c), float) for c in theme)
    v = coefs[:, [0]] * bg + coefs[:, [1]] * fg + coefs[:, [2]] * accent + coefs[:, 3:]
    return np.clip(np.rint(v), 0, 255)


def constant(coefs: np.ndarray) -> np.ndarray:
    """Per row of `coefs`, whether it ignores the seeds (a, b, c all but zero)."""
    return np.abs(coefs[:, :3]).sum(axis=1) < CONSTANT_SPAN


_ID = re.compile(r"""(?:^|\s)id\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_REF = re.compile(r"""url\(\s*['"]?#([^)'"\s]+)['"]?\s*\)|href\s*=\s*["']#([^"']+)["']""")


def _regions(svg: str) -> list[tuple[int, int, tuple[tuple[str, str | None], ...]]]:
    """(start, end, element chain) for each start tag and each <style> body, in order; the
    chain runs from the root to the element the tag (or style body) belongs to."""
    out = []
    stack: list[tuple[str, str | None]] = []
    for m in TAG.finditer(svg):
        name = m.group("name")
        if not name:
            continue
        if m.group("end"):
            while stack and stack.pop()[0] != name:
                pass
            continue
        ident = _ID.search(m.group("attrs"))
        chain = (
            *stack,
            (name, ident and (ident.group(1) if ident.group(1) is not None else ident.group(2))),
        )
        out.append((m.start(), m.end(), chain))
        if not m.group("empty"):
            stack.append(chain[-1])
            if name == "style":
                end = svg.find("</style", m.end())
                out.append((m.end(), len(svg) if end < 0 else end, chain))
    return out


def mask_bound(svg: str, positions: list[int]) -> list[bool]:
    """For each offset in `positions`, whether it paints only mask or clip content: inside a
    <mask>/<clipPath>, or inside an element (gradient, pattern, symbol...) whose id is only
    referenced from such content, transitively. Offsets outside any tag are not bound."""
    regions = _regions(svg)
    starts = [r[0] for r in regions]

    def chain_at(pos: int):
        i = bisect.bisect_right(starts, pos) - 1
        return regions[i][2] if i >= 0 and pos < regions[i][1] else None

    refs: dict[str, list] = {}
    for m in _REF.finditer(svg):
        chain = chain_at(m.start())
        if chain is not None:
            refs.setdefault(m.group(1) or m.group(2), []).append(chain)

    only: set[str] = set()

    def bound(chain) -> bool:
        return any(name in MASKING or ident in only for name, ident in chain)

    changed = True
    while changed:
        changed = False
        for ident, chains in refs.items():
            if ident not in only and all(bound(c) for c in chains):
                only.add(ident)
                changed = True
    return [bool(c) and bound(c) for c in map(chain_at, positions)]


def _line(svg: str, pos: int) -> int:
    return svg.count("\n", 0, pos) + 1


def first_diff(a: str, b: str) -> str:
    """Where two different strings first part, as `line N: '<a context>' vs '<b context>'`."""
    k = len(os.path.commonprefix([a, b]))
    return f"line {_line(a, k)}: {a[max(0, k - 30) : k + 30]!r} vs {b[max(0, k - 30) : k + 30]!r}"


def slot_rule(svg: str, rows: list[list[float]], occ: list[int]) -> list[str]:
    """Constant-slot rule errors for template `svg` with fitted `rows`/`occ`: a constant slot
    is allowed only in mask content (see mask_bound), a theme-dependent one never is."""
    spans = find_colours(svg)
    const = constant(np.array(rows).reshape(-1, 6))[occ] if occ else np.zeros(0, bool)
    masked = mask_bound(svg, [s for s, _, _ in spans])
    hard: dict[str, list[int]] = {}
    themed: dict[str, list[int]] = {}
    for (start, _, colour), c, m in zip(spans, const, masked):
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
            f"theme-dependent {c} ×{len(at)} in mask content (line {_line(svg, at[0])}): masks take #fff/#000 only"
            for c, at in themed.items()
        ),
    ]


def fit_aspect(
    render: Render, aspect: str, regimes: list[str]
) -> tuple[dict[str, str], dict[str, dict], list[str]]:
    """Fit one native aspect of a design for each of `regimes` ("dark", optionally "light").

    `render(theme)` returns the design's SVG at `aspect` under a preset name or seed triple.
    The dark template is the fireproof render; the light regime shares it when its skeleton
    (under flexoki-light) equals the dark one, else gets its own flexoki-light template.
    Returns (templates {file name: normalised svg}, entries {"<aspect>/<regime>": {file, n,
    coefs, occ}}, errors); a regime whose skeletons differ gets no template or entry.
    """
    templates: dict[str, str] = {}
    entries: dict[str, dict] = {}
    errors: list[str] = []
    dark_skeleton = skeleton(render(TEMPLATE_THEMES["dark"]))
    for regime in regimes:
        ref_theme = TEMPLATE_THEMES[regime]
        ref = render(ref_theme)
        ref_skeleton = skeleton(ref)
        roles = [("basis", _basis.BASIS), ("probe", _basis.PROBES), ("held-out", _basis.HELD_OUT)]
        differ = [
            (role, t, s) for role, themes in roles for t in themes[regime]
            if (s := skeleton(render(t))) != ref_skeleton
        ]  # fmt: skip
        if differ:
            role, t, s = differ[0]
            more = f" (and {len(differ) - 1} more)" if len(differ) > 1 else ""
            errors.append(
                f"{aspect} {regime}: geometry changes with the theme: {role} {label(t)} differs from {ref_theme}{more}, {first_diff(ref_skeleton, s)}"
            )
            continue

        if regime == "dark" or ref_skeleton == dark_skeleton:
            name = template_name(aspect)
            templates.setdefault(name, normalise(render(TEMPLATE_THEMES["dark"])))
        else:
            name = template_name(aspect, light=True)
            templates[name] = normalise(ref)

        basis = _basis.BASIS[regime]
        rows, occ = compact(fit(basis, [colours(render(t)) for t in basis]))
        table = np.array(rows).reshape(-1, 6)[occ] if occ else np.zeros((0, 6))
        misses = []  # (error, theme, slot, actual, predicted) per held-out theme off by more than MAX_ERROR
        for t in _basis.HELD_OUT[regime]:
            actual, predicted = colours(render(t)), predict(table, t)
            err = np.abs(predicted - actual).max(axis=1, initial=0)
            if err.max(initial=0) > MAX_ERROR:
                i = int(err.argmax())
                misses.append((err[i], t, i, rgb_to_hex(*actual[i]), rgb_to_hex(*predicted[i])))
        if misses:
            worst, t, i, actual, predicted = max(misses, key=lambda m: m[0])
            line = _line(templates[name], find_colours(templates[name])[i][0])
            errors.append(
                f"{aspect} {regime}: {len(misses)} of {len(_basis.HELD_OUT[regime])} held-out themes miss by more than {MAX_ERROR} units; "
                f"worst {label(t)}, off by {worst:.0f} at the slot on line {line} of {name} ({actual}, predicted {predicted}): "
                "colour arithmetic that is not a linear mix of tokens?"
            )
        errors += [f"{aspect} {regime}: {e}" for e in slot_rule(templates[name], rows, occ)]
        entries[f"{aspect}/{regime}"] = {"file": name, "n": len(occ), "coefs": rows, "occ": occ}
    return templates, entries, errors
