"""A radiolarian shell as a specimen plate in line and flat tones, with a spherical Voronoi lattice of pores."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import SphericalVoronoi

from walldye import (
    ACCENT,
    ACCENT_4,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    Canvas,
    P,
    Params,
    Vec,
    design,
    knob,
    ladder,
    mix,
    polar,
)

R = 210  # shell radius
PORE = 27  # pore pitch on the sphere surface
STRUT = 0.8  # pore scale inside its Voronoi cell; the rest is shared strut
SPINES = 14
LONG, SHORT = 180, 105  # spine lengths beyond the shell, alternating
HALF = math.degrees(5 / R)  # half the angle a spine's base spans at the shell
BRISTLES = 6 * SPINES
CAPSULE = 0.55 * R  # radius of the glow seen through the pores
DIM = 385  # drop of the dimension line below the center
GLOW = ladder((BG, ACCENT_4, ACCENT), 18)  # rung 0 is the unlit shell and is never drawn

type Pore = tuple[NDArray[np.float64], float]


def pores(c: Vec) -> list[Pore]:
    """The pores on the visible hemisphere of the shell centered on `c`, as (outline, distance of
    the cell's center from `c`) pairs, projected straight onto the screen."""
    n = round(4 * math.pi * R * R / (PORE * PORE * 0.866))
    i = np.arange(n) + 0.5
    z = 1 - 2 * i / n  # toward the viewer
    rho = np.sqrt(1 - z * z)
    a = i * math.pi * (3 - math.sqrt(5))  # a Fibonacci lattice: near-even sites, mostly hexagons
    sites = np.stack([rho * np.cos(a), rho * np.sin(a), z], 1)
    sv = SphericalVoronoi(sites)
    sv.sort_vertices_of_regions()
    out: list[Pore] = []
    for site, region in zip(sites, sv.regions, strict=True):
        if site[2] < 0.14:  # cells on the limb would poke through the silhouette
            continue
        v = site + (sv.vertices[region] - site) * STRUT
        out.append((c + R * v[:, :2], R * math.hypot(site[0], site[1])))
    return out


class Drawing(Params):
    dimensions: bool = knob(default=True, doc="the dimension across the shell")


@design(aspects="any", variants={"undimensioned": Drawing(dimensions=False)})
def draw(s: Canvas[Drawing]) -> None:
    # right of center on a landscape screen; centered across a portrait one, above the middle
    c = s.pick(landscape=(0.625, 0.486), portrait=(0.5, 0.4))

    # specimen-plate construction: center lines, and one dimension across the shell
    guide = P().M(c + (-R - 230, 0)).H(c.x + R + 230).M(c + (0, -R - 150)).V(c.y + R + 150)
    s.stroke(guide, UI, 1.2, dash=(36, 6, 4, 6))
    if s.params.dimensions:
        y = c.y + DIM
        dim = P().M(c.x - R, y).H(c.x + R)
        for x in (c.x - R, c.x + R):
            dim.M(x, c.y + 12).V(y + 14).M(x - 7, y + 7).L(x + 7, y - 7)
        s.stroke(dim, UI, 1.2)

    # spines and bristles sit behind the shell
    spines, ribs, bristles = P(), P(), P()
    for i in range(SPINES):
        b = i * 360 / SPINES
        tip = R + (LONG if i % 2 == 0 else SHORT)
        spines.poly(
            [
                polar(c, R - 10, bearing=b - HALF),
                polar(c, tip, bearing=b),
                polar(c, R - 10, bearing=b + HALF),
            ],
            closed=True,
        )
        ribs.M(polar(c, R, bearing=b)).L(polar(c, tip - 26, bearing=b))
    for i in range(BRISTLES):
        b = (i + 0.5) * 360 / BRISTLES
        bristles.M(polar(c, R, bearing=b)).L(polar(c, R + (15 if i % 3 == 1 else 9), bearing=b))
    s.stroke(bristles, UI, 1.3)
    s.fill(spines, UI)
    s.stroke(ribs, UI_ALT, 1.2)

    # the shell: a shaded disc with every pore cut through it
    holes = pores(c)
    frame = P().circle(c, R)
    for pts, _ in holes:
        frame.poly(pts, closed=True)
    shade = s.radial_gradient([(0, BG_ALT), (0.7, BG_ALT), (1, mix(BG_ALT, BG, 0.7))], c, R)
    s.fill(P().circle(c, R), BG)  # hides the guides behind the pores
    s.fill(frame, shade, rule="evenodd")

    # the capsule glows through the pores: each pore takes one flat rung by its distance
    with s.buckets(GLOW, "fill") as lit:
        for pts, d in holes:
            if (k := GLOW.rung(1 - d / CAPSULE)) > 0:
                lit[k].poly(pts, closed=True)
    s.stroke(P().circle(c, R), UI_ALT, 2)
