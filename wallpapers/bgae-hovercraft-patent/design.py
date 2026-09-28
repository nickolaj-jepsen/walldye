"""A patent sheet of Pey'j's hovercraft in side, rear and plan views with numbered leaders; outlines traced from in-game shots, only the boost lamp lit."""

from shapely import Point

from walldye import (
    ACCENT,
    ACCENT_6,
    BG,
    MUTED,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Paint,
    Path,
    Vec,
    design,
    polar,
)
from walldye.geom import Affine, Polyline, hatch
from walldye.pixel import glyphs

HIDDEN = (10, 6)  # hidden-line dash
CENTRE = (24, 6, 4, 6)  # centreline dash-dot

# Craft units (~px of the side_zoom shot), y up from the float bottom, bow at x=0,
# z to starboard. Side from side_zoom, stern from rear_zoom, plan from race_zoom.
LEN, FLOAT_H = 1140, 175  # float tube length and diameter
HALF_W = 393  # float half-width
CAP = 190  # ribbed cap length at each end of the float
CABIN = (
    (400, 175),
    (400, 440),
    (418, 460),
    (830, 460),
    (884, 434),
    (940, 364),
    (994, 276),
    (1034, 175),
)
CREST = CABIN[4:]  # the aft slope the sawtooth crest runs down
DRUM = (360, 756, 150, 370)  # x0, x1, y0, y1
DRUM_Z = (115, 255)
PORT = (808, 392, 34)  # x, y, radius
PROP_X, PROP_HUB, PROP_R, HUB_Z = 700, 490, 165, 300

K = 0.55  # craft units to canvas
X1, WL = 210, 470  # FIG. 1 bow x, waterline (FIG. 2 shares WL)
X3 = 1390  # FIG. 2 centre
Y2 = 780  # FIG. 3 centreline, projected under FIG. 1, clear of the sheet border


def view(x: float, y: float, flip: bool) -> Affine:
    """Craft units to canvas for one figure: scaled by K from origin (x, y), y upwards if `flip`."""
    return Affine.translate(x, y) @ Affine.scale(K, -K if flip else K)


SIDE = view(X1, WL, True)  # FIG. 1, (x, y)
REAR = view(X3, WL, True)  # FIG. 2, (z, y) seen from astern
PLAN = view(X1, Y2, False)  # FIG. 3, (x, z) seen from above

# The pig decal on a unit disc, y down, snout to the bow, after a near face-on shot: ear flopped
# forward, flat snout, one leg reaching ahead, one tucked under, tail up. Kept clear of the rim.
PIG = (
    (-0.51, -0.64),  # ear tip
    (-0.32, -0.55),
    (0.52, -0.31),  # back, down to the tail root
    (0.76, -0.41),  # tail tip
    (0.64, -0.22),
    (0.43, 0.33),  # rump, round to the hock
    (0.48, 0.47),
    (0.25, 0.65),  # hind hoof
    (0.16, 0.5),
    (-0.38, 0.36),  # belly
    (-0.46, 0.28),
    (-0.54, 0.38),  # fore hoof
    (-0.7, 0.2),
    (-0.57, 0.13),
    (-0.61, -0.19),  # jaw
    (-0.76, -0.21),  # snout
    (-0.75, -0.4),
    (-0.6, -0.45),  # brow
)
PIG_CURVES = {5: (0.76, 0.12), 9: (-0.1, 0.56)}  # vertex: control of the curve that ends there
PIG_EYE = (-0.43, -0.4)
LEGEND = (
    "FLOAT",
    "CABIN",
    "PORTHOLE",
    "MOTOR DRUM",
    "BOOST LAMP",
    "PROPELLER",
    "CREST",
    "CANNON",
    "EMBLEM",
    "GATLING POD",
)

type XY = tuple[float, float]
type Mark = tuple[XY, int, Vec]  # ring marker centre, legend number, leader target


