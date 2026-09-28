"""Map view: a smelting base's pollution cloud as an exponential falloff stepped chunk by chunk, lighting the biter bases it reaches."""

import numpy as np

from walldye import (
    ACCENT,
    ACCENT_4,
    ACCENT_5,
    ACCENT_6,
    ACCENT_7,
    ACCENT_8,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    NpRng,
    Params,
    Vec,
    design,
    knob,
    mix,
)
from walldye.pixel import grid_runs

T = 4  # canvas units per tile
CHUNK = 32  # tiles per chunk
CELL = 4  # tiles per overlay step; the map blends chunk values, so cloud edges stair-step inside chunks
# Map coordinates are tiles from the emitter, x toward the nests. The emitter sits 28 tiles
# east and 8 south of its chunk's corner, and the window spans chunks KX by KY around it.
CORNER = (-28, -8)
KX, KY = (-6, 16), (-7, 8)
CX, CY = (-4, 13), (-4, 6)  # the core: the chunks a 16:9 screen shows, plus a margin
LEVELS = (0.045, 0.12, 0.28, 0.55)  # overlay steps; the first also marks a nest as reached
CLOUD = (None, ACCENT_8, ACCENT_7, ACCENT_6, mix(ACCENT_6, ACCENT_5, 0.5))

BELT, INS, FURNACE, ASM, DRILL = range(5)
KINDS = (UI_HI, UI, mix(UI_HI, MUTED, 0.45), UI_ALT, UI_ALT)

# biter bases: centre, spawner offsets (5x5 tiles), worm offsets (2x2 tiles)
NESTS = (
    ((144, -64), ((0, 0), (8, -4), (4, 7), (-7, 5)), ((-10, -4), (13, 6))),
    ((174, 36), ((0, 0), (-8, 3), (5, 8)), ((9, -5), (-4, -8), (-12, 12))),
    ((268, 96), ((0, 0), (7, 2), (-2, -7), (-8, 3)), ((4, 9), (-12, -4))),
)

Rect = tuple[int, int, int, int]


class Cloud(Params):
    spread: float = knob(default=1.25, lo=0.8, hi=2, unit="chunks", doc="falloff length")
    east: float = knob(default=0.55, lo=0, hi=2, doc="extra reach toward the nests")


def factory() -> list[tuple[Rect, int]]:
    """The base's entities as ((x, y, w, h), kind) in map tiles, kind one of BELT .. DRILL."""
    ents: list[tuple[Rect, int]] = []

    def add(x: int, y: int, w: int, h: int, kind: int) -> None:
        ents.append(((x - 22, y - 23, w, h), kind))

    # smelting column: ore belt | ins | furnace | ins | plate belt | ins | furnace | ins | ore belt
    for x in (0, 10):
        add(x, 0, 1, 48, BELT)
    add(5, -1, 1, 25, BELT)
    for k in range(12):
        for fx in (2, 7):
            add(fx, 2 * k, 2, 2, FURNACE)
        for ix in (1, 4, 6, 9):
            add(ix, 2 * k, 1, 1, INS)
    # plate belt leaves the column's head and drops down the side of the assembler block
    add(6, -1, 8, 1, BELT)
    add(14, -1, 1, 26, BELT)
    # assembler rows: belt, ins, 3x3 assemblers at a 4-tile pitch, ins, next belt
    for r in range(5):
        add(15, 6 * r, 25, 1, BELT)
    for r in range(4):
        y = 6 * r + 2
        for c in range(6):
            x = 16 + 4 * c
            add(x, y, 3, 3, ASM)
            add(x + 1, y - 1, 1, 1, INS)
            add(x + 1, y + 3, 1, 1, INS)
    # drills paired either side of each ore line on the patch south of the furnaces
    for x in (0, 10):
        for k in range(7):
            add(x - 3, 27 + 3 * k, 3, 3, DRILL)
            add(x + 1, 27 + 3 * k, 3, 3, DRILL)
    # outlying ore patch to the west, belted in along one line
    for k in range(5):
        for j in range(2):
            add(-32 + 4 * k, 35 + 4 * j, 3, 3, DRILL)
    add(-32, 42, 26, 1, BELT)
    add(-7, 25, 1, 18, BELT)
    # plates leave east toward an outpost
    add(34, 6, 34, 1, BELT)
    add(68, 6, 1, 16, BELT)
    for k in range(3):
        add(69 + 4 * k, 17, 3, 3, ASM)
    return ents


