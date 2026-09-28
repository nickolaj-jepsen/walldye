"""A disc that draws everywhere but in the PYTHONHASHSEED=4242 determinism subprocess."""

import os

from walldye import ACCENT, Canvas, P, design


@design()
def draw(s: Canvas) -> None:
    if os.environ.get("PYTHONHASHSEED") == "4242":
        raise RuntimeError("only in the determinism subprocess")
    s.fill(P().circle(s.center, 100), ACCENT)
