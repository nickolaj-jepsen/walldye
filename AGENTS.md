# walldye

walldye is a catalogue of procedural SVG wallpapers. Each piece is a small seeded Python script that draws with the `walldye` library in theme tokens. `walldye build` renders it to SVG templates, which are committed, and fits a linear recolouring for every colour in them from three seed colours (bg, fg, accent). The Astro site at walldye.com uses those fits to show every piece in the visitor's colours and to export it as SVG, PNG, WebP or JPEG. `docs/design.md` records the decisions and is the source of truth; update it when a decision changes.

## Layout

- `walldye/`: the library designs import, plus the CLI in `walldye/tools/`. Everything outside `tools/` feeds the render-lib hash, so editing it means a `walldye build --all` afterwards.
- `wallpapers/<slug>/`: `design.py` and `meta.yaml` are written by hand, `build/` is generated. `wallpapers/index.json` and `wallpapers/.render-lib.sha256` are generated too.
- `taxonomy.yaml`: the allowed facet values for meta.yaml.
- `src/`: the site. `src/lib/` has the TypeScript ports of the theme, recolour, tokenizer and hash code, with fixtures shared with pytest in `src/lib/__fixtures__/`. `src/scripts/DOM.md` lists the hooks the client modules rely on.
- `tests/`: `python/` (pytest), `unit/` (vitest), `e2e/` (Playwright), and `fixtures/`, the Python renders the TypeScript recolouring is checked against.
- `scripts/`: `check-artifacts.ts`, the CI check that committed builds still match their inputs, and `fonts/`, which rebuilds the subset fonts in `src/assets/fonts/`.
- `infra/www-redirect/`: the Worker that sends www.walldye.com to the apex.
- `.claude/skills/walldye/`: the skill for designing one wallpaper. `.claude/workflows/wallpaper-batch.js` runs it for ten or more.
- `docs/`: `design.md`, and `deploy.md` for Cloudflare and CI.
- `import/`: gitignored scratch (nixos snapshots, prototypes, screenshots). Nothing in it is committed.

## Commands

```sh
uv run walldye --help                 # new, preview, render, check, build, review, sheet, list, drop, themes
uv run walldye check <slug>
uv run walldye build <slug>
uv run walldye build --verify         # re-render every committed template and diff; read-only
uv run pytest
uv run python tests/python/fixtures/regen.py   # after a build that changes the shared fixtures

pnpm test                             # vitest
pnpm check                            # astro check
pnpm check-artifacts                  # what CI checks instead of running Python
pnpm astro build
pnpm e2e:nix                          # Playwright on NixOS, with nixpkgs' browsers
```

On NixOS the Python wheels need `programs.nix-ld.enable`; there is no devShell.

## Rules

- Never edit anything in `wallpapers/*/build/` by hand. Only `walldye build` writes there, and `pnpm check-artifacts` catches hand edits.
- After changing a `design.py`, the `themes:` line of a `meta.yaml` or anything in the library, run `uv run walldye build` for the affected pieces and commit its output with the change. Run `uv run walldye build --verify` before committing.
- Anything a visitor reads (meta.yaml titles, descriptions and notes, design.py docstrings and comments, site text) follows the Copy rules in `docs/design.md`: no colour names, no theme roles as nouns, no internal terms, no evaluative adjectives.
- CI runs Node only. Do not add Python steps to `.github/workflows/`; drift in Python output is caught locally by `walldye build --verify`.

## Dev server

When starting the dev server, use background mode:

```
astro dev --background
```

Manage it with `astro dev stop`, `astro dev status` and `astro dev logs`.

## Astro docs

https://docs.astro.build. Read the relevant guide before working on [routing](https://docs.astro.build/en/guides/routing/), [components](https://docs.astro.build/en/basics/astro-components/), [content collections](https://docs.astro.build/en/guides/content-collections/) or [styling](https://docs.astro.build/en/guides/styling/).
