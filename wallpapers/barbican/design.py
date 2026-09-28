"""Night elevation of a brutalist tower in flat fills: round-ended balcony bands under a saw-tooth crown, one window lit."""

from walldye import (
    ACCENT,
    ACCENT_1,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    BG,
    BG_ALT,
    BG_DEEP,
    BLACK,
    UI,
    UI_ALT,
    Canvas,
    P,
    by_regime,
    design,
    mix,
)

BAY, FLOOR, PARAPET, PIER, SOFFIT = 120, 62, 26, 14, 3
LIP = 14  # how far each balcony runs past the facade before its rounded end
TOOTH, SLAB = 40, 40  # crown tooth height, roof slab depth
PANES = 3
# on paper the glass and the shadow under each balcony step towards the foreground instead
RECESS = by_regime(mix(BG_DEEP, BLACK, 0.4), mix(BG_ALT, UI, 0.5))
SHADOW = by_regime(BLACK, UI_ALT)
FLUTE = mix(BG, BG_ALT, 0.5)
EDGE = mix(BG_ALT, UI, 0.6)


@design(aspects="any")
def draw(s: Canvas) -> None:
    bays = 6 if s.landscape else 4
    # the tower's centre line and roof: left of centre on landscape, a tall tower on portrait
    top = s.pick(landscape=(0.3125, 0.198), portrait=(0.42, 0.3), snap=1)
    # the lit window: in the bay right of the middle pier on landscape, the second bay on portrait
    lit_bay, lit_y = (3, s.h * 0.55) if s.landscape else (1, s.h * 0.56)
    x0, x1, roof = top.x - bays * BAY / 2, top.x + bays * BAY / 2, top.y
    floors = int((s.h - roof) // FLOOR) + 1

    # saw-tooth crown: raked concrete upstands on the heavier roof slab, two per bay
    base = roof - SLAB + PARAPET
    crown = P().M(x0, base)
    for k in range(2 * bays):
        crown.L(x0 + (k + 1) * BAY / 2, base - TOOTH).V(base)
    s.fill(crown.Z(), BG_ALT)

    recess, mullions, flutes, bands, soffits, edges, piers = (P() for _ in range(7))
    for f in range(floors):
        y = roof + f * FLOOR
        wy0, wy1 = y + PARAPET, y + FLOOR
        recess.rect(x0, wy0, x1 - x0, FLOOR - PARAPET)
        for b in range(bays):
            for k in range(1, PANES):
                mullions.M(x0 + b * BAY + k * BAY / PANES, wy0).V(wy1)
        # piers carry the ribbed bush-hammering as a pair of flutes
        for b in range(bays + 1):
            px = x0 + b * BAY - PIER / 2
            flutes.M(px + PIER / 3, wy0 + SOFFIT).V(wy1).M(px + 2 * PIER / 3, wy0 + SOFFIT).V(wy1)
        # the roof slab is deeper than the balconies below it
        ty = y - (SLAB - PARAPET if f == 0 else 0)
        r = (wy0 - ty) / 2
        bands.rrect(x0 - LIP - r, ty, x1 - x0 + 2 * (LIP + r), wy0 - ty, r)
        soffits.rect(x0 - PIER / 2, wy0, x1 - x0 + PIER, SOFFIT)
        if f % 3 == 1:
            edges.M(x0 - LIP, ty + 0.8).H(x1 + LIP)
    for b in range(bays + 1):
        piers.rect(x0 + b * BAY - PIER / 2, roof, PIER, s.h - roof)
    s.fill(recess, RECESS)
    s.stroke(mullions, BG, 1.2)

    ly = roof + round((lit_y - roof) / FLOOR) * FLOOR
    wx, wy0, wy1 = x0 + lit_bay * BAY, ly + PARAPET, ly + FLOOR
    s.fill(P().rect(wx, wy0, BAY, FLOOR - PARAPET), ACCENT)
    # a half-drawn curtain in the first pane
    s.fill(P().rect(wx, wy0, BAY / PANES * 0.6, FLOOR - PARAPET), ACCENT_1)
    lit_mullions = P()
    for k in range(1, PANES):
        lit_mullions.M(wx + k * BAY / PANES, wy0).V(wy1)
    s.stroke(lit_mullions, ACCENT_5, 1.6)

    s.fill(piers, BG)
    s.stroke(flutes, FLUTE, 1.2)
    s.fill(soffits, SHADOW)
    s.fill(bands, BG_ALT)
    s.stroke(edges, EDGE, 1.6)

    # light on the soffit of the balcony above, falling off in two straight steps, and on the lip
    for spread, tone in ((28, ACCENT_7), (12, ACCENT_6)):
        s.fill(P().rect(wx - spread, wy0, BAY + 2 * spread, SOFFIT), tone)
    s.fill(P().rect(wx, wy1, BAY, 1.6), ACCENT_5)
