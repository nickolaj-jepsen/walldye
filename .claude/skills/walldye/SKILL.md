---
name: walldye
description: Design one procedural SVG wallpaper for the walldye catalogue and take it from `walldye new` through preview, check, build and review. Use when asked to make, design, add, generate, draw or rework a wallpaper or desktop background in this repo. For ten or more at once, the wallpaper-batch workflow runs this at scale.
---

# walldye

A wallpaper is a folder `wallpapers/<slug>/`: `design.py` (one `@design(...)` function
`draw(s: Canvas[...])` that draws with the `walldye` library), `meta.yaml` (title, description,
facets, sources) and `build/` (templates that only `walldye build` writes). The site recolours
the templates from each visitor's three seed colours. Colours in a design are symbolic theme
tokens, never values, so the drawing is the same under every theme of a regime (dark or light).

Run commands from the repo root as `uv run walldye <command>`; `-h` on any command lists its
flags.

## Ground rules

- Edit only `wallpapers/<slug>/design.py`, `meta.yaml` and `data/` by hand.
  `walldye build <slug>` writes `build/` and rewrites `wallpapers/index.json`, which is
  committed with the folder. Never edit `walldye/`, `taxonomy.yaml`, other pieces, or anything
  in `build/`.
- Always name the slug; never `--all`. The one exception is `walldye build --verify`, which
  is read-only and covers every piece.
- Previews go to `$WALLDYE_PREVIEW` (default `<tmp>/walldye`), never into the repo.

## Steps

1. Brief, then dedupe. Pin the idea down to one line (subject, composition, technique). With
   no brief, follow references/taste.md and references/principles.md; references/ideas.md
   has seeds, with the ones already built marked. Then check it doesn't exist yet:
   ```bash
   uv run walldye list | rg -i '<word>'
   rg -il '<word>' ~/nixos/modules/desktop/dms/wallgen/designs/   # until the M2 import
   ```
   If it does, change the subject or the composition, not the parameters.
2. Scaffold, with your own display name and model id, such as `"Claude Opus 5.5"` and
   `claude-opus-5-5` (drop a context suffix such as `[1m]` from the id):
   ```bash
   uv run walldye new <slug> --author "<model display name>" --model <model id>
   ```
   This writes a starter design.py and a draft meta.yaml (ai_generated true, added today,
   `draft: true`, no `license:`).
3. Write design.py, starting from the nearest file in examples/ and references/api.md. Decide
   the aspects: `@design(aspects="any")` whenever the composition can follow `s.pick`,
   `s.frac` and `s.inset`; leave it out for 16:9 only, and the site crops other screen shapes
   from that.
4. Preview for at least three rounds. Each run prints lint lines, `regime:`,
   `light geometry:` and, last, the PNG path. Read the PNG, critique it against the checklist
   in references/principles.md, revise.
   ```bash
   uv run walldye preview <slug>
   uv run walldye preview <slug> --crop X,Y,W,H          # canvas units, the busiest area
   uv run walldye preview <slug> --aspect 32:9           # with aspects, also 9:19.5 and 10:16
   uv run walldye preview <slug> --theme flexoki-light   # from round 2 on, and --theme nord
   uv run walldye preview <slug> --width 400             # thumbnail size, how it is mostly seen
   uv run walldye sheet <slug> --seeds 0..7              # choosing a seed
   uv run walldye sheet <slug> --wedge sweep=0..360..45  # choosing a knob's value
   ```
   `--set k=v` tries one params value in preview, render or sheet without publishing it.
5. Work through the light ladder (below).
6. Variants, only where the piece has a natural one (see Variant policy). Propose at most 3,
   each a `Params` instance in `@design(variants=...)`, previewed with `--variant <name>`,
   passing `uv run walldye check <slug> --variant <name>`, and listed in meta.yaml with
   `draft: true`. Most pieces have none.
7. Fill in meta.yaml (below). If any source has `kind: recreation`, ask the owner which
   `license:` to set; build fails without one.
