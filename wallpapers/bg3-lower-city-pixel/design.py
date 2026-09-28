"""Baldur's Gate from the harbour as pixel art in one index grid: cathedral bluff, Lower City, Wyrm's Rock with its beacon lit and Wyrm's Crossing, mirrored in the river."""

import numpy as np
from numpy.typing import NDArray

from walldye import ACCENT, ACCENT_4, ACCENT_5, BG, BG_ALT, UI, UI_ALT, UI_HI, Canvas, design
from walldye.field import noise_grid
from walldye.pixel import Pixels

type Grid = NDArray[np.int64]
type Mask = NDArray[np.bool_]

PX = 8
SHORE = 112  # first water row
DECK = 97  # Wyrm's Crossing roadway row
KX, KW, KTOP = 121, 11, 58  # Wyrm's Rock keep: left column, width, top row
BX, BY = KX + KW // 2, KTOP - 3  # beacon cell

# Palette indices, back to front; the river mirrors FAR..NEAR, so keep that order.
SKY, DIM, FAR, MID, NEAR, BEACON, GLOW, GLINT, HOLE = range(9)
PALETTE = (None, BG_ALT, UI, UI_ALT, UI_HI, ACCENT, ACCENT_4, ACCENT_5, BG)


def crenel(g: Grid, x0: int, x1: int, y: int, k: int) -> None:
    """Merlons on every other cell of the row above a wall top at row `y`, columns x0..x1."""
    g[y - 1, x0:x1:2] = k


def tower(g: Grid, x: int, w: int, top: int, base: int, k: int) -> None:
    """A square tower `w` cells wide from row `top` down to `base`, with a one-cell overhang
    and crenellations."""
    g[top + 2 : base, x : x + w] = k
    g[top + 1, x - 1 : x + w + 1] = k
    g[top, x - 1 : x + w + 1 : 2] = k


