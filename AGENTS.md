# walldye

walldye is a catalog of procedural SVG wallpapers. Each piece is a small Python script, one `@design` function that draws with the `walldye` library in symbolic theme colors, optionally with a few named variants. `walldye build` draws it once per version, screen shape and regime, writes SVG templates and records every color in them as a linear mix of three seed colors (bg, fg, accent), read off the formula it was drawn with. The Astro site at walldye.com uses those mixes to show every piece in the visitor's colors and to export it as SVG, PNG, WebP or JPEG.

## Docs

- `docs/architecture.md`: how walldye works and why. Update it in the same change when a decision changes.
- `docs/wallpapers.md`: a wallpaper's folder and meta.yaml, the copy rules, licensing and what a piece may draw.
- `docs/api.md`: the design API, build files and CLI. The docstrings in `walldye/` hold the exact semantics; when the two disagree, fix one of them in the same change.
- `docs/site.md`: the site's visual system, components and voice.
- `docs/deploy.md`: CI, Cloudflare and the going-live checklist.
- `src/client/DOM.md`: the hooks the server-rendered pages give the client modules.

## Writing docs and comments

- Docs describe the current system in as few words as it takes: no plans, history, open tasks or lists of what the tests cover, and nothing the code or a docstring already says. Each fact lives in one doc; the others link to it.
- Comments say only what the code can't: intent, a constraint, a gotcha, a tradeoff, units or bounds. One line where possible; no narrating the line below, no change history ("v1", "used to", "replaces").
- Docstrings state the contract (behavior, non-obvious parameters, return value, errors, invariants), not the signature or the callers.
- Comments and docstrings stand on their own and never cite the docs or their sections.
- No AI tropes: em dashes, "not X, it's Y", "serves as", "it's worth noting", magic adverbs (quietly, deeply), bold-first bullets, signposted conclusions.

## Layout

- `walldye/`: the library designs import (`walldye`, `walldye.geom`, `walldye.field`, `walldye.pixel`; the `_*.py` modules implement them), plus the CLI in `walldye/tools/`. Changing its code outside the modules `NEUTRAL` in `walldye/tools/hashing.py` names makes the next build draw every piece once and compare.
- `wallpapers/<slug>/`: `design.py`, `meta.yaml` and the optional `data/` are written by hand, and `build/` is generated. `wallpapers/index.json` is generated too, and `wallpapers/pyrefly.toml` sets the type-check level for designs.
- `wallpapers/taxonomy.yaml`: the allowed facet values for meta.yaml, each with the words the site shows for it, and the credit name of each model id.
- `wallpapers/featured.yaml`: the pieces the index opens on, in order, chosen by the owner.
- `src/`: the site. `src/lib/` is pure code any side may import (no DOM, Node or Astro runtime): the TypeScript ports of the theme, recolor and tokenizer code, with the fixtures shared with pytest in `src/lib/__fixtures__/`, `src/lib/labels.ts`, the words visitors see for the facets and licenses (taxonomy.yaml has those for facet values and models), and `src/lib/events.ts`, the product events the client sends and the Worker stores. `src/client/` runs only in the browser (one `page.ts` per page, plus the theme boot), `src/server/` only at build time (the collection in `src/server/catalog/`, meta.yaml's schema helpers and taxonomy.yaml), and `src/worker/` on Cloudflare: the site Worker's script, which answers `POST /e`, type-checked by its own tsconfig against the Workers runtime.
- `tests/`: `python/` (pytest: `core/`, `helpers/`, `tools/`, and `fixtures/` with the synthetic designs), `unit/` (vitest, self-contained), `parity/` (vitest against the Python output), `e2e/` (Playwright), and `fixtures/`, the gitignored Python renders and fixtures the parity tests read.
- `scripts/fixtures/`: `regen.py` writes `tests/fixtures/` from a build.
- `scripts/fonts/`: rebuilds the subset fonts in `src/assets/fonts/`.
- `scripts/promo/`: records the promo clip into `promo/`, gitignored.
- `scripts/views/`: fetches the daily page views onto the `stats` branch, checked out as `stats/` (docs/deploy.md).
- `flake.nix`: the Nix package, `mkWallpaper` and the dev shell. The Python environment comes from `uv.lock` through uv2nix.
- `wrangler.jsonc`: the Worker that serves `dist/` at walldye.com, deployed by CI.
- `infra/www-redirect/`: the Worker that sends www.walldye.com to the apex, deployed by hand.
- `.claude/skills/walldye/`: the skill for designing the wallpapers the owner names, or reworking one. `.claude/workflows/wallpaper-batch.js` invents a batch of new ones from research; `.claude/workflows/README.md` explains its arguments.

## Commands

.github/CONTRIBUTING.md lists the commands and the steps for adding a wallpaper by hand. On NixOS, run them in `nix develop`.

## Rules

- Build output is never committed; CI renders it. Locally, run `uv run walldye build --all` (drafts included, which `astro dev` shows) and `scripts/fixtures/regen.py` before `pnpm dev`, `pnpm test` or the e2e tests.
- Anything a visitor reads (meta.yaml titles, descriptions and notes, design.py docstrings and comments, site text, aria-labels and alt text) follows the Copy rules in `docs/wallpapers.md` and the voice in `docs/site.md` §7: no color names, no theme roles as nouns, no internal terms, no evaluative adjectives.
- Site styling stays inside the system in `docs/site.md`: tokens from `src/styles/site.css`, the 8px rhythm, and none of the rejected patterns in §8.
- All Python, including ` ```python ` blocks in Markdown, passes `ruff format` and `ruff check` (fix findings, no blanket `noqa`), and Pyrefly at its level: 0 errors in the library. The prek hook and CI run them; `walldye check` does not.
- All TypeScript passes `pnpm lint` (Biome; fix findings, a `biome-ignore` only with its reason) and `pnpm check`. `.astro` files are left to `astro check`: Biome does not format them.

## Dev server

When starting the dev server, use background mode:

```
pnpm astro dev --background
```

Manage it with `pnpm astro dev stop`, `status` and `logs`.

## Astro docs

https://docs.astro.build. Read the relevant guide before working on [routing](https://docs.astro.build/en/guides/routing/), [components](https://docs.astro.build/en/basics/astro-components/), [content collections](https://docs.astro.build/en/guides/content-collections/) or [styling](https://docs.astro.build/en/guides/styling/).
