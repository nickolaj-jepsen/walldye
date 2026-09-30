"""The Pioneer plaque's pulsar map as a line drawing: rays from the Sun with binary period ticks."""

from walldye import ACCENT, UI, UI_ALT, Canvas, P, Vec, design

HYDROGEN = 7.04024e-10  # hyperfine transition period (s), the plaque's unit of time
STEP, TICK, DASH = 6, 10, 4  # bit pitch; a '1' tick across the ray, a '0' dash along it
GAP, EDGE = 26, 140  # clear radius round the Sun; galactic-center line end to the screen edge
SUN_X = 640  # least landscape Sun x, so the rays reaching 522 units left keep a margin
H_R, H_SPAN, H_DROP = 26, 128, 80  # hydrogen glyph: atom radius, atom spacing, offset from line
# (name, galactic longitude deg, ray length px, period s); lengths are composed, not the plaque's distances.
# B0525+21 and the Crab sit 0.7deg apart on the plaque; they are spread to 5deg so the two rays read as two.
PULSARS = [
    ("B1727-47", 342.6, 560, 0.829823),
    ("B1240-64", 302.1, 400, 0.388481),
    ("B1133+16", 241.9, 440, 1.187911),
    ("B0833-45", 263.6, 320, 0.089290),
    ("B0525+21", 181.5, 390, 3.745539),
    ("B0531+21", 186.5, 525, 0.033085),
    ("B0823+26", 197.0, 430, 0.530661),
    ("B0950+08", 228.9, 300, 0.253065),
    ("B1929+10", 47.4, 590, 0.226518),
    ("B1933+16", 52.4, 350, 0.358736),
    ("B1451-68", 313.9, 290, 0.263377),
    ("B1642-03", 14.1, 720, 0.387690),
    ("B2016+28", 68.1, 440, 0.557953),
    ("B1508+55", 91.3, 310, 0.739681),
]


@design(aspects="any")
def draw(s: Canvas) -> None:
    # Landscape: the Sun a third in, the galactic center off to the right. Portrait: the map
    # turned a quarter turn, so that line runs up the tall screen.
    sun = s.pick(landscape=(1 / 3, 0.52), portrait=(0.52, 0.62))
    if s.landscape:
        sun, gc = Vec(max(sun.x, SUN_X), sun.y), Vec(1, 0)
        end = Vec(s.w - EDGE, sun.y)
    else:
        gc = Vec(0, -1)
        end = Vec(sun.x, EDGE)

    rays, code = P(), P()
    for _, lon, length, period in PULSARS:
        u = gc.rotate(deg=-lon)  # longitude runs counter-clockwise on screen
        n = u.perp()
        bits = f"{round(period / HYDROGEN):b}"
        d0 = length - STEP * (len(bits) - 0.5)
        # The ray breaks into the code: '1' a tick across the ray, '0' a short dash along it.
        rays.M(sun + u * GAP).L(sun + u * (d0 - STEP))
        for k, b in enumerate(bits):
            c = sun + u * (d0 + k * STEP)
            if b == "1":
                code.M(c + n * (TICK / 2)).L(c - n * (TICK / 2))
            else:
                code.M(c - u * (DASH / 2)).L(c + u * (DASH / 2))
    s.stroke(rays, UI, 1.2)
    s.stroke(code, UI_ALT, 1.5)
    s.stroke(P().M(sun + gc * GAP).L(end), ACCENT, 2.5)

    # The hydrogen glyph captions the galactic-center line, flush with its end.
    near = end + gc.perp() * H_DROP - gc * H_R
    far = near - gc * H_SPAN
    atoms = P().circle(near, H_R).circle(far, H_R).M(far + gc * H_R).L(near - gc * H_R)
    s.stroke(atoms, UI_ALT, 1.8)
    s.fill(P().circle(near, 4).circle(far, 4), UI_ALT)
    s.fill(P().circle(sun, 11), ACCENT)