def rbox(d: Path, m: Affine, x0: float, x1: float, y0: float, y1: float, r: float = 0) -> Path:
    """Append to `d` the craft-unit box x0..x1 by y0..y1 under figure `m`, corners rounded by `r`."""
    a, b = m((x0, y0)), m((x1, y1))
    return d.rrect(min(a.x, b.x), min(a.y, b.y), abs(b.x - a.x), abs(b.y - a.y), r * K)


def poly(m: Affine, pts: tuple[XY, ...]) -> Path:
    """The closed polygon through craft-unit `pts` under figure `m`."""
    return P().poly(m.apply(pts), closed=True)


def solid(s: Canvas, d: Path, paint: Paint = UI_HI, width: float = 2) -> None:
    """`d` filled with BG and outlined, so it hides the parts drawn behind it."""
    s.path(d, fill=BG, stroke=paint, stroke_width=width)


def emblem(s: Canvas, c: Vec, r: float, pitch: float) -> None:
    """The pig decal of radius `r`: the disc ruled upright every `pitch` units, the drafting sign
    for a painted colour, with the pig left clear."""
    rules = P()
    for seg in hatch(Point(c.x, c.y).buffer(r - 1, quad_segs=32), pitch, deg=90):
        rules.poly(seg)
    s.stroke(rules, UI, 1)
    s.stroke(P().circle(c, r), UI_HI, 1.6)
    pig = P().M(c + Vec(*PIG[0]) * r)
    for i, (u, v) in enumerate(PIG[1:], 1):
        if i in PIG_CURVES:
            pig.Q(c + Vec(*PIG_CURVES[i]) * r, c + (u * r, v * r))
        else:
            pig.L(c + (u * r, v * r))
    solid(s, pig.Z(), UI_HI, 1.4)
    s.fill(P().circle(c + Vec(*PIG_EYE) * r, 0.055 * r), UI_HI)


def tags(s: Canvas, marks: list[Mark]) -> None:
    """Numbered ring markers, each with a leader ending in a dot on the part it names."""
    leads, ends, rings = P(), P(), P()
    for (cx, cy), _, t in marks:
        c = Vec(cx, cy)
        leads.M(c + (t - c).unit() * 13).L(t)
        ends.circle(t, 2.4)
        rings.circle(c, 13)
    s.stroke(leads, UI_ALT, 1.2)
    s.fill(ends, UI_HI)
    solid(s, rings, UI_HI, 1.4)
    for (x, y), n, _ in marks:
        one = n < 10
        glyphs(
            s,
            [str(n)],
            MUTED,
            at=(x, y - 8),
            font="8x16" if one else "5x8",
            px=1 if one else 2,
            anchor="middle",
        )


def water(s: Canvas, x0: float, x1: float) -> None:
    """The waterline from x0 to x1 with section hatching below it."""
    s.stroke(P().M(x0, WL).H(x1), UI_ALT, 1.4)
    h = P()
    for x in range(int(x0) + 4, int(x1), 12):
        h.M(x, WL + 2).L(x - 9, WL + 11)
    s.stroke(h, UI, 1)


