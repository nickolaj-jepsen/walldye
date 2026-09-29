# Wallpaper idea seeds

Unbuilt concept seeds, grouped by family. Treat them as a starting point, not a menu: swap the subject, cross two families (a dithered instrument, a glyph-rendered simulation), or keep a seed's composition and change its technique. Each line reads **name** — concept; composition; technique.

Every seed assumes the house style: a calm, minimal field in theme grays, one small accent "event", no text, pure vector and crisp at 4K. "Accent" means the theme's ACCENT ramp, never a second hue. A seed leaves this list once it is built; `walldye list` shows what exists.

## Dither & pixel

- **engraving-sun** — a sun sinking into still water as an intaglio line screen; low horizon, sun off-center; `dither(method="lines")` or stroke widths that swell with tone.
- **bayer-dusk** — a plain dusk gradient whose visible 4x4 Bayer steps become the landscape bands; one accent planet above; wide and nearly empty; quantize a vertical ramp to 4-5 levels.
- **dither-fog-lamp** — a single streetlamp in fog, its light cone error-diffused onto wet ground; lamp small at one side, only the bulb in accent; Floyd-Steinberg on radial falloff plus noise.
- **dither-sampler** — a dither-strategy study of three identical shaded spheres in a row, each in a different method (Bayer, Atkinson, blue noise); one highlight in accent; generous margins.
- **pixel-sokoban** — a solved Sokoban level in gray wall and floor tiles, the last crate landing on its goal in accent; centered tilemap with a wide margin; `grid_runs` for tiles.

## ASCII, glyph & TUI

- **glyph-fire** — the demoscene fire effect in shade-block glyphs licking up from the bottom edge into sparse sparks; bottom quarter only; classic cooling-buffer sim mapped to the shade blocks ` ░▒▓█`.
- **glyph-tui** — a tmux-style tiled terminal in box-drawing glyphs, three panes of abstract content with the focused pane framed in accent; greek the content as glyph runs.
- **shade-horizon** — an ANSI-art sunset painted only in ░▒▓█: an off-center sun with a ▓ rim, low haze and a shimmering reflection; tone mapped to ` ░▒▓█` on a coarse grid.
- **pixel-terminal** — greeked pixel code, minimap-style, ending in an accent prompt and a block cursor; left-aligned block in one third of the canvas; bars from random line lengths and indents.
- **glyph-vu-meter** — stereo VU and spectrum bars in ▁▂▃▄▅▆▇█ block elements with a single peak-hold cell in accent; a low strip along the bottom edge; noise-driven bar heights.
- **glyph-diff** — a unified diff in greeked glyph blocks with +/- gutter marks; one hunk's added lines in accent; narrow column against one edge, the rest empty.

## Instruments & science displays

- **ecg-monitor** — one heartbeat trace sweeping across a patient-monitor grid, the erase gap just ahead of the pen, the newest QRS complex in accent; a thin band across the middle.
- **sonar-waterfall** — a passive sonar waterfall of noise speckle with one faint contact line drifting diagonally in accent; full-bleed but very dim; blue-noise dither of a time-bearing field.
- **antenna-pattern** — an antenna radiation pattern on a polar dB grid, gray side lobes and the main lobe outline in accent; grid cropped by one edge; plot |array factor| in polar form.

## Technical drawing & patents

- **facet-crystal** — a quartz point as a mineralogy plate, the prism line-drawn, hidden edges dashed, the termination catching the light; one specimen, centered, lots of air.
- **fountain-pen-section** — a longitudinal section of a fountain-pen nib and feed with its ink channel in accent; the pen lies diagonal across one half; hatch the section, fine line elsewhere.
- **zipper-patent** — a 1917-style zipper patent figure of interlocking teeth converging on the slider, with one engaging tooth pair in accent; a single diagonal run, ruled shading.

## Systems art & plotter canon

- **des-ordres** — a grid of concentric jittered squares, one cell's innermost square in accent; tremble increases toward one corner. Make the composition our own: a Molnár series is still in copyright.
- **ten-print** — the 10 PRINT maze of random ╱ ╲ diagonals in gray, with one connected path through it traced in accent; full-bleed but thin and dim.
- **truchet-loop** — Smith-style Truchet quarter-arc tiles forming meandering loops; one closed loop in accent; flood-fill the arc graph to find a loop of the right length.

## Math curves & tilings

