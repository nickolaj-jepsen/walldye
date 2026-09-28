"""Seigaiha wave scales laid bottom-up in painter's order, shedding rings towards a noise-ragged surf line, with one pyramid of three scales lit."""

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    BG,
    BG_ALT,
    UI,
    Canvas,
    P,
    design,
    ladder,
    mix,
    smoothstep,
)

R = 60  # scale radius; rows sit R / 2 apart, alternate rows shifted by R
SLOPE = 0.14  # the surf line's climb per unit to the right, eased on screens wider than 16:9
# Ring tones of the lit scales, outer to inner: the apex, then the two it rests on.
LIT = (ACCENT, ACCENT_2, ACCENT_3, ACCENT_5)
DIM = (ACCENT_2, ACCENT_3, ACCENT_5, ACCENT_6)
# Scales fade from UI at the surf line to the deep tone 150 units below it.
TONES = ladder((UI, mix(BG_ALT, BG, 0.17)), 6)


def radii(rings: int) -> list[float]:
    """Radii of a scale's outer `rings` rings, inset by half the widest stroke."""
    return [R * (1 - 0.2 * m) - 1.5 for m in range(rings)]


@design(aspects="any")
def draw(s: Canvas) -> None:
    n, rnd = s.noise(5), s.rng(5)
    # where the surf line crosses the middle of the screen
    base = s.h - 440 if s.landscape else 0.6 * s.h
    slope = SLOPE * min(1.0, 1920 / s.w)
    # Two rows start below the frame so the bottom edge is a mid-pattern crop.
    rows = [
        (s.h - k * R / 2, [i * 2 * R + (R if k % 2 else 0) for i in range(-1, s.w // (2 * R) + 2)])
        for k in range(-2, int((s.h - base + 320) / (R / 2)))
    ]

    # Bottom-up: a scale survives only if both scales it rests on did, so crests never float.
    kept: dict[tuple[float, float], float] = {}
    for k, (y, xs) in enumerate(rows):
        below = set(rows[k - 1][1]) if k else set()
        for x in xs:
            u = x - s.w / 2  # centred, so every screen shape shows the middle of one surf line
            surf = base - slope * u + 150 * n.fbm((u + 960) / 520, 0.5, 2) + rnd.uniform(-20, 20)
            if y >= surf and all(
                xb not in below or (xb, y + R / 2) in kept for xb in (x - R, x + R)
            ):
                kept[(x, y)] = y - surf

    # The lit apex sits two scales below the crest of a column right of centre.
    px = R * round((0.75 if s.landscape else 0.7) * s.w / R)
    py = min(y for x, y in kept if x == px) + 2 * R
    lit = {(px, py): LIT, (px - R, py + R / 2): DIM, (px + R, py + R / 2): DIM}

    # Painter's order: upper rows first, so each row hides the lower half of the one above.
    # Scales in one row never overlap, so a row is one fill and a few stroke buckets.
    for y, xs in reversed(rows):
        row = [(x, kept[(x, y)]) for x in xs if (x, y) in kept]
        s.fill(P().dots([(x, y) for x, _ in row if (x, y) not in lit], R - 1.5), BG)
        with (
            s.buckets(TONES, "stroke", stroke_width=2.2) as crest,
            s.buckets(TONES, "stroke", stroke_width=2) as deep,
        ):
            for x, depth in row:
                if (x, y) in lit:
                    continue
                # Crest scales keep only their outer rings: the foam thins out as it breaks.
                rings = min(4, 1 + int((depth + rnd.uniform(-12, 12)) / 45))
                d = (crest if depth < 60 else deep)[TONES.rung(smoothstep(0, 150, depth))]
                for r in radii(rings):
                    d.circle((x, y), r)
        for x, depth in row:
            tones = lit.get((x, y))
            if tones is None:
                continue
            w = 2.2 if depth < 60 else 2
            outer, *inner = radii(4)
            s.path(P().circle((x, y), outer), fill=ACCENT_7, stroke=tones[0], stroke_width=w)
            for r, tone in zip(inner, tones[1:], strict=True):
                s.stroke(P().circle((x, y), r), tone, w)
