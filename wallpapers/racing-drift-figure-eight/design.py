"""Tyre marks from a car drifting figure eights round two cones, seen from above: a kinematic simulation drawn in short tread strokes."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_5,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    NpRng,
    P,
    Rng,
    Vec,
    design,
    smoothstep,
)

type F = NDArray[np.float64]

# Toyota AE86, in metres
WHEELBASE = 2.400
TRACK_F, TRACK_R = 1.355, 1.345
TYRE = 0.185  # tread width of a 185/70 R13
PATCH = 0.15  # contact patch length, estimated
CONE = 0.38  # side of a cone's square base, m

GAP = 18.0  # m between the cones
RADIUS = (6.6, 6.2)  # loop radius of the car's centre round each cone, m
SLIP = math.radians(36)  # body slip angle held through a loop
SWING = 2.6  # half the distance over which the body swings across at the crossover, m
SPREAD = (0.3, 0.25)  # lap-to-lap scatter of a loop's centre and radius, m
KMAX = 1 / 4.2  # tightest path curvature, 1/m
LAG = 0.6  # distance over which the path curvature follows the steering, m
RG, HG = 0.6, 1.5  # steering gains on the distance off the loop (1/m) and the course error
DS = 0.05  # simulation step, m
LAPS = 20
SCALE = 32.0  # canvas units per metre
CELL = 4  # overlap grid cell, canvas units
TONES = (BG_ALT, UI, UI_ALT)
CUTS = (2.4, 4.5)  # laps crossing a cell at which rear marks step up a tone
# the marks laid last: metres before the end at which the lit rear marks fade in, then take
# their two stronger steps
LIT = (22.0, 17.0, 10.0)
TILT = -24  # turn of the cone axis on a landscape screen, degrees; portrait turns it back a
# quarter turn more, which keeps the second cone, where the lit marks are, uppermost


def wrap(a: float) -> float:
    return (a + math.pi) % math.tau - math.pi


def wrap_all(a: F) -> F:
    return (a + np.pi) % (2 * np.pi) - np.pi


def loop(rng: Rng, k: int) -> tuple[float, float, float, float, float, float]:
    """One loop round cone k as the driver happens to drive it: the centre it is circled
    about, its radius, a slow wobble in that radius (amplitude and phase) and the body slip
    angle, all in metres and radians."""
    a, off = rng.uniform(0, math.tau), abs(rng.gauss(0, SPREAD[0]))
    return (
        (k - 0.5) * GAP + off * math.cos(a),
        off * math.sin(a),
        RADIUS[k] + rng.gauss(0, SPREAD[1]),
        rng.uniform(0.05, 0.2),
        rng.uniform(0, math.tau),
        SLIP + rng.gauss(0, 0.05),
    )


def simulate(rng: Rng) -> tuple[F, F, F, NDArray[np.int64]]:
    """The car's centre (N, 2), course angle and body slip angle every DS metres over LAPS
    figure eights, with the lap each sample belongs to. It circles the first cone with the
    angle about it rising and the second the other way, steering along the tangent to each
    loop, and breaks off when its course lines up with the tangent to the next one. Laps run
    from one crossing of the midline towards the first cone to the next; the last runs on
    SWING + 1 metres past its crossing."""
    turn = (1, -1)
    k = 0
    cur, nxt = loop(rng, 0), loop(rng, 1)
    x = y = kappa = swept = last_err = 0.0
    lap, side, stop = 0, 1, -1
    brk = rng.gauss(0, 0.05)  # how early the driver breaks off towards the next cone, rad
    betas = [turn[1] * SLIP, turn[0] * cur[5]]  # signed slip through each loop in turn
    cross: list[float] = []
    pts: list[tuple[float, float]] = []
    course: list[float] = []
    laps: list[int] = []

    def aim(c: tuple[float, ...], sign: int, r0: float) -> float:
        """Course along the tangent to the circle of radius r0 about c, circled with `sign`;
        near or inside it, back onto it in proportion to the distance off."""
        r = math.hypot(x - c[0], y - c[1])
        off = max(math.asin(min(1.0, r0 / r)), math.pi / 2 - math.atan(RG * (r - r0)))
        return math.atan2(c[1] - y, c[0] - x) - sign * off

    theta = aim(cur, turn[0], cur[2])
    while True:
        r0 = cur[2] + cur[3] * math.sin(swept * 1.7 + cur[4])
        want = aim(cur, turn[k], r0)
        # the driver turns in ahead of the loop, then corrects onto it
        near = smoothstep(r0 + 2.5, r0 + 0.5, math.hypot(x - cur[0], y - cur[1]))
        cmd = turn[k] * near / r0 + HG * wrap(want - theta)
        # the path's curvature follows the steering over LAG metres, so wheel paths stay smooth
        kappa += (max(-KMAX, min(KMAX, cmd)) - kappa) * DS / LAG
        theta += kappa * DS
        a0 = math.atan2(y - cur[1], x - cur[0])
        x += DS * math.cos(theta)
        y += DS * math.sin(theta)
        swept += abs(wrap(math.atan2(y - cur[1], x - cur[0]) - a0))
        if len(pts) == stop:
            break
        if (x > 0) != (side > 0):
            side = -side
            if side < 0 and pts:
                lap += 1
                if lap == LAPS:
                    # the last lap runs on until the rear has stepped across
                    lap, stop = LAPS - 1, len(pts) + round((SWING + 1) / DS)
            cross.append(len(pts) * DS)
        pts.append((x, y))
        course.append(theta)
        laps.append(lap)
        if swept > 1.2 * math.pi:
            # the course keeps turning by about kappa * LAG as the steering unwinds
            err = wrap(aim(nxt, turn[1 - k], nxt[2]) - theta) - brk - kappa * LAG
            if abs(err) < 0.4 and last_err * err <= 0 and last_err != 0:
                k = 1 - k
                cur, nxt = nxt, loop(rng, 1 - k)
                brk = rng.gauss(0, 0.05)
                swept, last_err = 0.0, 0.0
                betas.append(turn[k] * cur[5])
                continue
            last_err = err
    s = np.arange(len(pts)) * DS
    beta = np.full(len(pts), betas[0])
    for sc, b0, b1 in zip(cross, betas, betas[1:], strict=False):
        u = np.clip((s - sc + SWING) / (2 * SWING), 0, 1)
        # smootherstep: the yaw rate and its rate of change both ease in and out
        beta += (b1 - b0) * u**3 * (u * (6 * u - 15) + 10)
    return np.asarray(pts), np.asarray(course), beta, np.asarray(laps)


def normals(path: F) -> F:
    """Unit normals (N, 2) to a polyline, a quarter turn from its direction of travel."""
    tan = np.gradient(path, axis=0)
    tan /= np.maximum(np.hypot(tan[:, 0], tan[:, 1]), 1e-9)[:, None]
    return np.stack([-tan[:, 1], tan[:, 0]], axis=1)


def dashes(
    path: F,
    width: F,
    rng: NpRng,
    ribs: tuple[float, ...],
    dash: tuple[float, float],
    gap: tuple[float, float],
) -> list[F]:
    """Short strokes along `path` (canvas units), one run per rib, each rib offset across the
    path by its fraction of the local mark `width`. Each stroke is a polyline with a vertex
    at least every 16 units, so it follows the curve."""
    arc = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(path, axis=0).T))])
    nrm = normals(path)
    out: list[F] = []
    for rib in ribs:
        m = int(arc[-1] / (dash[0] + gap[0])) + 2
        d = rng.uniform(*dash, m)
        g = rng.uniform(*gap, m)
        a0 = np.cumsum(np.concatenate([[rng.uniform(0, gap[1])], (d + g)[:-1]]))
        keep = a0 < arc[-1] - 1
        d = np.minimum(d, arc[-1] - a0)  # the last stroke stops where the path does
        line = path + (rib * width)[:, None] * nrm
        for start, length in zip(a0[keep].tolist(), d[keep].tolist(), strict=True):
            a = np.linspace(start, start + length, math.ceil(length / 16) + 1)
            out.append(np.stack([np.interp(a, arc, line[:, 0]), np.interp(a, arc, line[:, 1])], 1))
    return out


@design(aspects="any")
def draw(s: Canvas) -> None:
    centre, course, beta, laps = simulate(s.rng(3))
    psi = course + beta
    head = np.stack([np.cos(psi), np.sin(psi)], axis=1)
    left = np.stack([-np.sin(psi), np.cos(psi)], axis=1)
    front = centre + WHEELBASE / 2 * head
    rear = centre - WHEELBASE / 2 * head
    wheels = (
        rear + TRACK_R / 2 * left,
        rear - TRACK_R / 2 * left,
        front + TRACK_F / 2 * left,
        front - TRACK_F / 2 * left,
    )
    # A sliding tyre sweeps its contact patch sideways, so the mark widens with the slip angle
    # between the rear wheels' heading and their direction of travel.
    vel = np.gradient(rear, axis=0)
    alpha = np.abs(wrap_all(np.arctan2(vel[:, 1], vel[:, 0]) - psi))
    rear_w = (TYRE * np.cos(alpha) + PATCH * np.sin(alpha)) * SCALE

    rot = math.radians(TILT - (0 if s.landscape else 90))
    at = s.pick(landscape=(0.6, 0.5), portrait=(0.5, 0.45))
    m = SCALE * np.array([[math.cos(rot), -math.sin(rot)], [math.sin(rot), math.cos(rot)]])
    canvas = [w @ m.T + np.asarray(at) for w in wheels]

    rows, cols = s.h // CELL + 1, s.w // CELL + 1
    count = np.zeros((rows, cols))
    for lap in range(LAPS):
        hit = np.zeros((rows, cols), bool)
        for w in canvas[:2]:
            q = w[laps == lap]
            iy = np.clip((q[:, 1] // CELL).astype(int), 0, rows - 1)
            ix = np.clip((q[:, 0] // CELL).astype(int), 0, cols - 1)
            hit[iy, ix] = True
        count += hit
    density = gaussian_filter(count, 1.2)

    rng = s.np_rng(5)
    ago = (len(laps) - 1 - np.arange(len(laps))) * DS  # metres driven since each sample
    lit = ago < LIT[0]

    def tone(stroke: F) -> int:
        """The stroke's rung in TONES, from how many laps' rear marks cross its middle."""
        x, y = stroke[len(stroke) // 2]
        iy, ix = min(int(y // CELL), rows - 1), min(int(x // CELL), cols - 1)
        return int(np.digitize(density[iy, ix], CUTS))

    faint = P()
    for w in canvas[2:]:
        for stroke in dashes(w, np.full(len(w), TYRE * SCALE), rng, (0.0,), (6, 40), (3, 30)):
            faint.poly(stroke)
    s.stroke(faint, BG_ALT, 1.2, cap="round")
    with s.buckets(TONES, "stroke", stroke_width=1.3, stroke_linecap="round") as rb:
        for w in canvas[:2]:
            for stroke in dashes(w[~lit], rear_w[~lit], rng, (-0.3, 0.3), (10, 35), (2, 6)):
                rb[tone(stroke)].poly(stroke)
    # Each lit rear tyre is four ribs, thin and apart while the marks fade in, then fused into
    # one continuous band that brightens towards the end. Every step starts a little later on
    # some ribs than others (the outer ribs join the band last), so the band frays in and
    # its steps have no square ends.
    starts = [len(ago) - round(a / DS) for a in LIT]
    unit = DS * SCALE  # canvas units per sample, near enough
    lines = (P(), P(), P())
    for w in canvas[:2]:
        nrm = normals(w)
        for rib in (-0.375, -0.125, 0.125, 0.375):
            line = w + (rib * rear_w)[:, None] * nrm
            # units late at each step: the fray, the band (outer ribs last), full strength
            late = (
                rng.uniform(0, 40),
                36 * (abs(rib) > 0.25) + rng.uniform(0, 15),
                rng.uniform(0, 32),
            )
            cut = [a + round(d / unit) for a, d in zip(starts, late, strict=True)] + [len(ago)]
            for k, d in enumerate(lines):
                # each step runs a sample into the next, so no seam shows at the joint
                i0, i1 = cut[k], min(cut[k + 1] + 1, len(ago))
                d.poly(line[[*range(i0, i1 - 1, 2), i1 - 1]])
    s.stroke(lines[0], ACCENT_5, 1.0, cap="butt")
    s.stroke(lines[1], ACCENT_2, 2.0, cap="butt")
    s.stroke(lines[2], ACCENT, 2.0, cap="butt")

    # each cone from above: its square base, the body's foot and the tip, in the scene's frame
    base = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]]) * CONE / 2
    cones, tips = P(), P()
    for cx in (-GAP / 2, GAP / 2):
        c = Vec(*(np.array([cx, 0.0]) @ m.T)) + at
        cones.poly((base + (cx, 0.0)) @ m.T + np.asarray(at), closed=True)
        cones.circle(c, CONE * SCALE * 0.36)
        tips.circle(c, 1.6)
    s.stroke(cones, UI_HI, 1.2, join="miter")
    s.fill(tips, UI_HI)
