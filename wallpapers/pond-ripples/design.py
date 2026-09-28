"""Raindrop ripples on a pond in perspective: concentric elliptical bands whose overlaps cancel under an even-odd fill."""

from walldye import ACCENT, ACCENT_4, BG_ALT, MASK_BLACK, MASK_WHITE, Canvas, P, Path, Vec, design

type Drop = tuple[float, float, int]  # x, depth below the horizon, age

SQUASH = 0.28  # ellipse height over width on a landscape screen
RING = 39 / 440  # ring spacing per unit of depth
BAND = 520  # the pond's depth; on a landscape screen it fills the bottom 520 units
FADE = (60, 240)  # depths over which the far ripples fade in
RINGS, NEAR_RINGS = 6, 4

# Older drops have spread further and their inner rings have died out. x is in a 1920-wide
# frame: the first five drops are the 16:9 composition and the rest lie past its edges. A wider
# screen adds two thirds of its extra width on the left, so the nearest drop stays near the
# right third; a narrower one shows the same pond smaller.
WIDE: tuple[Drop, ...] = (
    (380, 240, 5),
    (820, 130, 6),
    (1330, 185, 8),
    (560, 450, 5),
    (840, 395, 7),
    (-165, 140, 6),
    (-520, 300, 6),
    (-1050, 470, 5),
    (2300, 140, 6),
    (2600, 330, 6),
)
# The nearest, youngest drop: in front of the rest, still small, its drop still falling.
NEAR_WIDE = (1500.0, 415.0)
# A portrait screen, 1080 wide, looks down on the pond from higher up: it fills the lower 60%.
TALL: tuple[Drop, ...] = ((760, 120, 6), (320, 200, 7), (260, 460, 5), (880, 430, 4))
NEAR_TALL = (700.0, 300.0)
TALL_POND = 0.6


def ripple(d: Path, c: Vec, unit: float, squash: float, age: int, rings: int) -> Path:
    """Annular bands (pairs of ellipses) so even-odd never fills a centre disc."""
    for k in range(age, age + rings):
        r = (k + 1) * unit
        w = unit * (0.55 - 0.05 * (k - age))
        d.ellipse(c, r, r * squash).ellipse(c, r - w, (r - w) * squash)
    return d


@design(aspects="any")
def draw(s: Canvas) -> None:
    if s.landscape:
        drops, near, frame, left = WIDE, NEAR_WIDE, 1920, 2 / 3
        zoom, stretch = min(1.0, s.w / frame), 1.0
    else:
        drops, near, frame, left = TALL, NEAR_TALL, 1080, 0.5
        zoom, stretch = 1.0, TALL_POND * s.h / BAND
    squash = SQUASH * stretch**0.5  # seen from higher up, the rings open out
    horizon = s.h - BAND * zoom * stretch

    def at(x: float, depth: float) -> Vec:
        return Vec(s.w * left + (x - frame * left) * zoom, horizon + depth * zoom * stretch)

    with s.mask() as far:
        lo, hi = (at(0, f).y for f in FADE)
        fade = far.linear_gradient([(0, MASK_BLACK), (1, MASK_WHITE)], (0, lo), (0, hi))
        far.fill(P().rect(0, 0, s.w, s.h), fade)
    d = P()
    for x, depth, age in drops:
        c, unit = at(x, depth), RING * depth * zoom
        reach = (age + RINGS) * unit
        if -reach < c.x < s.w + reach:  # drops past the edges of a narrower screen
            ripple(d, c, unit, squash, age, RINGS)
    s.path(d, fill=BG_ALT, fill_rule="evenodd", mask=far.ref)

    c, unit = at(*near), RING * near[1] * zoom
    s.fill(ripple(P(), c, unit, squash, 0, NEAR_RINGS), ACCENT_4, rule="evenodd")
    s.fill(P().circle(c - (0, 80 * zoom), 3.5), ACCENT)
