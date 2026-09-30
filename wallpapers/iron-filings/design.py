"""Iron filings over a magnet: short strokes turned along the field of point poles, gathered on the level sets of its stream function."""

import math
from typing import Literal

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_3,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Params,
    Rect,
    design,
    knob,
)
from walldye.geom import Affine, poisson_disk


class Sheet(Params):
    magnets: Literal["bar", "repelling", "horseshoe"] = knob(
        default="bar", doc="what lies under the sheet"
    )


VARIANTS = {"repelling": Sheet(magnets="repelling"), "horseshoe": Sheet(magnets="horseshoe")}

TILT = -12  # deg; the magnet's axis on a landscape screen, turned a quarter on a portrait one
LEN, THICK = 190, 44  # bar magnet
POLE = 0.42 * LEN  # monopoles sit a little inside the bar's ends
GAP = 100  # between the like poles of the repelling pair
G, W, ARM = 58, 36, 120  # horseshoe: arm centers at +-G, arm width, straight length before the bend
RA, RB = 640, 430  # halo semi-axes along / across the magnet
LINES = 4.5  # field-line chains per unit of the stream function
TONES = (BG_ALT, UI, UI_ALT, UI_HI)
STEPS = (0.25, 0.5, 0.9)  # field strength where the filings step up a tone
# bars as (center, +1 when north is at +x); the horseshoe has none
BARS = {
    "bar": ((0.0, 1),),
    "repelling": ((-(LEN + GAP) / 2, 1), ((LEN + GAP) / 2, -1)),
    "horseshoe": (),
}


def draw_bars(s: Canvas, bars: tuple[tuple[float, int], ...]) -> None:
    """Bar magnets with rounded corners on the local x axis, each split into a north and a
    south half."""
    north, south = P(), P()
    with s.clip() as outline:
        for cx, d in bars:
            outline.add(P().rrect(cx - LEN / 2, -THICK / 2, LEN, THICK, 6))
            north.rect(min(cx, cx + d * LEN / 2), -THICK / 2, LEN / 2, THICK)
            south.rect(min(cx, cx - d * LEN / 2), -THICK / 2, LEN / 2, THICK)
    with s.group(clip_path=outline.ref):
        s.fill(north, ACCENT)
        s.fill(south, ACCENT_3)


def draw_horseshoe(s: Canvas) -> None:
    """A horseshoe magnet with its tips on the local x axis and its bend at +y, split into a
    north and a south half at the bottom of the bend."""
    north, south = P(), P()
    for side, path in ((1, north), (-1, south)):
        path.rect(side * G - W / 2, 0, W, ARM)
        path.arc_band((0, ARM), G - W / 2, G + W / 2, deg=(90 - 90 * side, 90))
    s.fill(north, ACCENT)
    s.fill(south, ACCENT_3)


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Sheet]) -> None:
    kind = s.params.magnets
    # Local frame: x along the pole axis (north at +x), y across it, origin between the poles.
    horseshoe = kind == "horseshoe"
    tilt = TILT if s.landscape else TILT - 90
    frame = Affine.frame(s.pick(landscape=(0.406, 0.5), portrait=(0.5, 0.46)), deg=tilt)
    # the horseshoe's poles sit just inside its tips, as the bars' do
    poles = [(G, 15.0, 1), (-G, 15.0, -1)] if horseshoe else []
    for cx, d in BARS[kind]:
        poles += [(cx + d * POLE, 0.0, 1), (cx - d * POLE, 0.0, -1)]

    r = s.rng(11)
    pts = poisson_disk(Rect(-RA, -RB, 2 * RA, 2 * RB), 4.6, r)
    x, y = pts[:, 0], pts[:, 1]
    oval = np.hypot(x / RA, y / RB)
    # tight margin at the pole faces so filings pile onto the tips, wider along the flanks
    body = np.zeros(len(x), dtype=bool)
    for cx, _ in BARS[kind]:
        body |= (np.abs(x - cx) < LEN / 2 + 3.5) & (np.abs(y) < THICK / 2 + 9)
    if horseshoe:
        body |= (np.abs(np.abs(x) - G) < W / 2 + 9) & (y > -3.5) & (y < ARM)
        body |= (y >= ARM) & (np.abs(np.hypot(x, y - ARM) - G) < W / 2 + 9)
    keep = ~body & (oval < 1)
    x, y, oval = x[keep], y[keep], oval[keep]

    bx, by, psi = np.zeros_like(x), np.zeros_like(x), np.zeros_like(x)
    for px, py, q in poles:
        ex, ey = x - px, y - py
        d = np.hypot(ex, ey)
        bx += q * ex / d**3
        by += q * ey / d**3
        # Stokes stream function of point poles on one axis: its level sets are the field lines
        psi += q * ex / d
    # psi grows ~angle^2 off the axis; the root spreads the axial chains so they don't bundle
    u = np.sign(psi) * np.abs(psi) ** 0.6
    band = (0.5 + 0.5 * np.cos(2 * math.pi * LINES * u)) ** 6
    lm = np.log(np.hypot(bx, by))
    lo, hi = np.percentile(lm, 2), np.percentile(lm, 99.7)
    t = np.clip((lm - lo) / (hi - lo), 0, 1)
    fade = 1 - np.clip((oval - 0.35) / 0.65, 0, 1) ** 2
    # near the tips the field is strong enough that filings bristle regardless of the chains
    chain = 0.08 + 0.92 * np.maximum(band, np.clip((t - 0.8) / 0.15, 0, 1))
    odds = (0.4 + 0.6 * t) * fade * chain
    heading = np.arctan2(by, bx)
    tone = np.digitize(t, STEPS, right=True)

    with s.group(transform=frame):
        with s.buckets(TONES, "stroke", stroke_width=1.4, stroke_linecap="round") as grains:
            for px, py, tt, p, a, k in zip(x, y, t, odds, heading, tone, strict=True):
                if r.random() > p:
                    continue
                a += r.gauss(0, 0.1)
                half = 2.6 + 4.2 * tt**1.2 + r.uniform(-0.6, 0.6)
                ex, ey = half * math.cos(a), half * math.sin(a)
                grains[k].M(px - ex, py - ey).L(px + ex, py + ey)

        if horseshoe:
            draw_horseshoe(s)
        else:
            draw_bars(s, BARS[kind])
