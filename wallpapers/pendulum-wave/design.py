"""A pendulum wave as a patent drawing: bifilar pendulums in oblique projection, stopped mid S-curve, with the far crest picked out."""

import math

from shapely import Point

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_7,
    ACCENT_8,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Params,
    Path,
    Vec,
    design,
    knob,
    mix,
)
from walldye.geom import Affine


class Wave(Params):
    moment: float = knob(default=0.0741, lo=0, hi=1, doc="how far through the cycle, 0 to 1")


# halfway through, every other pendulum has made a whole number of swings: two rows
VARIANTS = {"halfway": Wave(moment=0.5)}


N, K = 18, 130  # pendulum n makes K + n swings per cycle
AMP = 0.44  # swing amplitude, radians
# The figure is drawn about its own centre, then placed and scaled by one transform.
X0, X1, BAR_Y, FOOT_Y = -540, 540, -268, 260  # posts' outer faces, bar underside, foot top
LMAX = 470  # the longest pendulum
DX, DY = 0.16, -0.56  # screen offset per unit of depth away from the viewer
BOB, SPREAD, INSET = 15, 17, 140  # bob radius, half the string V at the bar, post to string
PORTRAIT_STRETCH = 1.5  # post and string lengths on a portrait screen
GHOST = 0.00026  # fraction of the cycle between a bob and each of its two ghosts
# ghost fills, oldest first as (plain bob, crest bob), all barely above the ground
GHOSTS = (mix(BG, UI, 0.33), ACCENT_8, mix(BG, UI, 0.58), ACCENT_7)

type Box = tuple[float, float, float, float, float]


def proj(x: float, y: float, z: float) -> Vec:
    """Oblique projection; z > 0 comes towards the viewer."""
    return Vec(x - DX * z, y - DY * z)


def pivot_x(n: int) -> float:
    return X0 + INSET + (X1 - X0 - 2 * INSET) * n / (N - 1)


def swung(n: int, th: float, reach: float) -> Vec:
    """Pendulum n's bob on screen at angle th, the longest pendulum being `reach` long; the period
    goes as the square root of the length."""
    length = reach * (K / (K + n)) ** 2
    return proj(pivot_x(n), BAR_Y + length * math.cos(th), length * math.sin(th))


def bob(n: int, tau: float, reach: float) -> tuple[Vec, float]:
    """Pendulum n at cycle fraction tau: its bob on screen and its angle (negative swings away
    from the viewer)."""
    th = AMP * math.cos(2 * math.pi * (K + n) * tau)
    return swung(n, th, reach), th


def frame(s: Canvas, boxes: list[Box], wt: float) -> None:
    """Opaque oblique boxes (x0, x1, y0, y1, half-depth), none overlapping another: front, top
    and right faces, with a shade line along the lower and right edges; strokes are `wt` times
    their nominal width."""
    faces, shade = P(), P()
    for x0, x1, y0, y1, z in boxes:
        a, b, c, d = proj(x0, y0, z), proj(x1, y0, z), proj(x1, y1, z), proj(x0, y1, z)
        e, f, g = proj(x0, y0, -z), proj(x1, y0, -z), proj(x1, y1, -z)
        faces.poly([a, b, c, d], closed=True).poly([a, e, f, b], closed=True)
        faces.poly([b, f, g, c], closed=True)
        shade.poly([d, c, g, f])
    s.path(faces, fill=BG, stroke=UI_ALT, stroke_width=1.5 * wt, stroke_linejoin="round")
    s.stroke(shade, UI_ALT, 2.5 * wt, cap="round", join="round")


def leader(line: Path, heads: Path, pts: list[Vec]) -> None:
    """Patent leader: a gently curved line ending in a small arrowhead at pts[-1]."""
    line.spline(pts)
    dx, dy = pts[-1] - pts[-2]
    heads.arrowhead(pts[-1], 12.5, rad=math.atan2(dy, dx))


@design(aspects="any", variants=VARIANTS)
def draw(s: Canvas[Wave]) -> None:
    tau = s.params.moment
    # a portrait screen is narrower than the figure and much taller, so there the figure shrinks
    # to keep a clear margin (its strokes thickening to match) and its posts and strings lengthen
    at = s.pick(landscape=(7 / 12, 0.5), portrait=(0.5, 0.44))
    k, stretch = (1.0, 1.0) if s.landscape else (0.76, PORTRAIT_STRETCH)
    reach, foot, wt = LMAX * stretch, BAR_Y + (FOOT_Y - BAR_Y) * stretch, 1 / k
    place = (
        Affine.translate(at.x, at.y) @ Affine.scale(k) @ Affine.translate(0, (FOOT_Y - foot) / 2)
    )

    with s.group(transform=place):
        # the frame back to front: feet, posts, then the bar across them
        ground, hatch = P(), P()
        for x in (X0, X1 - 24):
            g = proj(x - 24, foot + 18, 70)
            ground.M(g + (-26, 0)).H(g.x + 118)
            for i in range(4):
                h = g + (i * 34, 3)
                hatch.M(h).L(h + (-14, 14))
        frame(s, [(x - 24, x + 48, foot, foot + 18, 70) for x in (X0, X1 - 24)], wt)
        frame(s, [(x, x + 24, BAR_Y - 24, foot, 12) for x in (X0, X1 - 24)], wt)
        s.stroke(hatch, BG_ALT, 1.6 * wt, cap="round")
        s.stroke(ground, UI, 1.5 * wt, cap="round")
        frame(s, [(X0 - 24, X1 + 24, BAR_Y - 24, BAR_Y, 14)], wt)

        bobs = [bob(n, tau, reach) for n in range(N)]
        # the far crest: swung furthest back, so highest on screen
        crest = [n for n, (_, th) in enumerate(bobs) if th < -0.9 * AMP]

        # the crest's arcs of travel, then the strings
        swing, strings = P(), P()
        for n in crest:
            swing.poly([swung(n, AMP * (i / 20 - 1), reach) for i in range(41)])
        s.stroke(swing, BG_ALT, 1.2 * wt)
        for n, (p, _) in enumerate(bobs):
            x = pivot_x(n)
            strings.M(x - SPREAD, BAR_Y).L(p).L(x + SPREAD, BAR_Y)
        s.stroke(strings, UI, 1.2 * wt)

        # two ghosts per bob, each a moment earlier
        with s.buckets(GHOSTS, "fill") as ghosts:
            for age in range(2):
                for n in range(N):
                    ghosts[2 * age + int(n in crest)].circle(
                        bob(n, tau - (2 - age) * GHOST, reach)[0], BOB
                    )

        # each bob with a crescent of patent shading on its lower right
        with s.buckets((UI_HI, ACCENT), "fill") as live:
            for n, (p, _) in enumerate(bobs):
                live[int(n in crest)].circle(p, BOB)
        with s.buckets((UI_ALT, ACCENT_2), "fill") as shade:
            for n, (p, _) in enumerate(bobs):
                lit = Point(p - (4, 4)).buffer(BOB, quad_segs=16)
                shade[int(n in crest)].shape(Point(p).buffer(BOB, quad_segs=16).difference(lit))

        # leaders to the middle crest bob and to the bar, numerals left off
        line, heads = P(), P()
        if crest:
            t = bobs[crest[len(crest) // 2]][0]
            leader(line, heads, [t + (150, -150), t + (70, -100), t + (20, -22)])
        b = proj(X0 + 200, BAR_Y - 24, -14)
        leader(line, heads, [b + (-120, -110), b + (-40, -70), b + (-4, -6)])
        s.stroke(line, UI_ALT, 1.3 * wt, cap="round")
        s.fill(heads, UI_ALT)
