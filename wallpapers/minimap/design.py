"""An editor minimap at wallpaper scale: made-up code as rounded bars, a lit viewport band and one identifier picked out under the caret."""

from typing import NamedTuple

from walldye import (
    ACCENT,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Ref,
    Rng,
    Stop,
    design,
    mix,
    smoothstep,
)

CW, PITCH, BAR, R = 6, 14, 7, 1.5  # char width, line pitch, bar height, bar corner radius
COLS = 100  # minimap width in characters; longer lines are cut at its right edge
RIGHT = 760  # the column's left edge stays at least this far from the canvas's right edge
HALF = 9  # the viewport shows 2 * HALF lines, centered on the caret line
COMMENT, IDENT, KEYWORD, STRING, CALL = range(5)  # token kinds, indices into the tone tables
KINDS = (COMMENT, IDENT, KEYWORD, STRING, CALL)
TONES = (mix(BG_ALT, UI, 0.45), UI, UI_ALT, mix(UI, UI_ALT, 0.5), UI_ALT)
# inside the viewport each kind steps up one tone, so the slab reads as lit rather than fogged
LIT = (UI, UI_ALT, mix(UI_ALT, UI_HI, 0.55), mix(UI_ALT, UI_HI, 0.3), mix(UI_ALT, UI_HI, 0.55))

type Spec = list[tuple[int, int, int]]  # (kind, length, gap after) per token


class Tok(NamedTuple):
    col: int
    n: int  # length in characters
    kind: int


class Code:
    """Pseudo-Python as lines of tokens, drawn from `r` in a fixed order."""

    def __init__(self, r: Rng) -> None:
        self.r = r
        self.lines: list[list[Tok]] = []

    def line(self, indent: int, spec: Spec) -> None:
        """Append one line, indented by four columns a level."""
        col = indent * 4
        toks: list[Tok] = []
        for kind, n, gap in spec:
            toks.append(Tok(col, n, kind))
            col += n + gap
        self.lines.append(toks)

    def ident(self, lo: int = 3, hi: int = 12) -> int:
        return self.r.randint(lo, hi)

    def expr(self, depth: int = 0) -> Spec:
        """Tokens of an expression: names, calls with arguments, string literals."""
        r = self.r
        out: Spec = []
        for _ in range(r.choice([1, 1, 2, 3])):
            roll = r.random()
            if roll < 0.3 and depth < 1:
                out.append((CALL, self.ident(4, 14), 1))
                out += self.expr(depth + 1)
            elif roll < 0.5:
                out.append((STRING, r.randint(4, 22), 2))
            else:
                out.append((IDENT, self.ident(), 2))
        return out

    def statement(self, ind: int) -> None:
        r = self.r
        roll = r.random()
        if roll < 0.08:
            self.line(ind, [(COMMENT, r.randint(12, 60), 0)])
        elif roll < 0.5:
            self.line(ind, [(IDENT, self.ident(), 3), *self.expr()])
        elif roll < 0.7:
            self.line(ind, [(CALL, self.ident(6, 18), 1), *self.expr(1)])
        else:
            self.line(ind, [(KEYWORD, 6, 1), *self.expr()])

    def block(self, ind: int, n: int, depth: int = 0) -> None:
        r = self.r
        for _ in range(n):
            if depth < 3 and r.random() < 0.22:
                self.line(ind, [(KEYWORD, r.choice([2, 3, 5]), 1), *self.expr(), (IDENT, 1, 0)])
                self.block(ind + 1, r.randint(1, 4), depth + 1)
                if r.random() < 0.3:
                    self.line(ind, [(KEYWORD, 4, 1)])
                    self.block(ind + 1, r.randint(1, 3), depth + 1)
            else:
                self.statement(ind)

    def function(self, ind: int) -> None:
        r = self.r
        head = [(KEYWORD, 3, 1), (CALL, self.ident(5, 16), 1)]
        self.line(ind, head + [(IDENT, self.ident(3, 8), 2) for _ in range(r.randint(1, 4))])
        if r.random() < 0.6:
            self.line(ind + 1, [(STRING, r.randint(20, 64), 0)])
        self.block(ind + 1, r.randint(3, 10))
        self.line(ind + 1, [(KEYWORD, 6, 1), *self.expr()])
        self.lines.append([])

    def module(self, n: int) -> list[list[Tok]]:
        """The first `n` lines of a module: imports, then functions and classes of methods."""
        r = self.r
        for _ in range(r.randint(3, 6)):
            name, alias = self.ident(), self.ident()
            self.line(0, [(KEYWORD, 4, 1), (IDENT, name, 1), (KEYWORD, 6, 1), (IDENT, alias, 0)])
        self.lines += [[], []]
        while len(self.lines) < n:
            if r.random() < 0.3:
                self.line(0, [(KEYWORD, 5, 1), (CALL, self.ident(6, 14), 0)])
                for _ in range(r.randint(2, 4)):
                    self.function(1)
            else:
                self.function(0)
            self.lines.append([])
        return self.lines[:n]


