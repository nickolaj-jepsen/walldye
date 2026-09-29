"""A helicorder drum record: ruled seismograph traces broken at each minute, one catching an earthquake whose coda runs on into the next line."""

import numpy as np
import shapely
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d

from walldye import ACCENT, ACCENT_2, ACCENT_4, BG_ALT, UI, Canvas, NpRng, P, Path, design
from walldye.field import runs

type Arr = NDArray[np.float64]

MX, MY, PITCH = 80, 120, 840 / 27  # side margin, top and bottom margin, line spacing
TICK, GAP = 64, 3  # minute marks: a GAP px break in the quiet traces every TICK px
LONGEST = 1100  # px of the event line after the onset, at most; 820 on 16:9
TAU = 300  # slow decay of the S-wave coda, px
FADE, CODA = 150, 420  # ink steps down over the last FADE px; the next line stays lit for CODA px
TOL = 0.2  # px a simplified trace may stray from its samples; halves the file


def noise(x: Arr, rng: NpRng) -> Arr:
    """Background microseism for samples `x`: smoothed random jitter plus three slow sines."""
    raw = gaussian_filter1d(rng.normal(0, 1, len(x)), 1.6)
    phase = rng.uniform(0, 6.3, 3)
    slow = sum(np.sin(x / p + ph) for p, ph in zip((97, 41, 23), phase, strict=True)) / 3
    return 1.3 * raw / raw.std() + 0.6 * slow


def quake(t: Arr, rng: NpRng) -> Arr:
    """Ground motion `t` px after the onset: a small P wave, and 170 px later the S-wave packet."""
    p = np.where(t > 0, 1 - np.exp(-t / 30), 0) * np.exp(-np.clip(t, 0, None) / 250) * 14
    ts = t - 170
    tc = np.clip(ts, 0, None)
    sw = (
        np.where(ts > 0, np.clip(ts / 40, 0, 1) ** 2, 0)
        * (0.6 * np.exp(-tc / 110) + 0.4 * np.exp(-tc / TAU))
        * 90
    )
    # ~5px carrier period so the packet reads as a hatched envelope, not a scribble.
    wob = gaussian_filter1d(rng.normal(0, 1, len(t)), 6)
    carrier = np.sin(t * 1.25 + np.cumsum(wob) * 0.02)
    jitter = np.abs(gaussian_filter1d(rng.normal(0, 1, len(t)), 3))
    return (p + sw) * carrier * np.clip(0.45 + jitter / jitter.mean() * 0.45, 0, 1.4)


def trace(d: Path, xs: Arr, ys: Arr, *, ticks: bool = True) -> None:
    """Adds the polyline through `xs`, `ys` to `d`, with a break at each minute mark if `ticks`."""
    keep = ((xs - MX) % TICK >= GAP) | (not ticks)
    for a, b in runs(keep):
        if b - a > 1:
            line = shapely.LineString(np.column_stack([xs[a:b], ys[a:b]]))
            d.poly(np.asarray(line.simplify(TOL, preserve_topology=False).coords))


@design(aspects="any")
def draw(s: Canvas) -> None:
    rng = s.np_rng(11)
    x0, x1 = MX, s.w - MX
    rows = round((s.h - 2 * MY) / PITCH) + 1
    gap = (s.h - 2 * MY) / (rows - 1)
    xs = np.arange(x0, x1 + 1, 2.0)
    fine = np.arange(x0, x1 + 1, 1.0)
    # the onset sits on the event line's right half (low on a portrait screen), but never so
    # far left on an ultrawide that the S-wave has died out long before the line ends
    ev = s.pick(landscape=(0.53125, 0.572), portrait=(0.4, 0.58))
    event = round((ev.y - MY) / gap)
    onset = max(ev.x, x1 - LONGEST)

    loud, tail, coda = P(), P(), P()
    with s.buckets((UI, BG_ALT), "stroke", stroke_width=1.4, stroke_linejoin="round") as gray:
        for i in range(rows):
            y, quiet = MY + i * gap, gray[i % 2]
            if i == event:
                ys = y + noise(fine, rng) + quake(fine - onset, rng)
                pre, end = fine < onset, fine >= x1 - FADE
                lit = (fine >= onset - 1) & (fine <= x1 - FADE)  # overlaps each neighbor by one px
                trace(quiet, fine[pre], ys[pre])
                trace(loud, fine[lit], ys[lit], ticks=False)
                trace(tail, fine[end], ys[end], ticks=False)
            elif i == event + 1:
                # the drum wraps: this line's left end follows on from the event line's right end
                ys = y + noise(fine, rng) + quake(fine - x0 + x1 - onset, rng)
                lit = fine <= x0 + CODA
                trace(coda, fine[lit], ys[lit], ticks=False)
                trace(quiet, fine[~lit], ys[~lit])
            else:
                trace(quiet, xs, y + noise(xs, rng))
    for d, paint in ((loud, ACCENT), (tail, ACCENT_2), (coda, ACCENT_4)):
        s.stroke(d, paint, 1.3, join="round")
