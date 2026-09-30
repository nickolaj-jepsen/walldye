"""`walldye check --similar`: near-clones among the built pieces, by their ink maps."""

from collections.abc import Sequence
from typing import Final

import numpy as np
from numpy.typing import NDArray

from walldye.tools import paths, raster

NEAR_CLONE: Final = 0.93
INK_WIDTH: Final = 256

type Ink = NDArray[np.float64]


def built_ink(slug: str, variant: str) -> Ink | None:
    """The ink map of a variant's build/[<variant>/]16x9.svg, measured from its own
    background; None when not built."""
    path = paths.build_dir(slug, variant) / "16x9.svg"
    if not path.exists():
        return None
    svg = path.read_text()
    return raster.ink_map(raster.rasterize(svg, INK_WIDTH), raster.background(svg))


def near_clones(slugs: Sequence[str]) -> None:
    """`check --similar`: print pairs involving `slugs` whose built default build/16x9.svg
    ink maps have cosine >= NEAR_CLONE, most similar first, then the `slugs` that have no
    built template."""
    maps: dict[str, Ink] = {}
    skipped: list[str] = []
    for slug in sorted(set(paths.slugs()) | set(slugs)):
        ink = built_ink(slug, "default")
        if ink is not None:
            maps[slug] = ink
        elif slug in slugs:
            skipped.append(slug)
    names = list(maps)
    pairs = [
        (sim, a, b) for i, a in enumerate(names) for b in names[i + 1 :]
        if (a in slugs or b in slugs) and (sim := float(maps[a] @ maps[b])) >= NEAR_CLONE
    ]  # fmt: skip
    for sim, a, b in sorted(pairs, reverse=True):
        print(f"similar ({sim:.2f}): {a} ~ {b}")
    if len(skipped) > 0:
        print(f"similar: skipped, no build/16x9.svg: {', '.join(skipped)}")
