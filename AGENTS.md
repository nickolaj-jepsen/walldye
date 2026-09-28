# walldye

walldye is a catalogue of procedural SVG wallpapers. Each piece is a small Python script, one `@design` function that draws with the `walldye` library in symbolic theme colours, optionally with a few named variants. `walldye build` draws it once per version, screen shape and regime, writes SVG templates, which are committed, and fits a linear recolouring for every colour in them from three seed colours (bg, fg, accent). The Astro site at walldye.com uses those fits to show every piece in the visitor's colours and to export it as SVG, PNG, WebP or JPEG.

## Docs

- `docs/design.md`: how walldye works and why. Update it in the same change when a decision changes.
- `docs/api.md`: the design API, file formats and CLI. When it and the code disagree, fix one of them in the same change.
- `docs/site.md`: the site's visual system, components and voice. Code cites its numbered sections, so keep the numbers stable.
- `docs/deploy.md`: CI, Cloudflare and the going-live checklist.
- `src/scripts/DOM.md`: the hooks the server-rendered pages give the client modules.

## Layout

- `walldye/`: the library designs import (`walldye`, `walldye.geom`, `walldye.field`, `walldye.pixel`; the `_*.py` modules implement them), plus the CLI in `walldye/tools/`. Everything outside `tools/` feeds the render-lib hash, so editing it means a `walldye build --all` afterwards.
- `wallpapers/<slug>/`: `design.py`, `meta.yaml` and the optional `data/` are written by hand; `build/` is generated, with named variants in `build/<variant>/`. Legacy pieces have `source.svg` and `palette.yaml` instead of a script. `wallpapers/index.json` and `wallpapers/.render-lib.sha256` are generated too, and `wallpapers/pyrefly.toml` sets the type-check level for designs.
- `taxonomy.yaml`: the allowed facet values for meta.yaml. Only `walldye review` adds to it.
- `src/`: the site. `src/lib/` has the TypeScript ports of the theme, recolour, tokenizer and hash code, with fixtures shared with pytest in `src/lib/__fixtures__/`; `src/lib/labels.ts` has the words visitors see for facet values and licences.
- `tests/`: `python/` (pytest: `core/`, `helpers/`, `tools/`, and `fixtures/` with the synthetic designs and `regen.py`), `unit/` (vitest), `e2e/` (Playwright), and `fixtures/`, the Python renders the TypeScript recolouring is checked against.
- `scripts/`: `check-artifacts.ts`, the CI check that committed builds still match their inputs, and `fonts/`, which rebuilds the subset fonts in `src/assets/fonts/`.
- `infra/www-redirect/`: the Worker that sends www.walldye.com to the apex, deployed by hand.
- `.claude/skills/walldye/`: the skill for designing one wallpaper. `.claude/workflows/wallpaper-batch.js` runs it for ten or more; `.claude/workflows/README.md` explains its arguments.

## Commands

```sh
uv run walldye --help                 # new, preview, render, check, build, review, sheet, params, list, drop, themes
uv run walldye check <slug>           # every variant; --variant NAME for one
uv run walldye build <slug>
uv run walldye build --verify         # re-render every committed template and diff; read-only
uv run walldye params <slug>          # a design's params and variants
uv run pytest
uv run ruff format . && uv run ruff check --fix .   # formatting (line length 100) and import order
uv run pyrefly check                  # the library at the strictest preset; walldye check types designs
uv run python tests/python/fixtures/regen.py   # after a build that changes the shared fixtures

pnpm test                             # vitest
pnpm check                            # astro check
pnpm check-artifacts                  # what CI checks instead of running Python
pnpm astro build
pnpm e2e:nix                          # Playwright on NixOS, with nixpkgs' browsers; `pnpm e2e` elsewhere
```

On NixOS the Python wheels need `programs.nix-ld.enable`; there is no devShell.

## Rules

- Never edit anything in `wallpapers/*/build/` by hand. Only `walldye build` writes there, and `pnpm check-artifacts` catches hand edits.
- After changing a `design.py`, a `data/` file, the `themes:` line or the `variants:` of a `meta.yaml`, or anything in the library, run `uv run walldye build` for the affected pieces and commit its output with the change. Run `uv run walldye build --verify` before committing.
- The render-lib hash covers the files under `walldye/` that git tracks, so `git add` a new library module (`git add -N` is enough) before `walldye build --all`, or the stamp misses it and CI fails.
- Anything a visitor reads (meta.yaml titles, descriptions and notes, design.py docstrings and comments, site text, aria-labels and alt text) follows the Copy rules in `docs/design.md` and the voice in `docs/site.md` §7: no colour names, no theme roles as nouns, no internal terms, no evaluative adjectives.
- Site styling stays inside the system in `docs/site.md`: tokens from `src/styles/site.css`, the 8px rhythm, and none of the rejected patterns in §8.
- Python is formatted with ruff (`uv run ruff format .`), including the ` ```python ` blocks in Markdown; CI fails on unformatted files. All Python also passes `uv run ruff check .` (fix findings, no blanket `noqa`), and the library passes `uv run pyrefly check` with 0 errors (a pytest test enforces it).
- CI runs Node only. Do not add Python steps to `.github/workflows/`; drift in Python output is caught locally by `walldye build --verify`.

## Dev server

When starting the dev server, use background mode:

```
astro dev --background
```

Manage it with `astro dev stop`, `astro dev status` and `astro dev logs`.

## Astro docs

https://docs.astro.build. Read the relevant guide before working on [routing](https://docs.astro.build/en/guides/routing/), [components](https://docs.astro.build/en/basics/astro-components/), [content collections](https://docs.astro.build/en/guides/content-collections/) or [styling](https://docs.astro.build/en/guides/styling/).
