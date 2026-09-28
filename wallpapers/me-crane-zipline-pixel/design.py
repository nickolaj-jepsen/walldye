"""Mirror's Edge rooftops in coarse pixels: a runner hangs by both hands from a zipline strung between two clamped posts while a lattice tower crane lifts an I-beam behind."""

from walldye import (
    ACCENT,
    ACCENT_4,
    ACCENT_6,
    BG,
    BG_ALT,
    BG_DEEP,
    UI,
    UI_ALT,
    Canvas,
    Rng,
    by_regime,
    design,
    mix,
)
from walldye.pixel import Pixels

PX = 6
# Depth steps back to front: the far skyline, BG_ALT, UI. BG_DEEP is lighter than BG on light
# themes, where it would erase the far skyline, so there that layer steps partway to BG_ALT.
SKYLINE = by_regime(BG_DEEP, mix(BG, BG_ALT, 0.45))
# The cable and near limbs are ACCENT, the far limbs a third of the way from ACCENT_4 back to
# ACCENT, the crane's jib and load ACCENT_6.
PALETTE = (None, SKYLINE, BG_ALT, UI, ACCENT, mix(ACCENT_4, ACCENT, 1 / 3), ACCENT_6, UI_ALT)
EMPTY, FAR, MID, NEAR, ACC, LIMB, BOOM, CRANE = range(8)

ZIP0, ZIP1 = (54, 74), (258, 130)  # (col, row) of the two post heads, a ~14° drop
GRIP = 0.42  # how far along the span the runner hangs

# Side view, travelling right: both hands over the cable, head tucked behind the arms, legs
# trailing back. a = near side, b = far arm/leg; the hands close over the cable in column 6.
RUNNER = """
......ba..
......ba..
......ba..
......ba..
.....ba...
..aa.ba...
.aaaa.a...
.aaaa.a...
..aa.aa...
...aaaa...
...aaaa...
..aaaaa...
..aaaa....
..aaaa....
..aaa.....
.aaab.....
.aaab.....
.aa.b.....
aa..b.....
a..b......
a..b......
..bb......
"""


