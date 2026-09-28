# House style and critique

This is the default look when the user gives no style brief, and the checklist to review every
design against before showing it. It comes from the owner's reviews: what they kept, and the
fixes they asked for again and again.

## Why the rules exist

A wallpaper spends most of its life behind windows. It is seen in slivers between
terminals, around a dock, through translucent panels, and as a thumbnail in a picker.
So it has to be calm: low contrast where windows sit, one clear thing to look at when
the desktop is empty, and nothing that looks like a bug when you see only a corner of
it. The best pieces read in one glance and still hold up when you zoom into a crop.

The house look: minimal, confident, lots of negative space, quiet greys, and one
restrained accent "event". Pure vector: no text, no raster images, no filters, no blur.

## Subjects

- Subjects that work: instruments and science plots (radar, helicorder, Smith chart, navball),
  dev artefacts (schematics, commit graphs, minimaps), crisp technical or patent drawings of
  one contained object, dithered and pixel/glyph art, quiet full-bleed tilings or fields with
  a small accent event, and a few bold single-gesture graphics.
- Subjects that fail: literal illustration (trees, fireflies, icebergs, koi), maximalist
  scenes, product mock-ups, and anything that reads as a UI.
- Choose subjects with a system behind them (a simulation, a notation, an engineering figure),
  so the detail comes from rules.
- Real rules beat vague homage. A real game record (shusaku), true Hollerith codes, actual star
  positions (star-chart) or standard track geometry (running-track) give the details something
  to be right about, and viewers who know the subject notice.
- A named real thing beats a generic one. Asked about a generic suspension bridge and a generic
  open-wheeler, the owner wanted the Great Belt Bridge and a 2026 Formula 1 car, drawn to their
  real figures. Where a subject has a well-known real instance, draw that one.
- Breadth before re-skins. Ten dune variations are weaker than ten different subjects; once a
  seed works, move to a new family or technique.

## Palette discipline

Write every colour as a theme token or a `mix()`, `ladder()` or `by_regime()` of tokens. A
hex value is never a paint, and `walldye check` fails any colour outside a mask that does not
move with the theme.

Greys carry the structure. Use them in this order of preference:

- `BG_ALT`: default for large textures and fields. Barely there, which is the point.
- `UI`: default for structural lines and the main object's linework.
- `UI_ALT`: emphasis lines and small fills. Never a large mass; one step too bright for
  anything that covers a big part of the screen.
- `UI_HI`: small marks only (ticks, a pivot dot). If it is the brightest grey on screen,
  make sure it is also tiny.
- `MUTED`, `FG_ALT`, `FG`: rare, tiny. Almost never needed.
- `BG_DEEP`, `BLACK`: recesses and knock-outs (wells, gaps under an accent line).

The accent is the event, and there is one event. Full `ACCENT` should cover only a few
percent of the canvas (as a guide, under ~3%), and the whole accent family, dark ramp
steps included, under ~10%. The event can be a small solid shape, a single line, a
highlighted segment of a grey structure, or a short run of cells. It should be one
connected thing. A second accent spot is allowed only if it is much smaller and clearly
subordinate (a darker ramp step), and usually the design is better without it. `ACCENT_HI`
is a glint on the accent, tiny areas only.

One hue: greys plus the accent ramp. Use the ramp for depth and falloff, never for a second
colour story.

Tone steps must be visibly different at wallpaper distance:

- Use few, wide steps. Three or four accent tones (e.g. `ACCENT`, `ACCENT_1`, `ACCENT_3`,
  `ACCENT_6`) beat an eight-step ramp. Two grey steps beat four close ones.
- `ACCENT_5`..`ACCENT_8` sit close to the background. As large fills on a dark theme they
  read as brown smudges or stains. Use them for strokes, thin halos and outline-only
  fades, or skip them.
- Do not fake overlaps with `opacity`. Alpha composites land between tokens as muddy,
  off-ramp colours (and `walldye check` cannot see them). Compute the intersection with shapely
  and fill it with a chosen token.
- The brightest grey element and the accent should not compete. The eye should land on
  the accent first; if something grey is louder, knock it down a step.

### Light themes

Tokens are semantic, so they invert on light themes: greys walk from `BG` toward a dark `FG`,
and `ACCENT_1`..`ACCENT_8` walk toward a pale `BG`. So:

- `BG_DEEP` and `BLACK` are _lighter_ than `BG` on a light theme. Treat them as "away from
  the foreground", not as "dark". A drop shadow in `BG_DEEP` becomes a highlight.
- A design whose drama relied on a near-black void (shadows, space scenes) can go flat on
  paper white.
