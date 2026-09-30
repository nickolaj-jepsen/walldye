"""Helpers for the tools tests: building fixture pieces and comparing recolors."""

import numpy as np

from walldye._theme import SEEDS, parse_seeds
from walldye.tools import build, coefs, common, new
from walldye.tools.tokenize import skeleton

LEGACY_SOURCE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">\n'
    '<rect x="0" y="0" width="1920" height="1080" fill="#1c1b1a"/>\n'
    '<circle cx="960" cy="540" r="200" fill="#CF6A4C"/>\n'
    '<path d="M0 0L100 100" stroke="#201A18"/>\n</svg>\n'
)
LEGACY_PALETTE = '"#1C1B1A": bg\n"#CF6A4C": accent\n"#201A18": [bg_deep, accent_8, 0.68]\n'


def built(capsys, *slugs, **kw) -> str:
    """build.run(slugs, jobs=1, **kw), which must pass; returns what it printed."""
    code = build.run(list(slugs), jobs=kw.pop("jobs", 1), **kw)
    out = capsys.readouterr().out
    assert code == 0, out
    return out


def legacy(wallpapers, slug="old", source=LEGACY_SOURCE, palette=LEGACY_PALETTE, **meta) -> str:
    d = wallpapers / slug
    d.mkdir()
    (d / "source.svg").write_text(source)
    (d / "palette.yaml").write_text(palette)
    fields = {"title": "Old", "description": "A disc.", "model": "claude-opus-5-5", **meta}
    (d / "meta.yaml").write_text("".join(f"{k}: {v}\n" for k, v in fields.items()))
    return slug


def seeds(theme) -> dict[str, str]:
    return parse_seeds(theme) if isinstance(theme, str) else dict(zip(SEEDS, theme, strict=True))


def assert_recolors(slug: str, theme, aspect: str = "16:9", variant: str = "default") -> None:
    """build.recolor of the built template matches a fresh render: same skeleton, slots
    within coefs.MAX_ERROR."""
    slots = build.load_slots(slug, variant)
    assert slots is not None
    table = build.entries(slots)
    s = seeds(theme)
    k = build.select(slots, aspect, s)
    template = (common.build_dir(slug, variant) / table[k]["file"]).read_text()
    got = build.recolor(template, table[k], s)
    want = common.render(slug, s, aspect, variant)
    assert skeleton(got) == skeleton(want)
    assert np.abs(coefs.colors(got) - coefs.colors(want)).max(initial=0) <= coefs.MAX_ERROR


VERSION_LABELS = {
    "default": {"label": "Two o'clock"},
    "late": {"label": "Eight o'clock", "draft": True},
    "bare": {"label": "Five, no ring", "draft": True},
}


def versions(wallpapers, slug: str = "versions", **meta) -> str:
    """Install the versions fixture with its meta.yaml variants: labels."""
    from fixtures import pieces

    return pieces.install(wallpapers, "versions", slug, variants=VERSION_LABELS, **meta)


# A ring everywhere; the dot only in the light regime, so light geometry differs.
TINY = '''"""A ring with a dot that only the light version draws."""

from walldye import ACCENT, UI, Canvas, P, design


@design(aspects="any")
def draw(s: Canvas) -> None:
    s.stroke(P().circle(s.center, 200), UI, 2)
    if s.light:
        s.fill(P().circle(s.center, 20), ACCENT)
'''
FLAT = '''"""A square."""

from walldye import UI, Canvas, P, design


@design()
def draw(s: Canvas) -> None:
    s.fill(P().rect(10, 10, 100, 100), UI)
'''


def piece(wallpapers, slug, design=TINY, **meta):
    d = wallpapers / slug
    d.mkdir()
    (d / "design.py").write_text(design)
    fields = {
        "title": slug.capitalize(),
        "description": "A test piece.",
        "model": "claude-opus-5-5",
    }
    new.write_meta(slug, {**fields, "draft": True, **meta})
    return d


def meta(slug):
    return common.load_meta(slug)
