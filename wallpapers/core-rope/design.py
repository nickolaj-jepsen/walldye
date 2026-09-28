"""Core rope memory: spline-drawn sense wires thread through or loop around a row of ferrite cores, and one wire's path spells a byte."""

from collections.abc import Sequence

from scipy.interpolate import Akima1DInterpolator

from walldye import ACCENT, ACCENT_5, BG_ALT, UI, UI_ALT, Canvas, P, Path, Rng, Vec, design, polar

CY = 670  # the rope's axis
XS = [760 + k * (1640 - 760) / 7 for k in range(8)]  # core centres
ORX, ORY, IRX, IRY = 34, 52, 17, 30  # outer and inner radii of a core seen at a slant
N = 52
ACCENT_WIRE, ACCENT_BITS = 17, (1, 0, 1, 1, 0, 0, 1, 0)
ACCENT_SIDES = (1, 1, 1, -1, -1, 1, 1, -1)  # bypass direction per core; only used on 0 bits
LEAD, TAIL = 420, 150  # where the wires join the bundle before the first and after the last core


def ell(cx: float, rx: float, ry: float, deg: float) -> Vec:
    """The point at `deg` on the ellipse of radii `rx`, `ry` around the core at `cx`."""
    p = polar((0, 0), 1, deg=deg)
    return Vec(cx + rx * p.x, CY + ry * p.y)


def front_half(d: Path, cx: float) -> Path:
    """The right (front) half of the core at `cx`, which the threading wires pass under."""
    d.M(cx, CY - ORY).A(ORX, ORY, 0, 0, 1, cx, CY + ORY)
    return d.L(cx, CY + IRY).A(IRX, IRY, 0, 0, 0, cx, CY - IRY).Z()


def front_edge(d: Path, cx: float, over: float = 3) -> Path:
    """The outlines of the front half; they run `over` degrees past 12 and 6 o'clock so they
    overlap the back outline instead of butting into it."""
    for rx, ry in ((ORX, ORY), (IRX, IRY)):
        d.M(ell(cx, rx, ry, -90 - over)).A(rx, ry, 0, 1, 1, ell(cx, rx, ry, 90 + over))
    return d


def akima(d: Path, kx: Sequence[float], ky: Sequence[float]) -> Path:
    """Emit the modified-Akima spline through the knots as exact cubic Béziers; unlike
    Catmull-Rom it never overshoots between the unevenly spaced knots."""
    dy = Akima1DInterpolator(kx, ky, method="makima").derivative()(kx)
    d.M(kx[0], ky[0])
    for i in range(len(kx) - 1):
        h = (kx[i + 1] - kx[i]) / 3
        d.C(
            (kx[i] + h, ky[i] + h * dy[i]),
            (kx[i + 1] - h, ky[i + 1] - h * dy[i + 1]),
            (kx[i + 1], ky[i + 1]),
        )
    return d


def knots(
    r: Rng,
    bits: Sequence[bool | int],
    sides: Sequence[int],
    x1: float,
    spread: float = 1.0,
    ends: tuple[float, float] = (0, 0),
) -> tuple[list[float], list[float]]:
    """Knots for one wire from x 0 to `x1`: through each core where its bit is set, else
    60-140 units above or below it on that core's side."""
    base = CY + r.gauss(0, 18) * spread
    ys = [
        CY + r.uniform(-9, 9) if b else CY + sd * r.uniform(60, 140) for b, sd in zip(bits, sides)
    ]
    # one knot per core (through or around it); between cores the wire relaxes toward the bundle,
    # except across a run of same-side bypasses, where it stays out and arcs over several cores
    kx, ky = [0.0, XS[0] - LEAD], [CY + ends[0] + r.gauss(0, 70) * spread, base]
    for k, (cx, y) in enumerate(zip(XS, ys)):
        kx.append(cx)
        ky.append(y)
        if k + 1 < len(XS):
            stay = not bits[k] and not bits[k + 1] and sides[k] == sides[k + 1]
            kx.append((cx + XS[k + 1]) / 2)
            pull = r.uniform(0.85, 1.1) if stay else r.uniform(0.55, 0.8)
            ky.append(base + ((y + ys[k + 1]) / 2 - base) * pull)
    kx += [XS[-1] + TAIL, x1]
    ky += [base, CY + ends[1] + r.gauss(0, 40) * spread]
    return kx, ky


@design()
def draw(s: Canvas) -> None:
    r = s.rng(11)
    dim, mid = P(), P()
    for i in range(N):
        if i == ACCENT_WIRE:
            continue
        # each wire favours one side when bypassing, so the 0-bit loops don't mirror into lens shapes
        side = r.choice((-1, 1))
        bits = [r.random() < (0.2 if lit else 0.55) for lit in ACCENT_BITS]
        sides = [side if r.random() < 0.85 else -side for _ in XS]
        akima(mid if i % 5 == 0 else dim, *knots(r, bits, sides, s.w))
    accent = akima(P(), *knots(r, ACCENT_BITS, ACCENT_SIDES, s.w, 0.0, ends=(-30, 26)))

    # whole cores underneath, so the front halves drawn over the wires leave no seam
    back = P()
    for cx in XS:
        back.ellipse((cx, CY), ORX, ORY).ellipse((cx, CY), IRX, IRY)
    s.fill(back, UI, rule="evenodd")
    s.stroke(back, UI_ALT, 1.4)

    s.stroke(dim, BG_ALT, 1.2)
    s.stroke(mid, UI, 1.2)
    # lit holes sit over the other wires so each reads as a clean glow behind the accent wire
    holes = P()
    for cx, lit in zip(XS, ACCENT_BITS):
        if lit:
            holes.ellipse((cx, CY), IRX - 0.7, IRY - 0.7)
    s.fill(holes, ACCENT_5)
    s.stroke(accent, ACCENT, 1.8)

    front, edge = P(), P()
    for cx in XS:
        front_half(front, cx)
        front_edge(edge, cx)
    s.fill(front, UI)
    s.stroke(edge, UI_ALT, 1.4)
