"""A graphic score after Cardew's Treatise in thin line work: shapes hung on one lifeline, one note filled in."""

from walldye import ACCENT, ACCENT_3, UI_ALT, UI_HI, Canvas, P, Vec, design, mix, polar
from walldye.geom import Affine

Y = 640  # the lifeline
NOTE = Vec(1390, Y)
CIRCLE, CR = Vec(690, Y), 118
HAIR, THIN, HEAVY = 1.0, 1.5, 3.5
INK = UI_HI
SOFT = mix(UI_ALT, UI_HI, 0.4)


@design()
def draw(s: Canvas) -> None:
    # One builder per paint and weight: hairlines, thin and heavy strokes, solid marks.
    hair, thin, heavy, solid = P(), P(), P(), P()

    # Staff fragment above the line, tilted 4 degrees, with open noteheads, one solid note and a
    # link down to the circle.
    x0, x1, top, gap = 250, 520, 500, 10
    tilt = Affine.rotate(deg=-4, about=(x0, top))
    for k in range(5):
        hair.M(tilt((x0, top + k * gap))).L(tilt((x1, top + k * gap)))
    for hx, step in ((300, 1), (365, 3), (430, 2)):
        thin.circle(tilt((hx, top + step * gap)), 6.5)
    thin.M(tilt((x0, top - 3))).L(tilt((x0, top + 4 * gap + 3)))
    thin.M(tilt((x1, top + 4 * gap))).L(CIRCLE.x - CR, Y)
    solid.circle(tilt((400, top + 4 * gap)), 6.5)

    # Large circle bisected by the lifeline, with a smaller disc resting on its rim.
    thin.circle(CIRCLE, CR)
    heavy.M(CIRCLE.x - CR, Y).L(CIRCLE.x + CR, Y)
    rest = polar(CIRCLE, CR + 14, deg=-58)

    # Dense band of parallel hairlines, leaning 28 degrees off vertical, hung from a short bar.
    bx, n, pitch = 860, 34, 5
    for k in range(n):
        foot = Vec(bx + k * pitch, Y + 14)
        hair.M(foot).L(polar(foot, 190, deg=90 - 28))
    solid.rect(bx - 1, Y + 10, (n - 1) * pitch + 2, 4)

    # Triangle standing on the line, its right edge doubled in weight.
    tx, tw, th = 1120, 120, 150
    tri = [Vec(tx, Y), Vec(tx + tw, Y), Vec(tx + tw * 0.62, Y - th)]
    thin.poly(tri, closed=True)
    heavy.M(tri[1]).L(tri[2])

    # Dotted trajectory thrown from the apex onto the note.
    trail = P().M(tri[2] + (26, -6)).A(230, 230, 0, 0, 1, NOTE.x, Y - 46)

    # A staff grows out of the line after the note and bends up into concentric quarter arcs.
    fx, run, R, gap = 1500, 80, 190, 10
    for k in range(1, 6):
        y, r = Y - k * gap, R - k * gap
        hair.M(fx, y).L(fx + run, y).A(r, r, 0, 0, 0, fx + run + r, Y - R)
    thin.M(fx, Y - 5 * gap - 4).L(fx, Y)
    thin.M(fx + run + R - 5 * gap - 6, Y - R).L(fx + run + R - gap + 6, Y - R)
    for r in (5, 13, 24):
        hair.circle((1660, Y + 74), r)

    s.stroke(P().M(0, Y).L(s.w, Y), INK, 2)
    s.stroke(hair, SOFT, HAIR)
    s.stroke(thin, INK, THIN)
    s.stroke(heavy, INK, HEAVY)
    s.fill(solid, INK)
    s.fill(P().circle(rest, 14), UI_ALT)
    s.stroke(trail, SOFT, 3, cap="round", dash=(0, 11))
    s.stroke(P().circle(NOTE, 34), ACCENT_3, 1.5)
    s.fill(P().circle(NOTE, 22), ACCENT)
