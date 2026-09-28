"""After Nees' Achsenparalleler Irrweg: a random walk of alternating horizontal and vertical steps tangles inside a square until its last steps break out through one wall to a filled square."""

from itertools import count

from walldye import ACCENT, UI, Canvas, P, design
from walldye.geom import Affine

HALF = 340  # the walk stays inside a square of side 2 * HALF around the frame's origin
MIN_STEPS = 470
EXIT_LO, EXIT_HI = -100, 60  # where on the far wall the walk may break out
# tail: hesitant jogs off the far wall, then one confident run into the square
JOGS, DROPS, RUN = (10, 18, 30, 50), (54, 30, 16, 8), 260
REACH = 0.66  # the run ends at least this far along the long side, so wide screens get a longer run


def step(v: float, n: float) -> float:
    """v moved by n; a step that would leave the square stops on the wall, or turns back if v is
    already on it."""
    if -HALF <= v + n <= HALF:
        return v + n
    if v in (-HALF, HALF):
        return min(HALF, max(-HALF, v - n))
    return min(HALF, max(-HALF, v + n))


@design(aspects="any")
def draw(s: Canvas) -> None:
    # local +x is the break-out direction: rightwards on landscape, down on portrait
    c = s.pick(landscape=(7 / 24, 0.5), portrait=(0.5, 0.33))
    frame = Affine.frame(c, deg=0 if s.landscape else 90)
    along = c.x if s.landscape else c.y
    r = s.rng(1969)
    x, y = r.uniform(-HALF + 100, HALF - 100), r.uniform(-HALF + 100, HALF - 100)
    knot = [(x, y)]
    # break out at the first horizontal step onto the far wall near mid-height, once the knot is dense
    for i in count():
        n = min(320, 24 + r.expovariate(1 / 110)) * r.choice((-1, 1))
        if i % 2 == 0:
            x = step(x, n)
        else:
            y = step(y, n)
        knot.append((x, y))
        if i % 2 == 0 and i + 1 >= MIN_STEPS and x == HALF and EXIT_LO <= y <= EXIT_HI:
            break
    tail = [(x, y)]
    for h, v in zip(JOGS, DROPS, strict=True):
        x += h
        tail.append((x, y))
        y += v
        tail.append((x, y))
    x = max(x + RUN, REACH * max(s.w, s.h) - along)
    tail.append((x, y))
    end = frame((x, y))
    s.stroke(P().poly(frame.apply(knot)), UI, 1.4, join="miter")
    s.stroke(P().poly(frame.apply(tail)), ACCENT, 2.4, join="miter")
    s.fill(P().rect(end.x - 6, end.y - 6, 12, 12), ACCENT)
