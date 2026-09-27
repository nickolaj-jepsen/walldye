---
name: walldye
description: Design one procedural SVG wallpaper for the walldye catalogue and take it from `walldye new` through preview, check, build and review. Use when asked to make, design, add, generate, draw or rework a wallpaper or desktop background in this repo. For ten or more at once, the wallpaper-batch workflow runs this at scale.
---

# walldye

A wallpaper is a folder `wallpapers/<slug>/`: `design.py` (a seeded `draw(s)` that draws with
the `walldye` library in theme tokens), `meta.yaml` (title, description, facets, sources) and
`build/` (templates that only `walldye build` writes). The site recolours the templates from
each visitor's three seed colours, so a design must colour everything with tokens and keep its
drawing identical across themes of one regime (dark or light).

Run commands from the repo root as `uv run walldye <command>`; `-h` on any command lists its
flags.

## Ground rules

- Edit only `wallpapers/<slug>/design.py` and `meta.yaml` by hand. `walldye build <slug>`
  writes `build/` and rewrites `wallpapers/index.json`, which is committed with the folder.
  Never edit `walldye/`, `taxonomy.yaml`, other pieces, or anything in `build/`.
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
3. Write design.py, starting from the nearest file in examples/ and the helpers in
   references/api.md. Decide `ASPECTS`: `["any"]` when the composition follows `W`/`H`;
   leave it out for 16:9 only, and the site crops other screen shapes from that.
4. Preview for at least three rounds. Each run prints lint lines, `regime:`,
   `light geometry:` and, last, the PNG path. Read the PNG, critique it against the checklist
   in references/principles.md, revise.
   ```bash
   uv run walldye preview <slug>
   uv run walldye preview <slug> --crop X,Y,W,H          # canvas units, the busiest area
   uv run walldye preview <slug> --aspect 32:9           # with ASPECTS, also 9:19.5 and 10:16
   uv run walldye preview <slug> --theme flexoki-light   # from round 2 on, and --theme nord
   uv run walldye preview <slug> --width 400             # thumbnail size, how it is mostly seen
   ```
5. Work through the light ladder (below).
6. Fill in meta.yaml (below). If any source has `kind: recreation`, ask the owner which
   `license:` to set; build fails without one.
7. `uv run walldye check <slug>` must report no errors. Warnings are judgement calls, except
   colour words, `luminance(`/`hex_to_rgb(` calls and fractional grid origins: fix those.
   A check takes from about 15 seconds to 5 minutes (a dense `ASPECTS = ["any"]` piece is
   the slow end), so give it a 600000 ms Bash timeout; `build` takes as long.
8. `uv run walldye build <slug>`, then `uv run walldye check --set <slug>`: after running
   the whole check again, it prints `similar (0.95): a ~ b` for each built piece whose
   thumbnail nearly matches yours. Before committing, run
   `uv run walldye build --verify` over all pieces; a `DRIFT` line means a committed render
   changed and needs a look first.
9. `uv run walldye review <slug>` with `run_in_background`. It serves a local page, blocks
   until the owner presses Done, then prints JSON with the approved, rejected (with notes),
   published and refused slugs. Act on the notes. Confirm with the owner before
   `uv run walldye drop <slug> --yes` on a reject.

## Geometry rules

`check` renders every native aspect under a set of themes per regime, plus one theme where bg,
fg and accent are equal and one whose token hex strings sort the other way, and fails when the
drawing changes within a regime.

- Key dicts, sorts and path buckets by role or index, never by hex: `glyphs(..., key=role)`,
  tone lists indexed by int.
- Never compare token values (`if c == UI`), or feed colour distances or luminance into
  geometry.
- `if is_light():` is the only theme-dependent control flow.
- Mask content is `#fff`/`#000` only. Every other colour is a token or a
  `mix()`/`ramp()`/`accent_ramp()` of tokens.
- Seed all randomness (`rng(n)`, `np.random.default_rng(n)`, `Noise(n)`), and never iterate
  a set of strings.
- One `<path>` per colour and stroke style. No `<text>` (draw characters with `glyphs()`), no
  `<filter>`, no `<image>`. Aim under 600 kB and 15k elements.
- Pixel work goes through `grid_runs`, `sprite` or `glyphs`, with the origin snapped to the
  cell grid.

## Light ladder

Stop at the first step that gives a good flexoki-light render:

1. Tokens only.
2. A per-regime token choice, `STRUCT = MUTED if is_light() else UI`. One template still
   serves both regimes.
3. A geometry branch under `if is_light():`. Build adds a light template per native aspect.
4. `themes: [dark]` in meta.yaml, only after steps 2 and 3 were tried, with the reason in
   `notes`.

references/themes.md has the details.

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
- `author`, `ai_generated`, `model`, `added`, `draft`: as `new` wrote them. Review flips
  `draft`.

## Copy rules

They cover everything a visitor reads: title, description, notes, source titles, and
design.py, which the site publishes as source code. Claude drafts, the owner approves.

- A description is one or two short sentences, at most 30 words. It doubles as the alt text
  and the page lede, so say concretely what is drawn and how. Vary its shape from the last few
  pieces (`walldye list` shows them).
- Theme-neutral: no colour names (terracotta, orange, grey) and no theme roles as nouns ("the
  accent", "the background"). Say what is picked out, filled in or lit.
- No evaluative adjectives (stunning, mesmerising, elegant, timeless). Run the avoid-ai-tropes
  skill on every draft.
- Use words a visitor would use. Never: regime, seed, token, native, hand-tuned, light-ready,
  preset, slot, template, derived, licence names or identifiers, contrast ratios, colour
  tolerances, pixel sizes, keyboard hints.
- Italics only for titles of works (`*Schotter*` in notes). Source titles stay plain text;
  the site italicises them itself.
- The design.py docstring is one theme-neutral line: concept plus technique. Comments name
  tokens or roles (`UI`, the accent ramp), never hues. The colour-word lint is a plain word
  list, so "golden section" and "black" trip it as well.

## References

- references/api.md: every helper, `is_light()`, `SITE_ASPECTS`, the pixel helpers'
  `class="px"` paths and cells, `glyphs(key=...)`, masks and the check limits.
- references/principles.md: house style, critique checklist, failure modes.
- references/themes.md: tokens, presets, regimes and the light ladder in full.
- references/taste.md: what the owner likes and rejects.
- references/ideas.md: about 150 seeds, built ones marked, and lessons from review.
- examples/: dither-moon (blue-noise dither, light geometry branch), radar-sweep (instrument,
  tone buckets by index), glyph-terrain (glyph roles, per-regime tokens), pixel-invaders
  (sprites), patent-lamp (patent drawing), eclipse-contours (contours in a clip), ribbons (flow
  field), hitomezashi (stitch tiling). Every one passes `walldye check`.
