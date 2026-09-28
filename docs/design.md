# walldye: design

How walldye works and why. [api.md](api.md) is the reference for the design API, the file formats and the CLI, with every signature; [site.md](site.md) is the reference for how the site looks and what it says. This file links to both instead of repeating them. Update it in the same change when a decision here changes.

## What it is

A catalogue of procedural SVG wallpapers at walldye.com. Each piece is a small seeded Python script that draws with the `walldye` library in symbolic theme colours. Visitors pick three seed colours (background, foreground and accent), the wallpapers and the site itself are recoloured from them, and any wallpaper can be downloaded as SVG, PNG, WebP or JPEG at the common screen sizes.

## Repository

- One repository holds the library and CLI (`walldye/`), the designs, their metadata and their generated templates (`wallpapers/`), the site (`src/`), CI and deploy, and the Claude tooling (`.claude/`).
- Python is a uv project (`pyproject.toml`, `uv.lock`, `.python-version` pinned to 3.13) with the console script `walldye`. The prebuilt wheels need `programs.nix-ld.enable` on NixOS; there is no Nix devShell.
- The site is Astro, built with pnpm on Node 24 (`packageManager` in package.json, `.node-version`).
- CI never runs Python. Everything Python produces (templates, slots.json, index.json, the hash stamp, the test fixtures) is committed, and CI checks it with TypeScript ports of the hash and tokenizer code. Render drift from dependency bumps or another machine is caught locally with `walldye build --verify`.
- Python is formatted and linted with ruff (line length 100, import sorting; config in pyproject.toml), including the ` ```python ` blocks in Markdown. Types are checked with Pyrefly: the library at the strictest preset through a pytest test, each design at the standard level inside `walldye check` (api.md §15).

## Layout

```
walldye/
  __init__.py                 # the core design API, re-exports only (api.md §2)
  geom.py field.py pixel.py   # helper modules designs import
  _colour.py _vec.py _affine.py _path.py _params.py _noise.py _canvas.py _document.py _design.py
                              # the core's implementation
  _aspect.py                  # SITE_ASPECTS, canvas sizes, template names
  _theme.py                   # presets, derive_theme, is_light, parse_theme
  _check_themes.py            # the held-out, probe and sample themes the checks serialise under
  font.py                     # Spleen bitmap glyphs (BSD-2-Clause)
  __main__.py                 # `python -m walldye`, used by the determinism subprocess
  tools/                      # the CLI, check, build, review; outside the render-lib hash
wallpapers/<slug>/
  design.py                   # @design(...) def draw(s: Canvas[...]); absent for legacy pieces
  data/                       # optional .json, .txt and .npy files read with s.data()
  source.svg, palette.yaml    # legacy script-less pieces only
  meta.yaml
  build/                      # generated and committed; only `walldye build` writes here
    16x9.svg                  # the default version's fireproof template
    16x9.light.svg            # rendered under flexoki-light, only when light geometry differs
    <aspect>[.light].svg      # the other aspects the design composes for
    slots.json                # hashes, focus, cells, probes, and the slot coefficients per template
    <variant>/                # one directory per named variant, laid out the same way
wallpapers/index.json         # generated summary of every built piece
wallpapers/.render-lib.sha256 # generated hash of the render inputs
wallpapers/pyrefly.toml       # the type-check level for designs
taxonomy.yaml                 # the allowed facet values
src/                          # the Astro site
scripts/                      # check-artifacts.ts (CI's stale-build check), fonts/ (the subset fonts)
tests/                        # pytest, vitest, Playwright and the shared fixtures
infra/www-redirect/           # the www to apex Worker
.claude/                      # the walldye skill and the wallpaper-batch workflow
```

## Theme model

- Three seeds, `bg`, `fg` and `accent`. All 21 tokens derive from them through `derive_theme`, as linear mixes (api.md §4.2 has the table).
- Two regimes. Light means `luminance(bg) > luminance(fg)`; ties count as dark. `is_light(bg, fg)` is the one test, and derive_theme, build's regime selection, colour resolution and the TypeScript port all use it.
- Designs never see colour values. Tokens and `mix()` are symbolic `Colour` formulas that compare and hash by formula and resolve to hex only when a document is serialised under a theme (api.md §4). The only theme fact a design can read is `s.light`, and `by_regime(dark, light)` picks a colour per regime without branching. Because geometry cannot depend on a colour value, one drawing per regime serves every theme.
- Presets: fireproof, flexoki-light, gruvbox-dark, nord, catppuccin-mocha, tokyo-night, rose-pine, everforest-dark, ayu-dark, dracula and solarized-light.
- `fireproof` pins all 21 tokens by hand, well off the derived values (the accent ramp by up to 21 units).
  - Exact fireproof seeds, compared as uppercase `#RRGGBB`, resolve to the pinned preset everywhere: the site serves the template untouched, the site CSS uses the pinned table, and the CLI resolves `--theme 1c1b1a-dad8ce-cf6a4c` to `fireproof`.
  - Any other seeds use the derived model, so a 1-unit edit next to fireproof moves the accent ramp by up to 21 units. The picker does not mark fireproof as special.
  - Fireproof is not in the held-out set: its pinned tokens have no coefficients to check.
- `--theme` accepts only a preset name or three seeds. Per-token overrides are rejected: the site could not reproduce them.

### Theme token

One grammar serves `?t=`, localStorage, the CLI's `--theme` and export file names:
- A theme is a preset name or `<hex6>-<hex6>-<hex6>` (bg-fg-accent, no `#`, case-insensitive, canonical lowercase).
- The CLI also accepts `bg,fg,accent` and `bg=#..,fg=#..,accent=#..`.
- Each seed must match `^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$` and is normalised to uppercase `#RRGGBB`.
- pytest and vitest parse the same token fixture.

### Picker

