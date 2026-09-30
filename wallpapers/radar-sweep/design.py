"""A radar plan position indicator mid-sweep, with a stippled coastline."""

from walldye import (
    ACCENT,
    ACCENT_4,
    ACCENT_6,
    BG,
    BG_ALT,
    UI,
    Canvas,
    P,
    Params,
    Vec,
    design,
    knob,
    ladder,
    mix,
    polar,
    smoothstep,
)


class Radar(Params):
    sweep: float = knob(default=60, lo=0, hi=360, unit="deg", doc="arm bearing from north")
    glow: float = knob(default=70, lo=20, hi=180, unit="deg", doc="afterglow length")


VARIANTS = {"late": Radar(sweep=210, glow=120)}

R, STEPS = 420, 36  # scope radius; afterglow wedges
LAND = (38, 175)  # coastline bearings
ISLANDS = ((151, 0.66, 26), (160, 0.8, 18), (170, 0.56, 15))  # bearing, range (x R), radius
CONTACTS = ((-11, 0.66), (-27, 0.34), (-44, 0.7))  # bearing behind the arm, range (x R)
DB, DR, MAX_RUN = 0.6, 6, 3  # grain grid: bearing step, ring step, longest grain in steps
# Grain tones by age: ACCENT_4 fading to UI under the afterglow (0-4), then UI to BG_ALT (5-7).
TONES = (*ladder((ACCENT_4, UI), 5), *ladder((UI, BG_ALT), 4)[1:])


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Radar]) -> None:
    p = s.params
    # landscape: right of center, leaving the left for windows; portrait: low, under the clock
    c = s.pick(landscape=(0.71875, 5 / 9), portrait=(0.5, 0.6))

    def at(r: float, b: float) -> Vec:
        return polar(c, r, bearing=b)

    def tone(b: float) -> int:
        """Index into TONES for a grain at bearing `b`: the afterglow behind the arm, then a
        35-degree fade from UI to BG_ALT, which also runs 45 to 80 degrees ahead of the arm."""
        age = (p.sweep - b) % 360  # degrees since the arm passed
        if age <= p.glow:
            return round(age / p.glow * 4)
        return 4 + round(smoothstep(0, 35, min(age - p.glow, 315 - age)) * 3)

    with s.clip() as scope:
        scope.add(P().circle(c, R))
    with s.group(clip_path=scope.ref):
        for i in range(STEPS):
            end = p.sweep - p.glow * i / STEPS
            # a 0.3 degree overlap hides anti-aliasing seams between wedges
            wedge = P().arc_band(c, 0, R + 2, bearing=(end - p.glow / STEPS - 0.3, end))
            s.fill(wedge, mix(BG, ACCENT_6, (1 - i / STEPS) ** 1.6))

    # Coastline returns: a low-frequency land mask plus a few islands, cut into short arc grains.
    noise, rng = s.noise(5), s.rng(5)
    isles = [(at(R * rr, b), rad) for b, rr, rad in ISLANDS]
    b0, b1 = LAND
    with s.buckets(TONES, "stroke", stroke_width=1.4, stroke_linecap="butt") as grains:

        def emit(rr: float, run: list[float]) -> None:
            grains[tone((run[0] + run[-1]) / 2)].arc(c, rr, bearing=(run[0] - 0.2, run[-1] + 0.2))

        for ring in range(int(R * 0.4 / DR), int(R * 0.93 / DR)):
            rr = ring * DR
            run: list[float] = []
            for k in range(int((b1 - b0) / DB) + 1):
                b = b0 + k * DB
                # scope-relative, so the coast is the same wherever the scope sits
                q = at(rr, b) - c
                edge = smoothstep(b0, b0 + 25, b) * (1 - smoothstep(b1 - 50, b1 - 25, b))
                mass = noise.fbm(q.x / 220 + 6.27, q.y / 220 + 2.73, 4) + 0.7 * (rr / R - 0.55)
                land = edge > 0.3 and mass > 0.17
                wobble = 1 + 0.35 * noise(q.x / 40, q.y / 40)
                isle = any(abs(at(rr, b) - ic) < rad * wobble for ic, rad in isles)
                dense = 0.62 if isle else min(0.6, 0.3 + 2.5 * (mass - 0.17))
                # the sweep line always breaks a run
                hit = (land or isle) and rng.random() < dense and abs(b - p.sweep) > DB / 2
                if hit:
                    run.append(b)
                if run and (not hit or len(run) == MAX_RUN):
                    emit(rr, run)
                    run = []
            if run:
                emit(rr, run)

    rings = P()
    for k in range(1, 5):
        rings.circle(c, R * k / 5)
    s.stroke(rings, BG_ALT, 1.2)
    ticks, major = P(), P()
    for b in range(0, 360, 5):
        long = b % 30 == 0
        (major if long else ticks).M(at(R, b)).L(at(R - (18 if long else 6), b))
    s.stroke(ticks, UI, 1.2)
    s.stroke(major, UI, 1.6)
    s.stroke(P().M(c.x - R, c.y).H(c.x + R).M(c.x, c.y - R).V(c.y + R), UI, 1)
    s.stroke(P().circle(c, R), UI, 2)
    # fresh contacts under the afterglow, and one fading behind the arm
    s.fill(P().dots([at(R * rr, p.sweep + db) for db, rr in CONTACTS], 5), ACCENT)
    s.fill(P().circle(at(R * 0.55, p.sweep + 190), 5), ACCENT_4)
    s.stroke(P().M(c).L(at(R, p.sweep)), ACCENT, 1.6, cap="round")
