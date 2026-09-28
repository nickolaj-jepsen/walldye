"""Norris's 2024 Monza pole lap as a spectrogram of engine harmonics in hatching, one gear lit."""

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, ACCENT_2, BG, BG_ALT, UI, Canvas, P, Params, Path, design, knob, mix

LAP = 79.327  # s, line to line
LIT = 60.0  # s, inside the seventh-gear pull from Ascari towards the Parabolica
# (from, to) s with the throttle under half open, from FastF1's throttle channel
LIFTS = ((8.25, 13.85), (27.5, 31.35), (35.75, 37.3), (40.8, 42.35), (54.0, 55.95), (69.35, 71.3))
BASE, FMAX = 40, 8200  # units from the edge to 0 Hz; Hz at the far edge of the short side
HARMONICS = 12
EDGE = 40  # units every upshift keeps from the screen's short edges
LIT_AT = (0.63, 0.70)  # where the lit gear's middle may fall along the time axis
CAP = 0.4  # longest dash off the throttle, as a fraction of the gap between orders
HATCH = 3  # units
# per harmonic: TONES step, lit paint
STEP = (0,) * 7 + (1,) * 5
LIT_PAINT = (ACCENT_2,) * 8 + (ACCENT,) * 4
TONES = (UI, mix(UI, BG_ALT, 0.5), BG_ALT, mix(BG_ALT, BG, 0.4))  # off the throttle: two down


class Orders(Params):
    pitch: float = knob(default=6, lo=4, hi=12, unit="units", doc="frame spacing")
    speed: float = knob(default=42, lo=24, hi=120, unit="units/s", doc="time scale")
    band: float = knob(default=22, lo=4, hi=40, unit="Hz", doc="ridge half-width")


@design(aspects="any")
def draw(s: Canvas[Orders]) -> None:
    p = s.params
    lap: dict[str, list[float]] = s.data("lap.json")
    bt, brpm = np.array(lap["t"]), np.array(lap["rpm"])
    shifts = bt[1:][np.diff(bt) == 0]  # breakpoints repeat at each upshift
    span = s.w if s.landscape else s.h  # time runs along the long side
    ku = (1080 - BASE) / FMAX  # units per Hz
    # the lit gear sits near `lead` along the time axis; wide screens stretch time to stay in the
    # lap, and portrait ones run faster so the Lesmo and Roggia ladders don't crowd the top
    lead = 0.64 if s.landscape else 0.65
    fit = span / min(LIT / lead, (LAP - LIT) / (1 - lead))  # slowest speed that stays in the lap
    base = max(p.speed * (1 if s.landscape else 1.45), fit)
    # slide the window up to 1.5 s, and failing that change the speed in half steps by up to a
    # tenth (slower first), the least that keeps every upshift clear of both edges and the lit
    # gear's middle within LIT_AT
    i = np.searchsorted(shifts, LIT)
    lit_mid = (shifts[i - 1] + shifts[i]) / 2
    m = int(0.1 * base / 0.5)
    ups_c = base + 0.5 * np.arange(-m, m + 1)[:, None]
    dt = np.round(np.arange(-150, 151) / 100, 2)[None, :]
    t0_c = LIT - lead * span / ups_c + dt
    x = (shifts[:, None, None] - t0_c) * ups_c
    ok = (np.minimum(abs(x), abs(x - span)) >= EDGE).all(axis=0)
    ok &= (t0_c >= 0) & (t0_c + span / ups_c <= LAP + 1e-9)
    frac = (lit_mid - t0_c) * ups_c / span
    ok &= (frac >= LIT_AT[0]) & (frac <= LIT_AT[1])
    cost = np.where(ok, abs(ups_c - base) * 20 + (ups_c > base) * 5 + abs(dt), np.inf)
    j = np.unravel_index(np.argmin(cost), cost.shape)
    if ok[j]:
        ups, t0 = float(ups_c[j[0], 0]), float(t0_c[j])
    else:
        ups, t0 = base, LIT - lead * span / base

    def at(u: float, f: float) -> tuple[float, float]:
        return (u, s.h - BASE - f * ku) if s.landscape else (BASE + f * ku, u)

    # sample every half unit, then take each frame's frequency range in the gear that fills
    # most of it, so every upshift is one clean drop
    u = np.arange(0, span, 0.5) + 0.25
    t = t0 + u / ups
    fire = np.interp(t, bt, brpm) / 20  # Hz: a four-stroke V6 fires three times a revolution
    gear = np.searchsorted(shifts, t, side="right")  # np.interp takes the later value at a shift
    frame = (u // p.pitch).astype(int)
    starts = np.flatnonzero(np.r_[True, np.diff(frame * 64 + gear) != 0])
    n = np.diff(np.r_[starts, len(u)])
    same = frame[starts][1:] == frame[starts][:-1]
    keep = np.ones(len(starts), bool)
    keep[:-1] &= ~(same & (n[:-1] < n[1:]))
    keep[1:] &= ~(same & (n[1:] <= n[:-1]))
    lo = np.minimum.reduceat(fire, starts)[keep]
    hi = np.maximum.reduceat(fire, starts)[keep]
    mid = (np.add.reduceat(fire, starts) / n)[keep]
    fu = frame[starts][keep] * p.pitch + p.pitch // 2 + 0.5  # odd hatch widths land on whole pixels
    ft = t0 + fu / ups
    lit = gear[starts][keep] == np.searchsorted(shifts, LIT, side="right")
    lift = np.zeros(len(ft), bool)
    for a, b in LIFTS:
        lift |= (ft > a) & (ft < b)
    # a braking blip can sweep further than the gap between orders in one frame; off the
    # throttle a dash spans at most CAP of that gap, the same in Hz for every order
    cap = np.where(lift, CAP / 2 * mid, np.inf)

    def ridges(k: int, sel: NDArray[np.bool_]) -> Path:
        d = P()
        for x, a, b, m, c in zip(fu[sel], lo[sel], hi[sel], mid[sel], cap[sel], strict=True):
            f0, f1 = max(k * a - p.band, k * m - c), min(k * b + p.band, k * m + c)
            d.M(*at(x, f0)).L(*at(x, f1))
        return d

    # the lit pull goes last, so no unlit dash from the next gear lands on it
    for k in range(1, HARMONICS + 1):
        s.stroke(ridges(k, ~lit & ~lift), TONES[STEP[k - 1]], HATCH)
        s.stroke(ridges(k, ~lit & lift), TONES[STEP[k - 1] + 2], HATCH)
    for k in range(1, HARMONICS + 1):
        s.stroke(ridges(k, lit), LIT_PAINT[k - 1], HATCH)
