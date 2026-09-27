"""A disc placed by the unseeded global random generator."""

import random

from walldye import ACCENT, H, W


def draw(s):
    s.circle(random.uniform(0, W), H / 2, 50, fill=ACCENT)
