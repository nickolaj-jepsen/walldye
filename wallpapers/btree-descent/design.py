"""A B+-tree index as a textbook diagram of pointer and key cells; the pointers a lookup of key 417 follows are filled in from root to leaf."""

from walldye import ACCENT, BG, UI, UI_ALT, UI_HI, Canvas, P, Paint, Vec, design
from walldye.pixel import glyphs

KW, PW, CH = 36, 10, 28  # key cell width, pointer cell width, node height
LEAF_SIZES = (2, 3, 2, 2, 3, 2, 3, 2, 2)  # keys per leaf, three leaves under each inner node
LEAF_GAP, DOT = 22, 2.2
TARGET = 417


def node_w(n: int) -> float:
    """The width of a node holding `n` keys between n + 1 pointer cells."""
    return n * (KW + PW) + PW


@design(aspects="any")
def draw(s: Canvas) -> None:
    rng = s.rng(11)
    pool = [k for k in range(104, 990) if k != TARGET]
    rest = sorted([*rng.sample(pool, sum(LEAF_SIZES) - 1), TARGET])
    leaves: list[list[int]] = []
    for n in LEAF_SIZES:
        leaves.append(rest[:n])
        rest = rest[n:]
    # separators: the first key of every child after the first
    inner = [[leaf[0] for leaf in leaves[3 * g + 1 : 3 * g + 3]] for g in range(3)]
    root = [leaves[3][0], leaves[6][0]]

    # the B+-tree search: at each level, one child to the right per separator not above TARGET
    ri = sum(TARGET >= k for k in root)
    ii = sum(TARGET >= k for k in inner[ri])
    li = 3 * ri + ii

    lit, edges, boxes, hot, links = P(), P(), P(), P(), P()
    dots, lit_dots = P(), P()
    labels: list[tuple[Vec, str, Paint]] = []  # key cell center, text, paint

    def node(
        x: float, y: float, keys: list[int], ptr: int | None = None, key: int | None = None
    ) -> list[Vec]:
        """Lay out the cells p k p k ... p of a node with its top-left corner at (x, y), filling
        in pointer number `ptr` or the cell of key `key`; returns the pointer cell centers."""
        ptrs: list[Vec] = []
        cx = x
        for i in range(2 * len(keys) + 1):
            w = KW if i % 2 else PW
            if i:
                boxes.M(cx, y).V(y + CH)
            c = Vec(cx + w / 2, y + CH / 2)
            if i % 2:
                k = keys[i // 2]
                if k == key:
                    lit.rect(cx, y, w, CH)
                labels.append((c, f"{k:03d}", BG if k == key else UI_HI))
            else:
                on = len(ptrs) == ptr
                if on:
                    lit.rect(cx, y, w, CH)
                (lit_dots if on else dots).circle(c, DOT)
                ptrs.append(c)
            cx += w
        boxes.rect(x, y, cx - x, CH)
        return ptrs

    # The leaf row is wider than a portrait screen: there the root moves right so the whole
    # lookup path fits, and the tree runs off the edge mid-way through the seventh leaf.
    root_top = s.pick(landscape=(0.5, 0.25), portrait=(0.75, 0.32), snap=1)
    step = 250 if s.landscape else 300  # between the tops of two rows
    rows = [root_top.y + k * step for k in range(3)]
    total = sum(node_w(n) for n in LEAF_SIZES) + LEAF_GAP * (len(LEAF_SIZES) - 1)
    x = root_top.x - total / 2
    leaf_x: list[float] = []
    for n in LEAF_SIZES:
        leaf_x.append(x)
        x += node_w(n) + LEAF_GAP
    pairs = list(zip(leaf_x, leaves, strict=True))
    leaf_tops = [Vec(lx + node_w(len(keys)) / 2, rows[2]) for lx, keys in pairs]
    leaf_ptrs = [
        node(lx, rows[2], keys, key=TARGET if i == li else None)
        for i, (lx, keys) in enumerate(pairs)
    ]

    # inner nodes centered over their three leaves; each edge leaves from a pointer cell's foot
    inner_tops: list[Vec] = []
    for g, seps in enumerate(inner):
        kids = leaf_tops[3 * g : 3 * g + 3]
        top = Vec(sum(k.x for k in kids) / 3, rows[1])
        inner_tops.append(top)
        ptrs = node(top.x - node_w(len(seps)) / 2, top.y, seps, ptr=ii if g == ri else None)
        for c, (p, kid) in enumerate(zip(ptrs, kids, strict=True)):
            (hot if g == ri and c == ii else edges).M(p + (0, CH / 2)).L(kid)
    ptrs = node(root_top.x - node_w(len(root)) / 2, rows[0], root, ptr=ri)
    for c, (p, kid) in enumerate(zip(ptrs, inner_tops, strict=True)):
        (hot if c == ri else edges).M(p + (0, CH / 2)).L(kid)

    # each leaf's last pointer links to the next leaf, ending in an open arrowhead
    for lp, nx in zip(leaf_ptrs[:-1], leaf_x[1:], strict=True):
        p, tip = lp[-1], nx - 3
        links.M(p.x + 5, p.y).H(tip).M(tip - 5, p.y - 4).L(tip, p.y).L(tip - 5, p.y + 4)

    s.fill(lit, ACCENT)
    s.stroke(edges, UI, 1.2)
    s.stroke(boxes, UI_ALT, 1)
    s.stroke(hot, ACCENT, 2)
    s.stroke(links, UI_ALT, 1.2)
    s.fill(dots, UI_ALT)
    s.fill(lit_dots, BG)
    for c, text, paint in labels:
        glyphs(s, text, paint, at=(round(c.x), c.y - 8), font="8x16", px=1, anchor="middle")

    # the record id each leaf key points at, under its cell
    rids = s.rng(5)
    for i, (lx, keys) in enumerate(pairs):
        for k, key in enumerate(keys):
            cx = round(lx + PW + k * (KW + PW) + KW / 2)
            paint = UI_HI if i == li and key == TARGET else UI_ALT
            rid = f"{rids.randrange(16, 255):02x}"
            glyphs(s, rid, paint, at=(cx, rows[2] + CH + 14), font="5x8", px=1, anchor="middle")
    glyphs(
        s,
        f"find({TARGET})",
        UI_HI,
        at=(root_top.x, rows[0] - 48),
        font="5x8",
        px=2,
        anchor="middle",
    )
