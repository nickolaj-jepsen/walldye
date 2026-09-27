"""PPI radar scope mid-rotation: stepped accent wedges fake a phosphor afterglow over noise-masked arc grains (coastline)."""

import math

from walldye import (
    ACCENT,
    ACCENT_4,
    ACCENT_6,
    BG,
    BG_ALT,
    UI,
    H,
    Noise,
    P,
    W,
    mix,
    polar,
    rng,
    smoothstep,
)

ASPECTS = ["any"]

U = min(W, H) / 1080  # short-side unit: the scope keeps its size relative to the short edge
R = 420 * U
# landscape: scope right of centre, leaving the left for windows; portrait: low-centre, under the clock
CX, CY = (W * 0.71875, H * 5 / 9) if W > H else (W / 2, H * 0.6)

SWEEP, GLOW, STEPS = (
    60,
    70,
    36,
)  # arm bearing (deg clockwise from north), afterglow length, wedge count
LAND = (38, 175)  # coastline bearings; only its first ~20deg sits under the afterglow
ISLANDS = [(151, 0.66, 26), (160, 0.8, 18), (170, 0.56, 15)]  # bearing, range (x R), radius (x U)
DB, DR, MAX_RUN = 0.6, 6 * U, 3  # grain grid: bearing step, ring step, longest grain in steps
# Grain tones by sweep age, one ladder: ACCENT_4 fading to UI under the afterglow (0-4), then UI to BG_ALT.
TONES = [mix(ACCENT_4, UI, k / 4) for k in range(5)] + [mix(UI, BG_ALT, k / 3) for k in range(1, 4)]


def at(r, bearing):
    return polar(CX, CY, r, math.radians(bearing - 90))


def wedge(r, b0, b1):
    return P().M(CX, CY).L(*at(r, b0)).A(r, r, 0, 0, 1, *at(r, b1)).Z()


def tone(b):
    """Index into TONES for a grain at bearing `b`: accent under the afterglow, UI just ahead of the arm, BG_ALT beyond."""
    if b < SWEEP:
        return round((SWEEP - b) / GLOW * 4)
    return 4 + round(smoothstep(105, 140, b) * 3)


def draw(s):
    with s.g(clip_path=s.clip(f'<circle cx="{CX:.1f}" cy="{CY:.1f}" r="{R:.1f}"/>')):
        for i in range(STEPS):
            end = SWEEP - GLOW * i / STEPS
            # 0.3deg overlap hides anti-aliasing seams between wedges
            s.path(
                wedge(R + 2 * U, end - GLOW / STEPS - 0.3, end),
                fill=mix(BG, ACCENT_6, (1 - i / STEPS) ** 1.6),
            )

    # coastline returns: a low-frequency land mask plus a few islands, speckled into short arc grains.
    # Noise is sampled relative to the centre, so the coast is identical wherever the scope sits.
    n, r = Noise(5), rng(5)
    b0, b1 = LAND
    isles = [(*at(R * rr, b), rad * U) for b, rr, rad in ISLANDS]
    grains = {}  # tone index -> one merged path

    def emit(rr, start, stop):
        grains.setdefault(tone((start + stop) / 2), P()).M(*at(rr, start - 0.2)).A(
            rr, rr, 0, 0, 1, *at(rr, stop + 0.2)
        )

    for ring in range(int(R * 0.4 / DR), int(R * 0.93 / DR)):
        rr, run = ring * DR, []
        for k in range(int((b1 - b0) / DB) + 1):
            b = b0 + k * DB
            x, y = at(rr, b)
            nx, ny = (x - CX) / U, (y - CY) / U  # scope-relative noise coordinates
            edge = smoothstep(b0, b0 + 25, b) * (1 - smoothstep(b1 - 50, b1 - 25, b))
            mass = n.fbm(nx / 220 + 6.27, ny / 220 + 2.73, 4) + 0.7 * (rr / R - 0.55)
            land = edge > 0.3 and mass > 0.17
            isle = any(
                math.hypot(x - ix, y - iy) < rad * (1 + 0.35 * n(nx / 40, ny / 40))
                for ix, iy, rad in isles
            )
            dense = 0.62 if isle else min(0.6, 0.3 + 2.5 * (mass - 0.17))
            # the sweep line always breaks a run
            hit = (land or isle) and r.random() < dense and abs(b - SWEEP) > DB / 2
            if hit:
                run.append(b)
            if run and (not hit or len(run) == MAX_RUN):
                emit(rr, run[0], run[-1])
                run = []
        if run:
            emit(rr, run[0], run[-1])
    for k, d in grains.items():
        s.path(d, fill="none", stroke=TONES[k], stroke_width=1.4 * U, stroke_linecap="butt")

    rings = P()
    for k in range(1, 5):
        rk = R * k / 5
        rings.M(CX + rk, CY).A(rk, rk, 0, 1, 1, CX - rk, CY).A(rk, rk, 0, 1, 1, CX + rk, CY).Z()
    s.path(rings, fill="none", stroke=BG_ALT, stroke_width=1.2 * U)
    ticks, major = P(), P()
    for b in range(0, 360, 5):
        long = b % 30 == 0
        (major if long else ticks).M(*at(R, b)).L(*at(R - (18 if long else 6) * U, b))
    s.path(ticks, stroke=UI, stroke_width=1.2 * U)
    s.path(major, stroke=UI, stroke_width=1.6 * U)
    s.path(P().M(CX - R, CY).H(CX + R).M(CX, CY - R).V(CY + R), stroke=UI, stroke_width=U)
    s.circle(CX, CY, R, fill="none", stroke=UI, stroke_width=2 * U)

    for b, rr in [(49, 0.66), (33, 0.34), (16, 0.7)]:  # fresh contacts under the glow
        s.circle(*at(R * rr, b), 5 * U, fill=ACCENT)
    s.circle(*at(R * 0.55, 250), 5 * U, fill=ACCENT_4)  # one fading behind the arm
    s.path(
        P().M(CX, CY).L(*at(R, SWEEP)), stroke=ACCENT, stroke_width=1.6 * U, stroke_linecap="round"
    )
