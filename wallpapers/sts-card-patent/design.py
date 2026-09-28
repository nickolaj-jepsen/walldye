"""Patent sheet of the three Spire card frames in hairline outline; only the attack card's energy orb is lit."""

from walldye import ACCENT, ACCENT_2, BG, UI, UI_ALT, UI_HI, Canvas, P, Paint, Path, Rect, design
from walldye.pixel import Font, glyphs, text_width

# Proportions measured on the StS1 card renders (Bash/Defend/Inflame, 590x828 card body).
CH = 420
CW = round(CH * 0.713)
PITCH = 378  # card centre to card centre
# per type (attack, skill, power): outer corner radius, and the portrait bottom (V tip / rrect /
# oval) where the type tab sits, as fractions of the card
OUTER_R = (0, 0.04, 0.09)
ART_BOT = (0.585, 0.575, 0.55)
R_ORB = 0.11 * CW


def portrait(p: Path, kind: int, card: Rect, inset: float = 0.0) -> None:
    """Art frame for card type `kind`; `inset` (px) shrinks it for the inner art edge."""
    d, f = inset, card.frac
    if kind == 0:  # attack: straight jambs, then a shield V down to the type tab
        (xl, yt), (xr, ys), (xm, yb) = f(0.07, 0.13), f(0.93, 0.47), f(0.5, ART_BOT[0])
        p.M(xl + d, yt + d).H(xr - d).V(ys - d * 0.4).L(xm, yb - d * 1.9)
        p.L(xl + d, ys - d * 0.4).Z()
    elif kind == 1:
        (x, y), (x2, y2) = f(0.07, 0.13), f(0.93, ART_BOT[1])
        p.rrect(x + d, y + d, x2 - x - 2 * d, y2 - y - 2 * d, 0.05 * CW - d * 0.6)
    else:  # power: a full oval whose top peeks above the banner
        p.ellipse(f(0.5, 0.285), 0.455 * CW - d, 0.265 * CH - d)


def banner(p: Path, card: Rect) -> None:
    """The name ribbon, arched slightly upward; each end drops into a horn curling outward."""
    f = card.frac
    tl, tm, tr = f(-0.03, 0.075), f(0.5, 0.042), f(1.03, 0.075)
    bl, bm, br = f(0.03, 0.148), f(0.5, 0.118), f(0.97, 0.148)
    # a quadratic's control sits twice as far from the chord as the curve's midpoint
    p.M(tl).Q((tm.x, 2 * tm.y - (tl.y + tr.y) / 2), tr)
    p.Q(f(1.075, 0.12), f(1.045, 0.225)).Q(f(1.02, 0.165), br)  # right horn
    p.Q((bm.x, 2 * bm.y - (bl.y + br.y) / 2), bl)
    p.Q(f(-0.02, 0.165), f(-0.045, 0.225)).Q(f(-0.075, 0.12), tl).Z()  # left horn


def label(s: Canvas, text: str, cx: float, y: float, paint: Paint, font: Font = "5x8") -> None:
    """`text` centred on `cx`, its origin on a whole pixel."""
    glyphs(s, text, paint, at=(round(cx - text_width(text, font=font) / 2), round(y)), font=font)


