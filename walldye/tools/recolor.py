"""The Python reference of the site's recolor (src/lib/recolor.ts): a built template set to
any seeds through its slots.json entry."""

from collections.abc import Mapping

from walldye._theme import FIREPROOF, SEEDS, hex_to_rgb, is_light, normalize_seed, rgb_to_hex
from walldye.tools import paths, slotfile
from walldye.tools.themes import theme_token
from walldye.tools.tokenize import find_colors, substitute

_FIREPROOF = {k: FIREPROOF[k] for k in SEEDS}


def select(entries: Mapping[str, object], aspect: str, seeds: Mapping[str, str]) -> str:
    """The entry "<aspect>/<regime>" of `entries` for recoloring at `aspect` under `seeds`
    ({bg, fg, accent}), in the seeds' regime. KeyError if there is no such entry."""
    light = is_light(normalize_seed(seeds["bg"]), normalize_seed(seeds["fg"]))
    k = f"{aspect}/{'light' if light else 'dark'}"
    if k not in entries:
        raise KeyError(f"no {k} entry in slots.json")
    return k


def recolor(template_svg: str, entry: slotfile.Entry, seeds: Mapping[str, str]) -> str:
    """The browser's recolor: `template_svg` (the file `entry` names, `entry` the one
    select() picks for `seeds`) with slot i set to coefs[occ[i]] = [a, b, c, dr, dg, db]
    evaluated per channel as ((a*bg + b*fg) + c*accent) + d, rounded half to even and
    clamped. Exact fireproof seeds return the template unchanged, and so does a template
    whose slot count is not entry["n"] (the browser's fallback)."""
    s = {k: normalize_seed(seeds[k]) for k in SEEDS}
    spans = find_colors(template_svg)
    if s == _FIREPROOF or len(spans) != entry["n"]:
        return template_svg
    bg, fg, accent = (hex_to_rgb(s[k]) for k in SEEDS)
    rows = [
        rgb_to_hex(*(a * bg[i] + b * fg[i] + c * accent[i] + d[i] for i in range(3)))
        for a, b, c, *d in entry["coefs"]
    ]
    return substitute(template_svg, [rows[o] for o in entry["occ"]])


def themed(slug: str, seeds: dict[str, str], variant: str = "default", aspect: str = "16:9") -> str:
    """A version's built template at `aspect` recolored to `seeds` the way the site does it;
    fireproof's exact seeds return the dark template untouched. KeyError if slots.json lacks
    the entry, FileNotFoundError when not built."""
    slots = slotfile.load(slug, variant)
    if slots is None:
        raise FileNotFoundError(f"{paths.build_dir(slug, variant)} has no slots.json")
    d = paths.build_dir(slug, variant)
    table = slots.entries
    if theme_token(seeds) == "fireproof":
        return (d / table[f"{aspect}/dark"]["file"]).read_text()
    k = select(table, aspect, seeds)
    return recolor((d / table[k]["file"]).read_text(), table[k], seeds)
