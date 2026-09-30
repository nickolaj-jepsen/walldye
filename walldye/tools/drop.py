"""walldye drop: delete pieces and take them off featured.yaml, index.json and the review
state."""

import re
import shutil
from collections.abc import Sequence

from walldye.tools import index, paths, review


def unfeature(slugs: Sequence[str]) -> list[str]:
    """Remove the `- <slug>` lines of `slugs` from featured.yaml, keeping every other line;
    returns the slugs that were on it."""
    if not paths.FEATURED.exists():
        return []
    lines = paths.FEATURED.read_text().splitlines(keepends=True)
    entry = re.compile(r"-\s+['\"]?([a-z0-9-]+)['\"]?\s*(?:#.*)?$")
    kept: list[str] = []
    gone: list[str] = []
    for line in lines:
        m = entry.match(line.strip())
        if m is not None and m.group(1) in slugs:
            gone.append(m.group(1))
        else:
            kept.append(line)
    if len(gone) > 0:
        paths.FEATURED.write_text("".join(kept))
    return gone


def run(slugs: Sequence[str], yes: bool) -> int:
    """`walldye drop`: delete wallpapers/<slug>/ for each of `slugs` after a y/N prompt (skipped with `yes`),
    then take them off featured.yaml, regenerate index.json and forget their review state.
    Returns 1 when the prompt is declined."""
    dirs = [paths.piece_dir(s) for s in slugs]
    if not yes:
        try:
            answer = input(f"Delete {', '.join(str(d) for d in dirs)}? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("nothing deleted")
            return 1
    for d in dirs:
        shutil.rmtree(d)
        print(f"removed {d}")
    for slug in unfeature(slugs):
        print(f"took {slug} off {paths.FEATURED.name}")
    state = review.state.load_state()
    if any(s in state for s in slugs):
        review.state.save_state({k: v for k, v in state.items() if k not in slugs})
    index.write()
    return 0
