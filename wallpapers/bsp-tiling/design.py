"""A tiling window manager's spiral layout: windows cut from each side in turn, winding in to the focused one, as thin outlines."""

from typing import NamedTuple

from walldye import ACCENT, BG, UI, Canvas, P, Path, Rng, design, mix

GAP, EDGE = 20, 72  # gap between windows, margin to the screen edge
SHARE = 0.4  # each cut's window, as a share of the span it cuts
DEPTH = 7  # cuts between the screen and the focused window
PAD, PITCH, BAR, CW = 18, 13, 5, 7  # window padding, line pitch, bar height, char width
BORDER, FOCUS = 2, 3.25  # border widths
# border tones, rising one step per two windows inward
TONES = (mix(BG, UI, 0.55), mix(BG, UI, 0.7), mix(BG, UI, 0.85), UI)
INK = mix(BG, UI, 0.9)
LEFT, TOP, RIGHT, BOTTOM = range(4)  # the side a cut takes its window from


class Win(NamedTuple):
    x: float
    y: float
    w: float
    h: float


def spiral(box: Win, order: tuple[int, ...]) -> tuple[list[Win], Win]:
    """Cut `box` DEPTH times, each cut taking a window of SHARE of the span from the next side
    in `order`, cycling. Returns the windows cut off and the focused window left over."""
    x, y, w, h = box
    out: list[Win] = []
    for k in range(DEPTH):
        side = order[k % len(order)]
        span = w if side in (LEFT, RIGHT) else h
        a = span * SHARE - GAP / 2
        if side == LEFT:
            out.append(Win(x, y, a, h))
            x, w = x + a + GAP, w - a - GAP
        elif side == RIGHT:
            out.append(Win(x + w - a, y, a, h))
            w -= a + GAP
        elif side == TOP:
            out.append(Win(x, y, w, a))
            y, h = y + a + GAP, h - a - GAP
        else:
            out.append(Win(x, y + h - a, w, a))
            h -= a + GAP
    return out, Win(x, y, w, h)


def code(d: Path, win: Win, r: Rng) -> tuple[float, float]:
    """Indented code as bars from the window's top-left, over about three quarters of its lines.
    Returns the top-left of the cell just past the last bar."""
    cols = int((win.w - 2 * PAD) // CW)
    x0, y0 = win.x + PAD, win.y + PAD + (PITCH - BAR) / 2
    end, indent = (x0, y0), 0
    for i in range(int((win.h - 2 * PAD) // PITCH * 0.75)):
        y = y0 + i * PITCH
        if i and r.random() < 0.08:
            continue
        if i:
            indent = max(0, min(2, indent + r.choice((-1, 0, 0, 1, 1))))
        col = indent * 4
        for _ in range(r.randint(1, 3)):
            n = r.randint(2, 8)
            if col + n > cols:
                break
            d.rect(x0 + col * CW, y, n * CW, BAR)
            col += n + 1
            end = (x0 + col * CW, y)
    return end


@design(aspects="any")
def draw(s: Canvas) -> None:
    box = Win(EDGE, EDGE, s.w - 2 * EDGE, s.h - 2 * EDGE)
    # counterclockwise from the long side, so the spiral winds in right of center and high
    wins, focus = spiral(
        box, (LEFT, BOTTOM, RIGHT, TOP) if s.landscape else (TOP, LEFT, BOTTOM, RIGHT)
    )

    b = BORDER / 2
    with s.buckets(TONES, "stroke", stroke_width=BORDER) as borders:
        for k, (x, y, w, h) in enumerate(wins):
            borders[k // 2].rect(x + b, y + b, w - BORDER, h - BORDER)
    text = P()
    cx, cy = code(text, focus, s.rng(9))
    f = FOCUS / 2
    s.fill(text, INK)
    s.fill(P().rect(cx, cy - 3, CW, BAR + 6), UI)  # the cursor
    s.stroke(P().rect(focus.x + f, focus.y + f, focus.w - FOCUS, focus.h - FOCUS), ACCENT, FOCUS)
