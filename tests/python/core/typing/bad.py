"""Planted mistakes: each line marked `# expect: <code>` must get exactly that Pyrefly error."""

from typing import Literal

from walldye import ACCENT, MASK_WHITE, UI, Canvas, P, Params, design, knob, mix


class Radar(Params):
    sweep: float = knob(default=60, lo=0, hi=360)
    mode: str = knob(default="a", choices=("a", "b"))
    kind: Literal["x", "y"] = "x"


class Other(Params):
    x: int = 1


@design(variants={"x": Radar(sweep="a")})  # expect: bad-argument-type
def draw(s: Canvas[Radar]) -> None:
    s.fill(P(), "#FF0000")  # expect: bad-argument-type
    s.stroke(P(), UI, 1, cap="flat")  # expect: bad-argument-type
    s.path(P(), stroke=UI)  # expect: missing-argument
    s.path(P(), fill="none", stroke_widht=2)  # expect: unexpected-keyword
    with s.mask() as m:
        m.fill(P(), ACCENT)  # expect: bad-argument-type
    s.fill(P(), MASK_WHITE)  # expect: bad-argument-type
    _ = mix(ACCENT, MASK_WHITE, 0.5)  # expect: no-matching-overload
    s.params.sweep = 3  # expect: read-only
    _ = s.params.nope  # expect: missing-attribute
    P().arc((0, 0), 5, (0, 90))  # expect: no-matching-overload
    _ = Radar(nope=1)  # expect: unexpected-keyword
    _ = Radar(kind="z")  # expect: bad-argument-type


@design(variants={"x": Other()})  # expect: bad-argument-type
def draw2(s: Canvas[Radar]) -> None:
    pass


@design(aspects="16:9")  # expect: bad-argument-type
def draw3(s: Canvas) -> None:
    pass