- The dark ramp steps become pale tints on paper, so fades that were muddy on dark themes
  look clean, and fades that were subtle can vanish. Pale or cool accents (rose-pine,
  nord) also make the event weaker: make it read by shape and size, not hue alone.
- On the ladder's second step, one `by_regime` can lift a whole set of roles a step, as
  glyph-terrain does with `by_regime(STEPS[k], STEPS[k + 1])`. On the third, dither-moon inks
  its shadows instead of its highlights under `if s.light:`.

Always look at a design under at least one light preset and one cool preset before calling it
done (`--theme flexoki-light`, `--theme nord`; `solarized-light` is a second light check).
`uv run walldye themes` lists the presets. When the owner names a known scheme that is not a
preset (Kanagawa, One Dark), use its published background, foreground and signature accent as
the `--theme` seeds.

## Composition

- One focal element or cluster, placed deliberately, usually off-centre on a thirds or
  golden line (roughly 0.3-0.4 or 0.6-0.7 of the long side). Dead-centre, evenly
  weighted compositions look static and disappear behind a centred window.
- Pair a quiet field with one event: the strongest pieces are low-contrast grey textures (a
  record, a lattice, a stipple, a dithered field) holding one meaningful anomaly, such as an
  escaped square, a spiking core, a lit window or a glider.
- Keep at least ~40% of the screen empty or near-empty. A full-bleed texture counts as
  "quiet" only if it is low contrast (`BG_ALT`, or thin `UI` lines).
- Keep the event away from the edges where bars and docks sit (roughly the top 60 and
  bottom 80 units) and out of the exact middle, which is the area most often covered.
- Counterweights are optional. A small isolated element far from the cluster reads as a
  stray speck or dust. Either give it a clear relationship to the main form or remove it.
- Rhythm must be either strict or clearly varied. Almost-even spacing reads as a
  spreadsheet or table; small random angle jitter reads as sloppy.
- A design needs a legible idea. If the viewer has to work out the concept rather than
  see it, exaggerate the one gesture that carries it and cut the rest (often ~40% of the
  elements).

Crops must look intentional:

- An object is either clearly inside the frame (margin of at least ~80-100 units) or
  clearly bleeding off it (at least a quarter of it off-canvas). Near-tangents, where a
  ring comes within 15-30 units of the edge, look like mistakes, and so do near-tangents between
  any two of your own outlines (a rounded corner almost touching a grid corner): overlap them
  clearly or separate them clearly.
- Repeating patterns must extend past every edge, so each edge is a mid-pattern crop.
  A last row with no row beneath it shows as a different pattern.
- Lines that run edge to edge cut the empty space in two. Stop them near the object
  unless the full-width line is the idea.

Surviving aspect changes (designs that declare `aspects="any"`):

- Size objects in plain units (the short side is always 1080) so they do not balloon on
  ultrawide or shrink on portrait. Place them with `s.pick`, `s.frac` or `s.inset`, or
  anchor them to an edge (`s.w - 420`), never with hardcoded 1920-era coordinates.
- Generate full-bleed fields by looping over the actual `s.w` and `s.h`.
- A right-thirds focal point that works at 16:9 can be cramped at 9:19.5. `s.pick` takes a
  portrait position, and `s.landscape` can switch the layout when it needs more.
  `walldye check` renders 16:9, 16:10, 21:9, 32:9, 9:19.5 and 10:16; preview at least 32:9
  and the portrait cases yourself.

## Craft at 4K

The canvas short side is 1080 units, so 1 unit is 1 px at 1080p, 1.33 px at 1440p and
2 px at 4K.

- Visible lines: at least ~1.2 units. Quiet texture hairlines: 1 unit is fine. Accent
  lines usually 2-3 units. Very heavy strokes (8+ units) are rare and deliberate.
- Things meant to be seen must survive 1080p: a 1-unit `BG_ALT` line or a 3-unit `UI`
  dot on a dark ground often disappears. Commit (raise a step or thicken) or cut it.
- Merge geometry: one `<path>` per colour and stroke style. Aim for under ~600 kB and
  ~15k elements (`walldye check` warns above that and fails above 1 MB / 20k). Use `grid_runs`, `sprite` and `glyphs`,
  which already merge runs.
- Union same-colour polygons with `shapely.unary_union` instead of stroking each piece to
  hide gaps; per-piece strokes leave seams at every shared edge.
- A stroke is centred on its path, so half of it spills outside a filled shape. Inset
  outlines by half the stroke width, or draw one line per edge instead of per-cell rects
  (per-cell rects give double lines in every gutter).
- Parallel lines closer than about two stroke widths merge into a double line or a
  bright sheet. Inset hatching from the cell edges; drop diagonals nearly parallel to an
  edge.
