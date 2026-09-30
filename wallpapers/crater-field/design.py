"""A lunar crater field under a low sun, in flat crescents of shade and light."""

import math

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_4,
    ACCENT_5,
    ACCENT_6,
    BG,
    BG_ALT,
    BG_DEEP,
    BLACK,
    UI,
    UI_ALT,
    Buckets,
    Canvas,
    P,
    Path,
    Rect,
    Rng,
    Vec,
    by_regime,
    design,
    mix,
    polar,
    smoothstep,
)
from walldye.field import gauss, runs
from walldye.geom import poisson_disk, ribbon

FR = 34  # fresh crater radius
DENSITY = 1900 / (2000 * 1160)  # craters per square unit of the bled canvas
RMIN, RMAX = 4, 160
MARE_SIGMA = 325  # spread of the calm plain (a mare), where windows usually sit
FIELD_WORDS = 1_828_010  # 32-bit words the 16:9 crater field draws from stream 5
# On light themes both walls darken, the shaded one more, since nothing is lighter than the page.
SHADE = by_regime(BLACK, mix(BG_ALT, UI, 0.25))
RIM_SHADOW = by_regime(BG_DEEP, mix(BG, BG_ALT, 0.5))
LIT, LIT_BIG = by_regime(UI, mix(BG, BG_ALT, 0.3)), by_regime(UI_ALT, mix(BG, BG_ALT, 0.4))
RAY_TONES = (ACCENT_6, ACCENT_5, ACCENT_4)  # far to near, the drawing order
RIM, FLOOR, WALL, GLINT = range(4)  # bucket order: rim shadow, floor, shaded wall, lit wall


def arc_flags(c: Vec, p: Vec, q: Vec, via: Vec) -> tuple[bool, bool]:
    """The SVG (large, sweep) flags of the arc around `c` from `p` to `q` that passes `via`."""
    t1, t2, tv = (math.atan2(v.y - c.y, v.x - c.x) for v in (p, q, via))
    span = (t2 - t1) % math.tau
    if (tv - t1) % math.tau < span:
        return span > math.pi, True
    return math.tau - span > math.pi, False


def lune(d: Path, a: Vec, ra: float, b: Vec, rb: float) -> Path:
    """Append the region inside circle (a, ra) and outside circle (b, rb) to `d` as a two-arc
    subpath. The circles must cross."""
    dist = abs(b - a)
    u = (b - a) / dist
    along = (dist * dist + ra * ra - rb * rb) / (2 * dist)
    h = math.sqrt(max(ra * ra - along * along, 0))
    m = a + u * along
    p1, p2 = m + u.perp() * h, m - u.perp() * h
    large, cw = arc_flags(a, p1, p2, a - u * ra)
    d.M(p1).A(ra, ra, 0, large, cw, p2)
    large, cw = arc_flags(b, p2, p1, b - u * rb)
    return d.A(rb, rb, 0, large, cw, p1).Z()


def crater(b: Buckets, c: Vec, rad: float, *, floor: bool) -> None:
    """A crater lit from the left: the left wall is in shade, the right wall catches the sun
    across about 120 degrees, and a big one's rim throws a thin shadow to the right. With
    `floor`, a disc of ground first hides the older craters it lands on."""
    if floor:
        b[FLOOR].circle(c, rad)
    lune(b[WALL], c, rad, c + (rad * 0.55, 0), rad)
    lune(b[GLINT], c, rad, c - (rad * 0.2375, 0), rad * 1.1375)
    if rad > 40:
        lune(b[RIM], c + (rad * 0.09, 0), rad * 1.03, c, rad)


def ray_angles(r: Rng, n: int) -> list[float]:
    """Clustered ray directions in radians: gamma-distributed gaps leave a few wide empty
    sectors."""
    gaps = [r.gammavariate(0.55, 1) for _ in range(n)]
    total, a, out = sum(gaps), r.uniform(0, math.tau), []
    for g in gaps:
        a += g / total * math.tau
        out.append(a % math.tau)
    return out