def extent(toks: list[Tok]) -> int:
    """The column just past the line's last token; 0 for an empty line."""
    return max((t.col + t.n for t in toks), default=0)


def caret_token(toks: list[Tok]) -> int | None:
    """Index of the first mid-length identifier after the line's first token, if any."""
    return next((j for j, t in enumerate(toks) if j and t.kind == IDENT and 5 <= t.n <= 12), None)


def fits(toks: list[Tok]) -> bool:
    """Whether the line can carry the caret: indented, three to five visible tokens, medium
    width, with an identifier to pick out."""
    shown = [t for t in toks if t.n * CW > BAR]
    return (
        bool(toks)
        and toks[0].col >= 8
        and 3 <= len(shown) <= 5
        and 24 <= extent(toks) <= 44
        and caret_token(toks) is not None
    )


@design(aspects="any")
def draw(s: Canvas) -> None:
    # right of center, but never nearer than RIGHT to the right edge (1160 at 16:9); low on portrait
    at = s.pick(landscape=(0.605, 7 / 15), portrait=(0.3, 0.58))
    x0, cursor = min(round(at.x), s.w - RIGHT), round(at.y / PITCH)
    view0, view1 = (cursor - HALF) * PITCH, (cursor + HALF) * PITCH
    n = s.h // PITCH + 1
    code = Code(s.rng(11)).module(n + 60)
    # scroll so a medium line of a few tokens sits mid-viewport; its identifier is under the caret
    top = next(k - cursor for k in range(cursor + 10, len(code) - n + cursor) if fits(code[k]))
    lines = code[top : top + n]

    def inside(i: int) -> bool:
        return view0 <= i * PITCH < view1

    right = max(extent(t) for i, t in enumerate(lines) if inside(i))
    slab = P().rect(x0 - 18, view0, min(right, COLS) * CW + 36, view1 - view0)
    s.fill(slab, mix(BG, BG_ALT, 0.8))

    m = round(12 * s.h / 1080)  # gradient stops, 90 units apart

    def fade(k: int) -> Ref:
        """TONES[k] at full strength around the viewport, sinking toward the ground at the top and
        bottom of the sheet."""
        mid = (view0 + view1) / 2
        stops: list[Stop] = []
        for j in range(m + 1):
            beyond = abs(s.h * j / m - mid) - HALF * PITCH  # distance past the viewport's edge
            stops.append((j / m, mix(TONES[k], BG, 0.85 * smoothstep(0, 440, beyond))))
        return s.linear_gradient(stops, (0, 0), (0, s.h))

    # bucket 2k holds kind k outside the viewport (faded), 2k + 1 inside it (lit)
    paints = [p for k in KINDS for p in (fade(k), LIT[k])]
    caret = P()
    sel = caret_token(lines[cursor])
    with s.buckets(paints, "fill") as bars:
        for i, toks in enumerate(lines):
            y = i * PITCH + (PITCH - BAR) / 2
            for j, t in enumerate(toks):
                x, w = x0 + t.col * CW, min(t.n, COLS - t.col) * CW
                if w <= BAR:
                    continue
                if i == cursor and j == sel:
                    caret.rrect(x, y, w, BAR, R).rect(x + w + 3, i * PITCH, 2, PITCH)
                else:
                    bars[2 * t.kind + int(inside(i))].rrect(x, y, w, BAR, R)
    s.fill(caret, ACCENT)
