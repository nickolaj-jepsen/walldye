# Wallpaper idea seeds

About 150 concept seeds, grouped by family. Treat them as a starting point, not a menu. Swap the subject, cross two families (a dithered instrument, a glyph-rendered simulation), or keep a seed's composition and change its technique. Each line reads **name** — concept; composition; technique.

Every seed assumes the house style: a calm, minimal field in theme greys, one small accent "event", no text, pure vector and crisp at 4K. "Accent" means the theme's ACCENT ramp, never a second hue. The lessons at the end explain which kinds of idea tend to fail.

114 of the 152 seeds are marked (built): a design with that name already exists, under `wallpapers/` or, until the M2 import, in `~/nixos/modules/desktop/dms/wallgen/designs/`. Build one again only with a different subject or composition, and under a new slug. glyph-terrain (example) is `examples/glyph-terrain.py`, not yet a piece.

## Dither & pixel

- **dither-moon** (built) — a gibbous moon as a 1-bit photo on a classic Mac; off-centre in a big empty sky; shaded sphere plus noise maria through `dither(method="atkinson")` or blue noise, 2 levels.
- **riemersma-nebula** (built) — a dim emission nebula cut by dust lanes, mostly black; the cloud sits off-centre; Riemersma (Hilbert-curve) diffusion for a soft, curly grain unlike other dithers.
- **dither-gas-giant** (built) — the limb of a banded gas giant in one corner, one storm oval in accent; noise-warped latitude bands through Stucki diffusion with serpentine rows.
- **dither-wave** (built) — one great swell curling at the lower-left, its lip catching accent foam; the rest is empty sky; Jarvis-Judice-Ninke serpentine on a shaded tube surface.
- **dither-smoke** (built) — a thin incense plume rising from a tiny accent ember and fading to grey; tall, narrow, about 90% empty; Sierra-Lite dither of a curl-noise density ribbon.
- **dither-spectrogram** (built) — spectrogram of a whistled melody, a bright fundamental and two overtones, cut off at a playhead; one horizontal band; 8x8 Bayer on a time-frequency field.
- **pattern-window** (built) — a dark room, a tall window and its slanted patch of light on the floor; every tone is a hand-drawn 8x8 MacPaint fill pattern tiled with `grid_runs`.
- **engraving-sun** — a sun sinking into still water as an intaglio line screen; low horizon, sun off-centre; `dither(method="lines")` or stroke widths that swell with tone.
- **bayer-dusk** — a plain dusk gradient whose visible 4x4 Bayer steps become the landscape bands; one accent planet above; wide and nearly empty; quantise a vertical ramp to 4-5 levels.
- **dither-fog-lamp** — a single streetlamp in fog, its light cone error-diffused onto wet ground; lamp small at one side, only the bulb in accent; Floyd-Steinberg on radial falloff plus noise.
- **dither-sampler** — a dither-strategy study of three identical shaded spheres in a row, each in a different method (Bayer, Atkinson, blue noise); one highlight in accent; generous margins.
- **pixel-campfire** (built) — a tiny campfire under a sparse pixel starfield, its warmth dithered onto the ground; small, low and centred; `sprite()` logs and flame, Bayer glow ring.
- **pixel-desk** (built) — an isometric pixel room corner at night (desk, keyboard, mug, window) whose only warm light is the monitor; diorama fills one third; `sprite()` with a strict 4-grey palette.
- **pixel-bonsai** (built) — a pixel bonsai in a shallow pot, one foliage pad in accent and a leaf drifting down; small and low with plenty of air; hand-authored sprite rows.
- **pixel-invaders** (built) — a Space Invaders formation in quiet greys; one crab breaks formation and dives in accent; formation across the top, a ruined bunker low; `sprite()` per invader.
- **pixel-planet** (built) — a ringed pixel planet lit from behind: thin accent crescent, banded night side, tilted grey ring; sparse single-pixel stars; dither the terminator.
- **pixel-sokoban** — a solved Sokoban level in grey wall and floor tiles, the last crate landing on its goal in accent; centred tilemap with a wide margin; `grid_runs` for tiles.
- **glider** (built) — settled Game of Life ash in grey; one glider escapes toward a corner in accent, trailing fading ghost generations; run a real soup, then `grid_runs` the live cells.
- **langton-ant** (built) — Langton's ant after about 11k steps, a grey chaotic blob with the periodic highway breaking out and marching off-canvas in accent; simulate on a grid, emit runs.
- **rule-30** (built) — Wolfram's Rule 30 grown from one cell at the top edge; the chaotic triangle fills the frame, its centre column traced in accent; tiny cells, grey on grey.