@design(aspects="any")
def draw(s: Canvas) -> None:
    # 16:9 keeps the fresh crater at (1340, 420) and the plain at (430, 580)
    fresh = s.pick(landscape=(1340 / 1920, 420 / 1080), portrait=(0.64, 0.3))
    mare = s.pick(landscape=(430 / 1920, 580 / 1080), portrait=(0.34, 0.66))

    r = s.rng(5)
    field = Rect(-40, -40, s.w + 80, s.h + 80)
    pool: list[list[float]] = poisson_disk(field, 11, r).tolist()
    r.shuffle(pool)
    n = s.noise(11)
    craters: list[tuple[Vec, float]] = []
    for x, y in pool[: round(DENSITY * field.w * field.h)]:
        c = Vec(x, y)
        rad = RMIN * (1 - r.random() * (1 - (RMIN / RMAX) ** 2)) ** -0.5  # N(>r) ~ r^-2
        calm = smoothstep(
            0.02, 0.32, n.fbm(x / 600, y / 600, 3) + 0.55 * gauss(abs(c - mare), MARE_SIGMA)
        )
        if r.random() < calm * (1.0 if rad > 14 else 0.9):
            continue  # smooth maria keep only a sprinkle of small craters
        dist = abs(c - fresh)
        if dist < FR * 2.2 + rad or (rad > 30 and dist < 240 + rad):
            continue  # the fresh crater sits on clean ground
        craters.append((c, rad))
    craters.sort(key=lambda cr: -cr[1])

    # Big craters draw one by one so a younger one visibly cuts an older rim; smaller tiers merge.
    tiers = [[cr] for cr in craters if cr[1] >= 60] + [
        [cr for cr in craters if lo <= cr[1] < hi] for lo, hi in ((18, 60), (0, 18))
    ]
    older = np.empty((0, 3))  # center and painted reach (rim shadow included) of earlier tiers
    for tier in filter(None, tiers):
        glint = LIT_BIG if tier[0][1] >= 60 else LIT
        with s.buckets((RIM_SHADOW, BG, SHADE, glint), "fill") as b:
            for c, rad in tier:
                # a floor on bare ground is invisible, so only craters over older ones get one
                gap = np.hypot(older[:, 0] - c.x, older[:, 1] - c.y) - older[:, 2]
                crater(b, c, rad, floor=bool((gap < rad).any()))
        older = np.vstack([older, [(v.x, v.y, rv * 1.12) for v, rv in tier]])

    # Tycho-style rays: clustered, uneven lengths, continuous tapered streaks broken by noise.
    # Stream 5 resumes where the 16:9 field left it, so every screen shape gets the same rays.
    spray = s.rng(5)
    spray.getrandbits(32 * FIELD_WORDS)
    angles = ray_angles(spray, 22)
    long_rays = set(spray.sample(range(len(angles)), 4))
    gate = s.noise(8)
    with s.buckets(RAY_TONES, "fill") as rays:
        for k, a in enumerate(angles):
            long = k in long_rays
            reach = spray.uniform(550, 750) if long else 120 + spray.betavariate(1.2, 2.2) * 200
            split = [150 + spray.uniform(-20, 20), 330 + spray.uniform(-30, 30)]
            # a ray is a few fine streaks that fan apart slightly and break up with distance
            for m in range(spray.choice((2, 3)) if long else spray.choice((1, 1, 2))):
                b0, bend = a + spray.gauss(0, 0.012), spray.gauss(0, 0.02)
                w0 = spray.uniform(1.8, 2.8) if long else spray.uniform(1.5, 2.3)
                end = reach * spray.uniform(0.7, 1.0)
                t = np.arange(FR * 1.1, end, 3.0)
                f = (t - FR) / (end - FR)
                on = gate.fbm(t / 55, k * 3.7 + m * 11.3, 2) > -0.35 + 0.55 * f
                width = 1.2 + (w0 - 1.2) * (1 - f) ** 1.3
                bearing = b0 + bend * f * f
                pts = fresh + np.column_stack([np.cos(bearing), np.sin(bearing)]) * t[:, None]
                band = len(RAY_TONES) - 1 - np.digitize(t, split)  # near the rim is brightest
                for i, j in runs(on & (f < 0.995)):
                    for tone in range(len(RAY_TONES)):
                        idx = np.arange(i, j)[band[i:j] == tone]
                        if len(idx) < 2:
                            continue
                        # each run tapers to a point at both ends
                        taper = np.minimum(1, np.minimum(idx - idx[0], idx[-1] - idx) / 4 + 0.15)
                        rays[tone].poly(ribbon(pts[idx], width[idx] * taper), closed=True)

    # Ejecta blanket: a few specks near the rim, gathered at the ray roots.
    specks = P()
    for _ in range(50):
        a = spray.choice(angles) + spray.gauss(0, 0.12)
        at = polar(fresh, FR * spray.uniform(1.5, 2.5), rad=a)
        specks.circle(at, spray.uniform(1.0, 1.9))
    s.fill(specks, ACCENT_5)

    s.fill(P().circle(fresh, FR), BG)
    s.fill(lune(P(), fresh, FR, fresh + (FR * 0.42, 0), FR), SHADE)
    s.fill(lune(P(), fresh, FR, fresh - (FR * 0.2, 0), FR), ACCENT_2)
    s.stroke(P().circle(fresh, FR), ACCENT, 3)
