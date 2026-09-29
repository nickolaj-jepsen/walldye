"""An xxd dump of an ELF binary in bitmap glyphs, fading at top and bottom, one string selected."""

from walldye import (
    ACCENT,
    ACCENT_7,
    ACCENT_HI,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    Colour,
    P,
    Params,
    Path,
    Rng,
    design,
    knob,
    mix,
    smoothstep,
)
from walldye.pixel import glyphs

PX, FW, FH = 2, 8, 16
CW, CH = FW * PX, FH * PX  # text cell
STR = 0x10F  # string table start; splits the default word as fire|proof across a row break
SIZE = 1024  # bytes generated, more than the tallest screen shows
LIT = (1.0, 0.6, 0.25)  # how far rows 0, 1 and 2 away from the selection brighten
FADE = 6  # tone steps from the top and bottom rows to the middle


class Dump(Params):
    word: str = knob(default="fireproof", max_len=24, doc="the selected string")


def blob(r: Rng, word: bytes) -> bytes:
    """The first SIZE bytes of a plausible x86-64 ELF: header, a program header, code, the
    string table at STR with `word` among its names, then sparse data."""
    hdr = bytes.fromhex(
        "7f454c46020101000000000000000000"
        "03003e00010000004010000000000000"
        "4000000000000000b832000000000000"
        "00000000400038000d00400020001f00"
        "06000000040000004000000000000000"
        "40000000000000004000000000000000"
        "d802000000000000d802000000000000"
        "0800000000000000"
    )
    code = bytes.fromhex("f30f1efa554889e54883ec10897dfc488975f0bf00000000e8")
    code += bytes(r.randrange(256) for _ in range(STR))
    strs = b"\0.symtab\0.strtab\0.shstrtab\0.text\0.data\0.bss\0.rodata\0.comment\0"
    strs += word + b"\0main\0_start\0GCC: (GNU) 14.2.1\0"
    tail = bytes(r.choice([0, 0, 0, r.randrange(256)]) for _ in range(SIZE))
    return ((hdr + code)[:STR] + strs + tail)[:SIZE]


@design(aspects="any")
def draw(s: Canvas[Dump]) -> None:
    # xxd -c 16 on landscape screens, -c 8 on portrait ones: same glyph size, a narrower block
    n = 16 if s.landscape else 8
    hex0, hex1 = 10, 10 + n // 2 * 5 - 1  # hex columns, in groups of two bytes
    asc0 = hex1 + 2  # ASCII columns
    cols, rows = asc0 + n, s.h // CH

    word = s.params.word.encode()
    data = blob(s.rng(5), word)
    lo = data.index(word, STR)  # the string table's copy, even when the header holds it too
    hi = lo + len(word)  # selected bytes [lo, hi); the cursor sits on hi
    # Start the dump so the selection sits a little below the middle row.
    top = max(0, lo // n - round(0.62 * rows))
    base = top * n
    sel_rows = range(lo // n - top, (hi - 1) // n - top + 1)
    lines = []
    for r in range(rows):
        a = base + r * n
        chunk = data[a : a + n]
        hx = " ".join(chunk[k : k + 2].hex() for k in range(0, n, 2))
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{a:08x}: {hx}  {asc}")

    # 0.6125 puts the block's left edge on the first third of a 16:9 screen (x=640)
    c = s.pick(landscape=(0.6125, 0.5), portrait=(0.5, 0.5), snap=PX)
    x0, y0 = c - (cols * CW // 2, rows * CH // 2)

    def cell(a: int) -> tuple[int, int, int]:
        """Row, hex column and ASCII column of byte `a`."""
        r, k = divmod(a - base, n)
        return r, hex0 + k // 2 * 5 + k % 2 * 2, asc0 + k

    def addr(c: int, r: int) -> int | None:
        """Byte address under text cell (c, r), or None for offset and spacing cells."""
        if hex0 <= c < hex1 and (c - hex0) % 5 != 4:
            return base + r * n + (c - hex0) // 5 * 2 + (c - hex0) % 5 // 2
        if asc0 <= c < cols:
            return base + r * n + c - asc0
        return None

    def span(d: Path, r: int, c0: int, c1: int) -> Path:
        """`d` with text cells c0..c1 of row r, inclusive, added as one rect."""
        return d.rect(x0 + c0 * CW, y0 + r * CH, (c1 - c0 + 1) * CW, CH)

    # selection: one rect per row across the hex groups and one across the ASCII gutter
    band = P()
    for r in sel_rows:
        a0, a1 = max(lo, base + r * n), min(hi, base + (r + 1) * n) - 1
        (_, h0, g0), (_, h1, g1) = cell(a0), cell(a1)
        span(span(band, r, h0, h1 + 1), r, g0, g1)
    s.fill(band, ACCENT_7)
    r, h, g = cell(hi)
    s.fill(span(span(P(), r, h, h + 1), r, g, g), ACCENT_HI)

    def paint(c: int, r: int, _ch: str) -> Colour | None:
        a = addr(c, r)
        if a is not None and lo <= a < hi:
            return ACCENT
        if a == hi:
            return BG  # knocked out of the cursor block
        edge = min(r + 0.5, rows - r - 0.5) / (rows / 2)
        step = round(smoothstep(0.05, 0.95, edge) * FADE)
        if step == 0:
            return None  # the outermost rows would sit within a few levels of BG; skip them
        near = min(abs(r - k) for k in sel_rows)
        lit = LIT[near] if near < len(LIT) else 0  # the dump brightens around the selection
        if c < hex0:
            tone = mix(BG_ALT, UI, 0.2)
        elif c >= asc0:
            tone = mix(mix(BG_ALT, UI, 0.6), UI, lit)
        else:
            tone = mix(UI, UI_ALT, lit)
        return mix(BG, tone, 0.1 + 0.9 * step / FADE)

    glyphs(s, lines, paint, at=(x0, y0), font="8x16", px=PX)
