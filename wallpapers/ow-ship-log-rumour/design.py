"""The Outer Wilds ship log in rumour mode: cards at their in-game positions, explored ones holding Bayer-dithered photos, joined by arrowed links."""

import numpy as np
from numpy.typing import NDArray

from walldye import (
    ACCENT,
    BG,
    BG_ALT,
    BG_DEEP,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Rect,
    Vec,
    clamp,
    design,
    mix,
)
from walldye.pixel import dither, glyphs, grid_runs, text_width

type Card = tuple[float, float, tuple[str, ...], str | None, bool]

# id: (rumour-mode position x, y (y up), title lines, parent card, explored), from the game's layout.
CARDS: dict[str, Card] = {
    "TH_VILLAGE": (1479, 908, ("Village",), None, True),
    "TH_ZERO_G_CAVE": (1547, 822, ("Zero-G Cave",), "TH_VILLAGE", True),
    "GD_GABBRO_ISLAND": (1378, 563, ("Gabbro's", "Island"), None, False),
    "TM_ESKER": (1716, 1222, ("Esker's Camp",), None, False),
    "TM_EYE_LOCATOR": (1957, 1010, ("Eye Signal", "Locator"), None, True),
    "BH_RIEBECK": (2241, 1104, ("Riebeck's", "Camp"), None, False),
    "BH_OBSERVATORY": (2423, 843, ("Southern", "Observatory"), None, True),
    "ORBITAL_PROBE_CANNON": (1941, 610, ("Orbital Probe", "Cannon"), None, False),
}
# Rumour links revealed by the explored entries, source first.
EDGES = (
    ("TH_VILLAGE", "GD_GABBRO_ISLAND"),
    ("TH_VILLAGE", "TM_ESKER"),
    ("TH_VILLAGE", "TM_EYE_LOCATOR"),
    ("TM_EYE_LOCATOR", "BH_OBSERVATORY"),
    ("TM_EYE_LOCATOR", "BH_RIEBECK"),
    ("BH_OBSERVATORY", "ORBITAL_PROBE_CANNON"),
)

S = 1.17  # px per layout unit
MID = (1900, 916)  # layout point placed just above the canvas centre
PHOTO = 44  # side of the game's card photos, in pixels
PHOTO_LEVELS = (None, UI, UI_ALT, UI_HI, MUTED)  # index 0 lets the BG_DEEP well show
CHEVRON = ((11, 0), (-8, 15), (-2, 0), (-8, -15))  # (along, across) the link
LEGEND = (("Map Mode", "C"), ("Zoom View", "L Shift"), ("Leave Ship Log", "Q"))
FAINT = mix(BG, BG_ALT, 0.55)
LINK = mix(UI_ALT, UI_HI, 0.5)


def card_box(key: str, anchor: Vec) -> tuple[Rect, int, int]:
    """The card's outline (a header above a square photo well), its header height and its
    photo cell; child cards are drawn at 0.6x."""
    x, y, _, parent, _ = CARDS[key]
    c = anchor + Vec(x - MID[0], MID[1] - y) * S
    w, hh, cell = (80, 30, 2) if parent else (132, 48, 3)
    return Rect(round(c.x - w / 2), round(c.y - (w + hh) / 2), w, hh + w), hh, cell


def photo(s: Canvas, raw: NDArray[np.int64], well: Rect, cell: int) -> None:
    """The card photo resampled to the well, contrast-stretched and Bayer-dithered."""
    n = int(well.w) // cell
    idx = (np.arange(n) * PHOTO / n).astype(int)
    ranked = np.sort(raw, axis=None)
    lo, hi = ranked[ranked.size // 50], ranked[-ranked.size // 100]
    tone = clamp((raw[np.ix_(idx, idx)] - lo) / (hi - lo)) ** 1.2
    levels = dither(tone, len(PHOTO_LEVELS), method="bayer", matrix=4)
    grid_runs(s, levels, PHOTO_LEVELS, cell, (well.x, well.y))


def legend(s: Canvas, right: float, y: float) -> None:
    """The key legend: 'label [key]' pairs, right-aligned at `right` and centred on `y`."""
    parts: list[tuple[float, str, float, str]] = []
    x = 0.0
    for label, key in LEGEND:
        lw = text_width(label, font="5x8", px=2)
        parts.append((x, label, x + lw + 16, key))
        x += lw + 16 + text_width(key, font="5x8", px=2) + 20 + 48
    x0 = right - (x - 48)
    caps = P()
    for _, _, kx, key in parts:
        caps.rect(x0 + kx, y - 16, text_width(key, font="5x8", px=2) + 20, 32)
    s.fill(caps, UI)
    for lx, label, kx, key in parts:
        glyphs(s, label, UI_HI, at=(x0 + lx, y - 8), font="5x8", px=2)
        glyphs(s, key, MUTED, at=(x0 + kx + 10, y - 8), font="5x8", px=2)


# 16:9 only: the cards keep their real rumour-mode spacing under a screen-wide legend.
@design()
def draw(s: Canvas) -> None:
    photos: dict[str, list[str]] = s.data("photos.json")
    anchor = s.center - (0, 18)

    # Ship-log backdrop: a sparse grid, the centre crosshair and the screen frame.
    grid = P()
    for k in (1, 2, 4, 5):
        grid.rect(k * s.w / 6, 0, 1, s.h)
    s.fill(grid, FAINT)
    s.fill(P().rect(0, s.h / 2, s.w, 2).rect(s.w / 2 - 1, 0, 2, s.h), BG_ALT)
    s.stroke(P().rect(*s.inset(12)), BG_ALT, 2)
    legend(s, s.w - 48, 64)

    links, heads = P(), P()
    for a, b in EDGES:
        pa, pb = card_box(a, anchor)[0].center, card_box(b, anchor)[0].center
        u = (pb - pa).unit()
        mid = (pa + pb) / 2
        links.M(pa).L(pb)
        heads.poly([mid + u * p + u.perp() * q for p, q in CHEVRON], closed=True)
    s.stroke(links, LINK, 5)
    s.fill(heads, LINK)

    # Child cards overlap their parents, so they go last.
    for key in sorted(CARDS, key=lambda k: CARDS[k][3] is not None):
        box, hh, cell = card_box(key, anchor)
        _, _, title, parent, explored = CARDS[key]
        well = Rect(box.x, box.y + hh, box.w, box.w)
        s.fill(P().rect(box.x - 2, box.y - 2, box.w + 4, box.h + 4), UI_HI if explored else MUTED)
        s.fill(P().rect(*well), BG_DEEP)
        if explored:
            rows = np.frombuffer(bytes.fromhex("".join(photos[key])), dtype=np.uint8)
            photo(s, rows.reshape(PHOTO, PHOTO).astype(np.int64), well, cell)
        else:
            at = (well.x + (well.w - 48) / 2, well.y + (well.h - 96) / 2)
            glyphs(s, "?", ACCENT, at=at, font="8x16", px=6)
        fpx = 1 if parent else 2
        top = box.y + (hh - len(title) * 10 * fpx + 2 * fpx) / 2
        for i, line in enumerate(title):
            left = box.x + (box.w - text_width(line, font="5x8", px=fpx)) // 2
            glyphs(s, line, BG, at=(left, top + i * 10 * fpx), font="5x8", px=fpx)