8. `uv run walldye check <slug>` must report no errors. It covers every variant and runs ruff
   and Pyrefly on design.py; `uv run ruff format wallpapers/<slug>` fixes formatting.
   Warnings are judgement calls, except colour words and fractional grid origins: fix those. A
   check takes from a few seconds to about half a minute (a dense `aspects="any"` piece with
   variants is the slow end, and heavy simulations take longer), so give it a 600000 ms Bash
   timeout; `build` takes as long.
9. `uv run walldye build <slug>`, then `uv run walldye check --similar <slug>`: after running
   the whole check again, it prints `similar (0.95): a ~ b` for each built piece whose
   thumbnail nearly matches yours. Before committing, run `uv run walldye build --verify` over
   all pieces; a `DRIFT` line means a committed render changed and needs a look first.
10. `uv run walldye review <slug>` with `run_in_background`. It serves a local page, blocks
    until the owner presses Done, then prints JSON with the approved, rejected (with notes),
    published and refused slugs, and the same for variants. Act on the notes. Review never
    edits design.py: remove a rejected variant from design.py and meta.yaml by hand. Confirm
    with the owner before `uv run walldye drop <slug> --yes` on a reject.

## Geometry rules

`check` draws every version, native aspect and regime once, writes each drawing under many
themes, and fits how every colour moves with the seeds. The API keeps most mistakes out:

- Colours are formulas, never values. Key buckets, dicts and sorts by role or index
  (`s.buckets`, a `ladder` and `TONES.rung(v)`), and give an explicit sort key where order
  matters: sorting colours raises, and so does `str()` of one.
- `s.light` is the only theme-dependent control flow; for a per-regime colour use
  `by_regime(dark, light)`.
- Mask content is `MASK_WHITE`, `MASK_BLACK` and mixes of the two.
- Randomness comes only from `s.rng(key)`, `s.np_rng(key)` and `s.noise(key)`, and nothing at
  module level changes while drawing.
- One path per paint and stroke style. No text elements (draw characters with `glyphs()`), no
  filters, no images: the API cannot write them. Aim under 600 kB and 15k elements.
- Pixel work goes through `grid_runs`, `Pixels`, `sprite` or `glyphs` from `walldye.pixel`,
  with the origin snapped to the cell grid (`s.pick(..., snap=CELL)`).

## Light ladder

Stop at the first step that gives a good flexoki-light render:

1. Tokens only.
2. A per-regime colour, `STRUCT = by_regime(UI, MUTED)` (dark first). One template still
   serves both regimes.
3. A geometry branch under `if s.light:`. Build adds a light template per native aspect.
4. `themes: [dark]` in meta.yaml, only after steps 2 and 3 were tried, with the reason in
   `notes`.

references/themes.md has the details.

## Variant policy

A variant is a named version of a piece, shown on its page as a version the visitor can switch
to. Each one is built for every aspect and regime, reviewed and kept, so the bar is high:

- A variant must change what is depicted (a moon phase, a rule number, a reaction regime, the
  moment of a sweep), not nudge a value. A new seed is a variant only when the result shows
  something different; seed ladders are for `sheet --seeds`, never for the site.
- At most 4 named variants per design (5 versions with the default). Propose at most 3, and
  always as `draft: true`; the owner approves each one in `walldye review`.
- Every two versions of a piece must look different at thumbnail size: `check` fails an
  ink-map cosine of 0.93 or more. A piece with a large fixed structure fails this with a
  detail-only change: radar-sweep's rings and afterglow dominate its thumbnail, so a new
  coastline measures 0.98 against the default, and only moving the arm passes (0.20).
  Passing is necessary, not sufficient: on a fine-textured piece a 4% nudge of one value
  can measure 0.91 and pass, so judge by eye whether the subject changed.
- Values live in design.py, copy and state in meta.yaml. There is no variant name inside
  `draw`: branch on params.

## meta.yaml

Keep the keys `walldye new` wrote, in that order, and add no comments: review rewrites the file.