- **collatz-coral** — Collatz orbits drawn as a bending coral tree, each even/odd step a small turn left/right; the orbit of 27 in accent; grows from the bottom edge.

## Physics & simulation

- **bubble-chamber** — bubble-chamber tracks, gray straight and gently curved paths with one electron spiraling tightly inward in accent; dotted strokes, full-bleed but sparse.
- **caustics** — the caustic network on a pool floor, bright wavering lines on gray, one cusp junction in accent; `iso_lines` of a warped noise field, thin strokes.
- **vortex-street** — a Kármán vortex street shed behind a small cylinder, drawn as streaklines; the cylinder in accent; flow left to right across the lower half.

## Astronomy

- **transit-curve** — an exoplanet light curve, thousands of gray photometry dots in a flat band with one transit dip picked out in accent; low horizontal strip.
- **kepler-areas** — an elliptical orbit with equal-time sectors swept from the focus in alternating hairline hatch, one sector filled in accent; ellipse large and cropped.

## Landscape (minimal)

- **contour-island** — a single small island as topographic contour lines in an empty ocean, bathymetric dashes around it, the summit ring in accent; island at a third.
- **fuji-contours** — a lone volcano as fine gray contour rings and radial gullies, only the crater rim in accent. The red-cone version failed because its accent was a big flat mass.

## Textiles, paper & craft

- **weave-draft** — a weaving draft, with threading, tie-up and treadling grids around the drawdown; one repeat of the drawdown in accent; filled grid cells via `grid_runs`.
- **boro-patch** — a boro patchwork of mended gray rectangles held by running stitches, with one small patch in accent; slightly skewed patches, sashiko on top.

## Poster geometry & op-art

- **delaunay-drift** — a sparse Delaunay mesh drifting in from one corner and thinning to nothing, with one small faceted accent gem.

## Architecture & objects

- **brise-soleil** — a facade of angled concrete louvres casting a raked shadow pattern, one louvre catching accent light; the facade is cropped and fills one side.

## Developer & desktop

- **flame-graph** — a CPU flame graph of stacked gray frame bars with the one hot frame in accent; it rises from the bottom edge and fills about a third of the height.
- **regex-railroad** — an unlabeled railroad syntax diagram of rounded tracks, loops and branches, one accepted path in accent; long and horizontal through the middle.
- **contribution-calendar** — a year of contribution squares in faint gray steps with one week-long streak in accent; a 53x7 grid low on the canvas.
- **trace-waterfall** — a distributed-trace span waterfall, nested gray bars stepping right with the critical path in accent; left-aligned block, most of the canvas empty.
- **store-graph** — a layered dependency DAG of package derivations with thin curved edges converging on one root; a single build path in accent; layout by depth.

## Charts, schematics and RFCs

The owner asked for more of these. Draw a real instance where one exists (principles.md, Subjects), and check a work's license before calling a piece a recreation of it.

- **harbor-approach** — the approach chart of one real harbor: channel limits dashed, soundings and depth contours in gray, the leading-light line in accent; the harbor mouth at a third, the sea empty; drawn from the harbor's published chart data, credited as a `data` source.
- **tidal-atlas** — a tidal stream atlas page for one real strait, gray arrows sized by rate over the coastline and depth contours, one hour's strongest stream in accent; arrows on a regular grid, the land cropped by one edge.
- **regen-receiver** — the schematic of a one-valve regenerative radio receiver on a dotted drafting grid, orthogonal wires and junction dots, the feedback loop in accent; a compact block off-center.
- **astable-555** — the classic 555 astable circuit as an unlabeled schematic, the timing capacitor's charge path in accent; small and low, with generous margins.
- **ipv4-header** — the IPv4 header diagram from RFC 791 as its 32-bit ruled box grid in box-drawing glyphs, one field (time to live) in accent; a narrow block off-center, no labels.
- **tcp-states** — the TCP connection state diagram from RFC 793 as unlabeled boxes and arrows, the three-way handshake's path in accent; long and low across the canvas.
- **arpanet-map** — an early ARPANET logical map as node boxes and leased lines, one path across the network in accent; the map at a third, the rest empty.

## Dropped in review

Don't propose these again as they were.

- tetris-well: the look of the well is protected (*Tetris Holding v. Xio*).
- tomoe, vertigo-spiral, vega-bulge, red-fuji, lava-lamp: big flat accent shapes. fuji-contours above is the version that keeps the accent to the crater rim.
- winter-tree, fireflies, iceberg, rain-moon: clip-art illustration.
