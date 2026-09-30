"""Sun glitter on water as perspective rows of dashes under a half-set sun."""

import math

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_6,
    BG_ALT,
    BG_DEEP,
    UI,
    Canvas,
    P,
    design,
)

SR = 70  # sun radius
ROWS, DEEP = 58, 480  # glint rows per 480 units of sea (the 16:9 sea, horizon to bottom)
CALM = (13 / 60) ** 1.7  # rows shallower than this stay sparse: the first ten of the 16:9 sea
# Glint paints by bucket, dimmest first: the sea, then the accent ladder of the path.
TONES = (BG_ALT, UI, ACCENT_6, ACCENT_3, ACCENT_1, ACCENT)
SEA, CREST, PATH_6, PATH_3, PATH_1, CORE = range(len(TONES))


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the sun's center, on the horizon
    foot = s.pick(landscape=(17 / 24, 5 / 9), portrait=(0.6, 0.55))
    hy = foot.y
    sea = s.h - hy
    rows = ROWS * sea / DEEP  # a taller sea gets more rows of the same pitch
    # a half-set disc leaves a calm gap under it before the path ignites
    calm_gap, core_from = 22, 45

    def depth(k: int) -> float:
        """Row k's distance below the horizon as a fraction of the sea (1 at the bottom)."""
        return ((k + 3) / (rows + 2)) ** 1.7

    r, n = s.rng(11), s.noise(5)
    # a BG_DEEP haze thickening down to the horizon
    s.fill(
        P().rect(0, hy - 150, s.w, 150),
        s.linear_gradient([(0, BG_DEEP, 0), (1, BG_DEEP, 1)], (0, 0), (0, 1), units="bbox"),
    )
    with s.buckets(TONES, "fill") as glints:
        k = 0
        while hy + sea * depth(k) < s.h + 10:
            d = depth(k)
            y0 = hy + sea * d
            gap = sea * (depth(k + 1) - d)
            half = 26 + 165 * d  # the path widens towards the viewer but stays a path
            x = r.uniform(-40, 0)
            while x < s.w:
                ln = (5 + 38 * d) * r.uniform(0.4, 1.6)
                cx = x + ln / 2
                off = abs(cx - foot.x) / half
                g = math.exp(-(off**2)) * (0.8 + 0.4 * n(cx / 90, k / 3))
                swell = 0.5 + 0.5 * n(cx / 260 + 7, k / 4.5)
                tone: int | None = None
                y = y0 + r.uniform(-0.15, 0.15) * gap
                if g > 0.08 and r.random() < 0.2 + 0.7 * g:
                    v = g + r.uniform(-0.25, 0.2)
                    if y < hy + calm_gap:
                        tone = PATH_3 if v > 0.55 and r.random() < 0.5 else None
                    elif v > 0.78 and off < 0.4 and y > hy + core_from:
                        tone = CORE
                    elif v > 0.6 and off < 0.7:
                        tone = PATH_1
                    elif v > 0.4:
                        tone = PATH_3
                    elif v > 0.2:
                        tone = PATH_6
                if tone is None:
                    # the first rows stay sparse and dark so the horizon reads as one clean line
                    calm = d < CALM
                    p = (0.2 + 0.6 * swell) * (0.9 - 0.35 * d) * (0.5 if calm else 1)
                    if r.random() < p:
                        crest = not calm and r.random() < 0.5 * swell * (1 - d)
                        tone = CREST if crest else SEA
                if tone is not None:
                    h = 1.2 + 2.3 * d
                    if tone >= PATH_1:
                        # bright glints are short tapered slivers, so the path shimmers
                        ln *= 0.6 if tone == CORE else 0.85
                        h *= 0.7
                        ta = ln / 4
                        glints[tone].M(x, y).L(x + ta, y - h / 2).H(x + ln - ta).L(x + ln, y)
                        glints[tone].L(x + ln - ta, y + h / 2).H(x + ta).Z()
                    else:
                        glints[tone].rect(x, y - h / 2, ln, h)
                x += ln + (3 + 30 * d) * r.uniform(0.6, 1.8)
            k += 1
    s.stroke(P().M(0, hy).H(s.w), UI, 1.2)
    s.fill(P().arc_band(foot, 0, SR, deg=(180, 360)), ACCENT)
