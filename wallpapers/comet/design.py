"""A comet's dust tail as syndyne lines integrated along a parabolic orbit, beside a straight ion tail."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_3,
    ACCENT_5,
    ACCENT_6,
    ACCENT_8,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    design,
    mix,
    ramp,
)

type Arr = NDArray[np.float64]

LIFT = 4  # degrees from the ion tail to the fan's axis, towards the dust
TRIM = 30  # dust emerges from this circle of the coma
Q = 0.5  # perihelion distance (GM = 1 units)
T_SPAN, STEPS, EVERY = 0.85, 500, 3  # dust leaves every step; every third release is drawn
SCALE, SQUASH = 1800.0, 0.3  # SQUASH foreshortens the orbit plane across the anti-sun axis
BETA_MIN = 0.05  # low enough that the fan's lower edge stays a smooth arc
# Dust tones from the nucleus outward: fine steps into near-sky, so line ends dissolve.
TONES = tuple(mix(UI_ALT, mix(BG, BG_ALT, 0.3), (i / 11) ** 1.4) for i in range(12))
COMA = ramp(ACCENT_8, ACCENT_5, 10)  # outermost disc first
STARS = ((UI, 1.1, 100), (UI_ALT, 1.3, 40), (UI_HI, 1.7, 10))  # tone, radius, per 1920 x 1080


def simulate(betas: Arr) -> tuple[Arr, Arr]:
    """Leapfrog a parabolic comet from perihelion for T_SPAN while dust leaves the nucleus every
    step, its pull to the sun weakened by 1 - beta. Returns the dust released every EVERY steps
    (counted back from the last) at the end, shaped (len(betas), releases, 2) oldest first, and
    the comet's final position."""
    dt = T_SPAN / STEPS

    def step(r: Arr, v: Arr, k: Arr) -> tuple[Arr, Arr]:
        def acc(r: Arr) -> Arr:
            return -k[..., None] * r / np.linalg.norm(r, axis=-1, keepdims=True) ** 3

        v = v + acc(r) * dt / 2
        r = r + v * dt
        return r, v + acc(r) * dt / 2

    c, v = np.array([Q, 0.0]), np.array([0.0, math.sqrt(2 / Q)])  # parabolic orbit at perihelion
    releases = range((STEPS - 1) % EVERY, STEPS, EVERY)
    k = np.repeat((1 - betas)[:, None], len(releases), 1)  # radiation pressure weakens the pull
    pr, pv = np.zeros((len(betas), len(releases), 2)), np.zeros((len(betas), len(releases), 2))
    n = 0  # grains released so far
    for i in range(STEPS):
        if i in releases:
            pr[:, n], pv[:, n] = c, v
            n += 1
        pr[:, :n], pv[:, :n] = step(pr[:, :n], pv[:, :n], k[:, :n])
        c, v = step(c, v, np.ones(()))
    return pr, c


@design(aspects="any")
def draw(s: Canvas) -> None:
    # The nucleus sits high on the right thirds line. On a landscape screen the ion tail runs
    # left and the dust lags below it, off the bottom edge; on a portrait one the comet is turned
    # a quarter and mirrored, so the tail falls and the dust lags off the left edge.
    turn = 1 if s.landscape else -1
    nuc = s.pick(landscape=(37 / 48, 5 / 18), portrait=(0.74, 0.18))
    ion = s.pick(landscape=(5 / 64, 0.55618), portrait=(0.33, 0.9))
    goal = (ion - nuc).unit().rotate(deg=-LIFT * turn)  # the fan's axis
    down = goal.rotate(deg=-90 * turn)  # the side the dust lags to

    pr, c = simulate(np.geomspace(BETA_MIN, 2.5, 110))
    # nucleus frame: a along the anti-sun axis, b across it
    u = c / np.linalg.norm(c)
    a, b = (pr - c) @ u, (pr - c) @ np.array([-u[1], u[0]])
    b = b * np.sign(b.mean())
    xy = nuc + (a[..., None] * goal + SQUASH * b[..., None] * down) * SCALE

    per = s.w * s.h / (1920 * 1080)  # star density stays that of the 16:9 sky
    stars = s.np_rng(4).uniform((0, 0), (s.w, s.h), (round(150 * per), 2))
    start = 0
    for tone, r, n in STARS:
        s.fill(P().dots(stars[start : start + round(n * per)], r), tone)
        start += round(n * per)

    # coma: close-stepped discs nudged down-tail; only the outermost sits under the dust
    coma = [(nuc + goal * r * 0.3, r) for r in np.linspace(34, 9, len(COMA))]
    s.fill(P().circle(*coma[0]), COMA[0])
    head = nuc + goal * TRIM * 0.3

    box = s.inset(-20)
    lo, hi = (box.x, box.y), (box.x1, box.y1)
    last = len(TONES) - 1
    # faintest first, so brighter line starts overlap the fainter ends
    with s.buckets(
        TONES[::-1], "stroke", stroke_width=1, stroke_linecap="round", stroke_linejoin="round"
    ) as dust:
        for line in xy[:, ::-1]:  # nucleus first
            line = line[np.argmax(np.linalg.norm(line - head, axis=1) > TRIM) :]
            n = len(line)
            for q in range(len(TONES)):
                # share the boundary sample, so no seam shows where tones change
                seg = line[q * n // len(TONES) : (q + 1) * n // len(TONES) + 1]
                seg = seg[((seg > lo) & (seg < hi)).all(axis=1)]
                if len(seg) > 1:
                    dust[last - q].poly(seg)

    fade = s.linear_gradient([(0, ACCENT_1), (0.7, ACCENT_3), (1, ACCENT_6)], nuc, ion)
    s.stroke(P().M(nuc).L(ion), fade, 1.5)

    for (o, r), tone in zip(coma[1:], COMA[1:], strict=True):
        s.fill(P().circle(o, r), tone)
    s.fill(P().circle(nuc, 6), ACCENT)
