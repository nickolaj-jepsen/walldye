"""Fixture: raw colours, a colour-keyed sort, string path data and a module-level BG."""

from wallgen import ACCENT, BG_ALT, BG_DEEP, UI, P, fmt, mix

BG = BG_DEEP
INK = "#343331"
TONES = [mix(BG_ALT, UI, k / 4) for k in range(5)]


def dot(x, y):
    return f"M{fmt(x)} {fmt(y)}h2v2h-2z"


def draw(s):
    buckets = {}
    for k in range(40):
        tone = TONES[k % 5]
        buckets.setdefault((k % 3, tone), P()).M(20 * k, 100).L(20 * k, 200)
    for (w, tone), d in sorted(buckets.items()):
        s.path(d, fill="none", stroke=tone, stroke_width=w + 1)
    s.path("".join(dot(10 * k, 300) for k in range(10)), fill=ACCENT)
    s.circle(500, 500, 40, fill=INK)
    seen = {id(t) for t in TONES}
    s.circle(600, 500, len(seen), fill=ACCENT)