## ASCII, glyph & TUI

- **glyph-donut** (built) — a donut.c homage, a lit torus frozen mid-spin in luminance glyphs; torus off-centre and large; map N·L to `DENSITY`, brightest glyphs in accent.
- **glyph-fire** — the demoscene fire effect in shade-block glyphs licking up from the bottom edge into sparse sparks; bottom quarter only; classic cooling-buffer sim mapped to `SHADES`.
- **glyph-hexdump** (built) — an xxd view of a binary (offset column, 16 hex columns, ASCII gutter) in quiet greys, with one selected byte run in accent; full-bleed but dim.
- **glyph-mandel** (built) — the Mandelbrot set as 1980s ASCII art, escape time mapped to density glyphs, interior blank, boundary band in accent; coarse cell grid, set off-centre.
- **glyph-roguelike** (built) — a NetHack-style dungeon in terminal glyphs, remembered rooms dim and the torch-lit view bright around an accent @; map in one half of the canvas.
- **glyph-terrain** (example) — a roguelike overworld where the glyph encodes terrain (~ . " ^ ▲) and one winding road leads to an accent town; noise height field quantised to glyph classes.
- **glyph-tui** — a tmux-style tiled terminal in box-drawing glyphs, three panes of abstract content with the focused pane framed in accent; greek the content as glyph runs.
- **braille-plot** (built) — a btop-style panel of per-core CPU history as braille area plots, one core spiking in accent; panel in a lower corner; pack 2x4 dots per braille cell.
- **shade-horizon** — an ANSI-art sunset painted only in ░▒▓█: an off-centre sun with a ▓ rim, low haze and a shimmering reflection; tone mapped to `SHADES` on a coarse grid.
- **pixel-terminal** — greeked pixel code, minimap-style, ending in an accent prompt and a block cursor; left-aligned block in one third of the canvas; bars from random line lengths and indents.
- **glyph-vu-meter** — stereo VU and spectrum bars in ▁▂▃▄▅▆▇█ block elements with a single peak-hold cell in accent; a low strip along the bottom edge; noise-driven bar heights.
- **glyph-pipes** (built) — the old "pipes" screensaver in box-drawing glyphs ─│┌┐: a few grey pipes wandering on a grid, one in accent; a self-avoiding random walk emitted as glyph runs.
- **glyph-diff** — a unified diff in greeked glyph blocks with +/- gutter marks; one hunk's added lines in accent; narrow column against one edge, the rest empty.

## Instruments & science displays

- **radar-sweep** (built) — a PPI radar scope mid-rotation, a phosphor afterglow wedge trailing the sweep over a grey coastline, a few contacts lit inside the afterglow; `arc_band` wedges with stepped opacity.
- **helicorder** (built) — a drum seismograph record of quiet ruled traces, one catching an earthquake whose accent coda spills over the lines below; filtered noise traces with one enveloped burst.
- **navball** (built) — an FDAI attitude ball at an odd tilt, line-grid sky and ground hemispheres, a fixed accent aircraft symbol and roll ticks; project a lat-long grid with hidden-line culling.
- **smith-chart** (built) — a huge Smith chart partly off-screen, with an accent matching path spiralling a load point home to the centre; constant-r and constant-x circles as hairlines.
- **oscilloscope** (built) — a 3:2 Lissajous trace on a scope graticule, brightest where the beam lingers; graticule at the centre; stroke opacity from inverse beam speed. Avoid phase ±π/4 for 3:2: the figure collapses to an open curve.
- **ecg-monitor** — one heartbeat trace sweeping across a patient-monitor grid, the erase gap just ahead of the pen, the newest QRS complex in accent; a thin band across the middle.
- **sonar-waterfall** — a passive sonar waterfall of noise speckle with one faint contact line drifting diagonally in accent; full-bleed but very dim; blue-noise dither of a time-bearing field.
- **antenna-pattern** — an antenna radiation pattern on a polar dB grid, grey side lobes and the main lobe outline in accent; grid cropped by one edge; plot |array factor| in polar form.

## Technical drawing & patents

- **airfoil** (built) — a wind-tunnel plate of a cambered airfoil at 6°, potential-flow streamlines around it and an accent suction envelope; NACA 4-digit profile, streamlines from a panel or conformal-map solution.
- **bridge-elevation** (built) — a suspension bridge in engineering elevation (towers, hangers, deck truss, foundations below the waterline) with the main cable in accent; long and low across the canvas.
- **cassette** (built) — a Compact Cassette as a drafting sheet with one detail view; only the magnetic tape is accent; flat technical line, dash-dot centre lines.
- **compass-construction** (built) — Richmond's ruler-and-compass pentagon with the construction left visible; grey arcs run to the edges, the pentagon traced in accent.
- **engine-section** (built) — a section view of a single-cylinder engine, walls in 45° hatch, only the combustion chamber in accent; clip hatch patterns to shapely section polygons.
- **patent-hatch** (built) — a mysterious apparatus (cylinder, sphere, cone) as a patent figure shaded only by hatching, swooping leader lines ending in tiny accent marks where numerals would sit.
- **patent-lamp** (built) — an incandescent lamp as a patent figure in ruled shading and stipple; only the filament glows; a single object, centred low, large margins.
- **ray-diagram** (built) — a ray diagram of a Keplerian telescope, lenses in section, with the on-axis star's rays in accent; the principal axis spans the canvas.
- **schematic** (built) — an unlabelled analog schematic on a dotted drafting grid, the signal path through one stage in accent; orthogonal wires, junction dots.
- **watch-movement** (built) — a technical plan of a watch movement (gear train as pitch circles with tooth ticks, jewels as double circles) with the balance hairspring in accent.
- **typebar-fan** (built) — a typewriter typebar basket, a semicircle of slender bars converging on one print point, with one bar mid-strike in accent.
- **facet-crystal** — a quartz point as a mineralogy plate, the prism line-drawn, hidden edges dashed, the termination catching the light; one specimen, centred, lots of air.
- **fountain-pen-section** — a longitudinal section of a fountain-pen nib and feed with its ink channel in accent; the pen lies diagonal across one half; hatch the section, fine line elsewhere.
- **zipper-patent** — a 1917-style zipper patent figure of interlocking teeth converging on the slider, with one engaging tooth pair in accent; a single diagonal run, ruled shading.

## Systems art & plotter canon

- **schotter** (built) — Nees' Schotter on its side, a band of square outlines shaking apart left to right with one square escaping in accent; disorder grows as `t**1.7`.
- **interruptions** (built) — Molnar's Interruptions, a field of randomly rotated short strokes broken by noise voids, with ordered accent strokes inside the largest void.
- **des-ordres** — Molnar's (Dés)Ordres, a grid of concentric jittered squares, one cell's innermost square in accent; tremble increases toward one corner.
- **hypercube** (built) — a 6-cube in its Coxeter-plane projection, with one geodesic through the centre traced in accent after Manfred Mohr; a crystalline hairline lattice.
- **ribbons** (built) — Fidenza-style ribbons on a gentle flow field that never collide, with a small school in accent; collision-checked streamlines at varying widths.
- **pegs** (built) — Cherniak's Ringers, one taut accent string wound around a cluster of grey pegs of different sizes; the string is the convex-hull-ish tour.
- **one-line** (built) — a crescent moon drawn as one unbroken line, a TSP tour through light-weighted stipples; tone comes from how tightly the line folds.
- **ten-print** — the 10 PRINT maze of random ╱ ╲ diagonals in grey, with one connected path through it traced in accent; full-bleed but thin and dim.
- **truchet-loop** — Smith-style Truchet quarter-arc tiles forming meandering loops; one closed loop in accent; flood-fill the arc graph to find a loop of the right length.

## Math curves & tilings

- **apollonian** (built) — an Apollonian gasket in grey hairlines, with one tangent chain descending into a cusp filled from the accent ramp; Descartes' theorem recursion.
- **lorenz** (built) — the Lorenz butterfly as one thin grey thread, with the single wing switch lifted out in accent: the moment of chaos.
- **dejong-veil** (built) — a de Jong attractor as a smooth density veil of fine quantised cells, only the densest fold in accent; histogram, log-scale, then `grid_runs`.
- **phyllotaxis** (built) — a sunflower head of Vogel-spiral florets rising from one corner, the Fibonacci-index ray in accent.
- **torus-wireframe** (built) — a hidden-line wireframe torus rising from the bottom-left corner like a planet's ring, with one meridian in accent.
- **harmonograph** (built) — a damped 2:3 harmonograph trace, detuned so the loops precess, with the last inward turns warming to accent.
- **times-table** (built) — times-table string art, chords i → k·i mod n on a circle, the cardioid cusp in accent; the circle is large and cropped.
- **collatz-coral** — Collatz orbits drawn as a bending coral tree, each even/odd step a small turn left/right; the orbit of 27 in accent; grows from the bottom edge.
- **penrose** (built) — a Penrose P3 rhomb tiling in faint grey; the tiles around one five-fold vertex step through the accent ramp.
- **hat-tiling** (built) — the 2023 "hat" aperiodic monotile in whisper-grey, with one supertile's mirrored hats in accent so the maths picks the accent.
- **girih** (built) — Hankin's polygons-in-contact star pattern on a 3.12.12 tiling, with one 12-fold rosette inlaid in accent.
- **poincare-disk** (built) — a {7,3} hyperbolic tiling in the Poincaré disk, the rim dissolving to hatch and the central heptagon in accent.

## Physics & simulation

- **fracture** (built) — a dark pane struck once, radial and ring cracks spreading out and a tiny burst of accent shards at the impact; impact off-centre.
- **chladni** (built) — a Chladni figure, sand stippled on the nodal lines of one plate mode, with one nodal loop in accent; `poisson_disk` points rejected by |mode|.
- **iron-filings** (built) — iron filings combed into a bar magnet's dipole field, the field lines emerging from texture; the magnet is the only solid thing.
- **double-slit** (built) — Young's double-slit fringes as a barcode strip, the central maximum in accent and side orders fading to grey.
- **electron-cloud** (built) — a hydrogen 3d_z² orbital as a stipple cloud sampled from |ψ|², its densest cores in accent.
- **ferrofluid** (built) — a ferrofluid crown under a magnet, black spikes on a hex lattice rim-lit in accent from one side.
- **bubble-chamber** — bubble-chamber tracks, grey straight and gently curved paths with one electron spiralling tightly inward in accent; dotted strokes, full-bleed but sparse.
- **caustics** — the caustic network on a pool floor, bright wavering lines on grey, one cusp junction in accent; `contours` of a warped noise field, thin strokes.
- **vortex-street** — a Kármán vortex street shed behind a small cylinder, drawn as streaklines; the cylinder in accent; flow left to right across the lower half.
- **reaction-diffusion** (built) — a Gray-Scott labyrinth whose feed gradient dissolves it into accent spots in one corner; `contours` of the V field as filled vector shapes.
- **coral-loop** (built) — differential growth, one closed line folding into a coral outline ringed by grey echoes of earlier generations.
- **tree-rings** (built) — a felled trunk's cross-section from the corner, with noise-driven climate years, one fire-scar year in accent and a radial drying crack.
- **diatom** (built) — a Haeckel radiolarian, a hex-pored silica sphere with spines, its inner capsule glowing accent through the lattice.

## Astronomy

- **pulsar-map** (built) — the Pioneer plaque pulsar map as pure line, fourteen coded rays with binary ticks and the galactic-centre reference in accent.
- **saturn** (built) — Saturn cropped by a corner, fine ring ellipses with the Cassini division and a latitude-hatched globe whose lit limb is in accent.
- **crater-field** (built) — a lunar crater field under a low sun, rim-light and shadow crescents, one fresh crater throwing accent ejecta rays; power-law crater sizes.
- **sunspot** (built) — solar granulation as dim Voronoi cells around one sunspot whose penumbral filaments radiate in accent.
- **comet** (built) — a great comet with a broad syndyne dust tail fanning from an accent nucleus and a dead-straight ion tail.
- **star-chart** (built) — a stereographic star atlas, a faint RA/Dec graticule over real star positions with one constellation traced in accent.
- **planetrise** (built) — the vast latitude-hatched limb of a planet along the bottom, rimmed by an accent atmosphere, with a tiny crescent moon high up.
- **event-horizon** (built) — a line-art black hole, a tilted accretion disk lensed over a black shadow and Doppler-beamed brighter on one side.
- **transit-curve** — an exoplanet light curve, thousands of grey photometry dots in a flat band with one transit dip picked out in accent; low horizontal strip.
- **kepler-areas** — an elliptical orbit with equal-time sectors swept from the focus in alternating hairline hatch, one sector filled in accent; ellipse large and cropped.

## Landscape (minimal)

- **dunes** (built) — a dune crest at dusk, a combed windward slope, a shadowed slip face and one glowing ridge line; vector ripple lines following the slope, or blue-noise dither of height-field shading.
- **karesansui** (built) — a raked dry garden from above, rake lines ringing three stones, one of them in accent; offset curves around each stone.
- **sun-glitter** (built) — a half-set sun on a level horizon over a sea of perspective glints, a glitter path pointing at the viewer; glints shrink toward the horizon.
- **pine-mist** (built) — pine ridges receding into fog, each a jagged conifer silhouette lighter with distance, a small accent sun behind the farthest hill.
- **lighthouse** (built) — a patent-style elevation of a lighthouse on its rock, the lamp's beam ruled out across the sea; the lamp is the accent.
- **contour-island** — a single small island as topographic contour lines in an empty ocean, bathymetric dashes around it, the summit ring in accent; island at a third.
- **fuji-contours** — a lone volcano as fine grey contour rings and radial gullies, only the crater rim in accent. The red-cone version failed because its accent was a big flat mass.
- **bamboo** (built) — a sumi-e bamboo grove on one edge, node rings and a few blade leaves, one culm lit in accent by the last sun; cropped top and bottom.
- **dandelion** (built) — a dandelion clock of foreshortened pappus rays, the few seeds drifting away in accent; seed head off-centre, the rest empty.

## Maps & charts

- **metro** (built) — an invented octilinear transit diagram, grey lines at 45° with rounded bends and station ticks, a wide dark river and one line in accent.
- **nautical-chart** (built) — a nautical chart corner, grey coast, dashed isobaths and soundings, with accent only in a light-sector arc, a track and the north needle.
- **weather-front** (built) — a synoptic chart, grey isobars wound round a low with its occluding front, triangles and semicircles, in accent.
- **running-track** (built) — a 400 m track at true standard geometry cropped to one bend, lane 4's 200 m run in accent.

## Textiles, paper & craft

- **tartan** (built) — a charcoal 2/2 twill tartan built from a real weave mask; the only colour is one thin accent overcheck.
- **hitomezashi** (built) — hitomezashi sashiko stitches with on/off phase from binary words; one enclosed region in accent thread.
- **dropped-stitch** (built) — a stockinette knit in grey with one dropped stitch laddered down to an accent loop.
- **weave-draft** — a weaving draft, with threading, tie-up and treadling grids around the drawdown; one repeat of the drawdown in accent; filled grid cells via `grid_runs`.
- **boro-patch** — a boro patchwork of mended grey rectangles held by running stitches, with one small patch in accent; slightly skewed patches, sashiko on top.
- **kintsugi** (built) — a dark bowl from above, its fractures rejoined in accent lacquer and one chip filled solid.
- **enso-hanko** (built) — a dry-brush grey enso stamped at its lower right with a small eroded accent seal of abstract carved marks.
- **miura-fold** (built) — a flat Miura-ori crease pattern with one lens of it folded up and catching the light.
- **seigaiha** (built) — seigaiha wave scales rising over the bottom edge and crumbling into a ragged surf line, a small cluster of scales in accent.
- **shippo-ripple** (built) — a faint shippo lattice with accent ink soaking outward through its petals from one point.
- **kumiko-light** (built) — a tall shoji panel of asanoha kumiko on one side, a few cells lit warm from behind.

## Poster geometry & op-art

- **beethoven-arcs** (built) — concentric rings broken into rhythmic arc segments after Müller-Brockmann's Beethoven poster, the core rings in accent; `arc_band` per segment.
- **red-wedge** (built) — a thin accent wedge piercing a grey disc after Lissitzky, with a few constructivist fragments along its vector; keep the wedge slim.
- **movement-squares** (built) — a Riley-style checker frieze whose columns compress to accent slivers at a fold.
- **riley-fall** (built) — a Riley Fall curtain of chirped sine lines on one side with a single accent vein.
- **prism** (built) — a grey ray splitting through a hollow prism into a fan of bands stepping down the accent ramp.
- **rothko** (built) — a Rothko colour field, stacked soft-edged grey blocks breathing on a warm ground; feathered edges come from many stacked low-opacity rects.
- **delaunay-drift** — a sparse Delaunay mesh drifting in from one corner and thinning to nothing, with one small faceted accent gem.

## Architecture & objects

- **barbican** (built) — a night elevation of a brutalist slab, stacked boat-edge balconies with one window lit in accent.
- **brise-soleil** — a facade of angled concrete louvres casting a raked shadow pattern, one louvre catching accent light; the facade is cropped and fills one side.
- **vinyl** (built) — an LP bleeding off the right edge, fine grooves with track gaps, a sheen wedge and an accent label.
- **keycaps** (built) — a top-down corner of a mechanical keyboard, sculpted grey keycaps and one accent Escape.
- **clockclock** (built) — a wall of 24 clocks whose hands draw one wave, with one clock telling the real time in accent.

## Retro computing

- **core-rope** (built) — AGC core rope memory, a bundle of sense wires threading through or bypassing a row of ferrite cores.
- **die-shot** (built) — a 1970s microprocessor die as mask artwork, register cells and Manhattan routing ringed by bond pads, with the ALU in accent.
- **punch-card** (built) — an 80-column punch card with real Hollerith codes for a short shell command and one fully punched accent column.
- **crt-scanlines** (built) — a curved CRT face whose only picture is a glowing orb drawn by swelling scanlines, barrel-distorted near the edges.

## Games & arcade

- **battlezone-horizon** (built) — a Battlezone vector horizon of jagged ranges, an erupting wireframe volcano with a few accent embers, and a two-arc crescent moon.
- **tempest-web** (built) — a Tempest playfield, a 16-lane star tube narrowing to its far rim with one lane lit in accent.
- **pong** (built) — Pong paused mid-rally, grey paddles, a dashed net and an accent ball bouncing off the top wall on a dotted arc.
- **tetris-well** (built) — a quiet Tetris well, a grey settled stack with an accent T hanging above its dashed ghost.
- **shusaku** (built) — a historic Go game at a famous move, all stones grey except the one that decided it; real game records give it authenticity.

## Developer & desktop

- **git-graph** (built) — a `git log --graph` at transit-map scale, grey lanes with commit dots and one feature branch forking and merging back in accent.
- **minimap** (built) — an editor minimap at wallpaper scale, grey code-token bars with realistic indentation, a viewport slab and one accent identifier under the caret.
- **sequencer** (built) — a 16-step x 8-track step sequencer, quiet pads with a few lit and the playhead column in accent.
- **flame-graph** — a CPU flame graph of stacked grey frame bars with the one hot frame in accent; it rises from the bottom edge and fills about a third of the height.
- **regex-railroad** — an unlabelled railroad syntax diagram of rounded tracks, loops and branches, one accepted path in accent; long and horizontal through the middle.
- **contribution-calendar** — a year of contribution squares in faint grey steps with one week-long streak in accent; a 53x7 grid low on the canvas.
- **trace-waterfall** — a distributed-trace span waterfall, nested grey bars stepping right with the critical path in accent; left-aligned block, most of the canvas empty.
- **store-graph** — a layered dependency DAG of package derivations with thin curved edges converging on one root; a single build path in accent; layout by depth.

## Lessons from review

1. **Keep accent areas small.** Big flat, saturated accent masses (a giant crest, a glowing cone, a bulging orb, a thick spiral ribbon) read as a logo or a warning sign, not a backdrop. Aim for a few percent of the pixels and let the accent mark an event.
2. **Pair a quiet field with one event.** The strongest pieces are low-contrast grey textures (a record, a lattice, a stipple, a dithered field) holding one meaningful anomaly: an escaped square, a spiking core, a lit window, an accent glider.
3. **Avoid clip-art illustration.** Literal scenes such as a bare tree with falling leaves, fireflies over grass, an iceberg or a moon behind rain look like stock vectors. Choose subjects with a system behind them (a simulation, a notation, an engineering figure) so detail comes from rules.
4. **Leave room for windows.** Full-sheet drawings like orthographic projections, floor plans and exploded assemblies compete with whatever is open on screen. Show one object, crop it, keep 40–60% of the canvas empty and put the detail near an edge or corner.
5. **Dither, pixel and instrument pieces hold up.** Their fine, even texture sits calmly under windows and rewards a close look at 4K. Vary the dither method between pieces (ordered, blue noise, error diffusion, line screen, Hilbert path) so each has its own grain.
6. **Prefer restraint over maximalism in terrain.** Busy low-poly landscapes and stacked illustrative scenes feel dated. One ridge, a contour set or a dithered height field says "landscape" with far less noise.
7. **Emblems need context.** A lone crest or badge reads as branding. Show its construction (compass arcs, a crease pattern, a drafting grid) or embed it in a system so the eye has something to explore.
8. **Real rules beat vague homage.** A real game record, true Hollerith codes, actual star positions or standard track geometry give the details something to be right about, and viewers who know the subject notice.
9. **Aim for breadth, not variants.** A set of ten dune variations is weaker than ten different subjects. Once a seed works, move to a new family or technique instead of re-skinning it.
10. **Use one hue.** Greys plus the accent ramp is enough. Use the ramp for depth and falloff, never for a second colour story.
