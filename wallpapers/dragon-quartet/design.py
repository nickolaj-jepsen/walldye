"""Four Heighway dragons around one point, built from square cells."""

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely.geometry.base import BaseGeometry

from walldye import ACCENT, ACCENT_2, BG_ALT, UI, Canvas, P, design
from walldye.geom import Affine

LEVEL = 10  # 2**LEVEL steps per dragon
UNIT = 18  # px per lattice step; a whole number keeps every cell edge on the pixel grid
GLOW = 25  # lattice steps from the shared origin to the glow's outer stop
OUTLINES = ((1, BG_ALT), (3, BG_ALT), (2, UI))  # quarter turns from the filled dragon, and tone


def dragon() -> NDArray[np.complex128]:
    """The vertices of the Heighway dragon of 2**LEVEL unit steps, starting at 0 heading +x."""
    n = np.arange(1, 2**LEVEL)
    right = (((n & -n) << 1) & n) != 0
    heading = np.concatenate([[0], np.cumsum(np.where(right, -1, 1))]) % 4
    step = np.array([1, 1j, -1, -1j])[heading]
    return np.concatenate([[0], np.cumsum(step)])


def region(z: NDArray[np.complex128]) -> BaseGeometry:
    """Union of the squares having each step of `z` as diagonal; every lattice edge owns one
    square, so the four rotated dragons tile without overlapping."""
    a, b = z[:-1], z[1:]
    m, h = (a + b) / 2, (b - a) * 0.5j
    quads = np.stack([a, m + h, b, m - h], axis=1)
    return shapely.union_all(
        shapely.polygons(np.stack([quads.real, quads.imag], axis=-1))
    ).simplify(0)


@design(aspects="any")
def draw(s: Canvas) -> None:
    # the pinwheel is symmetric about its shared origin, so that point is its center
    c = s.pick(landscape=(1250 / 1920, 500 / 1080), portrait=(0.5, 0.55), snap=1)
    to_canvas = Affine.frame(c, deg=0, scale=UNIT)
    # diagonal steps make the cells axis-aligned squares half a lattice step wide
    z = dragon() * (1 + 1j) / 2
    regions = [region(z * 1j**k) for k in range(4)]
    # outline edges stop short of the filled dragon, so they butt against it rather than trace it
    keep_out = regions[0].buffer(0.02)
    for k, tone in OUTLINES:
        edge = shapely.transform(regions[k].boundary.difference(keep_out), to_canvas.apply)
        s.stroke(P().shape(edge), tone, 1.2, join="round", cap="round")
    # brightest at the shared origin, cooling toward the tail
    glow = s.radial_gradient([(0, ACCENT), (1, ACCENT_2)], c, GLOW * UNIT)
    s.fill(P().shape(shapely.transform(regions[0], to_canvas.apply)), glow)
