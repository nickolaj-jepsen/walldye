"""The synthetic designs in designs/ installed as pieces, and the themes their recolors are
checked under."""

from collections.abc import Mapping
from pathlib import Path

import yaml

DESIGNS = Path(__file__).parent / "designs"
META = {
    "title": "Fixture",
    "description": "A synthetic design for the build tests.",
    "alt": "Test shapes.",
    "model": "claude-opus-5-5",
    "draft": True,
}
# vitest (b) themes: a 1-unit neighbor of fireproof (derived model), two presets, and a light
# corner, so each regime is recolored under two themes other than its template's.
RECOLOR_THEMES = ["1c1b1b-dad8ce-cf6a4c", "nord", "flexoki-light", "ffffff-000000-0000ff"]


def install(
    wallpapers: Path,
    design: str,
    slug: str | None = None,
    data: Mapping[str, str] | None = None,
    **meta: object,
) -> str:
    """Copy designs/<design>.py to wallpapers/<slug>/design.py (slug defaults to `design`)
    with META updated by `meta` as its meta.yaml and `data` as data/<name> files, credited by
    a data source unless `meta` gives the sources; returns the slug."""
    slug = slug or design
    if data and "sources" not in meta:
        meta = {**meta, "sources": [{"kind": "data", "topic": "Fixture points"}]}
    d = wallpapers / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "design.py").write_text((DESIGNS / f"{design}.py").read_text())
    (d / "meta.yaml").write_text(yaml.safe_dump({**META, **meta}, sort_keys=False))
    for name, text in (data or {}).items():
        (d / "data").mkdir(exist_ok=True)
        (d / "data" / name).write_text(text)
    return slug
