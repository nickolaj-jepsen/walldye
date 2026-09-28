# Deploy

How walldye.com is built, deployed and hosted, and how to check or change each part. architecture.md (CI) explains why CI renders the catalogue itself.

`,` in the commands below is comma, which runs a tool from nixpkgs without installing it; elsewhere, `pnpm dlx wrangler` does the same.

## CI

Three workflows run on pushes to `main`, on pull requests and on manual runs (Actions > <workflow> > Run workflow):

| Workflow | Runs | Does |
|---|---|---|
| `lint.yml` | on every change | `ruff format --check` (Markdown's ` ```python ` blocks included) and `ruff check`, with the standalone ruff binary |
| `python.yml` | when `walldye/`, `tests/python/`, a `design.py`, the skill examples, `wallpapers/pyrefly.toml`, `pyproject.toml`, `uv.lock` or `.python-version` changes | Pyrefly on the library at the strictest preset and on the designs and skill examples at the design level, then pytest |
| `ci.yml` | unless the change touches only `docs/`, Markdown, `.claude/`, `infra/`, `LICENSES/` or `.lycheeignore` | the jobs below |

`ci.yml`'s jobs:

| Job | Does |
|---|---|
| `build` | Restores main's last build from the Actions cache, runs `walldye build --all --published`, saves the result back to the cache on `main`, lists the pieces whose templates changed, runs `regen.py`, `pnpm test` and `pnpm astro build`, uploads `dist/` and the e2e inputs, then checks the links in the meta.yaml files the change touches |
| `e2e` | Playwright on Chromium against that `dist/` |
| `deploy` | After `build` and `e2e` pass: a push to `main` goes to production, and a pull request from a branch in this repository goes to a preview at `https://<branch>.walldye.pages.dev`. A comment on the PR links it and lists the pieces that draw differently from main's last build; later pushes edit it. Pull requests from forks never deploy, and manual runs build and test without deploying |

- A newer run cancels an older one on the same pull request or branch.
- The deploy job has no checkout. It runs `wrangler pages deploy dist --project-name=walldye --branch=<branch> --commit-hash=<sha>` through `cloudflare/wrangler-action`, so wrangler gets the commit explicitly.

Only `main` saves the render cache, so a pull request starts from main's last build and redraws only what it changed. GitHub drops a cache that goes unread for 7 days, and the next run then renders the whole catalogue from scratch, hence the 120-minute timeout. A change to `walldye/` outside `tools/`, or to the render dependencies in `uv.lock`, re-renders every piece's probes, which takes a few minutes.

## What is set up

GitHub:
- The public repository `nickolaj-jepsen/walldye`, the `origin` remote, with walldye.com as its website. The About page links to it, and every "Run it yourself" command clones it.
- A ruleset keeps `main` from being deleted or force-pushed. Secret scanning with push protection and Dependabot alerts are on.
- Fork pull requests run their workflows without the secrets and never deploy. Runs from outside contributors wait for approval (Settings > Actions > General).
- Repository secrets: `CLOUDFLARE_API_TOKEN`, a token scoped to Account / Cloudflare Pages / Edit, and `CLOUDFLARE_ACCOUNT_ID`. Previews of branches in this repository need them too, so they are not limited to `main`.

Cloudflare:
- walldye.com is registered with Cloudflare Registrar, and its zone is in the account.
- The Pages project `walldye`: Direct Upload, production branch `main`, created with `, wrangler pages project create walldye --production-branch main`.
- walldye.com is a custom domain of the Pages project, set in the dashboard (wrangler has no command for Pages domains). It serves whatever `main` last deployed. `public/_headers` sends `X-Robots-Tag: noindex` on walldye.pages.dev, and Pages adds the same header to every preview deployment, so only walldye.com gets indexed.
- www.walldye.com answers with a 301 to the apex, keeping path and query. It is the Worker in `infra/www-redirect/` on a Workers custom domain, which also owns the `www` DNS record and certificate. CI does not deploy it.
- Web Analytics is on for the Pages project. The beacon is injected into each deployment and sets no cookies, so the site needs no consent banner.
- Email Routing is on for walldye.com: takedown@walldye.com, the contact in the fan-work disclaimer, forwards to the owner's own address. The zone's MX records point at `route1`, `route2` and `route3.mx.cloudflare.net`.

## Going live

A push to `main` deploys only when `ci.yml` runs, and it skips docs-only changes, so walldye.com answers 404 until the first push to `main` that changes more than docs. Then run the checks below against it.

## Check that it works

- walldye.com loads, recolours when the theme changes, and exports a PNG from a detail page.
- `curl -sI 'https://www.walldye.com/schotter?t=nord'` answers `301` with `location: https://walldye.com/schotter?t=nord`.
- `https://walldye.com/robots.txt` ends with `Sitemap: https://walldye.com/sitemap-index.xml`, and the sitemap it names lists every published piece.
- A template under `/t/` is served with `cache-control: public, max-age=31536000, immutable`, and a page with `max-age=0, must-revalidate`.
- A pull request from a branch in this repository: once `build` and `e2e` pass, a comment links the preview, and later pushes edit the same comment.
- Actions > Links (weekly) > Run workflow: broken links end up in an issue titled "Broken links in wallpaper sources", which the next clean run closes.
- A test mail to takedown@walldye.com arrives in the owner's inbox.

## Changing things

- The www Worker: edit `infra/www-redirect/`, then run `, wrangler deploy` in that directory.
- A renamed wallpaper: add `/<old-slug> /<new-slug> 301` to `public/_redirects`.
- The API token: create a new one scoped to Account / Cloudflare Pages / Edit, store it with `gh secret set CLOUDFLARE_API_TOKEN`, then delete the old token in the dashboard.
- A manual deploy of a local build, if CI is down: `pnpm build`, then `, wrangler pages deploy dist --project-name=walldye --branch=main`.

## Link checks

The `build` job checks the URLs in every `wallpapers/*/meta.yaml` a change touches. A broken one fails a pull request; on `main` it is reported without holding back the deploy. `links-weekly.yml` checks every piece on Mondays and never blocks anything. The same check locally:

```sh
nix run nixpkgs#lychee -- --max-retries 3 --accept 200..=299,403,429 'wallpapers/*/meta.yaml'
```

`.lycheeignore` says when an exception is worth adding.
