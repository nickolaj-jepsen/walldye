# How walldye works

How walldye works and why it is built this way. [api.md](api.md) is the reference for the design API, the build files and the CLI, [wallpapers.md](wallpapers.md) has the rules for a wallpaper's metadata, words and license, [site.md](site.md) covers how the site looks and reads, and [deploy.md](deploy.md) covers CI and hosting.

## Themes

A theme is three seed colors: background, foreground and accent. `derive_theme` (`walldye/_theme.py`) turns them into 21 tokens, each a linear mix of the seeds (the table is in api.md, Colors). A theme is light when its background is brighter than its foreground, ties counting as dark. `is_light` is the one test, and the Python and TypeScript code both use it. A few tokens mix differently in the light regime, so derivation is linear within a regime but not across the two.

The presets are in `walldye/_theme.py`, each a scheme's own ground, text and accent colors, except where that accent sits so close to the text that a drawing's highlight would not stand out (rose-pine, everforest-dark, ayu-light). The site groups them into families (`src/lib/presets.ts`): most schemes pair a dark preset with a light one, and a visitor who picks a family by its name gets the preset for their system's color scheme. The default, fireproof, is the exception to derivation: its tokens are pinned by hand, well off the derived values. Exactly fireproof's seeds resolve to the pinned table everywhere (the site serves the template untouched and the CLI names the preset). Any other seeds, however close, use the derived model.

A theme is written as a preset name or as `bg-fg-accent` in hex, such as `1c1b1a-dad8ce-cf6a4c`. The same grammar serves `?t=`, the browser's storage, `--theme` and export file names, and pytest and vitest read one fixture for it. Per-token overrides are accepted nowhere, because the site could not reproduce them.

## Designs draw in formulas

A design never sees a color value. Tokens and `mix()` are symbolic `Color` formulas that compare and hash by formula and become hex only when a finished drawing is serialized under a theme. Colors cannot be sorted or printed, so geometry cannot depend on them, and one drawing per regime serves every theme.

The only theme fact a design can read is `s.light`. To look right on light themes a design works down this ladder, stopping as early as it can:

1. Tokens only. This usually works.
2. `by_regime(dark, light)` for a color that must differ by regime. Both regimes still share one template.
3. Geometry that branches on `s.light`. This costs a light template per shape and version.

Every piece is built for both regimes.

## Recoloring

`walldye build` draws each design once per version, screen shape and regime, and serializes the drawing as a template: under fireproof for the dark regime, and under flexoki-light for a light regime whose drawing differs. Every color occurrence in a template is a slot, and within a regime every slot's color is `a*bg + b*fg + c*accent + d`, with three scalars and a constant RGB vector. Build reads the coefficients off the slot's formula (a token's from the recipe `derive_theme` uses, a mix's by blending its two sides) and writes them to slots.json. The browser recolors a template by rewriting each slot from its coefficients and never runs Python.

- The coefficients are exact before rounding, but every token and every `mix` rounds to 8 bits, so a long chain of mixes drifts. The held-out check serializes each drawing under the other presets, corner themes and seeded random themes (`walldye/_check_themes.py`), and the build fails if any slot is predicted more than 2 RGB units off.
- Slots are per occurrence, not per hex value, because the same fireproof hex can come from different formulas.
- A constant slot (a = b = c = 0) recolors to itself. Only mask content may be constant, and mask content may only be constant. The API enforces both: `MASK_WHITE`, `MASK_BLACK` and their mixes are accepted only on a mask surface, which accepts nothing else. Check is the backstop, and it is what catches legacy SVGs.
- The slot tokenizer reads colors only where they paint (`fill`, `stroke`, `stop-color` and the like, as attributes, in `style=` and in `<style>`), so `url(#ad1)` is never read as a hex. Python and TypeScript share its spec.
- slots.json keeps each template's slot count, and the site shows the untouched template when the count does not match.
- Plates are `<img src=blob:>`, not inline SVG, because ids like `lg1` repeat across templates.

## Screen shapes

The site offers six shapes, `SITE_ASPECTS`: 16:9, 16:10, 21:9, 32:9, 9:19.5 and 10:16. The short side is always 1080 canvas units, so a stroke width looks the same on every shape. A design declares the shapes it composes for with `@design(aspects=...)`, or `"any"` for all of them, and lays itself out from `s.w` and `s.h`. 16:9 is always among them, because the index plates and the social cards use it.

Any other shape is a crop of the 16:9 template. The crop spans the template's full height or width and slides along the other axis. It starts centered on `focus`, the ink-weighted centroid that build stores in slots.json, and the visitor can move it (`?crop=`).

## Versions

A version is a named variant that a visitor can switch to on the piece's page: another moon phase, or a later moment of a sweep. Its values are a `Params` instance in design.py, and its label, description and draft flag are in meta.yaml.

- A version changes what is depicted, or leaves out a layer such as a drawing's dimensions; it never just nudges a value. Review judges this; check does not compare versions.
- A design has at most four named variants, so five versions with the default.
- Each version is built for every shape and regime into its own `build/<variant>/`, and is drafted or published on its own.
- A design has one page. The version shown is `?v=<name>`, and versions get no URL, social card or sitemap entry of their own.

## Legacy pieces

Pieces whose scripts were lost are a `source.svg` plus a `palette.yaml` that maps each hex to a token or a two-token mix. Build cuts the SVG at its colors, gives each slot its mapped formula and treats the result like any other drawing. Legacy pieces exist only at 16:9 and have no versions.

