"""`walldye new`: scaffold wallpapers/<slug>/ with a starter design.py and a draft meta.yaml."""

import datetime
from collections.abc import Mapping

from walldye.tools import lint, metadata, paths
from walldye.tools.errors import UsageError

DESIGN = '''"""TODO: one theme-neutral line, concept + technique."""

from walldye import ACCENT, UI, Canvas, P, design


@design()  # aspects="any" once the composition follows s.w and s.h
def draw(s: Canvas) -> None:
    c = s.pick(landscape=(0.62, 0.5), portrait=(0.5, 0.4))
    s.stroke(P().circle(c, 240), UI, 2)
    s.fill(P().circle(c, 10), ACCENT)
'''


def run(slug: str, credit: Mapping[str, str]) -> int:
    """Create wallpapers/<slug>/ holding DESIGN and a meta.yaml credited to `credit` (`{"model":
    id}` or `{"author": name}`), added today, draft true and with no license line. UsageError if
    `slug` is malformed, reserved or already taken."""
    try:
        d = paths.piece_dir(slug)
    except ValueError as e:
        raise UsageError(str(e)) from None
    if lint.piece.reserved(slug):
        raise UsageError(f"{slug!r} is reserved for a site route")
    if d.exists():
        raise UsageError(f"{d} already exists")
    d.mkdir(parents=True)
    (d / "design.py").write_text(DESIGN)
    metadata.write_meta(slug, {
        "title": slug.replace("-", " ").capitalize(),
        "description": "",
        "alt": "",
        "technique": [],
        "subject": [],
        "lineage": [],
        "sources": [],
        "added": datetime.datetime.now().astimezone().date(),
        **credit,
        "draft": True,
        "proposed_facets": {},
    })  # fmt: skip
    print(d)
    return 0
