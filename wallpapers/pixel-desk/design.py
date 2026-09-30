"""An isometric pixel-art corner room at night, lit only by the monitor on its desk."""

import math

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    ACCENT_3,
    ACCENT_4,
    ACCENT_5,
    BG_ALT,
    BG_DEEP,
    BLACK,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    Rect,
    Vec,
    by_regime,
    design,
)
from walldye.field import cells
from walldye.geom import Affine
from walldye.pixel import Pixels

type Mask = NDArray[np.bool_]
type Field = NDArray[np.float64]
type P3 = tuple[float, float, float]
type Span = tuple[float, float]

PX = 6
COLS, ROWS = 136, 124  # the room's bounding box in cells
OX, OY = 68, 56  # cell of world (0, 0, 0), the room's back corner at floor level

# Palette indices: the BG and UI tones from the deepest shade up, then the screen light from its faint pool
# up. Index 0 is bare canvas, which is also the inner face of the left wall. On paper the
# shade roles take ink instead of fading past the page, so the outer faces still read.
CANVAS, VOID, COFFEE, DEEP, BACK, FAINT, PLANE, RAISED, STAR = range(9)
POOL, SPILL, CODE, SCREEN = range(9, 13)
PALETTE = (
    None,
    by_regime(BLACK, UI_ALT),  # outer faces turned away to the right, window glass
    by_regime(BLACK, UI_HI),
    by_regime(BG_DEEP, UI),  # outer faces turned to the left, seams
    BG_DEEP,  # inner face of the back wall
    BG_ALT,
    UI,
    UI_ALT,
    by_regime(UI_ALT, BG_ALT),
    ACCENT_5,
    ACCENT_4,
    ACCENT_3,
    ACCENT,
)


def plane(z: float) -> Affine:
    """World (x, y) at height z to cell coordinates: 2:1 pixel isometric, +x runs right and
    down, +y left and down, and z rises 2 cells per unit."""
    return Affine(2, 1, -2, 1, OX, OY - 2 * z)


def iso(p: P3) -> Vec:
    """The cell coordinates of world point p."""
    return plane(p[2])((p[0], p[1]))


def ramp(v: Field, edge: float) -> Field:
    """1 where v is below `edge` and 0 beyond, across a band a third of a unit wide."""
    return np.clip((edge - v) * 3 + 0.5, 0, 1)


class Room:
    """The diorama as an index grid, plus which cells still show the desk top."""

    def __init__(self) -> None:
        self.px = Pixels(COLS, ROWS, PALETTE)
        self.desk: Mask = np.zeros((ROWS, COLS), bool)
        xs, ys = cells(Rect(0, 0, COLS, ROWS), 1)
        self.centers = np.column_stack([xs.ravel(), ys.ravel()])

    def quad(self, p0: P3, p1: P3, p3: P3, k: int, desk: bool = False) -> None:
        """Fill the parallelogram with world corners p0, p1, p3 and p1 + p3 - p0 in index k,
        testing cell centers."""
        a, b, d = iso(p0), iso(p1), iso(p3)
        uv = Affine(b.x - a.x, b.y - a.y, d.x - a.x, d.y - a.y, a.x, a.y).inverse()
        local = uv.apply(self.centers)
        m = ((local >= 0) & (local < 1)).all(axis=1).reshape(ROWS, COLS)
        self.px.grid[m] = k
        self.desk[m] = desk

    def xline(self, p0: P3, length: int, k: int) -> None:
        """A 2:1 pixel line `length` units long from world point p0 along +x: each unit steps
        two cells right and one down."""
        sx, sy = (round(v) for v in iso(p0))
        i = np.arange(length)
        self.px.grid[sy + i, sx + 2 * i] = k
        self.px.grid[sy + i, sx + 2 * i + 1] = k

    def box(
        self, x: Span, y: Span, z: Span, faces: tuple[int, int, int], desk: bool = False
    ) -> None:
        """A solid spanning x, y and z with its three visible faces (top, +y side, +x side) in
        the indices `faces`; `desk` marks the top as the desk surface."""
        (x0, x1), (y0, y1), (z0, z1) = x, y, z
        top, left, right = faces
        self.quad((x0, y1, z0), (x1, y1, z0), (x0, y1, z1), left)
        self.quad((x1, y0, z0), (x1, y1, z0), (x1, y0, z1), right)
        self.quad((x0, y0, z1), (x1, y0, z1), (x0, y1, z1), top, desk)