def pollution(spread: float, east: float, rng: NpRng) -> np.ndarray:
    """Pollution per CELL step over the KX by KY chunk window: an exponential falloff from the
    emitter, stretched east where the forest thins toward the nests, jittered per chunk and
    blended across chunk borders only."""
    xs = np.arange(*KX) * CHUNK + CORNER[0] + CHUNK / 2
    ys = np.arange(*KY) * CHUNK + CORNER[1] + CHUNK / 2
    dx, dy = np.meshgrid(xs / CHUNK, ys / CHUNK)
    d = np.hypot(dx, dy)
    toward = np.clip(dx / np.maximum(d, 1e-6), 0, 1)
    # the core draws its jitter first, so its cloud stays put however far the window reaches
    core = rng.uniform(0.82, 1.18, (CY[1] - CY[0], CX[1] - CX[0]))
    jitter = rng.uniform(0.82, 1.18, d.shape)
    jitter[CY[0] - KY[0] : CY[1] - KY[0], CX[0] - KX[0] : CX[1] - KX[0]] = core
    v = np.exp(-d / (1 + east * toward) / spread) * jitter
    ch, cw = v.shape
    n = CHUNK // CELL
    gy, gx = np.mgrid[0 : ch * n, 0 : cw * n]
    fx, fy = (gx + 0.5) / n - 0.5, (gy + 0.5) / n - 0.5
    x0 = np.clip(np.floor(fx).astype(int), 0, cw - 2)
    y0 = np.clip(np.floor(fy).astype(int), 0, ch - 2)
    # bilinear, sharpened so each chunk stays flat except in a band at its border
    tx, ty = (np.clip((np.clip(t, 0, 1) - 0.5) * 2.5 + 0.5, 0, 1) for t in (fx - x0, fy - y0))
    return (
        v[y0, x0] * (1 - tx) * (1 - ty)
        + v[y0, x0 + 1] * tx * (1 - ty)
        + v[y0 + 1, x0] * (1 - tx) * ty
        + v[y0 + 1, x0 + 1] * tx * ty
    )


@design(aspects="any")
def draw(s: Canvas[Cloud]) -> None:
    # the scene is centred, with the nests east, or south on a portrait screen, where the whole
    # map turns a quarter clockwise; the emitter snaps to the overlay's cells, in canvas tiles
    e = s.center + (Vec(-336, 4) if s.landscape else Vec(32, -300))
    ex, ey = round(e.x / (T * CELL)) * CELL, round(e.y / (T * CELL)) * CELL

    def place(x: int, y: int, w: int, h: int) -> Rect:
        """A map rect in canvas tiles."""
        if s.landscape:
            return ex + x, ey + y, w, h
        return ex - y - h, ey + x, h, w

    f = pollution(s.params.spread, s.params.east, s.np_rng(7))
    lvl = np.digitize(f, LEVELS)
    x0, y0 = KX[0] * CHUNK + CORNER[0], KY[0] * CHUNK + CORNER[1]
    ox, oy, _, _ = place(x0, y0, lvl.shape[1] * CELL, lvl.shape[0] * CELL)
    grid_runs(s, lvl if s.landscape else np.rot90(lvl, -1), CLOUD, T * CELL, (ox * T, oy * T))

    with s.buckets(KINDS, "fill") as b:
        for (x, y, w, h), kind in factory():
            px, py, pw, ph = place(x, y, w, h)
            # the map merges touching machines; a hairline keeps them countable
            inset = 1 if kind >= FURNACE else 0
            b[kind].rect(px * T, py * T, pw * T - inset, ph * T - inset)

    nests = np.zeros((s.h // T, s.w // T), int)
    for (cx, cy), spawners, worms in NESTS:
        # a base reads as reached when its centre cell is inside the cloud
        k = 1 if f[(cy - y0) // CELL, (cx - x0) // CELL] > LEVELS[0] else 2
        for dx, dy in spawners:
            px, py, pw, ph = place(cx + dx - 2, cy + dy - 2, 5, 5)
            nests[py : py + ph, px : px + pw] = k
        for dx, dy in worms:
            px, py, pw, ph = place(cx + dx, cy + dy, 2, 2)
            nests[py : py + ph, px : px + pw] = k
    grid_runs(s, nests, [None, ACCENT, ACCENT_4], T)
