# walldye

walldye is a catalog of desktop and phone wallpapers, each drawn by a small Python script. Pick three colors and every wallpaper is redrawn in them, along with the site itself. The catalog is at [walldye.com](https://walldye.com), where any piece downloads as SVG, PNG, WebP or JPEG.

## How the colors work

A design never sees a color value. It draws in symbolic theme colors (background, foreground, accent and shades mixed from them), so its shapes are the same under every theme. `walldye build` renders each design once per screen shape and for dark and light themes, then records every color in the resulting SVG as a linear mix of the three chosen colors, read off the formula it was drawn with. CI builds those templates and their coefficients for every published piece, and the site recolors a wallpaper for any theme by rewriting its colors in the browser, without running the script. [docs/architecture.md](docs/architecture.md) has the details.

## Running it locally

You need [uv](https://docs.astral.sh/uv/), which installs Python 3.13 on first use, and [pnpm](https://pnpm.io/) with Node 24.

```sh
git clone https://github.com/nickolaj-jepsen/walldye && cd walldye
uv run prek install                          # ruff and Pyrefly before each commit
uv run walldye build --all                  # the templates: not in git, and minutes on a first run
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
uv run prek run --all-files                  # ruff, and Pyrefly on the library and the designs
uv run python scripts/fixtures/regen.py # the Python renders vitest compares against, after a build
pnpm test                                    # vitest
pnpm build
pnpm e2e                                     # Playwright; `pnpm e2e:nix` on NixOS
```

With Nix, `nix develop` gives a shell with the Python environment from `uv.lock`, Node, pnpm and the browsers Playwright needs, and every command above works in it unchanged. Without the shell, NixOS needs `programs.nix-ld.enable = true;` for the prebuilt Python wheels, and `pnpm e2e:nix` runs Playwright with the browsers from nixpkgs.

## On NixOS

The flake packages the CLI, with the whole catalog, drafts included, and renders any piece as a PNG for your screen:

```nix
# flake inputs: walldye.url = "github:nickolaj-jepsen/walldye";
let
  wallpaper = inputs.walldye.packages.${pkgs.stdenv.hostPlatform.system}.default.mkWallpaper {
    slug = "radar-sweep";
    theme = "gruvbox-dark"; # or { bg = "#282828"; fg = "#EBDBB2"; accent = "#FE8019"; }
    width = 3440;
    height = 1440;
    # variant = "late";  set = { seed = 7; };
  };
in
{
  services.hyprpaper.settings.wallpaper = [ ",${wallpaper}" ]; # or stylix.image, swaybg, ...
}
```

A shape the piece wasn't drawn for is cut from its 16:9 version around the busiest part of the picture, as the site does. `nix run github:nickolaj-jepsen/walldye -- list` shows the slugs, and `overlays.default` adds `pkgs.walldye`.

## Adding a wallpaper

Each wallpaper is a folder `wallpapers/<slug>/`: `design.py`, one `@design` function that draws on a canvas; `meta.yaml`, with the title, description, facets, sources and license; and `build/`, which only `walldye build` writes and git ignores.

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
| `scripts/` | the font subsetter |
| `docs/` | [architecture.md](docs/architecture.md) (how it works and why), [wallpapers.md](docs/wallpapers.md) (metadata, copy and licensing rules), [api.md](docs/api.md) (the design API and CLI), [site.md](docs/site.md) (the site's visual system and voice), [deploy.md](docs/deploy.md) (hosting and CI) |
| `.claude/` | the Claude Code skill and batch workflow |
| `infra/` | the Worker that redirects www.walldye.com |
| `LICENSES/` | license texts, named by SPDX id |

## Licenses

| Path | License |
|---|---|
| Everything outside `wallpapers/` unless listed below | GPL-3.0-or-later ([LICENSE](LICENSE)) |
| `walldye/_font.py` (Spleen glyphs) | BSD-2-Clause, 2018-2024 Frederic Cambus |
| `src/assets/fonts/` | SIL OFL 1.1 ([OFL.txt](src/assets/fonts/OFL.txt)) |
| `wallpapers/<slug>/` | Per folder: the `license:` in its `meta.yaml`, `LicenseRef-fan-work` when it has a `franchise:`, or CC0-1.0 for an AI-generated piece that sets neither. |
| Third-party data in `wallpapers/<slug>/data/` | Its upstream license, with the notice in [REUSE.toml](REUSE.toml) |

Pieces with a `franchise:`, licensed `LicenseRef-fan-work`, are unofficial fan tributes to games and other franchises, not affiliated with or endorsed by their owners. No license is granted for those folders; [LICENSES/LicenseRef-fan-work.txt](LICENSES/LicenseRef-fan-work.txt) has the terms. Rights holders who want one taken down can write to takedown@walldye.com.

Before basing a piece on someone else's work, read "What a piece may draw" in [docs/wallpapers.md](docs/wallpapers.md#what-a-piece-may-draw). In short: techniques and ideas are free, only public-domain or openly licensed works are redrawn, and a work still in copyright can inspire a piece but is never copied.
