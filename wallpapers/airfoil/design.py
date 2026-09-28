"""Potential-flow streamlines round a cambered Joukowsky airfoil at 6°; ticks plot its suction."""

import math

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import LineString, Polygon

from walldye import ACCENT, ACCENT_4, BG, UI, UI_ALT, UI_HI, Canvas, P, Vec, design, ladder, polar
from walldye.field import iso_lines, runs, sample_field
from walldye.geom import Affine, Polyline, parts

ALPHA_DEG = 6
ALPHA = math.radians(ALPHA_DEG)
C, MX, MY = 1.0, 0.095, 0.04  # Joukowsky constant and circle offset: ~12% thick, ~2% camber
Z0 = complex(-MX, MY)
A = abs(C - Z0)
GAMMA = 4 * math.pi * A * math.sin(ALPHA + math.asin(MY / A))  # Kutta condition, U = 1
CHORD = 1000  # on a landscape screen; a narrow one shrinks the whole drawing to fit
SPAN = 1.3  # the drawing's width in chords, from the angle arc to the trailing edge
MARGIN = 80
PITCH = 56  # streamline spacing far upstream
CELL = 3  # stream-function grid
TICK_TONES = ladder((BG, ACCENT_4, ACCENT), 9)[4:]


def joukowsky(zeta: NDArray[np.complexfloating]) -> NDArray[np.complexfloating]:
    return zeta + C * C / zeta


def potential(zeta: NDArray[np.complexfloating]) -> NDArray[np.complexfloating]:
    """Complex potential about the circle for unit freestream at ALPHA."""
    q = zeta - Z0
    return (
        q * np.exp(-1j * ALPHA)
        + A * A * np.exp(1j * ALPHA) / q
        + 1j * GAMMA / (2 * math.pi) * np.log(q)
    )


