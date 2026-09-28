# walldye

walldye is a catalogue of desktop and phone wallpapers, each drawn by a small Python script. Pick three colours and every wallpaper is redrawn in them, along with the site itself. The catalogue is at [walldye.com](https://walldye.com), where any piece downloads as SVG, PNG, WebP or JPEG.

## How the colours work

A design never sees a colour value. It draws in symbolic theme colours (background, foreground, accent and shades mixed from them), so its shapes are the same under every theme. `walldye build` renders each design once per screen shape and for dark and light themes, then records every colour in the resulting SVG as a linear mix of the three chosen colours, read off the formula it was drawn with. CI builds those templates and their coefficients for every published piece, and the site recolours a wallpaper for any theme by rewriting its colours in the browser, without running the script. A piece's page can also run the script itself, in [Pyodide](https://pyodide.org/), to draw it again with another seed or with the values a visitor sets. [docs/architecture.md](docs/architecture.md) has the details.

## Running it locally

You need [uv](https://docs.astral.sh/uv/), which installs Python 3.13 on first use, and [pnpm](https://pnpm.io/) with Node 24.

```sh
git clone https://github.com/nickolaj-jepsen/walldye && cd walldye
uv run prek install                          # ruff and Pyrefly before each commit
uv run walldye build --all                  # the templates: not in git, and minutes on a first run
pnpm install
pnpm dev                                     # the site on http://localhost:4321; the first run fetches Pyodide, about 50 MB
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
uv run prek run --all-files                  # ruff, and Pyrefly on the library and the designs
uv run python tests/python/fixtures/regen.py # the Python renders vitest compares against, after a build
pnpm test                                    # vitest
pnpm build
pnpm e2e                                     # Playwright; `pnpm e2e:nix` on NixOS
```

On NixOS the prebuilt Python wheels (numpy, scipy, shapely, scikit-image, resvg-py) need `programs.nix-ld.enable = true;`, and `pnpm e2e:nix` runs Playwright with the browsers from nixpkgs. There is no Nix devShell.

## Adding a wallpaper

Each wallpaper is a folder `wallpapers/<slug>/`: `design.py`, one `@design` function that draws on a canvas; `meta.yaml`, with the title, description, facets, sources and licence; and `build/`, which only `walldye build` writes and git ignores.

With [Claude Code](https://claude.com/claude-code) in this repository, ask for a wallpaper: the walldye skill in `.claude/skills/walldye/` takes each subject you name from idea to review, and the wallpaper-batch workflow researches and builds a batch of new ones. By hand:

1. `uv run walldye new <slug> --model <model id>` scaffolds the folder with a starter design and a draft meta.yaml. For a piece you wrote yourself, replace `model:` with `author: <your name>` and choose a `license:`.
2. Write `design.py` against [docs/api.md](docs/api.md), and look at it with `uv run walldye preview <slug>`, also with `--theme flexoki-light` and `--aspect 9:19.5`.
3. Fill in `meta.yaml` following [docs/wallpapers.md](docs/wallpapers.md).
4. `uv run walldye check <slug>`, then `uv run walldye build <slug>`. Commit `design.py`, `meta.yaml` and `data/`; CI renders the rest.
5. `uv run walldye review <slug>` opens a local page for approving the draft.

## Repository layout

| Path | What |
|---|---|
| `walldye/` | the library designs import, and the CLI in `walldye/tools/` |
| `wallpapers/` | one folder per wallpaper |
| `src/` | the Astro site |
| `tests/` | pytest, vitest and Playwright suites and their fixtures |
| `scripts/` | the font subsetter, and the Pyodide fetcher the site build runs |
| `docs/` | [architecture.md](docs/architecture.md) (how it works and why), [wallpapers.md](docs/wallpapers.md) (metadata, copy and licensing rules), [api.md](docs/api.md) (the design API and CLI), [site.md](docs/site.md) (the site's visual system and voice), [deploy.md](docs/deploy.md) (hosting and CI) |
| `.claude/` | the Claude Code skill and batch workflow |
| `infra/` | the Worker that redirects www.walldye.com |
| `LICENSES/` | licence texts, named by SPDX id |

## Licences

| Path | Licence |
|---|---|
| Everything outside `wallpapers/` unless listed below | GPL-3.0-or-later ([LICENSE](LICENSE)) |
| `walldye/font.py` (Spleen glyphs) | BSD-2-Clause, 2018-2024 Frederic Cambus |
| `src/assets/fonts/` | SIL OFL 1.1 ([OFL.txt](src/assets/fonts/OFL.txt)) |
| `wallpapers/<slug>/` | Per folder: the `license:` in its `meta.yaml`, `LicenseRef-fan-work` when it has a `franchise:`, or CC0-1.0 for an AI-generated piece that sets neither. |
| Third-party data in `wallpapers/<slug>/data/` | Its upstream licence, with the notice in [REUSE.toml](REUSE.toml) |

Pieces with a `franchise:`, licensed `LicenseRef-fan-work`, are unofficial fan tributes to games and other franchises, not affiliated with or endorsed by their owners. No licence is granted for those folders; [LICENSES/LicenseRef-fan-work.txt](LICENSES/LicenseRef-fan-work.txt) has the terms. Rights holders who want one taken down can write to takedown@walldye.com.

Before basing a piece on someone else's work, read "What a piece may draw" in [docs/wallpapers.md](docs/wallpapers.md#what-a-piece-may-draw). In short: techniques and ideas are free, only public-domain or openly licensed works are redrawn, and a work still in copyright can inspire a piece but is never copied.