- `title`: a short, plain name in sentence case, like "Radar sweep" or "One-bit moon".
- `description` and `notes`: see Copy rules. Notes are optional Markdown shown on the page.
- `technique`, `subject`, `lineage`: only values listed in taxonomy.yaml. Put anything missing
  in `proposed_facets` (`{technique: [value]}`, drafts only); the owner decides in review.
- `sources`: a list of `{kind, title, author, year, url}`. `kind` is `recreation` (after a
  specific work), `inspiration` (suggested by one), `reference` (a technique, paper or fact)
  or `data` (real data drawn). Leave out any field you can't confirm. Fetch every URL with
  WebFetch before writing it, and keep it only when the page loads and shows what you cite.
  Never write a URL from memory.
- `license`: leave it out for the CC0-1.0 default. A recreation needs an explicit one from
  the owner. Game and franchise pieces use `LicenseRef-fan-work` plus
  `franchise: {title, owner}`; ask the owner before using it.
- `themes`: leave it out (dark and light) unless the ladder reached step 4.
- `variants`: only when design.py declares named variants. The keys are exactly `default`
  plus the declared names. Each needs a `label` (one to four plain words naming what that
  version shows, unique within the piece); a named variant may add a `description`, shown
  instead of the piece's, and carries `draft: true` until review approves it:
  ```yaml
  variants:
    default: {label: Early in the turn}
    late: {label: Late in the turn, draft: true}
  ```
- `author`, `ai_generated`, `model`, `added`, `draft`: as `new` wrote them. Review flips
  `draft`.

## Copy rules

They cover everything a visitor reads: title, description, notes, variant labels and
descriptions, source titles, and design.py, which the site publishes as source code. Claude
drafts, the owner approves.

- A description is one or two short sentences, at most 30 words. It doubles as the alt text
  and the page lede, so say concretely what is drawn and how. Vary its shape from the last few
  pieces (`walldye list` shows them).
- Theme-neutral: no colour names (terracotta, orange, grey) and no theme roles as nouns ("the
  accent", "the background"). Say what is picked out, filled in or lit.
- No evaluative adjectives (stunning, mesmerising, elegant, timeless). Run the avoid-ai-tropes
  skill on every draft.
- Use words a visitor would use. Never: regime, seed, token, native, hand-tuned, light-ready,
  preset, variant, param, slot, template, derived, licence names or identifiers, contrast
  ratios, colour tolerances, pixel sizes, keyboard hints. Visitors see variants as versions.
- Italics only for titles of works (`*Schotter*` in notes). Source titles stay plain text;
  the site italicises them itself.
- The design.py docstring is one theme-neutral line: concept plus technique. Comments name
  tokens or roles (`UI`, the accent ladder), never hues or temperatures ("warm", "cool"). The
  colour-word lint is a plain word list that also matches plurals, so "golden section",
  "black" and "greys" trip it as well. It does not know temperatures; avoid them by hand.

## References

- references/api.md: the design API for authors: anatomy, colours, canvas and layout,
  drawing, paths and angles, random streams, params and variants, the helper modules
  (`walldye.geom`, `walldye.field`, `walldye.pixel`) and the check limits. `docs/api.md` has
  every exact signature.
- references/principles.md: house style, critique checklist, failure modes.
- references/themes.md: tokens, presets, regimes and the light ladder in full.
- references/taste.md: what the owner likes and rejects.
- references/ideas.md: about 150 seeds, built ones marked, and lessons from review.
- examples/: dither-moon (blue-noise dither, a light geometry branch, phase variants),
  radar-sweep (instrument, grains bucketed by tone index, a clip, one variant),
  glyph-terrain (glyph roles, per-regime colours), pixel-invaders (sprites, buckets),
  patent-lamp (patent drawing placed by one transform), eclipse-contours (iso-lines in a
  clip), ribbons (flow field), hitomezashi (stitch tiling). Every one passes `walldye check`.
