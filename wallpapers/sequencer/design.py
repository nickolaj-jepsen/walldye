"""A 16-step drum sequencer grid of rounded pads, its playhead column lit; tall screens get a tracker's layout."""

from walldye import ACCENT, ACCENT_5, UI, UI_ALT, UI_HI, Canvas, P, Vec, design

PAD, GAP, BAR = 40, 12, 12  # step pad, gap between pads, extra gap between beats
PITCH = PAD + GAP
RULER, LED = 20, 39  # offsets from the grid of the step ruler and the track LEDs
HEAD = 10  # playhead step
MUTED = {7}
PATTERN = (
    "x...x...x...x...",  # kick
    "....x.......x..x",  # snare
    "..x...x...x...xx",  # closed hat
    "......x.......x.",  # open hat
    "...x......x.....",  # clap
    "x.......x.x.....",  # bass
    "..........x...x.",  # perc
    "x.......x.......",  # chord (muted)
)
# The grid's centre along the steps, and the centre of ruler plus grid across the tracks.
MID = Vec((16 * PITCH - GAP + 3 * BAR) / 2, (len(PATTERN) * PITCH - GAP - RULER) / 2)


def step_at(i: int) -> float:
    """Offset of step `i`'s pad along the steps, counting the extra gap after each beat."""
    return i * PITCH + (i // 4) * BAR


@design(aspects="any")
def draw(s: Canvas) -> None:
    # landscape: steps run left to right, right of centre; portrait: they run down, as in a tracker
    c = s.pick(landscape=(0.6708, 0.5), portrait=(0.5, 0.52), snap=1)

    def at(u: float, v: float) -> Vec:
        """The canvas point `u` along the steps and `v` across the tracks from the grid's corner."""
        if s.landscape:
            return c + (u - MID.x, v - MID.y)
        return c + (v - MID.y, u - MID.x)

    off, on, muted, head_off, head_on = P(), P(), P(), P(), P()
    for j, row in enumerate(PATTERN):
        for i, ch in enumerate(row):
            if ch == "x" and j in MUTED:
                d = muted
            elif i == HEAD:
                d = head_on if ch == "x" else head_off
            else:
                d = on if ch == "x" else off
            x, y = at(step_at(i), j * PITCH)
            d.rrect(x, y, PAD, PAD, 6)
    s.stroke(off, UI, 1.5)
    s.path(on, fill=UI, stroke=UI, stroke_width=1.5)
    s.stroke(muted, UI_ALT, 2.5)
    s.stroke(head_off, ACCENT_5, 1.5)
    s.path(head_on, fill=ACCENT, stroke=ACCENT, stroke_width=1.5)

    # Per-track mute LEDs: the muted track's LED is lit and its steps are hollow.
    leds, lit = P(), P()
    for j in range(len(PATTERN)):
        centre = at(-LED, j * PITCH + PAD / 2)
        if j in MUTED:
            lit.circle(centre, 6)
        else:
            leds.circle(centre, 5)
    s.stroke(leds, UI_ALT, 1.5)
    s.fill(lit, UI)

    # The step ruler: steps already played, still to come, and the one under the playhead.
    done, todo, now = P(), P(), P()
    for i in range(16):
        d = now if i == HEAD else done if i < HEAD else todo
        d.M(at(step_at(i), -RULER)).L(at(step_at(i) + PAD, -RULER))
    s.stroke(done, UI_HI, 3)
    s.stroke(todo, UI, 3)
    s.stroke(now, ACCENT, 3)