def tower(px: Pixels, r: Rng, x: int, w: int, top: int, v: int, ribbons: bool) -> None:
    """Modernist block with optional setback crown and horizontal ribbon windows."""
    g = px.grid
    g[top:, x : x + w] = v
    if w >= 10 and r.random() < 0.6:
        inset = r.randint(2, w // 4)
        g[top - r.randint(3, 7) : top, x + inset : x + w - inset] = v
    if ribbons:
        for y in range(top + 3, px.rows, 4):
            g[y, x + 1 : x + w - 1] = EMPTY


def ac_unit(px: Pixels, x: int, roof: int, w: int, v: int) -> None:
    px.grid[roof - 3 : roof, x : x + w] = v
    px.grid[roof - 4, x + 1 : x + w - 1 : 3] = v


def anchor(px: Pixels, x: int, y: int, roof: int, back: int) -> None:
    """Steel post with a back-stay strut and a cable clamp block on top; `back` (+1 or -1)
    points away from the span."""
    g = px.grid
    g[y:roof, x] = NEAR
    g[y:roof, x + back] = NEAR
    px.line(x + back, y + 3, x + 7 * back, roof - 1, NEAR)
    g[roof - 1, x + 5 * back : x + 9 * back : back] = NEAR  # strut foot plate
    g[y - 2 : y + 2, min(x - back, x + 2 * back) : max(x - back, x + 2 * back) + 1] = NEAR  # clamp
    g[roof - 1, x - 2 : x + 3] = NEAR  # post base plate


@design()
def draw(s: Canvas) -> None:
    r = s.rng(17)
    px = Pixels(s.w // PX, s.h // PX, PALETTE)
    g = px.grid

    x = 0
    while x < px.cols:
        w = r.randint(8, 18)
        tower(px, r, x, w, px.rows - r.randint(52, 96), FAR, r.random() < 0.7)
        x += w + r.randint(1, 5)

    # mid roofs: clean flat slabs with parapet lips and rooftop boxes
    for x, w, top in ((60, 50, 118), (116, 56, 132), (178, 40, 122)):
        g[top:, x : x + w] = MID
        g[top - 1, x : x + w : 2] = MID
        g[top - 4 : top, x + 3 : x + 9] = MID
    ac_unit(px, 188, 122, 6, MID)
    ac_unit(px, 150, 132, 7, MID)
    ac_unit(px, 159, 132, 7, MID)
    g[128, 122:148] = MID  # pipe run on stub supports, dropping into a riser
    g[129:132, 124:148:6] = MID
    g[128:132, 147] = MID
    # billboard frame on legs
    g[98:110, 78:104] = MID
    g[100:108, 80:102] = FAR
    for lx in (82, 99):
        g[110:117, lx] = MID

    # rooftop crane: scaffold-lattice mast, cab on a slewing ring, lattice jib and counter-jib
    tx, tw, roof = 262, 46, 104
    g[roof:, tx : tx + tw] = MID
    g[roof - 1, tx : tx + tw : 2] = MID
    g[roof - 6 : roof, tx + 34 : tx + 42] = MID  # water tank
    g[roof - 7, tx + 35 : tx + 41] = MID
    mx, mw, mtop = tx + 12, 7, 58  # mast: two uprights, ledgers every 6 rows, one diagonal per bay
    g[mtop:roof, mx] = CRANE
    g[mtop:roof, mx + mw - 1] = CRANE
    for y in range(mtop, roof, 6):
        g[y, mx : mx + mw] = CRANE
        px.line(mx, min(y + 6, roof - 1), mx + mw - 1, y, CRANE)
    g[mtop - 2 : mtop, mx - 1 : mx + mw + 1] = CRANE  # slewing ring
    jt, jb = mtop - 7, mtop - 3  # jib chords: horizontal Warren truss out to the tip
    tipx, cjx = 196, mx + mw + 14
    g[jt, tipx + 2 : cjx] = BOOM
    g[jb, tipx:cjx] = BOOM
    g[jt + 1 : jb, tipx] = BOOM
    for x in range(tipx, cjx - 4, 8):
        px.line(x, jb, x + 4, jt, BOOM)
        px.line(x + 4, jt, x + 8, jb, BOOM)
    g[jt : jb + 1, mx - 1 : mx + mw + 1] = CRANE  # turntable head
    g[jb + 1 : jb + 7, mx - 7 : mx - 1] = CRANE  # cab slung under the jib root
    g[jb + 2 : jb + 4, mx - 6 : mx - 3] = EMPTY
    g[jt - 1 : jb + 5, cjx - 5 : cjx] = CRANE  # counterweight
    g[jt - 12 : jt, mx + 3] = CRANE  # tower-top apex and pendant ties
    px.line(mx + 3, jt - 12, tipx + 40, jt - 1, CRANE)
    px.line(mx + 3, jt - 12, cjx - 3, jt - 2, CRANE)
    hx, ht = tipx + 14, jb + 10  # hook line from the jib, two slings, then the I-beam
    g[jb + 1 : jb + 22, hx] = CRANE
    px.line(hx, ht + 12, hx - 6, ht + 15, CRANE)
    px.line(hx, ht + 12, hx + 6, ht + 15, CRANE)
    g[ht + 16, hx - 9 : hx + 10] = BOOM
    g[ht + 17, hx - 8 : hx + 9] = BOOM
    g[ht + 18, hx - 9 : hx + 10] = BOOM

    # near left: tall roof carrying the upper zipline mount
    lr = 86
    g[lr:, 0:66] = NEAR
    g[lr - 2 : lr, 0:66:3] = NEAR
    g[lr - 2, 0:66] = NEAR
    for y in range(lr + 5, px.rows, 6):
        g[y : y + 2, 0:64] = MID  # ribbon windows
    ac_unit(px, 6, lr - 2, 8, NEAR)
    ac_unit(px, 17, lr - 2, 6, NEAR)
    g[lr - 14 : lr - 2, 30:32] = NEAR  # vent stack
    g[lr - 14, 29:33] = NEAR
    g[lr - 30 : lr - 2, 40] = NEAR  # antenna mast
    g[lr - 26, 39:42] = g[lr - 20, 39:42] = NEAR
    anchor(px, ZIP0[0], ZIP0[1], lr - 2, -1)

    # near right: lower roof; the cable ends at a post on its parapet
    rr = 152
    g[rr:, 196:] = NEAR
    g[rr - 2 : rr, 196::3] = NEAR
    g[rr - 2, 196:] = NEAR
    for y in range(rr + 5, px.rows, 6):
        g[y : y + 2, 198:] = MID
    anchor(px, ZIP1[0], ZIP1[1], rr - 2, 1)
    ac_unit(px, 208, rr - 2, 7, NEAR)
    ac_unit(px, 220, rr - 2, 5, NEAR)
    ac_unit(px, 296, rr - 2, 9, NEAR)

    px.line(ZIP0[0], ZIP0[1], ZIP1[0], ZIP1[1], ACC)
    # The cable is x-major, so it holds one cell per column: the one in the grip column pins the
    # sprite, and the knuckles close over it.
    hx = ZIP0[0] + int((ZIP1[0] - ZIP0[0] + 1) * GRIP)
    grip = int((g[:, hx + 6] == ACC).argmax())
    px.stamp(RUNNER, hx, grip + 1, {"a": ACC, "b": LIMB})
    g[grip, hx + 6 : hx + 8] = ACC

    px.draw(s, PX)