- Two groups: "Themes", the presets, and "Colours", three hex fields labelled Background, Foreground and Accent (site.md §6.3). No per-token overrides.
- Fields accept 3 or 6 digits, with or without `#`. Pasting a full theme token fills all three.
- Invalid input sets `aria-invalid` and shows "Use a hex colour, like #CF6A4C."
- Valid input applies after a 250 ms debounce. Escape reverts, unadvertised.
- When the raw bg/fg contrast is under 3:1 the picker warns "The background and foreground are too close, so wallpapers will be hard to see." It shows no regime or contrast readout.

### Resolution and persistence

1. `?t=<token>`: read on load, copied into sessionStorage and stripped with `history.replaceState`. It applies for the session and is not saved. While the session theme differs from the saved one, the header shows "You're looking at a shared theme." with "Keep it" and "Back to yours". Any picker edit saves it and clears the session theme. Invalid values are ignored.
2. sessionStorage.
3. localStorage. Every storage access is guarded; when a write fails, the token is kept on `<html>` for the rest of the page.
4. `prefers-color-scheme`: fireproof or flexoki-light. While nothing is saved, a matchMedia listener re-themes on change.

Internal links carry no `?t=`; "Copy link" always includes it. The inline `<head>` script that sets the CSS variables before first paint is `src/lib/theme-boot.ts`, bundled by esbuild in `src/lib/theme-boot-script.ts` and emitted `is:inline`, so the derivation and guard logic exist once, in `src/lib/theme.ts`.

### Site theming

