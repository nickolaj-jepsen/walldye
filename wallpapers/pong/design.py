"""Pong paused mid-rally: the ball's dotted flight off the top wall, its bounce angles marked like a patent figure."""

import math

from walldye import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ACCENT_4,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    Colour,
    P,
    Path,
    Point,
    Vec,
    design,
    polar,
)

TOP, BOT, X0, X1 = 110, 970, 120, 1800  # court walls and where they end
NET = 960
PADDLES = (Vec(160, 650), Vec(1760, 440))  # centres
PW, PH = 16, 136
BALL, B = Vec(1400, 350), 20  # centre and side
PITCH = 14  # dot spacing along the flight
LEG, ARC = 50, 36  # the solid angle legs at the bounce, and the angle arcs' radius
GHOSTS = ((16, ACCENT_2), (13, ACCENT_3), (10, ACCENT_4))  # afterimage side and tone, newest first


def square(c: Point, side: float) -> Path:
    """An axis-aligned square of `side` centred on `c`."""
    return P().rect(c[0] - side / 2, c[1] - side / 2, side, side)


@design()
def draw(s: Canvas) -> None:
    s.stroke(P().M(X0, TOP).H(X1).M(X0, BOT).H(X1), BG_ALT, 2)
    s.stroke(P().M(NET, TOP + 24).V(BOT - 24), BG_ALT, 4, dash=(16, 16))
    paddles = P()
    for c in PADDLES:
        paddles.rect(c.x - PW / 2, c.y - PH / 2, PW, PH)
    s.fill(paddles, UI_ALT)

    # Mirror the ball in the line its centre follows along the wall to find the bounce, k.
    a = PADDLES[0] + (PW / 2 + B / 2, 22)  # struck just below the paddle's centre
    wy = TOP + B / 2
    m = Vec(BALL.x, 2 * wy - BALL.y)
    k = Vec(a.x + (m.x - a.x) * (a.y - wy) / (a.y - m.y), wy)
    u = (BALL - k).unit()

    def span(side: float) -> float:
        """Half the extent of a square of `side` along the flight line."""
        return side / 2 * (abs(u.x) + abs(u.y))

    # afterimages nest back along the flight, shrinking with 3-unit gaps
    ghosts: list[tuple[Vec, float, Colour]] = []
    t, prev = 0.0, B
    for side, tone in GHOSTS:
        t += span(prev) + span(side) + 3
        ghosts.append((BALL - u * t, side, tone))
        prev = side
    tail = BALL - u * (t + span(prev) + 10)

    dots = P()
    for p0, p1 in ((a, k), (k, tail)):
        n = int(abs(p1 - p0) / PITCH)
        for i in range(n + 1):
            p = p0 + (p1 - p0) * (i / n)
            if not 0.5 < abs(p - k) < LEG:  # the solid legs replace the dots near the bounce
                dots.M(p).H(p.x)
    s.stroke(dots, UI, 3.2, cap="round")

    # Patent-figure aside: the ball's outline at contact, the normal, and the equal angles off it.
    s.stroke(square(k, B), UI, 1.4)
    s.stroke(P().M(k.x, TOP).V(wy + 80), UI, 1.2, dash=(6, 5))
    th = math.degrees(math.atan2(u.y, u.x))  # the flight's angle below the wall
    marks = P()
    for leg in (180 - th, th):
        mid = (90 + leg) / 2
        marks.M(k).L(polar(k, LEG, deg=leg)).arc(k, ARC, deg=(90, leg))
        marks.M(polar(k, ARC - 5, deg=mid)).L(polar(k, ARC + 5, deg=mid))
    s.stroke(marks, UI, 1.2)

    for c, side, tone in reversed(ghosts):
        s.fill(square(c, side), tone)
    s.fill(square(BALL, B), ACCENT)
