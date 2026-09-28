"""An accretion disk around an event horizon in line art: each ring's far half is bent over the shadow by a point lens, and its approaching side is more heavily lit."""

import math

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import LineString, Polygon, box

from walldye import (
    ACCENT,
    ACCENT_4,
    ACCENT_HI,
    BG,
    BG_ALT,
    BLACK,
    UI_ALT,
    Buckets,
    Canvas,
    P,
    Params,
    Style,
    Vec,
    by_regime,
    clamp,
    design,
    knob,
    ladder,
    mix,
    smoothstep,
)


class Horizon(Params):
    elevation: float = knob(
        default=15, lo=5, hi=75, unit="deg", doc="viewing angle above the disk plane"
    )


VARIANTS = {"edge-on": Horizon(elevation=5), "above": Horizon(elevation=70)}

type Pts = NDArray[np.float64]

RS, R0, R1, RINGS = 150, 175, 520, 26  # shadow radius; inner and outer disk ring radii
REF = math.radians(15)  # the elevation LENS and the rim were tuned at
LENS = 26 / math.cos(REF)  # Einstein radius^2 per unit of depth behind the hole
SAMPLES = 360  # per half turn of the outer ring; fewer on the inner ones
MARGIN = 90
TONES = ladder((BG, ACCENT_4, ACCENT), 14)[2:]
FADES = 4  # steps from the accent ladder towards UI_ALT on the outer rings
# PAINTS[i * FADES + g]: accent rung i pulled g steps towards its BG_ALT..UI_ALT match
PAINTS = [
    mix(TONES[i], mix(BG_ALT, UI_ALT, i / (len(TONES) - 1)), g / (FADES - 1))
    for i in range(len(TONES))
    for g in range(FADES)
]
LINE: Style = {"stroke_width": 1.2, "stroke_linejoin": "round"}
# the shadow: the deepest void on dark themes, a faintly shaded disc on paper
SHADOW = by_regime(BLACK, BG_ALT)


def tone(phi: float, r: float) -> int:
    """PAINTS index for ring radius `r` at angle `phi`: brighter on the approaching (left) side
    and towards the inner edge; the outer rings fade towards UI_ALT."""
    beam = (1 + math.cos(phi)) / 2
    heat = 1 - (r - R0) / (R1 - R0)
    v = 0.08 + 0.72 * beam**1.6 + 0.2 * heat
    g = smoothstep(380, 500, r) * (1 - 0.7 * beam**2)
    return min(len(TONES) - 1, int(v * len(TONES))) * FADES + min(FADES - 1, int(g * FADES))


def far(r: float, phi: Pts, tilt: float, lens: float) -> Pts:
    """Far half of ring r through a point lens (primary image), kept off the shadow by a soft
    floor, in hole-centred units."""
    floor = RS + 5 + (r - R0) * 0.15
    x, y = -r * np.cos(phi), -r * tilt * np.sin(phi)
    b = np.hypot(x, y)
    th = b / 2 + np.sqrt(b * b / 4 + lens * r * np.clip(np.sin(phi), 0, 1) ** 3)

    def soft(v: Pts | float) -> Pts:
        return (np.asarray(v) ** 6 + floor**6) ** (1 / 6)

    # the floor lifts the ends too; pull them back so the ring still meets its front half at +-r
    th = soft(th) - (soft(r) - r) * np.cos(phi) ** 2
    return np.column_stack([x / b * th, y / b * th])


def near(r: float, phi: Pts, tilt: float) -> Pts:
    """Near half of ring r, unlensed, in hole-centred units."""
    return np.column_stack([-r * np.cos(phi), r * tilt * np.sin(phi)])


def sweep(a0: float, a1: float, r: float) -> Pts:
    """Angles from a0 to a1, as many as SAMPLES per half turn scaled by r / R1."""
    n = max(8, math.ceil(SAMPLES * abs(a1 - a0) / math.pi * r / R1))
    return np.linspace(a0, a1, n + 1)


def trace(b: Buckets, pts: Pts, phi: Pts, r: float) -> None:
    """Stroke the polyline `pts`, sampled at angles `phi` on ring radius `r`, into the buckets:
    one subpath per run of equal tone, each segment toned at its middle angle."""
    tones = [tone(a, r) for a in ((phi[:-1] + phi[1:]) / 2).tolist()]
    start = 0
    for i in range(1, len(tones) + 1):
        if i == len(tones) or tones[i] != tones[start]:
            # a 0.1-unit tolerance drops points on the flat stretches, invisibly
            run = LineString(pts[start : i + 1]).simplify(0.1)
            b[tones[start]].poly(np.asarray(run.coords))
            start = i


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Horizon]) -> None:
    e = math.radians(s.params.elevation)
    # the far half recedes less, and so bends less, as the view turns face-on
    tilt, lens = math.sin(e), LENS * math.cos(e)
    radii: list[float] = (R0 + (R1 - R0) * np.linspace(0, 1, RINGS) ** 1.3).tolist()
    top = min(float(far(r, np.array([math.pi / 2]), tilt, lens)[0, 1]) for r in radii)
    bottom = max(R1 * tilt, RS + 25)
    # landscape: right of centre, the left free for windows; portrait: the upper middle
    c = s.pick(landscape=(1240 / 1920, 556 / 1080), portrait=(0.5, 0.42))
    k = min(1.0, (s.w - 2 * MARGIN) / (2 * R1), (s.h - 2 * MARGIN) / (bottom - top))
    c = Vec(
        clamp(c.x, MARGIN + k * R1, s.w - MARGIN - k * R1),
        clamp(c.y, MARGIN - k * top, s.h - MARGIN - k * bottom),
    )

    def place(pts: Pts) -> Pts:
        return np.asarray(c) + k * pts

    s.fill(P().circle(c, k * RS), SHADOW)
    # the near half of the disk passes in front: hide what lies behind its band, grown over
    # stroke edges but never above the hole's centre line, where the far half shows
    half = np.linspace(0, math.pi, 181)
    band = Polygon(np.vstack([place(near(R1, half, tilt)), place(near(R0, half[::-1], tilt))]))
    band = band.buffer(1.5, join_style="mitre").intersection(box(0, c.y, s.w, s.h))
    with s.clip() as behind:
        behind.add(P().shape(box(0, 0, s.w, s.h).difference(band)))
    with s.group(clip_path=behind.ref):
        with s.buckets(PAINTS, "stroke", **LINE) as b:
            for r in radii:
                phi = sweep(0, math.pi, r)
                trace(b, place(far(r, phi, tilt, lens)), phi, r)
        s.stroke(P().circle(c, k * (RS + 1)), ACCENT_HI, 2)
        # the disk's underside, lensed into a thin rim hugging the bottom of the photon ring; its
        # ends tuck behind the near band, which thins towards edge-on and, seen from high
        # above, covers the whole rim
        tuck = 0.35 * tilt / math.sin(REF)
        if tuck < 1.2:
            with s.buckets(PAINTS, "stroke", **LINE) as b:
                for j in range(6):
                    rho = RS + 6 + j * 3.2
                    phi = sweep(tuck, math.pi - tuck, rho)
                    rim = np.column_stack([-rho * np.cos(phi), rho * np.sin(phi)])
                    trace(b, place(rim), phi, R0 + j * 50)
    with s.buckets(PAINTS, "stroke", **LINE) as b:
        for r in radii:
            phi = sweep(0, math.pi, r)
            trace(b, place(near(r, phi, tilt)), phi, r)
