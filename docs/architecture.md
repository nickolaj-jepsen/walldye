# How walldye works

## Themes

A theme is three seed colors: background, foreground and accent. `derive_theme` (`walldye/_theme.py`) mixes them into 21 tokens (table in api.md, Colors). A theme is light when its background is brighter than its foreground; `is_light` is the only test, in both Python and TypeScript. A few tokens mix differently on light themes, so derivation is linear within a regime but not across both.

Presets live in `walldye/tools/themes.py`, and the site groups them into dark and light families (`src/lib/presets.ts`); picking a family by name follows the system color scheme. The default, fireproof, has hand-pinned tokens. Only its exact seeds get that table; any other seeds are derived.

A theme is written as a preset name or `bg-fg-accent` in hex (`1c1b1a-dad8ce-cf6a4c`), everywhere: `?t=`, browser storage, `--theme` and export file names. There are no per-token overrides, because the site couldn't reproduce them.

## Designs draw in formulas

Designs never see color values. Tokens and `mix()` are symbolic formulas that only become hex when a finished drawing is serialized under a theme. Since colors can't be sorted or printed, geometry can't depend on them, and one drawing per regime covers every theme.

The one theme fact a design can read is `s.light`. For light themes, stop at the first step that works:

1. Tokens only. Usually enough.
2. `by_regime(dark, light)` for a color that must differ. Still one template.
3. Geometry that branches on `s.light`. Costs a light template per shape and version.

## Recoloring

`walldye build` draws each design once per version, shape and regime, and saves the drawing as a template: under fireproof, plus flexoki-light when the light drawing differs. Each color occurrence is a slot, and every slot is `a*bg + b*fg + c*accent + d` within a regime. Build reads the coefficients off the slot's formula and writes them to slots.json, and the browser recolors by rewriting slots. Python never runs in the browser.

- Tokens and mixes round to 8 bits, so long mix chains drift. Build fails if any slot is more than 2 RGB units off under the held-out themes in `walldye/tools/themes.py`.
- Slots are per occurrence, not per hex, because one hex can come from different formulas.
- Only mask content may be constant (a = b = c = 0), and mask content may only be constant. The API enforces it; check catches it in legacy SVGs.
- The tokenizer reads colors only where they paint, so `url(#ad1)` is never a hex. Python and TypeScript share its spec.
- If a template's slot count doesn't match slots.json, the site shows it unrecolored.
- Plates are `<img src=blob:>`, because ids like `lg1` repeat across templates.

## Screen shapes

The site offers the shapes in `SITE_ASPECTS`. The short side is always 1080 units, so a stroke looks the same everywhere. A design lists the shapes it composes for in `@design(aspects=...)`, or `"any"`, and lays out from `s.w` and `s.h`. 16:9 is always included; the index and social cards use it.

Any other shape is cropped from the 16:9 template, at full height or width, starting at `focus` (the ink-weighted centroid in slots.json). Visitors can slide it (`?crop=`).

## Versions

A version is a named variant a visitor can switch to, like another moon phase. Its values are a `Params` instance in design.py; its label, alt text, description and draft flag are in meta.yaml.

- A version changes what's depicted, or drops a layer; it never just nudges a value. Review judges this, not check.
- At most four named variants, so five versions with the default.
- Each builds into its own `build/<variant>/` and is published on its own.
- One page per design. The version is `?v=<name>`, with no URL, social card or sitemap entry of its own.

## Legacy pieces

Pieces whose scripts were lost are a `source.svg` plus a `palette.yaml` mapping each hex to a token or two-token mix. Build slots the SVG by that map and treats it like any drawing. They're 16:9 only, with no versions.

## Build and check

`walldye build` runs `walldye check` first and writes nothing if it fails. Per version, check:

- runs the design lint and the meta.yaml and `data/` rules;
- draws every shape and regime twice in-process and once under another `PYTHONHASHSEED`, and requires identical output;
- shares the dark template with the light regime when the drawings match apart from color;
- runs the held-out check, plus two probe themes: near-equal seeds, and hex values that sort opposite to fireproof's;
- enforces the constant-slot rule, no text, filters or images, and at most 1 MB and 20,000 elements.

A design's `@cached` functions (api.md §9.1) run once per process for each distinct call, so the in-process draws share them while the PYTHONHASHSEED process computes them afresh, which still tests that they are deterministic. Check and build never read the disk copies that preview, render and sheet keep: a stale file can mislead a preview, never a template.

Build is incremental. slots.json records `design_sha` (the version's inputs) and `toolchain` (`walldye/tools/hashing.py`). A new `design_sha` rebuilds. A new `toolchain` alone draws once and compares the output; if it matches, only the stamp changes. Lints run on every piece at every build, so stricter rules apply at once; a stricter determinism check needs `walldye build --force`.

## CI

CI renders the catalog from main's last build in the Actions cache, so it only redraws what changed, and deploys the `dist/` it tested. Drafts are drawn afterwards for the cache and PR previews, never into that `dist/`, and a broken draft doesn't fail the run. [deploy.md](deploy.md) has the workflows.

## The site

walldye.com is a static Astro site on Cloudflare Pages.

- The loader (`src/server/catalog/loader.ts`) reads meta.yaml the way PyYAML does and checks only what pages need to render; `walldye check` owns the rest. It attaches templates, slots.json and design.py, hides drafts outside `astro dev` and `WALLDYE_DRAFTS=1`, and curls quotes.
- One page per design, `/<slug>`. Filters, sort, shape, version and crop are in the query string. Templates and slots are served by hash at `/t/` and cached as immutable. The index lists only 16:9 templates; other shapes look up their hash in slots.json, which keeps the page small. Each piece gets a 1200x630 social card cropped around its focus.
- An inline `<head>` script (`src/client/theme/boot.ts`) sets the CSS variables before first paint. The theme comes from `?t=` (for the session, with an offer to keep it), then sessionStorage, then localStorage, then fireproof and flexoki-light. A family chosen by name is stored as `pair:<dark>,<light>` and follows `prefers-color-scheme`. Choosing the default family clears storage. Internal links carry no `?t=`; "Copy link" adds it.
- A plate moving between a grid and its page is a cross-document view transition (`src/client/transition/`). Only that one plate is named, or the whole index would fly into "See also". The listeners are inline in `<head>` because `pagereveal` fires before page modules load. The arriving plate is still empty then, so the leaving one stays opaque under it.
- Site CSS uses the derived tokens with a contrast guard: 4.5:1 for text, 3:1 for controls and the focus ring. A failing role is nudged towards black or white just enough. Wallpapers always use the raw seeds.
- The index can sort by page views. Cloudflare samples days once they're a few days old, so each finished day is saved while exact, as a file on the `stats` branch ([deploy.md](deploy.md), Page views). The loader totals them, follows renames through `public/_redirects`, and weighs recent days more (`HALF_LIFE_DAYS` in `src/server/views.ts`). The order is fixed at build time, so each recorded day redeploys.
- The client needs OffscreenCanvas in workers (Safari 16.4+). Export runs in the browser: the recolored SVG is cropped via its viewBox, and resvg-wasm rasterizes PNG, WebP and JPEG in a worker. Only pixel pieces' `px` paths get `crispEdges`; on the root it would make curves jagged.
