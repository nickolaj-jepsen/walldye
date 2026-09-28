"""A ray traced through a prism with Snell's law fans out as six stepped bands over a faint optics diagram."""

import math

from walldye import (
    ACCENT,
    ACCENT_6,
    BG,
    BG_ALT,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Path,
    Point,
    Vec,
    design,
    mix,
    polar,
    ramp,
)

SIDE = 400  # prism side
ENTRY_T = 0.5  # entry point along the left face, bottom -> apex
RAY_DEG = -11.6  # the incoming ray climbs this steeply from the left
N_LO, N_HI = 1.22, 1.46  # low index and exaggerated dispersion keep the fan shallow
RAYS = 7  # rays at evenly spaced exit angles bound RAYS - 1 bands
FAN_ROOM = 1050  # landscape: prism centre to the right edge, so the fan keeps one length
RAY_CLEAR = 130  # the incoming ray meets the left edge at least this far above the bottom
NORMAL = 60  # drawn face normals run this far either side of the face
BANDS = ramp(ACCENT, ACCENT_6, RAYS - 1)  # least refracted first, most visible


def refract(d: Vec, n: Vec, eta: float) -> Vec:
    """Snell's law: unit direction `d` through a surface whose unit normal `n` faces against it.

    `eta` is n1 / n2. Raises ValueError on total internal reflection."""
    c = -d.dot(n)
    return d * eta + n * (eta * c - math.sqrt(1 - eta * eta * (1 - c * c)))


def hit(p: Vec, d: Vec, a: Vec, b: Vec) -> Vec:
    """Where the ray p + t d crosses the line through a and b."""
    m = (b - a).perp()
    return p + d * ((a - p).dot(m) / d.dot(m))


def outward(a: Vec, b: Vec, inside: Point) -> Vec:
    """Unit normal of segment a-b pointing away from `inside`."""
    n = (b - a).perp().unit()
    return n if (a - inside).dot(n) > 0 else -n


def angle_arc(d: Path, c: Point, u: Vec, v: Vec, r: float) -> None:
    """Append the short arc of radius r about c from direction u round to direction v."""
    a0 = math.atan2(u.y, u.x)
    turn = (math.atan2(v.y, v.x) - a0 + math.pi) % math.tau - math.pi
    d.arc(c, r, rad=(a0, a0 + turn))


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Trace about a prism centred on the origin, then place the whole diagram.
    h = SIDE * math.sqrt(3) / 2
    apex, bl, br = Vec(0, -2 * h / 3), Vec(-SIDE / 2, h / 3), Vec(SIDE / 2, h / 3)
    entry = bl + (apex - bl) * ENTRY_T
    d_in = polar((0, 0), 1, deg=RAY_DEG)
    n_left, n_right = outward(bl, apex, (0, 0)), outward(apex, br, (0, 0))

    def trace(n: float) -> tuple[Vec, Vec]:
        inside = refract(d_in, n_left, 1 / n)
        return hit(entry, inside, apex, br), refract(inside, -n_right, n)

    def exit_angle(n: float) -> float:
        out = trace(n)[1]
        return math.atan2(out.y, out.x)

    # bisect for the indices whose exit angles are evenly spaced, so the bands open evenly
    a0, a1 = exit_angle(N_LO), exit_angle(N_HI)
    rays: list[tuple[Vec, Vec]] = []
    for k in range(RAYS):
        target, lo, hi = a0 + (a1 - a0) * k / (RAYS - 1), N_LO, N_HI
        for _ in range(40):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if exit_angle(mid) < target else (lo, mid)
        rays.append(trace(lo))

    # Landscape: anchored to the right edge, lifted where a wide screen would start the incoming
    # ray near the bottom corner. Portrait: left of centre, above the middle.
    c = Vec(s.w - FAN_ROOM, s.h / 2) if s.landscape else s.frac(0.42, 0.42)
    reach = (c.x + entry.x) / d_in.x  # back along the incoming ray to the left edge
    ray_y = c.y + entry.y - reach * d_in.y
    c = c - (0, max(0.0, ray_y - (s.h - RAY_CLEAR)))

    apex, bl, br, entry = apex + c, bl + c, br + c, entry + c
    exits = [e + c for e, _ in rays]
    outs = [o for _, o in rays]
    far = [e + o * ((s.w + 40 - e.x) / o.x) for e, o in zip(exits, outs, strict=True)]
    prism = P().poly([apex, br, bl], closed=True)

    s.fill(prism, mix(BG, BG_ALT, 0.5))

    # optics-diagram layer: face normals at entry and exit, angle arcs to the rays, the apex angle
    mid_exit = exits[RAYS // 2]
    normals, arcs = P(), P()
    for p, n in ((entry, n_left), (mid_exit, n_right)):
        normals.M(p - n * NORMAL).L(p + n * NORMAL)
    angle_arc(arcs, entry, n_left, -d_in, 52)
    angle_arc(arcs, entry, -n_left, (mid_exit - entry).unit(), 40)
    angle_arc(arcs, mid_exit, n_right, outs[RAYS // 2], 52)
    angle_arc(arcs, apex, (bl - apex).unit(), (br - apex).unit(), 44)
    s.stroke(normals, UI, 1, dash=(12, 4, 2, 4))
    s.stroke(arcs, UI_ALT, 1.3)

    s.fill(P().poly([entry, exits[0], exits[-1]], closed=True), UI)
    for k, band in enumerate(BANDS):
        quad = P().poly([exits[k], exits[k + 1], far[k + 1], far[k]], closed=True)
        # a hairline of the band's own paint closes the anti-aliasing seam with its neighbour
        s.path(quad, fill=band, stroke=band, stroke_width=0.6, stroke_linejoin="round")
    s.stroke(P().M(entry - d_in * (reach + 4)).L(entry), MUTED, 3)
    s.stroke(prism, UI_HI, 3, join="round")
