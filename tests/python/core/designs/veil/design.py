"""A patterned field seen through a veil with round holes, inside a frame."""

from walldye import (
    ACCENT,
    ACCENT_2,
    BG,
    BG_DEEP,
    MASK_BLACK,
    MASK_WHITE,
    UI_ALT,
    Canvas,
    P,
    Params,
    design,
    knob,
    mix,
)


class Veil(Params):
    holes: int = knob(default=5, lo=1, hi=12, doc="holes in the veil")
    tilt: float = knob(default=15, lo=-45, hi=45, unit="deg", doc="hatching angle")
    ring: bool = True


VARIANTS = {"dense": Veil(holes=11, tilt=-30), "reseeded": Veil(seed=7, ring=False)}


@design(aspects=("16:9", "9:19.5"), variants=VARIANTS, bg=BG_DEEP)
def draw(s: Canvas[Veil]) -> None:
    p = s.params
    rng, nrng, noise = s.rng(3), s.np_rng(3), s.noise("veil")
    with s.clip() as frame:
        frame.add(P().rect(*s.inset(60)))
    with s.mask() as veil:
        veil.fill(P().rect(0, 0, s.w, s.h), MASK_WHITE)
        for _ in range(p.holes):
            hole = P().circle(s.frac(rng.random(), rng.random()), 40 + 60 * rng.random())
            veil.fill(hole, MASK_BLACK)
        grey = mix(MASK_BLACK, MASK_WHITE, 0.4)
        top = veil.linear_gradient([(0, grey), (1, MASK_WHITE)], (0, 0), (0, 80))
        veil.fill(P().rect(0, 0, s.w, 80), top)
    with s.pattern(24, 24) as hatch:
        hatch.stroke(P().M(0, 0).L(24, 24), UI_ALT, 2, cap="square")
    with s.group(clip_path=frame.ref, mask=veil.ref):
        s.fill(P().rect(0, 0, s.w, s.h), hatch.ref)
        s.fill(P().dots(nrng.uniform(0, 1, (40, 2)) * (s.w, s.h), 3), ACCENT_2)
    wave = P().poly(
        [(x, s.h / 2 + 80 * noise(x / 200, p.tilt / 10)) for x in range(0, s.w + 1, 40)]
    )
    s.stroke(wave, ACCENT, 3, join="round", dash=(12, 6))
    if p.ring:
        glow = s.radial_gradient([(0, ACCENT), (1, BG, 0)], s.center, 300, focus=s.frac(0.4, 0.4))
        s.fill(P().ring(s.center, 200, 300), glow)