- Curves that join must be C1-continuous. Kinks at spline joins, boolean seams at a
  head/tail neck, and knife-thin tips (under ~3 units) all show at 4K.
- Use butt caps where a line ends at an occluding edge and round joins only at real
  corners; round caps at T-junctions leave blobs.
- No `<filter>`, no blur, no `feTurbulence`. Glow is a few discrete tone steps.

Pixel, dither and glyph work:

- Cells are integer units (2-8), and the grid origin is an integer multiple of the cell.
  Multiples of 3 also stay exact at 1440p.
- Fine high-contrast periodic patterns (pitch under ~6 units, strict on/off) moiré under
  1.25x/1.5x fractional scaling. Keep fine periodic textures low contrast or coarser.
- Commit to a resolution. Smooth curves on a coarse 3-unit grid look like an upscaled
  bitmap: either make the pixels a deliberate feature or vectorise with `iso_lines()`.
- Random salt-and-pepper cells read as compression grain. Prefer ordered or blue-noise
  dither, or deterministic tone bands; remove orphan cells and components smaller than a
  few cells.
- Vary the dither method between pieces (ordered, blue noise, error diffusion, line screen,
  Hilbert path) so each has its own grain.
- Pixel art: 4-6 colours, deliberate clusters, clean silhouettes, no pillow shading, no
  anti-aliased edges. Glyph `px` is an integer (1-3).

Draw every random number from `s.rng`, `s.np_rng` or `s.noise`. `check` fails designs whose
output changes between renders or between processes.

## Critique checklist

Look at the full preview, a thumbnail (`walldye preview <slug> --width 400`), and at least one `--crop` into the
busiest region. Then answer each question honestly:

- [ ] Does it read instantly? Would a stranger name the idea from the thumbnail?
- [ ] Is there exactly one accent event, and is it where the eye lands first?
- [ ] Is the accent area restrained, with full `ACCENT` only at the core?
- [ ] Are the greys quiet enough that a terminal over any part of it stays readable?
      What is the brightest grey, and how big is it?
- [ ] Is the composition deliberate: off-centre focal point, balanced negative space,
      margins that look chosen?
- [ ] Is every crop intentional? Any near-tangents with the frame, half-rows at an edge?
- [ ] Are tone steps distinct, with no muddy brown fades or alpha composites?
- [ ] Is it clean in the crop: no seams, double lines, kinks, spikes, stray marks,
      orphan cells, jaggies or moiré?
- [ ] Does anything only show up when zoomed in (too faint), or dominate when it should
      be background (too loud)?
- [ ] Does it survive every declared aspect and at least one light and one cool theme?
- [ ] Is the geometry identical across themes in a regime (or an intentional light template)?
- [ ] Is it a sibling of the rest of the set, not a near-duplicate? `walldye check --similar`
      only compares built pieces, so until `walldye build <slug>` has run, compare the
      preview by eye with a sheet of its nearest neighbours from `walldye list`
      (`walldye sheet <slugs>`).
- [ ] Is the meta.yaml copy theme-neutral, with every source URL fetched?
- [ ] Does any variant change what is depicted, not just a value, look different from every
      other version at thumbnail size, and read as its subject as clearly as the default?
- [ ] Is nothing on it a time, date, counter or level that could pass for a live readout?
- [ ] Does the accent come out of the picture's own logic (its shading, its light, its
      subject), not sit on top of it?
- [ ] Is it one drawing language throughout? In a dither or pixel piece, no smooth or round
      vector shape sits over the grid.
- [ ] Is it physically plausible: nothing balancing on an edge, nothing lost inside another
      body, and the science drawn to the real rule?
- [ ] Does it read as a subject rather than a logo or badge?
- [ ] Does `walldye check` pass?

Scoring, on "would this sit proudly in the set as a daily wallpaper":

- **8+ (keep)**: reads instantly, one confident event, quiet greys, clean in every crop,
  distinct from its siblings. Remaining notes are optional polish.
- **7**: good idea and composition with a few concrete polish fixes (a stray mark, a
  step too loud, an awkward margin). Fix, then re-review.
- **6**: competent but held back by something structural: too literal, too busy, muddy
  tones, idea not legible, or two competing events. Needs a real revision.
- **5 or below**: the approach fails (clip-art, loud accent mass, illegible concept).
  Rework the approach, not the parameters.

Only 8+ goes to review. A design still under 8 after a real rework goes back to the owner with
its score and the reasons (SKILL.md, Independent critique); never drop a piece the owner has
seen without asking them.

## Failure modes and fixes

Each fix names the reviews that taught it, where there was one.

