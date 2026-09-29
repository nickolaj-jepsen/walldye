"""Sand splines after Anders Hoff: dash-stippled Catmull-Rom strands random-walk from near-pinned ends and pile into grainy bands, one picked out where it frays."""

import numpy as np

from walldye import ACCENT, UI_HI, Canvas, P, Stop, design
from walldye.field import gauss

# (seed, offset from the band's center, swell amplitude, paint, calm and peak opacity, passes,
# fray); only the picked-out strand frays visibly and brightens over the belly
STRANDS = (
    (1, -160, 34, UI_HI, 0.18, 0.18, 60, 0.7),
    (2, -95, 55, UI_HI, 0.2, 0.2, 60, 0.7),
    (11, 0, 60, ACCENT, 0.2, 0.46, 90, 1.2),
    (4, 90, 45, UI_HI, 0.2, 0.2, 60, 0.7),
    (5, 170, 38, UI_HI, 0.12, 0.12, 60, 0.6),
)
# Seven nodes on every screen shape, so each one shows the same walk stretched to its width.
NODES, REACH = 7, 120  # the end nodes sit this far off-canvas
# Opacity across the width: (offset, edge fade, weight of the peak opacity over the belly).
PROFILE = (
    (0, 0.0, 0),
    (0.073, 0.3, 0),
    (0.177, 1, 0),
    (0.5, 1, 0),
    (0.552, 1, 1),
    (0.719, 1, 1),
    (0.792, 1, 0),
    (0.875, 1, 0),
    (0.948, 0.3, 0),
    (1, 0.0, 0),
)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # belly right of center; the band sits a little below the middle
    belly = s.pick(landscape=(0.6, 5 / 9), portrait=(0.6, 0.56))
    xs = np.linspace(-REACH, s.w + REACH, NODES)
    # the step peaks over the belly, so the ends stay near-pinned and one belly frays
    step = 1.0 + 6.5 * gauss((xs - belly.x) / s.w, 0.28)
    swell = np.sin(
        np.linspace(0, 2.2 * np.pi, NODES)[None] + 0.35 * np.arange(len(STRANDS))[:, None] + 0.4
    )
    # a stippled dash pattern turns each stroke into a line of sand grains
    rng = s.np_rng(11)
    dash = np.column_stack([rng.uniform(0.5, 1.2, 60), rng.uniform(1.5, 7, 60)]).ravel().tolist()
    with s.group(stroke_width=1.1, stroke_dasharray=dash):
        for k, (seed, dy, amp, paint, calm, top, passes, fray) in enumerate(STRANDS):
            rng = s.np_rng(seed)
            # opacity lives in the gradient: strands emerge at the left edge, dissolve at the right
            grad: list[Stop] = [(o, paint, f * (calm + (top - calm) * w)) for o, f, w in PROFILE]
            ys = belly.y + dy + amp * swell[k] + rng.uniform(-15, 15, NODES)
            walk = np.zeros((NODES, 2))
            with s.group(stroke=s.linear_gradient(grad, (0, 0), (s.w, 0))):
                for _ in range(passes):
                    walk += rng.normal(0, 1, (NODES, 2)) * fray * step[:, None] * [0.4, 1.0]
                    ctrl = np.column_stack([xs, ys]) + walk
                    s.path(P().spline(ctrl), fill="none", stroke_dashoffset=rng.uniform(0, 250))