@design()
def draw(s: Canvas) -> None:
    c = s.center
    cards = [Rect(c.x + (i - 1) * PITCH - CW / 2, c.y - CH / 2, CW, CH) for i in range(3)]
    top, bottom = cards[0].y, cards[0].y1

    with s.pattern(5, 5) as hatch:
        hatch.stroke(P().M(-1, 1).L(1, -1).M(0, 5).L(5, 0).M(4, 6).L(6, 4), UI, 1)

    outline, panel, faint, frames, arts, ribbons, tabs, tablines = (P() for _ in range(8))
    for i, card in enumerate(cards):
        f = card.frac
        outline.rrect(*card, OUTER_R[i] * CW)
        # description panel: runs up behind the portrait, thick frame below it
        (px, py), (px2, py2) = f(0.075, 0.47), f(0.925, 0.94)
        panel.rrect(px, py, px2 - px, py2 - py, 0 if i == 0 else 0.025 * CW)
        if i == 0:  # attack frame is bevelled: miters from panel corners to card corners
            panel.M(px, py2).L(card.x, card.y1).M(px2, py2).L(card.x1, card.y1)
        portrait(frames, i, card)
        portrait(arts, i, card, inset=6)
        banner(ribbons, card)
        tab = f(0.5, ART_BOT[i])
        tw, th = 0.19 * CW, 0.05 * CH
        tabs.rrect(tab.x - tw / 2, tab.y - th / 2, tw, th, 6)
        tablines.M(tab.x - 0.045 * CW, tab.y).H(tab.x + 0.045 * CW)
        rows = ((0.715, 0.62), (0.765, 0.7)) if i == 0 else ((0.74, 0.54),)
        for v, w in rows:
            row = f(0.5, v)
            faint.M(row.x - w * CW / 2, row.y).H(row.x + w * CW / 2)
    orbs = [card.frac(0.044, 0.036) for card in cards]

    # reference numerals: FIG. 1's on its left, FIG. 3's on its right
    lead = P()
    left, right = cards[0].x - 96, cards[2].x1 + 96
    refs = (
        (orbs[0] + (-R_ORB - 6, 2), (left, top - 16), "10", -1),
        (cards[0].frac(-0.05, 0.215), (left, top + 0.3 * CH), "12", -1),
        (cards[2].frac(0.965, 0.33), (right, top + 0.36 * CH), "14", 1),
        (cards[2].frac(0.86, 0.86), (right, top + 0.82 * CH), "16", 1),
    )
    for (sx, sy), (ex, ey), num, side in refs:
        tx = ex - side * 6
        lead.M(sx, sy).Q((sx + tx) / 2, sy + (ey - sy) * 0.05 - 14, tx, ey)
        label(s, num, ex + side * 14, ey - 8, UI_ALT)

    # dimensions: card width under FIG. 2, card height right of FIG. 3
    dim, heads = P(), P()
    x0, x1, yd = cards[1].x, cards[1].x1, bottom + 26
    dim.M(x0, bottom + 8).V(yd + 8).M(x1, bottom + 8).V(yd + 8).M(x0 + 9, yd).H(x1 - 9)
    heads.arrowhead((x0, yd), 9, deg=180, width=3).arrowhead((x1, yd), 9, deg=0, width=3)
    r3 = cards[2].x1
    xd = r3 + 34
    dim.M(r3 + 8, top).H(xd + 8).M(r3 + 8, bottom).H(xd + 8).M(xd, top + 9).V(bottom - 9)
    heads.arrowhead((xd, top), 9, bearing=0, width=3)
    heads.arrowhead((xd, bottom), 9, bearing=180, width=3)

    s.stroke(dim, UI, 1)
    s.fill(heads, UI)
    # a BG underlay breaks the dimension line where FIG. 3's leaders cross it
    s.stroke(lead, BG, 6)
    s.stroke(lead, UI, 1)
    s.stroke(outline, UI_HI, 1.5, join="round")
    s.stroke(panel, UI_ALT, 1)
    s.stroke(faint, UI, 2, cap="round")
    # portraits, ribbons and tabs cover what lies beneath, so each fills with BG first
    s.path(frames, fill=BG, stroke=UI_HI, stroke_width=1.5, stroke_linejoin="round")
    s.stroke(arts, UI_ALT, 1, join="round")
    s.fill(ribbons, BG)
    s.path(ribbons, fill=hatch.ref, stroke=UI_HI, stroke_width=1.5, stroke_linejoin="round")
    s.path(tabs, fill=BG, stroke=UI_HI, stroke_width=1.5)
    s.stroke(tablines, UI_ALT, 2, cap="round")

    # cost orbs: plain rings, except FIG. 1's, which is filled with the accent
    plain, rims = P(), P()
    for o in orbs[1:]:
        plain.circle(o, R_ORB)
        rims.circle(o, R_ORB - 7)
    s.path(plain, fill=BG, stroke=UI_HI, stroke_width=1.5)
    s.stroke(rims, UI_ALT, 1)
    lit = orbs[0]
    s.stroke(P().circle(lit, R_ORB + 6), ACCENT_2, 1)
    s.fill(P().circle(lit, R_ORB), ACCENT)
    # the glyph sits high and its flag weights it left, so nudge it to the optical centre
    label(s, "1", lit.x + 1, lit.y - 14, BG, font="8x16")

    for i, card in enumerate(cards):
        label(s, f"FIG. {i + 1}", card.center.x, bottom + 48, UI_ALT)

    s.stroke(P().rect(s.w - 280, s.h - 80, 240, 40), UI, 1)
    label(s, "SHEET 1 OF 1", s.w - 160, s.h - 68, UI)