| Failure                                                                   | Fix                                                                                                    |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Big flat saturated accent mass (a large solid `ACCENT` shape or orb)      | Shrink it, cap most of it at `ACCENT_1`/`ACCENT_3`, keep full `ACCENT` for a small core or edge. A giant crest, a glowing cone, a bulging orb and a thick spiral ribbon all read as a logo or a warning sign. |
| Clip-art illustration (literal trees, animals, weather, stickers)         | Abstract it to one gesture or a technical drawing of it; drop decorative extras. A bare tree with falling leaves, fireflies over grass, an iceberg and a moon behind rain looked like stock vectors. |
| Maximalist terrain (a busy low-poly landscape, stacked scenery)           | One ridge, a contour set or a dithered height field says "landscape" with far less noise.              |
| Reads as a UI (dialog chrome, spreadsheet, dashboard, product mock-up)    | Remove the chrome and the evenly ruled cells; keep the one element that carries the idea.              |
| Reads as a logo or badge (a lone crest, a bare symmetric curve)           | Show its construction (compass arcs, a crease pattern, a drafting grid) or embed it in a system. The oscilloscope's sideways figure eight looked like the Meta logo. |
| Busy full-sheet blueprint                                                 | Draw one contained object with generous margins; keep dimension and construction lines a step quieter. Orthographic projections, floor plans and exploded assemblies competed with the windows over them. |
| Full-bleed texture too bright                                             | Drop to `BG_ALT` or thin `UI` lines, lower density, fade it away from the event.                       |
| Brightest grey outshines the accent                                       | Knock that element down a grey step or thin it, so the accent is the first read.                       |
| Two accent events (sun plus ridge, dot plus needle, scattered islands)    | Keep the single largest connected accent; turn the rest grey or a much darker ramp step.               |
| Muddy tone steps (long fade into the background, brown smudges)           | Cut to 3-4 wide steps; end fades as outline-only strokes, not dark fills.                              |
| Alpha overlaps                                                            | Compute the intersection with shapely and fill it with a token.                                        |
| Stray accidental marks (orphan dots, lone counterweights, leftover rings) | Connect them to the main form or delete them.                                                          |
| Salt-and-pepper noise, orphan cells                                       | Use deterministic bands or ordered dither; drop small components.                                      |
| Symmetric dead-centre composition                                         | Move the focal point to a thirds line and let one side stay empty.                                     |
| Accidental-looking crop or near-tangent with the frame                    | Pull it inside with a real margin, or push it clearly off the edge.                                    |
| Doesn't read at thumbnail size (event is a small smudge)                  | Enlarge the event or raise its contrast; make the idea's gesture bigger.                               |
| Too faint: key parts only visible when zoomed                             | Raise a grey step or thicken to at least 1.2-1.5 units, or cut the part.                               |
| Idea not legible (worked out, not seen)                                   | Exaggerate the one gesture, cut ~40% of the elements.                                                  |
| Almost-even rhythm (table look) or random jitter (sloppy look)            | Make spacing strict, or vary it clearly with one thin and one wide interval.                           |
| Seams, double lines, kinks, boolean notches                               | Union shapes, inset strokes, smooth joins, clamp minimum tip width.                                    |
| Moiré or shimmer                                                          | Snap to integer units, coarsen or quiet fine periodic patterns, avoid packed near-parallel lines.      |
| Upscaled-bitmap look                                                      | Commit to crisp pixels on an integer grid, or vectorise with `iso_lines()`.                             |
| Near-duplicate of a sibling                                               | Change the subject or the composition, not just the parameters.                                        |
| A variant that nudges a value, or a seed ladder offered as versions       | Keep one version, or pick a variant that shows something else (a phase, a moment, a rule).             |
| A version that reads less clearly than the default                        | Drop it. Review dropped a full moon whose dither lost the terminator that makes it a sphere, birdsong that no longer read as a spectrogram, pendulums caught lined up in two rows, and a black hole seen from above that lost its bent far side. A pollution cloud that reached one nest further passed `check` and was still too close to its default. |
| A time, date, counter or level that could pass for a live readout         | Show the mechanism or the motion, and leave the reading out. The clock wall's version that spelled 11:22 across its dials looked like a frozen display. |
| An accent that looks pasted on (a solid block, a second motif)            | Carry the shading ramp on into the accent, or give it the one role the subject motivates. The ANSI teapot's solid knob and accent steam were replaced by the belly's shading ramp carried on into the accent. |
| Smooth or round vector shapes over a dither or pixel grid                 | Rebuild them on the cell grid with stepped edges and dithered faces, or drop them. The Mirror's Edge rooftop's smooth strokes, round fans and flat route blocks clashed with the dither around them. |
| Implausible physics (a cone on a table edge, an orbit inside the sun)     | Give it a clear margin, and draw the science to its real rule. The double slit showed more fringe orders than its slits allow and read as an audio meter. |
