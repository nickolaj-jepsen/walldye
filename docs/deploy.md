# Deploy

How walldye.com is built, deployed and hosted, and how to check or change each part. architecture.md (CI) explains why CI renders the catalog itself.

`,` in the commands below is comma, which runs a tool from nixpkgs without installing it; elsewhere, `pnpm dlx wrangler` does the same.

## CI

Three workflows run on pushes to `main`, on pull requests and on manual runs (Actions > <workflow> > Run workflow):

| Workflow | Runs | Does |
|---|---|---|
| `lint.yml` | on every change | `ruff format --check` (Markdown's ` ```python ` blocks included) and `ruff check`, and `biome ci` for the TypeScript |
| `python.yml` | when a path in its `paths` list changes: the library, its tests, the designs and their meta.yaml, taxonomy.yaml or the Python environment | Pyrefly on the library at the strictest preset and on the designs at the design level, then pytest |
| `ci.yml` | unless the change touches only `docs/`, Markdown, `.claude/`, `infra/` or `LICENSES/` | the jobs below |

`ci.yml`'s jobs:

| Job | Does |
|---|---|
| `build` | Checks out `stats/`, restores main's last build from the Actions cache, runs `walldye build --all --published`, then `walldye build --all` for the drafts, which never fails the job, saves the cache on `main`, lists the pieces whose templates changed, runs `regen.py`, `pnpm test`, `pnpm check` and `pnpm astro build`, and uploads `dist/` and the e2e inputs. A pull request with built drafts also gets a `preview/` built with `WALLDYE_DRAFTS=1` |
| `e2e` | Playwright on Chromium against that `dist/` |
| `deploy` | After `build` and `e2e` pass: a push to `main` goes to production, and a pull request from a branch in this repository goes to a preview at `https://<branch>.walldye.pages.dev`. The preview deploys `preview/` when there is one, so it shows the drafts. A comment on the PR links it and lists the pieces that draw differently from main's last build and the drafts it shows; later pushes edit it. Pull requests from forks or Dependabot never deploy, since neither gets the secrets, and a manual run deploys only on `main` with `deploy` ticked |

GitHub drops a cache that goes unread for 7 days (the daily redeploy reads it on any day with views), and the next run then renders the whole catalog, which the 120-minute timeout allows for. A render cut short is saved as it stands, and the next run on `main` picks up from there. A toolchain change takes about a third of the time of a full render.

## Page views

`views.yml` runs daily at 02:23 UTC and on manual runs. `scripts/views/fetch.ts` writes each finished UTC day's page views by slug to `stats/views/<YYYY-MM-DD>.json`. The job pushes new files to the `stats` branch, then starts `ci.yml` on `main` with `deploy` ticked, since a push made with the workflow's token starts no workflow. The next run picks up a missed day, sampled if it is a few days old by then.

To build locally with the views: `git fetch origin stats && git worktree add --detach stats FETCH_HEAD`; after a later fetch, `git -C stats checkout --detach origin/stats`.

## What is set up

GitHub:
- The public repository `nickolaj-jepsen/walldye`, the `origin` remote, with walldye.com as its website. The About page links to it, and every "Run it yourself" command clones it.
- A ruleset keeps `main` from being deleted or force-pushed. Secret scanning with push protection and Dependabot alerts are on.
- Runs from outside contributors wait for approval (Settings > Actions > General).
- Repository secrets: `CLOUDFLARE_API_TOKEN`, a token scoped to Account / Cloudflare Pages / Edit, and `CLOUDFLARE_ACCOUNT_ID`. Previews of branches in this repository need them too, so they are not limited to `main`.
- Environments `production`, which only `main` may deploy to, and `preview`. They record the deploys and hold no secrets.
- Every action in the workflows is pinned to a commit SHA, and Dependabot (`.github/dependabot.yml`) bumps them. Its security updates are off.
- For `views.yml`: the secret `CLOUDFLARE_ANALYTICS_TOKEN`, a token scoped to Account / Account Analytics / Read.

Cloudflare:
- walldye.com is registered with Cloudflare Registrar, and its zone is in the account.
- The Pages project `walldye`: Direct Upload, production branch `main`, created with `, wrangler pages project create walldye --production-branch main`.
- walldye.com is a custom domain of the Pages project, set in the dashboard (wrangler has no command for Pages domains). It serves whatever `main` last deployed. `public/_headers` sends `X-Robots-Tag: noindex` on walldye.pages.dev, and Pages adds the same header to every preview deployment, so only walldye.com gets indexed.
- www.walldye.com redirects to the apex through the Worker in `infra/www-redirect/`, on a Workers custom domain.
- Web Analytics is on for the Pages project. The beacon is injected into each deployment and sets no cookies, so the site needs no consent banner.
- Email Routing is on for walldye.com: takedown@walldye.com, the contact in the fan-work disclaimer, forwards to the owner's own address. The zone's MX records point at `route1`, `route2` and `route3.mx.cloudflare.net`.

## Check that it works

- walldye.com loads, recolors when the theme changes, and exports a PNG from a detail page.
- `curl -sI 'https://www.walldye.com/loose-squares?t=nord'` answers `301` with `location: https://walldye.com/loose-squares?t=nord`.
- `https://walldye.com/robots.txt` ends with `Sitemap: https://walldye.com/sitemap-index.xml`, and the sitemap it names lists every published piece.
- A template under `/t/` is served with `cache-control: public, max-age=31536000, immutable`, and a page with `max-age=0, must-revalidate`.
- A pull request from a branch in this repository: once `build` and `e2e` pass, a comment links the preview, and later pushes edit the same comment.
- After a `views.yml` run that finds a new day, `stats` has a commit named after it, a `ci.yml` run on `main` has deployed, and the index sort offers "popular" and "most viewed".
- A test mail to takedown@walldye.com arrives in the owner's inbox.

## Changing things

- The www Worker: edit `infra/www-redirect/`, then run `, wrangler deploy` in that directory.
- A renamed wallpaper: add `/<old-slug> /<new-slug> 301` to `public/_redirects`.
- The API token: create a new one scoped to Account / Cloudflare Pages / Edit, store it with `gh secret set CLOUDFLARE_API_TOKEN`, then delete the old token in the dashboard. The analytics token the same way, scoped to Account / Account Analytics / Read, with `gh secret set CLOUDFLARE_ANALYTICS_TOKEN`.
- A manual deploy of a local build, if CI is down: `pnpm build`, then `, wrangler pages deploy dist --project-name=walldye --branch=main`.