@design()
def draw(s: Canvas) -> None:
    with s.group(stroke_linejoin="round"):
        # sheet border and title block
        sheet = P().rect(60, 60, 1800, 960).M(1620, 1020).V(940).H(1860)
        sheet.M(1620, 972).H(1780).M(1780, 940).V(1020)  # two rows beside the emblem's cell
        s.stroke(sheet, UI, 1.2)
        glyphs(s, ["PL. 1"], MUTED, at=(1640, 948), font="5x8", px=2)
        glyphs(s, ["PEY'J"], UI_HI, at=(1640, 988), font="5x8", px=2)
        emblem(s, Vec(1820, 980), 30, 4)

        side(s)
        rear(s)
        plan(s)

        for i, name in enumerate(LEGEND):
            glyphs(
                s,
                [f"{i + 1:>2} {name}"],
                lambda col, row, ch: MUTED if col < 2 else UI_HI,
                at=(1120 + (i // 5) * 280, 640 + (i % 5) * 32),
                font="5x8",
                px=2,
            )
        fig1 = (round(SIDE((LEN / 2, 0)).x), WL + 34)
        glyphs(s, ["FIG. 1"], UI_HI, at=fig1, font="5x8", px=2, anchor="middle")
        glyphs(s, ["FIG. 2"], UI_HI, at=(X3, WL + 34), font="5x8", px=2, anchor="middle")
        fig3 = (round(PLAN((LEN, 0)).x) + 50, Y2 - 8)
        glyphs(s, ["FIG. 3"], UI_HI, at=fig3, font="5x8", px=2)


def side(s: Canvas) -> None:
    """FIG. 1, the port side."""
    f = SIDE
    water(s, X1 - 40, f((LEN, 0)).x + 40)

    # cabin: bow face behind the drum, flat roof, helmet slope aft
    solid(s, poly(f, CABIN))
    s.stroke(P().M(f((850, 460))).C(f((862, 380)), f((870, 300)), f((866, 175))), UI_ALT, 1.2)
    # cockpit opening in the bow face
    s.stroke(P().M(f((400, 250))).L(f((400, 420))), UI, 1.2, dash=HIDDEN)
    # sawtooth crest down the aft slope, teeth leaning astern
    crest, teeth, n = Polyline(CREST), P(), 6
    for i in range(n):
        a = crest.at(crest.length * (0.1 + 0.72 * i / n))
        b = crest.at(crest.length * (0.1 + 0.72 * (i + 1) / n))
        t = (b - a).unit()
        teeth.M(f(a)).L(f(b + Vec(t.y, -t.x) * 30 - t * 6)).L(f(b))
    s.stroke(teeth, UI_HI, 1.6)

    # porthole
    port = f((PORT[0], PORT[1]))
    s.stroke(P().circle(port, PORT[2] * K), UI_HI, 2)
    s.stroke(P().circle(port, PORT[2] * K - 5), UI_ALT, 1.2)

    # turret: blocky, set forward; blade fins, bent pipe, cannon over the bow
    solid(s, poly(f, ((478, 590), (492, 676), (522, 686), (530, 590))))
    solid(s, poly(f, ((684, 590), (704, 664), (736, 670), (742, 590))))
    solid(s, poly(f, ((430, 460), (430, 560), (460, 590), (770, 590), (790, 560), (790, 460))))
    s.stroke(P().M(f((430, 520))).L(f((790, 520))), UI_ALT, 1.2)
    pipe = P().M(f((600, 590))).L(f((600, 626))).Q(f((600, 646)), f((624, 646))).L(f((640, 646)))
    s.stroke(pipe, UI_HI, 1.6)
    solid(s, poly(f, ((520, 590), (520, 620), (560, 636), (660, 636), (660, 590))))
    solid(s, rbox(P(), f, 392, 560, 598, 628, 12))
    solid(s, rbox(P(), f, 376, 396, 592, 634))

    # gatling pod on the turret flank: drum body, muzzle collar, barrel tips
    solid(s, rbox(P(), f, 400, 560, 456, 534, 18))
    s.stroke(P().M(f((430, 456))).L(f((430, 534))), UI_ALT, 1.2)
    solid(s, rbox(P(), f, 384, 404, 462, 528, 6))
    barrels = P()
    for y in (474, 495, 516):
        barrels.M(f((384, y))).L(f((366, y)))
    s.stroke(barrels, UI_HI, 3, cap="butt")

    # motor drum: intake grille at the bow end, seams, rivets, pig decal
    x0, x1, y0, y1 = DRUM
    solid(s, rbox(P(), f, x0, x1, y0, y1, 40))
    grille = P()
    for x in range(372, 404, 8):
        grille.M(f((x, 196))).L(f((x, 344)))
    s.stroke(grille, UI_ALT, 1.2)
    s.stroke(P().M(f((410, 172))).L(f((410, 368))).M(f((700, 172))).L(f((700, 368))), UI_ALT, 1.2)
    s.fill(P().dots(f.apply([(x, 356) for x in range(436, 700, 30)]), 1.5), UI_HI)
    d = f((556, 260))
    decal = Vec(round(d.x), round(d.y))  # whole units keep the upright rules crisp
    emblem(s, decal, 44, 4)

    # the lit boost lamp across the drum's aft end, its corner following the drum's
    r = 40 * K
    lx, top = f((712, y1 - 1))
    bx, by = f((x1, 176))
    lamp = P().M(lx, top).H(bx - r).A(r, r, 0, 0, 1, bx, top + r).V(by).H(lx).Z()
    s.path(lamp, fill=ACCENT_6, stroke=ACCENT, stroke_width=2)
    slots = P()
    for y in range(206, 356, 24):
        slots.M(f((722, y))).L(f((744, y)))
    s.stroke(slots, ACCENT, 1.6)

    # near propeller: nacelle on its lateral arm (end-on here), pusher disc edge-on
    solid(s, rbox(P(), f, 604, 690, PROP_HUB - 26, PROP_HUB + 26, 22))
    solid(s, P().circle(f((640, PROP_HUB)), 9 * K + 2), UI_ALT, 1.2)
    solid(s, poly(f, ((690, PROP_HUB + 18), (724, PROP_HUB), (690, PROP_HUB - 18))))
    hub = f((PROP_X + 6, PROP_HUB))
    s.stroke(P().ellipse(hub, 12 * K, PROP_R * K), UI_ALT, 1.2, dash=(4, 4))
    # blades at 90/210/330 deg: one full up, the other two coincide at half length
    blades = P().M(hub + (0, -12)).L(hub + (-2, 4 - PROP_R * K))
    blades.M(hub + (0, 12)).L(hub + (1, PROP_R * K * 0.5))
    s.stroke(blades, UI_HI, 4, cap="round")

    # float: plain middle band, ribbed caps at both ends
    solid(s, rbox(P(), f, 0, LEN, 0, FLOAT_H, FLOAT_H / 2))
    ribs = P()
    for i in range(5):
        x = 40 + i * 30
        ribs.M(f((x, 8))).C(f((x - 12, 60)), f((x - 12, 115)), f((x, 167)))
        x = LEN - 40 - i * 30
        ribs.M(f((x, 8))).C(f((x + 12, 60)), f((x + 12, 115)), f((x, 167)))
    s.stroke(ribs, UI_ALT, 1.2)
    caps = P().M(f((CAP, 1))).L(f((CAP, 174))).M(f((LEN - CAP, 1))).L(f((LEN - CAP, 174)))
    s.stroke(caps, UI_HI, 1.4)
    s.stroke(P().M(f((560, 2))).L(f((560, 173))), UI_ALT, 1.2)
    s.stroke(P().M(f((-30, FLOAT_H / 2))).L(f((LEN + 30, FLOAT_H / 2))), UI_ALT, 1, dash=CENTRE)

    tags(
        s,
        [
            ((150, 360), 1, f((110, 120))),
            ((150, 250), 4, f((380, 300))),
            ((180, 150), 10, f((420, 470))),
            ((330, 110), 8, f((470, 624))),
            ((830, 370), 2, f((985, 205))),
            ((680, 110), 6, f((PROP_X + 4, PROP_HUB + 130))),
            ((780, 180), 3, port + (12, -12)),
            ((830, 250), 7, f((960, 380))),
            ((880, 450), 5, f((744, 200))),
            ((330, 400), 9, decal + (-41, 16)),
        ],
    )


def rear(s: Canvas) -> None:
    """FIG. 2, seen from astern."""
    f = REAR
    water(s, X3 - 300, X3 + 300)
    # props: lateral arms off the roof shoulders, pusher discs facing aft
    r0, r1, w = 18 * K, (PROP_R - 8) * K, 9  # blade root, tip radius and width
    for sg in (-1, 1):
        hub = f((sg * HUB_Z, PROP_HUB))
        s.stroke(P().circle(hub, PROP_R * K), UI_ALT, 1.2, dash=(4, 4))
        root, tip = sg * 120, sg * HUB_Z
        arm = (
            (root, PROP_HUB - 30),
            (tip, PROP_HUB - 14),
            (tip, PROP_HUB + 14),
            (root, PROP_HUB + 26),
        )
        solid(s, poly(f, arm))
        # three blades; the port disc mirrors the starboard one
        blades = P()
        for k in range(3):
            u = polar((0, 0), 1, deg=(-60 if sg < 0 else -120) + 120 * k)
            n = u.perp()
            outline = [
                hub + u * r0 + n * (w / 2),
                hub + u * r1 + n * w,
                hub + u * (r1 + 10),
                hub + u * r1 - n * 2,
                hub + u * r0 - n * (w / 2),
            ]
            blades.poly(outline, closed=True)
        solid(s, blades, UI_HI, 1.6)
        solid(s, P().circle(hub, 28 * K), UI_HI, 1.6)
        s.stroke(P().circle(hub, 12 * K), UI_ALT, 1.2)

    # turret block and centreline fin peeking over the dome
    solid(s, poly(f, ((-12, 560), (-8, 676), (8, 676), (12, 560))))
    solid(s, poly(f, ((-110, 520), (-96, 590), (96, 590), (110, 520))))
    # broad helmet dome
    dome = (
        (-190, 180),
        (-194, 320),
        (-178, 420),
        (-130, 500),
        (-60, 530),
        (60, 530),
        (130, 500),
        (178, 420),
        (194, 320),
        (190, 180),
    )
    solid(s, P().spline(f.apply(dome)))
    # centre plate with louvres, crest ridge above
    solid(s, poly(f, ((-72, 190), (-58, 470), (58, 470), (72, 190))), UI_HI, 1.6)
    s.stroke(P().M(f((0, 470))).L(f((0, 528))), UI_ALT, 1.2)
    louvres = P()
    for y in (400, 350, 300):
        louvres.poly(f.apply([(-44, y), (44, y), (36, y - 22), (-36, y - 22)]), closed=True)
    s.stroke(louvres, UI_HI, 1.4)
    # skirt plate the dome and drums bolt onto
    solid(s, poly(f, ((-250, 175), (-240, 196), (240, 196), (250, 175))), UI_HI, 1.6)
    # drums flanking the dome, lamp faces unlit from astern
    for sg in (-1, 1):
        z0, z1 = sorted((sg * DRUM_Z[0], sg * DRUM_Z[1]))
        solid(s, rbox(P(), f, z0, z1, 180, DRUM[3], 40))
        lz0, lz1 = z0 + 16, z1 - 16
        solid(s, rbox(P(), f, lz0, lz1, 214, 340, 12), UI_ALT, 1.4)
        slots = P()
        for y in range(236, 330, 20):
            slots.M(f((lz0 + 10, y))).L(f((lz1 - 10, y)))
        s.stroke(slots, UI_ALT, 1.2)

    # float from astern: plain rear band between chevron-ribbed corner lobes
    solid(s, rbox(P(), f, -HALF_W, HALF_W, 0, FLOAT_H, FLOAT_H / 2))
    seams, chevrons = P(), P()
    for sg in (-1, 1):
        seams.M(f((sg * 130, 2))).L(f((sg * 130, 173)))
        for i in range(6):
            z = sg * (150 + i * 34)
            chevrons.poly(f.apply([(z, 10), (z + sg * 20, FLOAT_H / 2), (z, FLOAT_H - 10)]))
    s.stroke(seams, UI_HI, 1.4)
    s.stroke(chevrons, UI_ALT, 1.2)
    s.stroke(P().M(f((0, -20))).L(f((0, 700))), UI_ALT, 1, dash=CENTRE)
    tags(
        s,
        [
            ((X3 + 290, 130), 6, f((HUB_Z + 60, PROP_HUB + 120))),
            ((X3 + 290, 400), 4, f((230, 220))),
            ((X3 - 290, 140), 7, f((0, 510))),
            ((X3 - 290, 420), 1, f((-300, 60))),
        ],
    )


def plan(s: Canvas) -> None:
    """FIG. 3, seen from above, bow to the left."""
    f = PLAN
    # float ring hugging the hull, ribbed round its corners
    R = 250
    ring = rbox(P(), f, 0, LEN, -HALF_W, HALF_W, R)
    rbox(ring, f, FLOAT_H, LEN - FLOAT_H, -HALF_W + FLOAT_H, HALF_W - FLOAT_H, R - FLOAT_H)
    s.path(ring, fill=BG, fill_rule="evenodd", stroke=UI_HI, stroke_width=2)
    ribs = P()
    for corner, a0 in (
        ((LEN - R, HALF_W - R), 0),
        ((R, HALF_W - R), 90),
        ((R, -HALF_W + R), 180),
        ((LEN - R, -HALF_W + R), 270),
    ):
        for i in range(1, 6):
            a = a0 + 90 * i / 6
            ribs.M(f(polar(corner, R - FLOAT_H + 6, deg=a))).L(f(polar(corner, R - 6, deg=a)))
    s.stroke(ribs, UI_ALT, 1.2)

    # skirt plate, then the helmet dome: blunt bow face, round stern
    solid(s, rbox(P(), f, 392, 1050, -250, 250, 90), UI_HI, 1.6)
    dome = P().M(f((400, -150))).L(f((400, 150))).L(f((860, 190)))
    solid(s, dome.A(176 * K, 190 * K, 0, 0, 0, f((860, -190))).Z())
    # crest spikes on the stern ridge
    spikes = P()
    for x in range(900, 1030, 22):
        spikes.M(f((x, 0))).L(f((x + 20, 0))).M(f((x + 20, -8))).L(f((x + 20, 8)))
    s.stroke(spikes, UI_HI, 1.4)

    for sg in (-1, 1):
        z0, z1 = sorted((sg * DRUM_Z[0], sg * DRUM_Z[1]))
        solid(s, rbox(P(), f, DRUM[0], DRUM[1], z0, z1, 26))
        s.stroke(P().M(f((712, z0 + 8))).L(f((712, z1 - 8))), UI_ALT, 1.4)
        # arm out to the nacelle, disc edge-on astern of it
        solid(s, rbox(P(), f, 628, 664, sg * 120, sg * HUB_Z))
        solid(s, rbox(P(), f, 604, 690, sg * HUB_Z - 26, sg * HUB_Z + 26, 22))
        solid(s, poly(f, ((690, sg * HUB_Z + 18), (724, sg * HUB_Z), (690, sg * HUB_Z - 18))))
        # gatling pods on the turret flanks
        solid(s, rbox(P(), f, 384, 560, sg * 150 - 34, sg * 150 + 34, 14))

    # turret, mantlet, cannon and muzzle along the centreline, fins edge-on
    solid(s, rbox(P(), f, 430, 790, -120, 120))
    solid(s, rbox(P(), f, 520, 660, -40, 40), UI_HI, 1.6)
    solid(s, rbox(P(), f, 392, 560, -16, 16, 10), UI_HI, 1.6)
    solid(s, rbox(P(), f, 376, 396, -22, 22), UI_HI, 1.6)
    s.stroke(P().M(f((478, 0))).L(f((530, 0))).M(f((684, 0))).L(f((742, 0))), UI_HI, 4, cap="round")

    discs = P()
    for sg in (-1, 1):
        discs.ellipse(f((PROP_X + 6, sg * HUB_Z)), 12 * K, PROP_R * K)
    s.stroke(discs, UI_ALT, 1.2, dash=(4, 4))
    s.stroke(P().M(f((-40, 0))).L(f((LEN + 40, 0))), UI_ALT, 1, dash=CENTRE)
    tags(
        s,
        [
            ((150, Y2 - 160), 1, f((60, -300))),
            ((150, Y2 + 100), 10, f((400, 170))),
            ((820, Y2 - 180), 6, f((PROP_X + 4, -HUB_Z - 110))),
            ((820, Y2 + 190), 4, f((740, 200))),
        ],
    )