@design(aspects="any")
def draw(s: Canvas) -> None:
    room = Room()
    g = room.px.grid

    # Floor slab and the two walls: dark planes, only the cut edges pick out the room.
    room.box((0, 32), (0, 32), (-2, 0), (FAINT, DEEP, VOID))
    for y in range(4, 32, 4):  # floor boards
        room.xline((0, y, 0), 32, DEEP)
    room.box((-2, 0), (-2, 32), (-2, 26), (PLANE, DEEP, VOID))
    room.box((0, 32), (-2, 0), (-2, 26), (PLANE, DEEP, VOID))
    room.quad((0, 0, 0), (0, 32, 0), (0, 0, 26), CANVAS)
    room.quad((0, 0, 0), (32, 0, 0), (0, 0, 26), BACK)

    # Window on the left wall: frame, glass, mullions and a few stars.
    room.quad((0, 9, 10), (0, 23, 10), (0, 9, 22), PLANE)
    room.quad((0, 10, 11), (0, 22, 11), (0, 10, 21), VOID)
    room.quad((0, 15.75, 11), (0, 16.25, 11), (0, 15.75, 21), PLANE)
    room.quad((0, 10, 15.75), (0, 22, 15.75), (0, 10, 16.25), PLANE)
    for y, z in ((12, 19), (14, 13.5), (20.5, 13), (19, 19.5)):
        sx, sy = iso((0, y, z))
        g[math.floor(sy), math.floor(sx)] = STAR

    # Desk against the back wall: drawer block, far leg, top.
    room.box((21, 27), (0.5, 11), (0, 13), (PLANE, FAINT, DEEP))
    for z in (4.5, 9):  # drawer seams
        room.xline((21, 11, z), 6, DEEP)
    room.box((5, 6), (9.5, 10.5), (0, 13), (PLANE, FAINT, DEEP))
    room.box((4, 28), (0, 11.5), (13, 14), (PLANE, FAINT, DEEP), desk=True)

    # Monitor: stand, body, screen with left-aligned code lines inset from the bezel.
    room.box((15, 17), (2, 3), (14, 17), (FAINT, FAINT, DEEP))
    room.box((10, 22), (2, 3), (16, 24), (PLANE, PLANE, FAINT))
    room.quad((10.5, 3, 16.5), (21.5, 3, 16.5), (10.5, 3, 23.5), SCREEN)
    for k, (indent, n) in enumerate(((0, 6), (1, 8), (1, 4), (0, 7))):
        x, z = 11.5 + indent, 22.5 - 1.5 * k
        room.quad((x, 3, z), (x + n, 3, z), (x, 3, z + 0.5), CODE)

    # Screen glow as an iso pool on the desk top, straight out from the screen: two dithered
    # steps of a distance in desk-top units, measured on the plane z = 14.
    top = plane(14).inverse().apply(room.centers)
    dx, dy = top[:, 0].reshape(ROWS, COLS), top[:, 1].reshape(ROWS, COLS)
    reach = np.maximum(dy - 3, 1.5 * np.maximum(10.5 - dx, dx - 21.5))
    light = (ramp(reach, 3) + ramp(reach, 5.5)) / 2
    room.px.dither(light, [PLANE, POOL, SPILL], method="bayer", matrix=2, where=room.desk)

    # Keyboard lit along its far edge; mug with a handle on the lit side.
    room.box((11, 20), (5.5, 8.5), (14, 14.5), (RAISED, PLANE, FAINT))
    room.xline((11, 5.5, 14.5), 9, POOL)
    room.box((23, 25.5), (5.5, 8), (14, 17), (RAISED, RAISED, PLANE))
    room.quad((23.5, 6, 17), (25, 6, 17), (23.5, 7.5, 17), COFFEE)
    handle = (((25.5, 26.5), (16, 16.5)), ((25.5, 26.5), (14.5, 15)), ((26.5, 27), (14.5, 16.5)))
    for x, z in handle:  # top bar, bottom bar, outer upright
        room.box(x, (6.5, 7), z, (RAISED, RAISED, PLANE))

    # Right of center on a landscape screen, the upper half on a portrait one.
    c = s.pick(landscape=(0.62, 0.5), portrait=(0.5, 0.42), snap=PX)
    room.px.draw(s, PX, c - (COLS // 2 * PX, ROWS // 2 * PX))
