"""Three overlapping discs of fine parallel stripes, each turned a few degrees, so the overlap shimmers into moire."""

from shapely.geometry import Point

from walldye import ACCENT_1, BG, BG_ALT, UI, Canvas, P, design
from walldye.geom import hatch

PITCH, STRIPE = 10, 5  # stripe spacing across the lines, and stripe width
# Back to front: center offset from the largest disc, radius, stripe angle (deg), paint, and the
# width of the bare ring knocked out around the disc (0 for none).
DISCS = (
    ((0, 0), 270, 0, UI, 0),
    ((180, 130), 200, 8, BG_ALT, 0),
    ((-100, 235), 150, -4, ACCENT_1, 3),
)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the largest disc's center: right of center on a desktop, under the clock on a phone
    anchor = s.pick(landscape=(0.65, 0.435), portrait=(0.45, 0.55))
    for offset, r, deg, paint, gap in DISCS:
        c = anchor + offset
        if gap:
            s.fill(P().circle(c, r + gap), BG)
        with s.clip() as disc:
            disc.add(P().circle(c, r))
        lines = P()
        for seg in hatch(Point(c).buffer(r + STRIPE), PITCH, deg=deg):
            lines.poly(seg)
        with s.group(clip_path=disc.ref):
            s.stroke(lines, paint, STRIPE)