@design(aspects="any")
def draw(s: Canvas) -> None:
    chord = min(CHORD, (s.w - 2 * MARGIN) / SPAN)
    f = chord / CHORD
    mid = s.pick(landscape=(1010 / 1920, 560 / 1080), portrait=(0.59, 0.44))
    # width beyond 16:9 goes mostly downstream, where the wake runs out
    mid -= (0.2 * max(0.0, s.w - s.h * 16 / 9), 0)

    # profile in the aerofoil plane; the frame pitches it so the freestream runs horizontal
    th = np.linspace(0, 2 * math.pi, 721)
    circle = Z0 + A * np.exp(1j * th)
    zp = joukowsky(circle)
    le, te = zp.real.min(), zp.real.max()
    zc = (le + te) / 2
    k = chord / (te - le)
    frame = Affine.frame(mid, deg=ALPHA_DEG, scale=k)  # local y points down, aerofoil y up
    to_aero = frame.inverse()

    def screen(z: NDArray[np.complexfloating]) -> NDArray[np.float64]:
        return frame.apply(np.column_stack([z.real - zc, -z.imag]))

    # stream function on a canvas grid; inverse Joukowsky picks the root outside the circle
    def stream(i: NDArray[np.int64], j: NDArray[np.int64]) -> NDArray[np.float64]:
        uv = to_aero.apply(np.column_stack([(-2 + CELL * i).ravel(), (-2 + CELL * j).ravel()]))
        z = (zc + uv[:, 0] - 1j * uv[:, 1]).reshape(i.shape)
        r = np.sqrt(z * z - 4 * C * C + 0j)
        z1, z2 = (z + r) / 2, (z - r) / 2
        zeta = np.where(np.abs(z1 - Z0) >= np.abs(z2 - Z0), z1, z2)
        return potential(zeta).imag * k  # canvas units far upstream

    psi = sample_field(stream, (s.w + 4) // CELL, (s.h + 4) // CELL)
    psi_wall = float(potential(np.array([Z0 + A])).imag[0]) * k
    pts = screen(zp)
    body = Polygon(pts)
    lead = frame((le - zc, 0))
    tail = frame((te - zc, 0))
    u = (tail - lead) / chord

    # suction on the upper surface: normal ticks scaled by -Cp, and their envelope
    q = circle - Z0
    dw = np.exp(-1j * ALPHA) - A * A * np.exp(1j * ALPHA) / q**2 + 1j * GAMMA / (2 * math.pi) / q
    dz = 1 - C * C / circle**2
    with np.errstate(divide="ignore", invalid="ignore"):
        cp = 1 - np.abs(dw / dz) ** 2
    # the whole suction run, aft upper surface round the nose, so the envelope closes on the
    # body at both ends; the first samples sit on the trailing-edge singularity
    start, stop = runs(cp[4:] < 0)[0]
    idx = np.arange(start + 4, stop + 4)
    along = pts[idx + 1] - pts[idx - 1]
    normal = (
        np.column_stack([-along[:, 1], along[:, 0]]) / np.hypot(along[:, 0], along[:, 1])[:, None]
    )
    env = pts[idx] + normal * (-cp[idx] * 34 * f)[:, None]
    ticks: list[tuple[int, Vec, Vec]] = []
    for j in range(0, len(idx), 6):
        p = Vec(pts[idx[j], 0], pts[idx[j], 1])
        if (p - lead).dot(u) / chord < 0.85:
            out = Vec(normal[j, 0], normal[j, 1])
            ticks.append((min(4, int(-cp[idx[j]] * 2)), p + out * 4, Vec(env[j, 0], env[j, 1])))
    ends = np.concatenate([[idx[0] - 1], idx, [idx[-1] + 1]])
    env = np.concatenate([pts[ends[:1]], env, pts[ends[-1:]]])  # land on the surface
    suction = Polygon(np.concatenate([pts[ends], env[::-1]]))
    shadow = suction.buffer(10)
    keep_out = body.buffer(6).union(shadow)

    # evenly spaced upstream like a smoke rake; the squeeze over the section comes for free.
    # Level 0 is the dividing streamline, which meets the nose at the stagnation point and
    # leaves the trailing edge.
    streams, divide = P(), P()
    lo = math.ceil((psi.min() - psi_wall) / PITCH)
    hi = math.floor((psi.max() - psi_wall) / PITCH)
    for i in range(lo, hi + 1):
        for line in iso_lines(psi, psi_wall + i * PITCH, cell=CELL, origin=(-2, -2)):
            if len(line) < 20:
                continue
            ls = LineString(line)
            crosses = ls.intersects(shadow)
            for g in parts(ls.difference(body.buffer(3) if i == 0 else keep_out)):
                # a line the envelope swallows stays gone over the section, back in the wake
                if g.length > 30 and not (crosses and lead.x < g.bounds[0] < tail.x - 10):
                    # resample evenly so the smooth path shows no grid facets
                    run = Polyline(np.asarray(g.coords))
                    n = max(4, int(run.length / 12))
                    even = run.at(np.linspace(0, run.length, n + 1))
                    (divide if i == 0 else streams).spline(even)
    s.stroke(streams, UI, 1.2)
    s.stroke(divide, UI_ALT, 1.3)

    # chord (dash-dot, carried upstream to show the angle) and camber line (dashed); both
    # break around the envelope and stop short of the crowded trailing edge
    ar = 260 * f  # angle-of-attack arc radius
    ext = ar + 34 * f
    gap = suction.buffer(6)
    refs = P()
    for g in parts(LineString([lead - u * ext, lead + u * chord * 0.93]).difference(gap)):
        refs.poly(np.asarray(g.coords))
    s.stroke(refs, UI_ALT, 1.3, dash=(26, 6, 3, 6))
    xs = np.linspace(le, le + 0.95 * (te - le), 76)
    upper, lower = th <= math.pi, th >= math.pi
    yu = np.interp(xs, zp.real[upper][::-1], zp.imag[upper][::-1])
    order = np.argsort(zp.real[lower])
    yl = np.interp(xs, zp.real[lower][order], zp.imag[lower][order])
    s.stroke(P().poly(screen(xs + 1j * (yu + yl) / 2)), UI_ALT, 1.2, dash=(8, 6))

    # station ticks every tenth of chord, and the angle of attack against the freestream
    st = P()
    across = u.perp()
    for i in range(11):
        c = lead + u * chord * i / 10
        h = 9 if i % 5 == 0 else 5
        st.M(c - across * h).L(c + across * h)
    for g in parts(LineString([lead - (ext, 0), lead - (24, 0)]).difference(gap)):
        st.poly(np.asarray(g.coords))
    s.stroke(st, UI_ALT, 1.3)
    # α is too small for arrows inside the arc: tails run past both lines, heads point back
    over = math.degrees(16 / ar)
    arc = P().arc(lead, ar, deg=(180 - over, 180 + ALPHA_DEG + over))
    heads = (
        P()
        .arrowhead(polar(lead, ar, deg=180), 9, deg=270, width=3.2)
        .arrowhead(polar(lead, ar, deg=180 + ALPHA_DEG), 9, deg=90 + ALPHA_DEG, width=3.2)
    )
    s.stroke(arc, UI_HI, 1.2)
    s.fill(heads, UI_HI)

    with s.buckets(TICK_TONES, "stroke", stroke_width=1.4) as b:
        for tone, p0, p1 in ticks:
            b[tone].M(p0).L(p1)
    s.stroke(P().poly(env), ACCENT, 1.8, join="round")

    s.stroke(P().poly(pts, closed=True), UI_HI, 2.5, join="round")