def roof(g: Grid, x: int, w: int, eave: int, k: int) -> None:
    """A hipped roof over columns x..x+w seen side-on, rising from row `eave`; the ridge goes
    flat at a third of the width."""
    for i in range(w):
        rise = min(i, w - 1 - i, max(2, w // 3)) + 1
        g[eave - rise : eave, x + i] = k


def rimmed(g: Grid, m: Mask, k: int) -> None:
    """Paint mask `m` in `k` over a one-cell DIM outline along its top edge, so it reads
    against whatever stands behind it."""
    rim = np.zeros_like(m)
    rim[:-1] |= m[1:]
    g[rim & ~m] = DIM
    g[m] = k


def townhouse(g: Grid, x: int, w: int, eave: int, gable: bool, base: int = SHORE) -> None:
    """A Lower City house `w` cells wide, walls from `eave` down to `base`, under a steep gable
    or a hipped roof, rimmed so it stands out from the roofs behind."""
    m = np.zeros_like(g, bool)
    m[eave:base, max(x, 0) : x + w] = True
    for i in range(-1, w + 1):
        rise = min(i + 1, w - i) + 1 if gable else min(i + 1, w - i, max(2, w // 3)) + 1
        if 0 <= x + i < g.shape[1]:
            m[eave - rise : eave, x + i] = True
    rimmed(g, m, MID)


@design()
def draw(s: Canvas) -> None:
    cols, rows = s.w // PX, s.h // PX
    px = Pixels(cols, rows, PALETTE)
    g = px.grid
    r = s.rng(3)
    xs = np.arange(cols)
    yy, xx = np.mgrid[0:rows, 0:cols]

    for _ in range(26):  # stars
        g[r.randrange(0, 40), r.randrange(2, cols - 2)] = FAR

    # The crag east of the city: long concave western ridge, hooked summit, steep broken
    # eastern face.
    prof = np.interp(
        xs,
        [136, 156, 170, 180, 186, 192, 196, 200, 205, 210, 216, 222, 230, 240],
        [100, 92, 82, 70, 56, 42, 32, 27, 29, 36, 40, 38, 46, 52],
    )
    crag = np.convolve(s.np_rng(5).random(cols + 2), np.ones(3) / 3, "valid") * 6 - 3
    for x in range(138, cols):
        g[int(prof[x] + crag[x]) : SHORE, x] = DIM

    # Upper City bluff: cliff under the city wall with square towers.
    ridge = np.interp(xs, [0, 50, 60, 70], [70, 70, 78, 86])
    for x in range(70):
        g[int(ridge[x]) : SHORE, x] = FAR
    crenel(g, 0, 52, 70, FAR)
    for tx in (2, 50):
        tower(g, tx, 5, 60, 72, FAR)

    # Gothic cathedral: steep-roofed nave with buttress pinnacles and lancets, apse to the
    # east, square west tower with a spire.
    nb, ne = 56, 62  # nave roof ridge and eaves rows
    g[ne:70, 12:46] = FAR
    g[nb:ne, 13:45] = FAR
    g[nb - 1, 14:44] = FAR
    g[ne, 12:46] = SKY  # eave shadow
    for bx in range(14, 46, 4):
        g[nb - 2 : 70, bx] = FAR  # buttress pinnacles
    for wx in range(32, 46, 4):
        g[63:68, wx - 2] = HOLE  # lancets
    g[60:70, 46:52] = FAR  # apse
    g[59, 46:52:2] = FAR
    g[36:70, 18:27] = FAR  # west tower
    g[35, 17:28:2] = FAR
    for cx in (17, 27):  # corner pinnacles
        g[31:35, cx] = FAR
    for k in range(10):  # spire
        g[24 + k, 22 - k // 4 : 23 + k // 4] = FAR
    for wy in (40, 48, 64):
        g[wy : wy + 4, 22] = HOLE
    for k in range(10):  # crossing fleche
        g[nb - 10 + k, 38 - k // 5 : 39 + k // 5] = FAR

    # Upper City wall-walk and towers running east behind the Lower City.
    g[84:SHORE, 52:150] = np.maximum(g[84:SHORE, 52:150], FAR)
    crenel(g, 52, 150, 84, FAR)
    for tx, tt in ((62, 72), (84, 74), (108, 76), (140, 80)):
        tower(g, tx, 5, tt, 86, FAR)

    # Lower City: terraces of tiled roofs stepping down from under the bluff to the quays,
    # two towers and a few cypresses.
    for terrace in range(3):
        x = -r.randint(0, 4)
        while x < 116:
            w = r.choice((5, 6, 7, 8, 9))
            slope = int(np.interp(x, [0, 50, 80, 118], [76, 82, 90, 98]))
            eave = slope + 7 * terrace - r.randint(2, 6)
            townhouse(g, x, w, eave, r.random() < 0.4)
            if terrace == 0 and r.random() < 0.3:  # a taller house or hall behind
                w2 = max(3, w - 3)
                townhouse(g, x + r.randint(0, w - w2), w2, eave - r.randint(4, 7), False, eave)
            x += w + r.choice((0, 1))
    for tx, tb, th in ((34, 86, 16), (74, 94, 14)):
        tower(g, tx, 5, tb - th, tb, MID)
    for cx, cb, ch in ((8, 86, 12), (11, 86, 9), (56, 92, 11), (100, 100, 9)):
        for k in range(ch):
            half = 1 if 2 <= k < ch - 2 else 0
            g[cb - ch + k, cx - half : cx + half + 1] = MID

    # Hall of Wonders: ribbed glass dome on its drum.
    dx, dy, rw, rh = 96, 84, 8.5, 6.0
    dome = (((xx + 0.5 - dx) / rw) ** 2 + ((yy + 0.5 - dy) / rh) ** 2 <= 1) & (yy < dy)
    dome[dy : dy + 6, dx - 9 : dx + 9] = True
    dome[dy - 8 : dy - 5, dx - 1 : dx + 1] = True
    rimmed(g, dome, MID)
    g[dy, dx - 9 : dx + 9] = DIM
    for rx in (-4, 0, 4):
        g[dy - 5 + abs(rx) // 3 : dy, dx + rx] = FAR

    # Quay wall along the harbour.
    g[107:SHORE, 0:98] = MID

    # Wyrm's Crossing: roadway on arched stone piers, crowded with timber houses two and three
    # storeys high.
    g[DECK : DECK + 3, 98:cols] = NEAR
    piers = [98, 112, 150, 170, 190, 210, 230]
    for i, p in enumerate(piers):
        g[DECK:SHORE, p : p + 5] = NEAR
        g[SHORE - 2 : SHORE, p - 1 : p + 6] = NEAR  # cutwater
        if i + 1 < len(piers):
            a0, a1 = p + 5, piers[i + 1]
            cx, rw = (a0 + a1) / 2, (a1 - a0) / 2
            span = (xx >= a0) & (xx < a1) & (yy >= DECK + 3) & (yy < SHORE)
            arch = ((xx + 0.5 - cx) / rw) ** 2 + ((yy + 0.5 - SHORE) / (SHORE - DECK - 5)) ** 2 > 1
            g[span & arch] = NEAR
    x = 152
    while x < 224:
        w = r.choice((5, 6, 7, 8, 10))
        eave = DECK - r.choice((5, 7, 9, 12, 14))
        g[eave:DECK, x : x + w] = NEAR
        if r.random() < 0.5:  # steep front gable
            for i in range(w + 2):
                rise = min(i, w + 1 - i) + 1
                g[eave - rise : eave, x - 1 + i] = NEAR
        else:  # hipped tile roof with wide eaves
            roof(g, x - 1, w + 2, eave, NEAR)
        g[eave, x : x + w] = MID  # shadow under the eaves
        g[eave:DECK, x + w - 1] = MID
        if eave < DECK - 8:  # jettied upper storey
            g[eave + 5, x - 1 : x + w + 1] = NEAR
            g[eave + 6, x : x + w] = MID
        if r.random() < 0.5:  # timber gallery cantilevered off the deck on raking struts
            px.line(x, DECK + 5, x + 2, DECK + 3, NEAR)
            px.line(x + w - 1, DECK + 5, x + w - 3, DECK + 3, NEAR)
        x += w + r.choice((0, 1, 1, 2))
    # Rivington end: tall timber watchtower with a pyramid roof and an open lookout.
    g[72:DECK, 229:236] = NEAR
    g[70:72, 228:237] = NEAR
    g[66:70, 228] = g[66:70, 236] = NEAR
    for k in range(5):
        g[61 + k, 232 - k : 233 + k] = NEAR
    g[74:80, 231:234] = HOLE

    # Wyrm's Rock: rock islet, a lower crenellated block with corner turrets, and one tall keep
    # offset to the west with the beacon on top.
    rock = np.interp(xs, [112, 115, 121, 140, 148, 153], [SHORE, 106, 102, 102, 106, SHORE])
    for x in range(112, 153):
        g[int(rock[x]) : SHORE, x] = NEAR
    g[82:102, 116:148] = NEAR
    crenel(g, 116, 148, 82, NEAR)
    for tx in (116, 144):
        tower(g, tx, 4, 76, 86, NEAR)
    g[74:84, 134:144] = NEAR  # inner gatehouse block
    crenel(g, 134, 144, 74, NEAR)
    for tx in (133, 142):
        tower(g, tx, 3, 70, 76, NEAR)
    tower(g, KX, KW, KTOP, 102, NEAR)
    g[KTOP + 10, KX - 1 : KX + KW + 1] = NEAR  # string course
    for wy in (63, 73, 88):
        g[wy : wy + 4, BX] = HOLE
    g[96:102, 139:142] = HOLE  # gate
    g[BY : BY + 2, BX - 1 : BX + 1] = BEACON
    g[BY + 1, BX - 2] = g[BY + 1, BX + 1] = GLOW
    g[BY - 1, BX - 1 : BX + 1] = GLOW

    # Cogs moored at the quay: curved sheer, raised sterncastle, tall masts with furled yards.
    hull = 11  # half length
    for mx, mt, d, lateen in ((22, 74, 1, False), (70, 78, -1, True)):
        for i in range(-hull, hull + 1):
            u = i * d / hull  # -1 at the stern, +1 at the bow
            g[SHORE - 4 - round(3 * u * u) : SHORE, mx + i] = NEAR
        for tier, (x0, x1) in enumerate(((-hull, -hull + 8), (-hull, -hull + 5))):  # sterncastle
            lo, hi = sorted((mx + x0 * d, mx + x1 * d))
            g[SHORE - 10 - 3 * tier : SHORE - 7, lo : hi + 1] = NEAR
        lo, hi = sorted((mx + (hull - 5) * d, mx + hull * d))
        g[SHORE - 9 : SHORE - 7, lo : hi + 1] = NEAR  # forecastle
        px.line(mx + hull * d, SHORE - 8, mx + (hull + 6) * d, SHORE - 12, NEAR)  # bowsprit
        g[mt : SHORE - 4, mx] = NEAR  # mainmast
        g[mt + 2 : mt + 4, mx - 1 : mx + 2] = NEAR  # fighting top
        if lateen:
            for o in (0, 1):  # furled lateen yard, raked high aft and low forward
                px.line(mx + 6 * d + o, SHORE - 12, mx - 4 * d + o, mt - 4, NEAR)
            mz = mx - 9 * d
            g[mt + 14 : SHORE - 10, mz] = NEAR  # mizzen
            px.line(mz + 3 * d, SHORE - 14, mz - 3 * d, mt + 10, NEAR)
        else:
            for yard, hw in ((mt + 6, 4), (mt + 16, 6)):  # square yards, sails furled
                g[yard : yard + 2, mx - hw : mx + hw + 1] = NEAR
            px.line(mx, mt + 1, mx + (hull + 5) * d, SHORE - 12, NEAR)  # forestay to the bowsprit
            fm = mx + 8 * d
            g[mt + 14 : SHORE - 7, fm] = NEAR  # foremast
            g[mt + 20 : mt + 22, fm - 3 : fm + 4] = NEAR

    # River: the skyline mirrored one step quieter (NEAR as FAR, the rest as DIM), broken by
    # stretched noise that eats more of it with depth, and the beacon's glints.
    n = noise_grid(cols, 60, 7, s.np_rng(11), octaves=2)
    for k in range(22):
        row = g[SHORE - 1 - k]
        src = np.where((row >= FAR) & (row < BEACON), np.where(row == NEAR, FAR, DIM), SKY)
        g[SHORE + k] = np.where(n[k * 3 % 60] > -0.05 + k * 0.032, src, SKY)
    for k, w in ((1, 3), (3, 2), (4, 1), (7, 2), (9, 1), (12, 1), (15, 1)):
        o = r.randint(-1, 1)
        g[SHORE + k, BX - w // 2 + o : BX + (w + 1) // 2 + o] = GLINT

    px.draw(s, PX)
