# Contributing

[docs/architecture.md](docs/architecture.md) explains how walldye works.

## Setup

Needs [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/) with Node 24. On NixOS, `nix develop` has everything; outside it, set `programs.nix-ld.enable` for the Python wheels.

```sh
uv run prek install          # ruff, Pyrefly and Biome on every commit
uv run walldye build --all   # the SVG templates, which git doesn't track; slow the first time
pnpm install
pnpm dev                     # http://localhost:4321, drafts included
```

## Adding a wallpaper

1. `uv run walldye new <slug> --author "<your name>"` creates `wallpapers/<slug>/` with a starter `design.py` and a draft `meta.yaml`.
2. Write `design.py` against [docs/api.md](docs/api.md). `uv run walldye preview <slug>` renders a PNG; try `--theme flexoki-light` and `--aspect 9:19.5` too.
3. Fill in `meta.yaml`, including `license:`, following [docs/wallpapers.md](docs/wallpapers.md).
4. `uv run walldye check <slug>`, then `uv run walldye build <slug>`.
5. `uv run walldye review <slug>` opens a page to look the piece over and publish it.
6. Commit `design.py`, `meta.yaml` and `data/`, and open a pull request. CI renders the rest.

## Commands

```sh
uv run walldye --help
uv run walldye params <slug>          # a design's params and variants
uv run walldye build --all --published   # what CI runs
uv run pytest
uv run ruff format . && uv run ruff check --fix .
uv run pyrefly check                  # the library, strictest preset
uv run pyrefly check -c wallpapers/pyrefly.toml wallpapers/*/design.py
uv run python scripts/fixtures/regen.py   # after a build, before pnpm test

pnpm test                             # vitest
pnpm check                            # astro check, after a build
pnpm lint                             # Biome; pnpm format fixes what it can
pnpm astro build
pnpm e2e                              # Playwright; pnpm e2e:nix on NixOS outside nix develop
pnpm promo                            # the README clip, into promo/
```

To update the clip, copy `promo/walldye.webp` over `.github/promo.webp`.
