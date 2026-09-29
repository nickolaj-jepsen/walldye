"""A typewriter's typebar basket in flat shapes: bars fanned in an arc below the platen, one swung up mid-strike through the type guide."""

from numpy.typing import NDArray

from walldye import (
    ACCENT,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    P,
    Path,
    Point,
    Rng,
    Vec,
    design,
    mix,
    polar,
)
from walldye.geom import Affine

R, L = 440, 250  # pivot radius from the print point; bar length
N, A0, A1 = 36, 24, 156  # bars, fanned over this arc (deg, clockwise from east)
STRIKE = 20  # the bar in flight
PAPER = mix(BG, BG_ALT, 0.58)
TYPED = mix(BG_ALT, UI, 0.17)


def slug(c: Point, deg: float, w: float = 7, h: float = 18) -> NDArray:
    """Corners of a type slug: an `h` by `w` block centered on `c`, its long side along `deg`."""
    corners = [(-h / 2, -w / 2), (h / 2, -w / 2), (h / 2, w / 2), (-h / 2, w / 2)]
    return Affine.frame(c, deg=deg).apply(corners)


def typed(c: Vec, rng: Rng, rows: int = 5) -> Path:
    """Greeked lines already typed on the sheet above `c`, ragged right like a letter."""
    d = P()
    for row in range(rows):
        x, y = c.x - 118, c.y - 152 + 26 * row
        ragged = rng.uniform(0, 70)  # drawn on the short last line too, to keep the stream
        end = c.x + 118 - (ragged if row < rows - 1 else 120)
        while x < end:
            w = min(rng.uniform(10, 46), end - x)
            d.rect(x, y, w, 5)
            x += w + 8
    return d


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the print point: right of center on landscape, centered and a little high on portrait
    c = s.pick(landscape=(0.6875, 0.38), portrait=(0.5, 0.42), snap=1)
    s.fill(P().rect(c.x - 150, c.y - 270, 300, 270), PAPER)
    s.fill(typed(c, s.rng(3)), TYPED)
    s.fill(P().rrect(c.x - 380, c.y - 18, 760, 36, 18), BG_ALT)

    bars, parts = P(), P()
    for i in range(N):
        a = A0 + (A1 - A0) * i / (N - 1)
        if i != STRIKE:
            bars.M(polar(c, R, deg=a)).L(polar(c, R - L, deg=a))
            parts.circle(polar(c, R, deg=a), 3)
            parts.poly(slug(polar(c, R - L - 8, deg=a), a), closed=True)
    s.stroke(bars, UI, 4)
    s.fill(parts, UI_ALT)

    a = A0 + (A1 - A0) * STRIKE / (N - 1)
    # The knockout stops short of the guide so it only separates the bar from the fan.
    s.stroke(P().M(polar(c, R, deg=a)).L(polar(c, 28, deg=a)), BG, 12)
    # the type guide: the small fork the striking slug passes through at the print point
    guide = (
        P()
        .M(c + (-22, -18))
        .V(c.y + 8)
        .Q(c + (-22, 22), c + (-8, 22))
        .H(c.x + 8)
        .Q(c + (22, 22), c + (22, 8))
        .V(c.y - 18)
    )
    s.stroke(guide, UI_ALT, 3)
    s.stroke(P().M(polar(c, R, deg=a)).L(polar(c, 14, deg=a)), ACCENT, 4.5)
    strike = (
        P().circle(polar(c, R, deg=a), 4.5).poly(slug(polar(c, 8, deg=a), a, 9, 23), closed=True)
    )
    s.fill(strike, ACCENT)