- The site's CSS uses the same derived tokens as the wallpapers; the wallpapers always use the raw seeds. site.md §2 lists every role.
- Contrast guard:
  - Text roles (fg, fg_alt, accent as link and error text, the listing's colours) need 4.5:1 on bg or bg_alt. muted is not a text colour; it draws only the dot leaders.
  - The focus ring, swatch rings and field underlines need 3:1 (WCAG 1.4.11).
  - Hairline rules are exempt.
  - The nudge is the smallest t, found by binary search, for `mix(c, pole, t)`, where the pole is whichever of black and white contrasts more with the surface.
  - It is active by default: fireproof's accent is 4.13:1 on bg_alt, so its listing keyword colour is nudged.
- TypeScript port rules:
  - `mix()` rounds half to even like Python's `round()`: fireproof-derived accent_3's green channel, 66.5, becomes 66, where `Math.round` gives 67.
  - Output is uppercase, and the pinned fireproof table ships with it.
  - Tests read `src/lib/__fixtures__/themes.json`, written by `walldye themes --json`: every preset, at least 20 seeded random triples per regime, and the edge cases bg==fg and #777777/#787878.

## Recolouring pipeline

- Every output colour is `a*bg + b*fg + c*accent + d` (scalars a, b, c and a constant RGB vector d), with one coefficient set per regime. Every token is a linear mix of the seeds within a regime and `mix()` is linear, so this is exact up to 8-bit rounding. The browser recolours a template by rewriting its colours from these coefficients; it never runs Python.
- Render model: a design is drawn once per (variant, aspect, regime) into a document, and that document is serialised under every theme the checks need (api.md §10.4). The per-theme work is only resolving colours. `walldye check --paranoid` also redraws from a fresh import for every theme and requires identical output.
- Coefficients:
  - Build reads each slot's coefficients off its colour's formula (`Document.coefs()`, api.md §10.2): a token's come from the recipe `derive_theme` uses, a `mix` blends its two sides, `by_regime` takes its regime's side, and a mask colour is constant. Build used to fit them by least squares over a basis of 8 random themes per regime; the formula gives them exactly, with no basis to keep well-conditioned.
  - They are exact before rounding, but every token and every `mix` rounds to 8 bits once, so a long chain of mixes drifts from them. The held-out check catches that drift: each regime's document is serialised under every preset except fireproof, corner themes (#000000/#FFFFFF extremes, accent==fg, accent==bg, a bg/fg luminance gap of about 0.05) and seeded random themes (`walldye/_check_themes.py`), and every slot must be predicted within 2 RGB units, or build fails. It samples rather than bounds: the `rounding` test fixture, 18 nested mixes, misses by 4 units, and 12 of them pass the held-out set yet miss by 4 elsewhere. On the catalogue the worst slot over 200 random themes per piece is 1 unit, where the fit reached 2.
  - Two probe themes per regime join the serialisation checks. One sets bg, fg and accent (almost) equal, which collapses every token; the other makes token hex strings sort opposite to fireproof's.
  - The fireproof-pinned render is only skeleton-checked. Its tokens are not derived, so exact fireproof seeds get the template untouched rather than a prediction.
- Coefficients are per colour occurrence (a slot), not per hex value. The same fireproof hex can come from different formulas, through rounding in adjacent fade steps, and per-occurrence slots are exact and cost nothing.
- Constant slots: there is no mask special case in the browser. A mask colour has a=b=c=0 and recolours to itself. `walldye check` allows a constant slot only inside `<mask>` or `<clipPath>`, or in a gradient or pattern referenced only from those. A theme-dependent slot inside a mask is an error, and any other constant slot counts as hardcoded and fails. The API makes both mistakes hard to write: the only constant colours are `MASK_WHITE`, `MASK_BLACK` and mixes of the two, which only a mask surface accepts, and a mask surface rejects theme colours. The rule is the backstop, and it is what catches legacy SVGs.
- Light ladder, in order of preference:
  1. Tokens only.
  2. A per-regime colour, `by_regime(UI, MUTED)`, which keeps one template.
  3. A geometry branch on `s.light`, which costs a light template per aspect and variant.
- Every piece is built for both regimes. A `themes: [dark]` opt-out, shown under light seeds with bg and fg swapped, was removed in September 2026 when no piece used it.
- Legacy pieces, whose scripts were lost, are `source.svg` plus `palette.yaml`, which maps each distinct hex to a token or a two-token mix. Build cuts source.svg into a document at its colour slots, gives each slot its mapped formula, and builds it like any other document (api.md §12.4). Legacy pieces have only the default version, at 16:9.
- Slot tokenizer: one spec, with a fixture shared by Python and TypeScript.
  - It matches colour values only in paint contexts: the attributes fill, stroke, stop-color, flood-color, lighting-color and color, and the same properties inside `style=` and `<style>`.
  - Values are hex3, hex6 or named. `none`, `currentColor` and `url(...)` are skipped; a bare-hex regex would rewrite `url(#ad1)`.
  - Every matched value is written as uppercase `#RRGGBB` in the committed template.
- slots.json holds, per template, `{file, sha256, n, coefs: [[a,b,c,dr,dg,db], ...] (deduplicated, 5 dp), occ: [coef index per occurrence]}`. The browser checks `n` and falls back to the untouched template on a mismatch.
- Plates are displayed as `<img src=blob:>`. Inline SVG is avoided because ids like `lg1` repeat across files.

## Aspect ratios

- The aspect set is `SITE_ASPECTS`: 16:9, 16:10, 21:9, 32:9, 9:19.5 and 10:16. check, build and the site all use it.
- A design declares the aspects it composes for in `@design(aspects=...)`: `"any"` for all of them, or a tuple. 16:9 is always native. It composes from `s.w` and `s.h`, usually through `s.frac`, `s.pick(landscape=, portrait=, snap=)`, `s.center` and `s.inset(margin)`; module-level code cannot see the canvas.
- Coordinates are pixels and the short side is always 1080:

  | Aspect | Canvas |
  |---|---|
  | 16:9 | 1920x1080 |
  | 16:10 | 1728x1080 |
  | 21:9 | 2520x1080 |
  | 32:9 | 3840x1080 |
  | 9:19.5 | 1080x2340 |
  | 10:16 | 1080x1728 |
- Templates are named after the aspect: `16x9.svg`, `16x10.svg`, `21x9.svg`, `32x9.svg`, `9x19.5.svg`, `10x16.svg`, with `.light` before `.svg`. Parse names with `^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(\.light)?\.svg$`. A named variant's templates carry the same names inside `build/<variant>/`, and every variant is built for every native aspect.
- Any other shape is a crop of the 16:9 template:
  - The crop spans the full height (or width) and moves on one axis.
  - It is a range input plus a drag handle, clamped to the canvas.
  - It is centred by default on `focus`, the ink-weighted centroid that build stores in slots.json.
  - It is shareable as `?crop=<0..1>`.
  - The export panel says "cropped from 16:9" under a cropped shape and nothing for a native one.

## Variants

A variant is a named version of a piece that a visitor can switch to on its page: another moon phase, a later moment of a sweep, another rule number.

- The values live in design.py as `Params` instances in `@design(variants=...)` (api.md §8, §9). meta.yaml holds only their copy and state, under `variants:` (api.md §13.4).
- A variant must change what is depicted, not nudge a value. A new seed is a variant only when the result shows something different; seed ladders are for `walldye sheet --seeds`, never for the site.
- At most 4 named variants per design, so at most 5 versions with the default. `walldye check` requires every pair of versions to have an ink-map cosine below 0.93 on their 16:9 dark templates. The gate is necessary, not sufficient: on a fine-textured piece a 4% nudge of one value can measure 0.91, so review still judges whether the subject changed. On a piece with a large fixed structure the reverse happens: radar-sweep's afterglow and rings dominate its ink map, so a new coastline measures 0.98 and only moving the arm passes (api.md §17).
- Every variant is built for every native aspect and regime, into `build/<variant>/` with its own slots.json.
- Draft state is per variant. Agents propose at most 3, always as `draft: true`; a draft variant is built and reviewed but hidden from the production site, and `walldye review` approves each one on its own. A piece-level `draft: true` hides every version.
- On the site a design has one page, and its versions are a radio group headed "Versions". The version lives in `?v=<name>`, absent for the default; variants never get a URL, social card or sitemap entry of their own.

## Build and CI

### Hashes

- Each hash is the sha256 of lines `<key>\t<value>`, sorted, each ending in a newline; for a file the key is its repo-relative posix path and the value the sha256 of its bytes.
- `design_sha` (in slots.json) covers design.py (or source.svg and palette.yaml) and every file in `data/`. A named variant's `design_sha` adds the line `variant\t<name>`; the default's has none (api.md §13.2).
- The render-lib hash (`wallpapers/.render-lib.sha256`) covers:
  - the git-tracked files under `walldye/`, except `walldye/tools/**` and `__pycache__`;
  - `dep\t<name>==<version>` lines for numpy, scipy, shapely and scikit-image, read from uv.lock;
  - a `python\t<.python-version>` line.
- slots.json also stores `probes`: the sha256 of the fireproof render and of one render per regime under its sample theme. When the render-lib hash changes, `walldye build --all` re-renders only the probes of each variant. If they match, it restamps the hash; otherwise it re-renders and rebuilds that variant.
- `.gitattributes` sets `* text=auto eol=lf`. The hash test vectors (one plain design, one with a data file and a variant line) are asserted by both pytest and vitest.

### CI checks

`pnpm check-artifacts` (`scripts/check-artifacts.ts`) is how CI knows the committed build is current without running Python:

1. Recompute every version's `design_sha` and the render-lib hash, and fail with "run walldye build" on a mismatch.
2. Check each template's sha256 and slot count against slots.json, which catches hand edits.
3. Require a `build/<variant>/` for each named variant in meta.yaml, with the default's set of templates, and no other directory in `build/`.
4. Check `wallpapers/index.json` against meta.yaml and slots.json.
5. Require `checked: <walldye version>` in every slots.json. Build writes slots.json only after check passes.

The same CI job also runs ruff's format check, vitest and `astro build`, and a second job runs Playwright against that build (Hosting and analytics lists the jobs).

### `walldye check <slug>`

`walldye build` runs check first and refuses to write if it fails. Check covers every variant unless `--variant` names one, and runs, in order:

1. Load: import design.py once. A missing or malformed `@design`, a bad `Params` class or a bad variant fails here.
2. Source: the design lint (api.md §15.1), `ruff format --check` and `ruff check`, Pyrefly at the standard level, the meta.yaml rules including `variants:`, and the `data/` rules. Ruff and Pyrefly run once over all target files.
3. Determinism, per variant, aspect and regime: two in-process draws must serialise identically, and one subprocess per piece and variant under `PYTHONHASHSEED=4242` (`python -m walldye _hashes`) must reproduce every hash. A failure stops the check before any geometry step.
4. `viewBox="0 0 W H"`, exact per aspect.
5. Templates: the dark template is the fireproof serialisation; the light regime shares it when the two documents' skeletons match, and otherwise gets a flexoki-light template.
6. The slot coefficients per regime: held-out error at most 2 units, and every probe theme serialises.
7. The constant-slot rule.
8. Errors: `<text>`, any `<filter>`, any `<image>`, more than 1 MB or 20k elements. The API cannot emit the first three; the check is a backstop.
9. Variant siblings: the ink-map rule above. Ink maps and `focus` measure the distance from the template's own background. Only pairs with a freshly checked side are compared: with `--variant`, that variant against the other variants' committed templates; in a build, the variants it re-checks.
10. Warnings: more than 600 kB or 15k elements; colour words in the docstring, comments or meta.yaml; a non-integer pixel-grid origin; a variant whose check took more than 120 seconds; a named variant's value outside its knob's soft range.
11. `--similar`: advisory near-clone pairs across pieces (ink-map cosine of 0.93 or more), read from the default versions' committed 16:9 templates.
12. `--paranoid`: every serialisation is compared with a fresh import and draw under that theme.

`walldye check` and `walldye build` run in a process pool, one task per piece and variant, with `--jobs` workers (default: every core); the parent does all printing and writing. A piece takes from a couple of seconds to about half a minute, and heavy simulations longer.

`walldye build --verify [<slug>...]` is the local drift check. It re-renders the committed templates of every variant of each named piece, or of every piece when none is named, under their template theme, and diffs them against the committed files without writing. Run it before committing, and always after a uv.lock or `.python-version` change.

### Tests

pytest (`tests/python/`) covers the core, the helpers and the tools (api.md §18), including a Pyrefly run that must report 0 errors for `walldye/` at the strictest preset and for the skill examples at the standard level, and a draw-once test: one document serialised under N themes equals N fresh draws.

vitest (`tests/unit/`):
- Exact fireproof seeds return the template bytes unchanged.
- For each of three reference pieces (schotter, dither-moon, radar-sweep), `recolour(template, slots, T)` matches a Python render stored under `tests/fixtures/` for T in {1c1b1b-dad8ce-cf6a4c (a 1-unit neighbour of fireproof), nord, flexoki-light, a corner theme}: identical skeleton, every slot within 2 units.
- The TypeScript derive_theme is byte-equal to the themes.json fixture.
- The contrast guard holds over the presets and 1,000 random triples.
- The tokenizer, theme-token and hash fixtures are shared with pytest.
- A synthetic design where two roles collide on one fireproof hex: a slot table keyed by hex misses by more than 2 units, and the per-occurrence one passes.
- The copy lint (Copy rules), the meta.yaml variants schema, check-artifacts and the export geometry.

Playwright (`tests/e2e/`), on Chromium for pull requests and on Chromium, Firefox and WebKit for pushes to main and manual runs, against the built site, plus a second site built from a generated catalogue with named variants for the version tests:
- Theming, recolouring, the picker and shared themes; the index filters; the detail page, versions (`?v=`, the plate, the description and the export file name follow the version) and export; layout and accessibility checks with axe.
- One resvg-wasm pixel comparison against a reference PNG that resvg-py renders locally and that is committed under `tests/fixtures/`, so CI only reads the PNG.
- Perf, local only: the built index with every plate, the 20 heaviest published 16:9 templates moved to the top, at 4x CPU throttle; no long task over 200 ms on a theme change. It is the `perf` project, which CI never selects, and it runs with tracing off, since a trace's DOM snapshots of the whole index are long tasks of their own.

Running Playwright:
- On NixOS: `pnpm e2e:nix`, which points `PLAYWRIGHT_BROWSERS_PATH` at nixpkgs' playwright-driver browsers; `@playwright/test` is pinned to that version.
- In CI: `pnpm exec playwright install --with-deps` for that run's engines, with the browsers cached, against the dist from the build job (`E2E_SKIP_BUILD=1`).

## Metadata (`meta.yaml`)

```yaml
title: Squares shaking loose
description: A band of squares shaking apart left to right; one escapes.
notes: |                     # optional Markdown, shown on the detail page
  ...
technique: [drafting]        # facets, checked against taxonomy.yaml
subject: []
lineage: [early-computer-art]
sources:
  - kind: inspiration        # recreation | inspiration | reference | data
    title: Schotter
    author: Georg Nees
    year: 1968
    url: https://...         # optional for every kind
    lang: de                 # optional language of a foreign title
added: 2026-09-27
author: Claude Opus 5.5
ai_generated: true
model: claude-opus-5-5       # only when ai_generated
license: CC0-1.0             # SPDX id or LicenseRef-fan-work; may be omitted for the CC0 default
franchise:                   # required when license is LicenseRef-fan-work
  title: Outer Wilds
  owner: Mobius Digital
draft: false                 # true hides the piece from the production site
proposed_facets: {}          # only while draft: true
variants:                    # only when design.py declares named variants
  default: {label: Sideways}
  settled: {label: Settled, draft: true}
```

- `license` covers the whole folder: design.py, meta.yaml, data/ and build/. The exception is third-party data in data/, which keeps its upstream licence and notice, recorded in `REUSE.toml`. An AI-generated piece may omit `license` for `CC0-1.0`, except that any piece with a `kind: recreation` source must set it explicitly, and so must a human-made piece; the build fails otherwise. A recreation of a work under an attribution licence takes that licence (nix-snowflake, after the CC BY 4.0 NixOS logo, is `CC-BY-4.0`). Every licence needs its text in `LICENSES/`.
- `LicenseRef-fan-work` covers fan pieces from games and other franchises, which are published and credited in `sources`.
  - No licence is granted for those folders, and meta.yaml must carry `franchise: {title, owner}`.
  - The site shows: "Unofficial fan tribute, not affiliated with or endorsed by {franchise.owner}. {franchise.title} and its characters are trademarks of their owners. Non-commercial; contact takedown@walldye.com for takedown.", with the address as a `mailto:` link.
  - `LICENSES/LicenseRef-fan-work.txt` says the same: no licence is granted; each piece is an unofficial fan tribute; trademarks belong to their owners; non-commercial use only; takedown requests go to takedown@walldye.com.
- Variants: the keys of `variants:` are exactly `default` plus the names declared in design.py. Every entry needs a `label`, a few plain words naming the version. A named variant may add a `description`, shown instead of the piece's when that version is on screen, and `draft`.
- Drafts live on main. Agents write `draft: true` folders and variants, `walldye review` flips approved ones to `draft: false` (and can set a published piece or version back to `draft: true`), and rejected pieces are deleted with `walldye drop` after the owner confirms. The site shows drafts only in `astro dev`.
- A source's `title` names a work, and the site sets it in italics. A maker with no single work is an `author` with no title, and a genre, style, place or phenomenon is a `reference`, shown only among the footnotes.
- URLs are optional. When present, the agent fetches them before writing them, and CI checks them with a link checker.
- The content loader's zod schema (`src/content.config.ts`) checks facets against taxonomy.yaml, the licence rules, facet labels and reserved slugs. Agents never add facet values: they write `proposed_facets`, allowed only while `draft: true`. In `walldye review`, accepting one appends it to taxonomy.yaml and moves it into the piece's facets, and approval is refused while any remain. The owner can also add a value there. Either way review asks for its label and writes it to `src/lib/labels.ts`, so the site build never meets a value without one.
- Computed facets, with the labels visitors see: "has source code" (has a script), "fits any screen" (composes for every aspect), "has references" (any source), "made with Claude" and "human-made" (ai_generated). An entry that matches every piece or none is hidden.
- Facet values are slugs. The site shows a plain-words label for each from `src/lib/labels.ts` (drafting is "technical drawing", glyph "text characters"). The lineage facet is headed "Inspired by"; homage and fan-work have no filter entry.
- `wallpapers/index.json` summarises every built piece (`aspects`, `draft`, `license`, `title` and the named `variants`) for consumers outside the site; build, review and drop regenerate it, and CI checks it (api.md §13.5).

## Site

### Direction

- An exhibition catalogue in the manner of the 1968 computer-art catalogues: museum-label captions, hairline rules instead of cards, typography-only chrome, and the wallpapers carrying all the colour. site.md is the visual reference, including the rejected patterns.
- Type: EB Garamond for titles, captions and prose, and Walldye Mono, a renamed Monaspace Krypton subset, for data (seeds, colours, sizes, file names).
- Fonts are self-hosted woff2 through Astro's fonts API with `fontProviders.local()`. The files in `src/assets/fonts/` come from `scripts/fonts/subset.py`, run on the full upstream fonts (pins in `scripts/fonts/SOURCES.md`):
  - The Fontsource and Google EB Garamond latin subsets lack smcp, c2sc, onum and U+2197, which is why the site subsets its own.
  - The subset command is `pyftsubset EBGaramond[wght].ttf --unicodes=U+20-7E,U+A0-FF,U+152-153,U+2009-200A,U+2010-203A,U+2060,U+2190-2199,U+2212 --layout-features=kern,liga,smcp,c2sc,onum,lnum,pnum,tnum,case --flavor=woff2`, and the same for the italic.
  - Monaspace Krypton 1.400 is subset the same way and renamed "Walldye Mono", because "Monaspace" and "Krypton" are Reserved Font Names under the OFL.
  - Leader dots are drawn in CSS.

### Routing and content

- URLs are `/<slug>`, with astro.config `build: {format: 'file'}`, `trailingSlash: 'never'`, and `site` from `SITE_URL` (default https://walldye.com).
- The meta schema rejects the slugs about, index, t, og, fonts, 404, robots, sitemap*, favicon and anything starting with `_`.
- Renames go in `public/_redirects`. Filters (`?technique=dither&q=moon`, sort), the version (`?v=`), the export shape (`?shape=16x10`) and the crop (`?crop=`) live in the query string. `?t=` is only an entry parameter, read once and stripped.
- One page per design, whatever its versions.
- Content comes from a custom `wallpapers()` loader in `src/content.config.ts`. It globs `wallpapers/*/meta.yaml` with the folder name as the id; attaches slots.json, the templates with content-hashed URLs, the design.py text and each named variant's build with its label, description and draft flag; leaves out draft pieces and draft variants in production; curls the quotes and apostrophes in titles, descriptions, version labels, source names and the franchise, as Markdown does for the notes, so meta.yaml keeps typewriter quotes; and watches `wallpapers/` so `astro dev` refreshes on a rebuild.
- A prerendered endpoint serves templates and slots at `/t/<sha256[:12]>.svg` and `.slots.json`.
- `public/_headers`: `/t/*` and `/_astro/*` are `immutable, max-age=31536000`; HTML is `max-age=0, must-revalidate`; `https://:project.pages.dev/*` gets `X-Robots-Tag: noindex`.
- Each piece gets a prerendered `/og/<slug>.jpg` (a 1200x630 band of the default version's fireproof template, centred on its focus), `summary_large_image`, a meta description and card alt text (`og:image:alt`) equal to its description, a `<link rel=canonical>` without a query, and one sitemap entry.
- `/robots.txt`, an endpoint in `src/pages/robots.txt.ts`, allows every crawler and gives the sitemap index's address on `site`, which is how search engines find the sitemap.

### Header

- Masthead, nav (Index, About), and a theme button showing the preset name ("custom" when the seeds match none) and three swatches, which opens the picker as a `popover`. Its accessible name starts with the visible name (WCAG 2.5.3). There is no themes page.

### Index

- A book-index column on the left: `<fieldset><legend>` facet headings, native checkboxes, leader dots and live counts; OR within a facet, AND across facets. It has the computed facets, plain-word labels for every value, a search over title, description and source names, and a sort by newest or title, breaking ties by slug.
- On phones the column becomes a "Filter" disclosure above the grid. There is a skip link and one polite live region.
- One plate per design, showing the default version, with a tombstone caption (site.md §6.5). The description is the alt text and is searched through a data attribute.
  - Loading uses an IntersectionObserver with a one-viewport margin and at most 6 concurrent fetches.
  - Grid rows use `content-visibility: auto`.
  - A theme change re-templates only the plates in view and marks the rest stale. Each swap waits for `img.decode()`, then revokes the old blob URL. The template cache is an LRU of about 8 MB.
  - Before JavaScript runs, a plate is an empty 16:9 box on the seed bg plus a `<noscript>` image of the template.

### Detail

- The plate spans the content width, with the label below on the left and the controls below on the right (site.md §6.6 to §6.9).
- The label shows the title, the attribution, the description, the credit "Made with {author}" ("Made by" for human-made pieces), a licence line when the licence is not CC0 (for `LicenseRef-fan-work`, the fan-work disclaimer), and the facts: Technique, Inspired by, Shape and Added. No licence identifiers. Sources are numbered footnotes, and notes render as Markdown.
- Captions by source kind:
  - recreation: "after {author}, *{title}*, {year}";
  - inspiration, when there is no recreation: "inspired by {author}, *{title}*";
  - reference and data appear only as footnotes;
  - several are listed as "A, B and C", a work by the same author as the one before it leaves the name out ("Mark Rothko, *No. 61* and *Seagram murals*"), and missing fields are dropped.
- Versions: when a design has published named variants, the "Versions" radio group lists the default's label first, then the others in meta.yaml order. Choosing one swaps the plate (that version's templates, slots, focus and cells), the description and alt text, the export file names and the run command, and writes `?v=<name>` with `history.replaceState`. Theme and crop are kept. An unknown or draft `?v=` shows the default.
- "Source code" shows design.py through Shiki with a CSS-variables theme (site.md §6.10), a Copy button, and "Run it yourself":
  - `git clone https://github.com/nickolaj-jepsen/walldye && cd walldye`
  - `uv run walldye render <slug> [--variant <name>] --theme <token> [--aspect A] [--crop x,y,w,h] -o <slug>[--<name>]-<token>-<aspect>.svg`

  It uses the preset name when the seeds match one. Legacy pieces say "The script for this wallpaper has been lost." instead.
- `f` toggles fullscreen, and does nothing when `requestFullscreen` is unavailable. It ignores fields, sliders, focused code regions, editable content and modified keys, and the page does not advertise it. There is no navigation between neighbours: no previous and next links, no arrow keys, no `?from=`.
- Accessibility: alt text is the description; `:focus-visible` gets a 2px accent outline guarded to 3:1; reduced motion turns off the recolour fade.

### About

- At most 110 words, in the maintainer's own voice: what the site is, how the three colours work, that Claude writes the scripts and the owner looks over each one, the download formats, one plain clause on use ("free to use unless their page says otherwise", linked to the CC0 deed), and a link to the code.
- No piece counts, no licence paragraph or identifiers, no colophon or font credits. The OFL notices ship in the font files, and Spleen's BSD-2-Clause notice stays in `walldye/font.py` and `LICENSES/`.
- The site has no footer.

### Interactivity

Plain TypeScript modules in `src/scripts/`, no UI framework. `src/scripts/DOM.md` lists the hooks the server-rendered pages give them.

### Export

- Formats: recoloured SVG, PNG, WebP and JPEG.
- Sizes per aspect:

  | Aspect | Sizes |
  |---|---|
  | 16:9 | 1920x1080, 2560x1440, 3840x2160, 5120x2880 |
  | 16:10 | 1920x1200, 2560x1600, 2880x1800, 3840x2400 |
  | 21:9 | 2560x1080, 3440x1440, 5120x2160 |
  | 32:9 | 3840x1080, 5120x1440, 7680x2160 |
  | 9:19.5 | 1080x2340, 1170x2532, 1290x2796, 1440x3120 |
  | 10:16 | 1200x1920, 1600x2560, 2400x3840 |

  There is also "your screen": the screen size times the device pixel ratio, mapped to the nearest aspect by |log ratio|. Phones default to it.
- Exports render at the exact pixel size. The viewBox is the largest rectangle of the target ratio inside the template or crop, with `preserveAspectRatio="xMidYMid slice"` and the width and height replaced.
- Rasteriser:
  - `@resvg/resvg-wasm` is pinned (2.6.2) and checked against a committed resvg-py reference PNG.
  - It runs in a module Worker, prefetched when the export panel scrolls into view, with its background set to the seed bg. The worker is terminated after each export.
  - PNG is encoded as RGB from resvg's pixels by a small encoder (fast-png). JPEG (quality 0.92) and WebP go through `OffscreenCanvas.convertToBlob`.
- Limits: WebP support is probed with a 1x1 encode. Sizes over 16,777,216 pixels or 32,767 px on a side are disabled up front, with the reason shown.
- Pixel pieces: `grid_runs`, `glyphs` and `sprite` record their cell size and tag their paths with class `px`, and build writes `cells` into slots.json. The exporter adds `shape-rendering="crispEdges"` to tagged paths only; on the root it would make the curves in many pixel designs jagged. When cells will not land on whole pixels at the chosen size, the panel says how wide they come out.
- File names (`--<variant>` only for a named variant; slugs and variant names never contain `--`, so the name splits back unambiguously):
  - Raster: `<slug>[--<variant>]-<token>-<w>x<h>.<ext>`.
  - SVG: `<slug>[--<variant>]-<token>-<aspect>[-crop].svg`, with `<title>` and `<desc>` "walldye.com/<slug>[?v=<variant>] · <license> · theme <token>".
- Every version can be exported at every aspect the site offers.

## Copy rules

- Claude drafts; the owner approves. site.md §7 is the full voice guide for the site.
- UI copy uses plain words a visitor would use. Internal terms never reach visitors: regime, seed, token, native, hand-tuned, light-ready, preset, variant, param, contrast ratios, colour tolerances, licence identifiers. Visitors see variants as "versions".
- Variant labels are a few plain words naming what that version shows ("Late in the turn", "Open water"): theme-neutral, unique within the piece, at most four words.
- Italics only for titles of works.
- No hint lines: keyboard shortcuts, tolerances and the site's internals are not explained on the page.
- Descriptions:
  - one or two short sentences, at most 30 words, varied in shape from piece to piece;
  - theme-neutral: no colour names ("terracotta") and no theme roles as nouns ("the accent"); say what is picked out, filled in or lit;
  - concrete about what is depicted and how;
  - no evaluative adjectives (stunning, mesmerising, elegant, timeless).
- Every draft goes through the avoid-ai-tropes check. The rules live in the skill, so new designs follow them.
- design.py is published under "Source code", so the rules cover its docstring too (one theme-neutral line: concept and technique) and its comments (name tokens or roles, never hues).
- Enforcement:
  - `walldye check` warns on colour words in design.py and meta.yaml, and rejects internal terms in variant labels.
  - A vitest copy lint (`lintCopy` in `src/lib/meta.ts`) covers meta.yaml titles, descriptions and notes, and variant labels and descriptions: colour words, banned adjectives and stock phrases, internal terms, licence identifiers, machinery numbers, theme roles as nouns, and descriptions over two sentences or 30 words.

## Claude tooling

### Skill (`.claude/skills/walldye/`)

The skill takes one piece from idea to review. `SKILL.md` has the steps; the references are `api.md` (a working guide to designing one piece, linking to `docs/api.md` for signatures), `principles.md` (the critique checklist), `themes.md` (tokens and the light ladder), `taste.md` (the owner's taste, theme-neutral) and `ideas.md` (seed ideas and the review lessons); `examples/` holds eight complete designs.

Steps, in short:
1. Brief, then dedupe against `walldye list`.
2. `uv run walldye new <slug> --author "<model display name>" --model <model id>`, which writes the starter design.py (api.md §14.3) and a draft meta.yaml with ai_generated true, added today, `draft: true` and no `license:`.
3. Write design.py from the nearest example, and declare `aspects="any"` whenever the composition can follow `s.pick`, `s.frac` and `s.inset`.
4. Preview for at least three rounds: a crop into the busiest area, the extreme aspects, flexoki-light and nord from round two, and `walldye sheet --seeds` or `--wedge` when choosing a seed or a value.
5. Work down the light ladder.
6. Variants only where the piece has a natural one, at most 3, each passing `walldye check <slug> --variant <name>` before it is proposed as a draft.
7. Fill in meta.yaml: facets from taxonomy.yaml (new ones as `proposed_facets`), every source URL fetched, the Copy rules. For a `kind: recreation` source, ask the owner for `license:`.
8. `walldye check <slug>`, then `walldye build <slug>`, then `walldye build --verify` over everything before committing.
9. `walldye review <slug>` in the background. Confirm with the owner before `drop`.

Ground rules: edit only `wallpapers/<slug>/` by hand (build also rewrites `wallpapers/index.json`, which is committed with the folder); never edit `walldye/` or taxonomy.yaml; always pass a slug, except to `build --verify`; previews go to `$WALLDYE_PREVIEW`.

Geometry rules: colours are formulas, never values, so key and group by role or index (`s.buckets`, a `ladder`) and give an explicit sort key where order matters, since sorting colours raises; `s.light` is the only theme-dependent control flow; mask content is `MASK_WHITE`, `MASK_BLACK` and mixes of the two; randomness comes only from `s.rng`, `s.np_rng` and `s.noise`, and nothing at module level is mutated while drawing.

### Batch workflow (`.claude/workflows/wallpaper-batch.js`)

For about ten or more pieces in one run. Research agents propose ideas per lens, an art director curates them (at most 10% of the set sharing one technique facet), builders, critics and fixers work in batches of three, a set pass builds the drafts and prunes near-clones and weak pieces, then sources are fetched, the copy is edited in one pass, the orchestrator builds and verifies, and the owner reviews. The owner is asked for the `license:` of any recreation before build. Everything lands as `draft: true` folders and is never committed by the run. `.claude/workflows/README.md` explains the arguments and the stages.

### CLI

`walldye` has these commands; api.md §14 has the flags.

| Command | For |
|---|---|
| `new` | scaffold `wallpapers/<slug>/` |
| `preview` | a PNG to `$WALLDYE_PREVIEW`, with the design lint, the regime and whether light geometry differs |
| `render` | one SVG to the working directory or `-o`, never into `build/` |
| `check` | the gate above |
| `build` | check, then write `build/`, slots.json and index.json; `--verify` diffs without writing |
| `review` | a localhost page that goes through versions one at a time to keep, drop or unpublish them and edit their words and facets; blocks until Apply |
| `sheet` | contact sheets of committed templates, or of one piece over `--wedge` and `--seeds` |
| `params` | a design's params, ranges and variants |
| `list` | slug, title, description, draft, aspects and variants, tab-separated |
| `drop` | delete a piece after the owner confirms |
| `themes` | the presets; `--json` writes the vitest fixture |

Loading imports `wallpapers/<slug>/design.py` once per process and draws it for every version, aspect and regime; the design's folder is not on `sys.path`. The environment variables are `WALLDYE_THEME` and `WALLDYE_PREVIEW` (default `<tmp>/walldye`). `--set k=v` overrides one param in preview, render and sheet for exploring, and build refuses it, because published values belong in a named variant. The rasteriser is resvg-py; Inkscape is an optional `--renderer` for debugging. Review keeps its state in the gitignored `.walldye-review.json`, writes nothing else until Apply, never renders missing SVGs, and never edits design.py: a rejected variant keeps `draft: true` with the note and is removed from design.py by hand.

## Licensing

- `GPL-3.0-or-later` for the library, the site and the tooling: LICENSE, package.json (`license`) and pyproject.toml (PEP 639).
- Each wallpaper folder has its own `license:`: CC0-1.0 by default for AI-generated work, explicit for recreations and human-made pieces, and `LicenseRef-fan-work` for fan pieces.
- Third-party data files keep their upstream licence, and `REUSE.toml` gives each one's notice: star-chart's star positions come from d3-celestial (BSD-3-Clause), and racing-spa-minisectors' centreline from the TUMFTM racetrack database (LGPL-3.0), which took it from OpenStreetMap (ODbL). The pieces' Sources credit them.
- `LICENSES/` holds GPL-3.0-or-later.txt, CC0-1.0.txt, CC-BY-4.0.txt, LicenseRef-fan-work.txt, BSD-2-Clause.txt, BSD-3-Clause.txt, LGPL-3.0-only.txt, ODbL-1.0.txt and OFL-1.1.txt, named by SPDX id. The README has the table of what is licensed how.
- `walldye/font.py` carries `SPDX-FileCopyrightText: 2018-2024 Frederic Cambus` and `SPDX-License-Identifier: BSD-2-Clause`. The fonts in `src/assets/fonts/` are under the SIL OFL 1.1, with both copyright notices in `src/assets/fonts/OFL.txt`.

### What a piece may draw

A piece is released as CC0 only when everything in it is ours to give away. The owner lives in the EU, where there is no fair use and copyright runs 70 years after the author's death. A CC0 label on someone else's work would tell visitors they can sell prints of it. These rules keep the realistic worst case at a takedown request. They are the owner's policy, not legal advice.

- Styles, techniques, algorithms, genres and ideas are free to use. Credit the work that suggested one as `kind: inspiration`, and the piece stays CC0.
- `kind: recreation`, which redraws one specific work, is only for works that are public domain in both the EU and the US (US federal works such as NASA's count) or under an open licence. A recreation of an attribution-licensed work takes that work's licence, as nix-snowflake does.
- Works still in copyright are never redrawn. A piece may stay recognisably in a work's spirit, keeping its visual idea and feel, but it makes two or three deliberate departures of its own: orientation, proportion, count, where the change happens, a focal point, or an added element. schotter is the model: a grid of squares coming loose, turned sideways, with strays leading to one filled square. Someone who knows the original should think "in the spirit of it", not "that is it". The title is not the work's title, the notes may say which idea is taken and what is done differently, and the work is credited as an inspiration. In September 2026 the pieces after Riley, Albers, Müller-Brockmann, Molnár, Nake, Nees, Cherniak and Sloane were reworked this way.
- Some looks stay off limits even as inspiration: game looks that courts have protected (a court held the Tetris well protectable in *Tetris Holding v. Xio*, 2012) and single famous images such as album covers. tetris-well and prism were dropped for this reason.
- Game and franchise pieces are `LicenseRef-fan-work`, and only with the owner's approval. They stay non-commercial, the site carries no ads, and takedown@walldye.com must reach the owner. Prefer drawing a subject over copying its assets: traced official renders, textures and logos come closer to redistribution than a depiction does. A rights holder's request is honoured by `walldye drop`.
- Third-party data keeps its upstream licence (above). Credit it as `kind: data`.

## Hosting and analytics

- Cloudflare Pages, deployed from GitHub Actions with `cloudflare/wrangler-action`: `pages deploy dist --project-name=walldye --branch=<branch> --commit-hash=<head sha>`. The deploy job has no checkout, so wrangler gets the commit explicitly. [deploy.md](deploy.md) is the runbook.
- CI builds one dist that the browser tests run against and the deploy uploads. Pull requests test on Chromium only so they finish quickly, and main tests on all three engines before it deploys. The Cloudflare credentials are repository secrets because the repository is private on the Free plan until it goes live, and such repositories have no deployment environments.
- CI (`.github/workflows/ci.yml`) runs on pushes to main, pull requests and manual runs:
  - build: ruff's format check (a standalone binary, no Python), `pnpm check-artifacts`, `pnpm test`, `astro build`, the dist uploaded as an artifact, then the link check;
  - e2e: Playwright against that dist;
  - deploy: pushes to main go to production, and pull requests from branches in this repository go to a preview whose URL is posted as a PR comment that later pushes edit. Fork pull requests never deploy, and `pull_request_target` is never used.
- A newer run cancels an older one on the same pull request or branch. Changes that touch only `docs/`, Markdown, `.claude/`, `infra/`, `LICENSES/` or `.lycheeignore` skip CI.
- Link checks: lychee on the URLs in changed meta.yaml files, with retries and a 7-day cache. A broken link fails a pull request; on main it is reported without blocking the deploy. A weekly full run (`links-weekly.yml`) opens an issue and closes it once every link resolves.
- Domain: walldye.com (Cloudflare Registrar), attached to the Pages project. www.walldye.com redirects to the apex with a 301, keeping path and query, through a Worker in `infra/www-redirect/` that is deployed by hand.
- Cloudflare Web Analytics is on for the project: an injected beacon, no cookies, so no consent banner.
- Cloudflare Email Routing forwards takedown@walldye.com, the contact in the fan-work disclaimer, to the owner.

## Not done yet

- The nixos cutover. The owner's nixos configuration still keeps its own copy of the older wallpaper scripts and backgrounds. The plan is for it to take this repository as a `flake = false` input, read `wallpapers/index.json` (dropping drafts and ignoring `variants`) and rasterise only the default version's `build/16x9.svg`, plus `build/10x16.svg` or a 10:16 crop around `focus` for portrait monitors. It is out of scope so far, and nothing here waits for it.
- geometry.svg and unknown.svg, two older backgrounds in the nixos configuration that predate Claude, are not in the catalogue until their provenance is confirmed. unknown.svg is an Illustrator export resembling the Unknown Pleasures plot and is likely third-party.
- The owner's review of the imported catalogue is still open; `walldye review --all` goes through all of it, over as many sittings as it takes. glyph-terrain is a draft, and so are 39 proposed versions.
- The GitHub repository is private. The About page and every "Run it yourself" command point at it, so it has to be public when the site goes live.
- Nothing has been deployed to production yet: main does not have this work, so walldye.com answers 404 until it lands there (deploy.md).
- A disk cache for heavy pure work is deferred. brain-coral reruns a 9-second reaction-diffusion on every draw, which bounds `walldye check --all` at about ten minutes on 16 cores.
