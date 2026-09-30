"""wallpapers/index.json: every built piece, for consumers outside the site."""

import json
import sys

from walldye._aspect import SITE_ASPECTS
from walldye.tools import lint, metadata, paths, slotfile


def write() -> None:
    """Regenerate wallpapers/index.json without importing designs; license
    is null when meta.yaml breaks the license rules. A piece whose meta.yaml or slots.json cannot
    be read is left out, with a note on stderr."""
    index: dict[str, object] = {}
    for slug in paths.slugs():
        try:
            slots = slotfile.load(slug)
            if slots is None:
                continue
            m = metadata.load_meta(slug)
            keys = slots.entries
        except (OSError, ValueError) as e:
            print(f"index.json: left out {slug}: {e}", file=sys.stderr)
            continue
        variants: dict[str, object] = {}
        for name, entry in metadata.meta_variants(m).items():
            if name != "default":
                label = entry.get("label")
                variants[name] = {
                    "draft": entry.get("draft") is True,
                    "label": label if isinstance(label, str) else "",
                }
        index[slug] = {
            "aspects": [a for a in SITE_ASPECTS if any(k.startswith(f"{a}/") for k in keys)],
            "draft": metadata.is_draft(m),
            "license": lint.license_of(m),
            "title": m.get("title"),
            "variants": variants,
        }
    (paths.WALLPAPERS / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False, default=str) + "\n"
    )
