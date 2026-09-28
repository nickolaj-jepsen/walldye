# walldye

walldye is a catalogue of desktop and phone wallpapers, each drawn by a small Python script. Pick three colours and every wallpaper is redrawn in them, along with the site itself. The catalogue is at [walldye.com](https://walldye.com), where any piece downloads as SVG, PNG, WebP or JPEG.

## How the colours work

A design never sees a colour value. It draws in symbolic theme colours (background, foreground, accent and shades mixed from them), so its shapes are the same under every theme. `walldye build` renders each design once per screen shape and for dark and light themes, then fits every colour in the resulting SVG as a linear mix of the three chosen colours. Those templates and their coefficients are committed, and the site recolours a wallpaper for any theme by rewriting its colours in the browser, without running the script. [docs/design.md](docs/design.md) has the details.

## Running it locally

You need [uv](https://docs.astral.sh/uv/), which installs Python 3.13 on first use, and [pnpm](https://pnpm.io/) with Node 24.

```sh
git clone https://github.com/nickolaj-jepsen/walldye && cd walldye
pnpm install
pnpm dev                                     # the site on http://localhost:4321
```

The Python side is the `walldye` library and CLI:

```sh
uv run walldye --help
uv run walldye list                          # every piece
uv run walldye preview schotter --theme nord # a PNG in $WALLDYE_PREVIEW, by default a folder in the temp directory
uv run walldye render radar-sweep --theme nord --aspect 21:9   # writes radar-sweep-nord-21x9.svg here
```

Tests and checks:

```sh
uv run pytest
uv run ruff format --check . && uv run ruff check .
uv run pyrefly check
pnpm test                                    # vitest
pnpm check-artifacts                         # committed builds against their inputs, as CI runs it
pnpm build
pnpm e2e                                     # Playwright; `pnpm e2e:nix` on NixOS
```

On NixOS the prebuilt Python wheels (numpy, scipy, shapely, scikit-image, resvg-py) need `programs.nix-ld.enable = true;`, and `pnpm e2e:nix` runs Playwright with the browsers from nixpkgs. There is no Nix devShell.

## Adding a wallpaper

Each wallpaper is a folder `wallpapers/<slug>/`: `design.py`, one `@design` function that draws on a canvas; `meta.yaml`, with the title, description, facets, sources and licence; and `build/`, which only `walldye build` writes.

With [Claude Code](https://claude.com/claude-code) in this repository, ask for a wallpaper: the walldye skill in `.claude/skills/walldye/` takes it from idea to review, and the wallpaper-batch workflow does the same for ten or more at once. By hand:

1. `uv run walldye new <slug> --author "<name>" --model <model id>` scaffolds the folder with a starter design and a draft meta.yaml. For a piece you wrote yourself, set `ai_generated: false`, remove `model:` and choose a `license:`.
2. Write `design.py` against [docs/api.md](docs/api.md), and look at it with `uv run walldye preview <slug>`, also with `--theme flexoki-light` and `--aspect 9:19.5`.
3. Fill in `meta.yaml` following the metadata and copy rules in [docs/design.md](docs/design.md).
4. `uv run walldye check <slug>`, then `uv run walldye build <slug>`. Commit the folder with its `build/` and the updated `wallpapers/index.json`.
5. `uv run walldye review <slug>` opens a local page for approving the draft.

## Repository layout

| Path | What |
|---|---|
| `walldye/` | the library designs import, and the CLI in `walldye/tools/` |
| `wallpapers/` | one folder per wallpaper, plus the generated `index.json` |
| `src/` | the Astro site |
| `tests/` | pytest, vitest and Playwright suites and their fixtures |
| `scripts/` | the stale-build check CI runs, and the font subsetter |
| `docs/` | [design.md](docs/design.md) (how it works and why), [api.md](docs/api.md) (the design API and CLI), [site.md](docs/site.md) (the site's visual system and voice), [deploy.md](docs/deploy.md) (hosting and CI) |
| `.claude/` | the Claude Code skill and batch workflow |
| `infra/` | the Worker that redirects www.walldye.com |
| `LICENSES/` | licence texts, named by SPDX id |

## Licences

| Path | Licence |
|---|---|
| Everything outside `wallpapers/` unless listed below | GPL-3.0-or-later ([LICENSE](LICENSE)) |
| `walldye/font.py` (Spleen glyphs) | BSD-2-Clause, 2018-2024 Frederic Cambus |
| `src/assets/fonts/` | SIL OFL 1.1 ([OFL.txt](src/assets/fonts/OFL.txt)) |
| `wallpapers/<slug>/` | Per folder: the `license:` in its `meta.yaml`, or CC0-1.0 for an AI-generated piece that leaves it out. `wallpapers/index.json` lists the result for every piece. |
| Third-party data in `wallpapers/<slug>/data/` | Its upstream licence, with the notice in [REUSE.toml](REUSE.toml) |

Pieces licensed `LicenseRef-fan-work` are unofficial fan tributes to games and other franchises, not affiliated with or endorsed by their owners. No licence is granted for those folders; [LICENSES/LicenseRef-fan-work.txt](LICENSES/LicenseRef-fan-work.txt) has the terms. Rights holders who want one taken down can write to takedown@walldye.com.

Before basing a piece on someone else's work, read "What a piece may draw" in [docs/design.md](docs/design.md#what-a-piece-may-draw). In short: techniques and ideas are free, only public-domain or openly licensed works are redrawn, and a work still in copyright can inspire a piece but is never copied.