## Build and check

`walldye build` runs `walldye check` first and writes nothing unless it passes. For each version, check:

- imports design.py once, and runs the design lint and the meta.yaml and `data/` rules;
- draws every shape and regime twice in-process and once in a subprocess under another `PYTHONHASHSEED`, and requires identical output;
- lets the light regime share the dark template when their skeletons (the SVG without its colors) match, and otherwise makes a light template;
- runs the held-out check, and serializes under two probe themes built to break assumptions: all three seeds nearly equal, and hex values that sort opposite to fireproof's;
- enforces the constant-slot rule and the limits: no text, filters or images, and at most 1 MB and 20,000 elements.

`--similar` reports near-clones across pieces, and `--paranoid` redraws from a fresh import for every theme.

Build is incremental. slots.json records `design_sha`, a hash of design.py (or the legacy files), `data/` and the variant name; `render_lib`, a hash of the library outside `walldye/tools/`, the pinned numpy, scipy, shapely and scikit-image versions and the Python version; `probes`, hashes of a few reference renders; and `checked`, the walldye version that checked it. A new `design_sha` or walldye version rebuilds a version. A new `render_lib` only re-renders the probes, and the templates are kept when the probes match. Bumping the version in pyproject.toml is how a stricter check reaches pieces that are already built.

## CI

Build output is never committed. CI restores main's last build from the Actions cache, runs `walldye build --all --published`, which redraws only what changed and checks what it redraws, and on main saves the result as the next cache. The site is built and tested from that output, and the tested `dist/` is what deploys. A second `walldye build --all` then draws the drafts, which go into the cache and a pull request's preview but never into the tested `dist/`; a draft that fails to build is left out of the preview without failing the run. [deploy.md](deploy.md) has the workflows and the hosting.

## The site

walldye.com is a static Astro site on Cloudflare Pages.

- The `wallpapers()` loader in `src/content.config.ts` reads each meta.yaml and validates it against taxonomy.yaml and the license rules. It attaches the built templates, slots.json and design.py, leaves out drafts unless it runs in `astro dev` or with `WALLDYE_DRAFTS=1`, and curls the quotes in visible text.
- Each design has one page, `/<slug>`. Filters, sort, the index's shape, version, export shape and crop live in the query string. Templates and slots are served at `/t/<sha256[:12]>.svg` and `.slots.json` and cached as immutable (`public/_headers`). The index lists only each piece's 16:9 template URLs; a plate in another shape reads its template's hash from slots.json, which keeps the page small. Renames go in `public/_redirects`. Each piece gets a prerendered 1200x630 social card cut from its fireproof template around its focus.
- An inline script in `<head>` (`src/client/theme/boot.ts`) sets the CSS variables before first paint. The theme comes from `?t=` first, which applies for the session, is stripped from the URL and comes with an offer to keep it; then sessionStorage, then localStorage, then the default pair, fireproof and flexoki-light. localStorage holds a theme token, or `pair:<dark>,<light>` for a family chosen by its name; a pair resolves by `prefers-color-scheme` and follows it when it changes. Choosing the default family clears localStorage, which is how a visitor goes back to it. The boot stores the pair itself so it does not need the family table. Internal links carry no `?t=`, and "Copy link" adds it.
- A plate carried between a grid and its page is a cross-document view transition (`src/client/transition/`). Naming every plate would carry the whole index into the "See also" grid, so both pages name only the plate for the piece the navigation opens or leaves, which each reads from the two URLs. `pagereveal` fires at the first render, ahead of the page modules, so the listeners are an inline `<head>` script, and a detail page holds its first render until its plate is parsed. The arriving plate is still empty then, because its picture is recolored after load, so the leaving picture stays opaque under it.
- The site's CSS uses the derived tokens, with a contrast guard: text needs 4.5:1 on its ground, and controls and the focus ring 3:1. A role that falls short is mixed towards black or white by the smallest amount that passes. The wallpapers always use the raw seeds.
- `src/lib/` holds the code the build and the browser share, and ports the theme, recolor and tokenizer code to TypeScript. `src/client/` runs only in the browser, `src/server/` only at build time. Its `mix()` rounds half to even like Python's `round()`. vitest's parity tests check the port against fixtures and Python renders that `scripts/fixtures/regen.py` writes after a build, and against the constants and crop positions the Python tools define.
- The index can sort by page views. Cloudflare Web Analytics keeps a rolling window and samples a day once it is a few days old, so each finished day is recorded while it is exact, as a file on the `stats` branch rather than a commit on main ([deploy.md](deploy.md), Page views). The loader totals the days, counting a renamed slug's views for its new slug through `public/_redirects`, and gives each piece `views` and `recent`, in which a day counts half as much for every 7 days it is older than the newest day. "popular" sorts by `recent` and "most viewed" by `views`. The index starts on "featured" instead: the pieces `featured.yaml` lists, in its order, then the rest as "popular". The loader rejects a list that names a missing folder, and `walldye drop` takes a dropped piece off it. The order is fixed at build time, so each recorded day redeploys main.
- The client supports browsers with OffscreenCanvas in workers (Safari 16.4 and later). Export happens in the browser. The recolored SVG is cropped by rewriting its viewBox, and resvg-wasm rasterizes it in a worker for PNG, WebP and JPEG. Pixel pieces tag their paths with `class="px"`, and the exporter sets `crispEdges` on those paths only, since on the root it would make curves jagged.
