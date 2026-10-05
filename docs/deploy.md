# Deploy

How walldye.com is built, deployed and hosted, and how to check or change each part. architecture.md (CI) explains why CI renders the catalog itself.

`,` in the commands below is comma, which runs a tool from nixpkgs without installing it; elsewhere, `pnpm dlx wrangler` does the same.

## CI

Three workflows run on pushes to `main`, on pull requests and on manual runs (Actions > <workflow> > Run workflow), and one when a pull request closes:

| Workflow | Runs | Does |
|---|---|---|
| `lint.yml` | on every change | `ruff format --check` (Markdown's ` ```python ` blocks included) and `ruff check`, and `biome ci` for the TypeScript |
| `python.yml` | when a path in its `paths` list changes: the library, its tests, the designs and their meta.yaml, taxonomy.yaml or the Python environment | Pyrefly on the library at the strictest preset and on the designs at the design level, then pytest |
| `ci.yml` | unless the change touches only `docs/`, Markdown, `.claude/`, `infra/www-redirect/` or `LICENSES/` | the jobs below |
| `preview-cleanup.yml` | when a pull request that `ci.yml` deploys closes | cancels a `ci.yml` run still going for it, then deletes its Preview, since the free plan keeps 100 Previews per Worker |

`ci.yml`'s jobs:

| Job | Does |
|---|---|
| `build` | Checks out `stats/`, restores main's last build from the Actions cache, runs `walldye build --all --published`, then `walldye build --all` for the drafts, which never fails the job, saves the cache on `main`, lists the pieces whose templates changed, runs `regen.py`, `pnpm test`, `pnpm check`, `pnpm astro build` and `pnpm build:worker`, and uploads `dist/`, the Worker bundle and the e2e inputs. A pull request with built drafts also gets a `preview/` built with `WALLDYE_DRAFTS=1` |
| `e2e` | Playwright on Chromium against that `dist/` |
| `deploy` | After `build` and `e2e` pass: a push to `main` goes to production with `wrangler deploy`, and a pull request from a branch in this repository goes to its Preview `pr-<number>` with `wrangler preview`, at `https://pr-<number>-walldye.<subdomain>.workers.dev`. The Preview deploys `preview/` when there is one, so it shows the drafts. A comment on the PR links it and lists the pieces that draw differently from main's last build and the drafts it shows; later pushes edit it. The job then requests the deployed site: a missing page must answer 404 with the 404 page, a template under `/t/` must be cached as immutable, `/about` must revalidate, a GET of `/e` must answer 405 from the Worker, and on walldye.com `/` must carry the Web Analytics beacon. Pull requests from forks or Dependabot never deploy, since neither gets the secrets, and a manual run deploys only on `main` with `deploy` ticked |

GitHub drops a cache that goes unread for 7 days (the redeploy after each `stats.yml` run that pushes reads it), and the next run then renders the whole catalog, which the 120-minute timeout allows for. A render cut short is saved as it stands, and the next run on `main` picks up from there. A toolchain change takes about a third of the time of a full render.

## Stats

`stats.yml` runs daily at 02:23 UTC and on manual runs, and saves each finished UTC day on the `stats` branch:

- `views/<YYYY-MM-DD>.json`: page views by slug from Web Analytics (`scripts/stats/views.ts`). A missed day is picked up on the next run, sampled if it is a few days old by then.
- `events/<YYYY-MM-DD>.json`: the product events in `walldye_events` (`scripts/stats/events.ts` describes the file). A missed day is picked up while Analytics Engine still holds it. Each run also rebuilds `events/all.json`, the dashboard's history.

A second job, which installs nothing, commits the new files as `stats through <day>`, pushes, then starts `ci.yml` on `main` with `deploy` ticked, since a push made with the workflow's token starts no workflow. One fetch failing still pushes what the other wrote.

To build locally with the stats: `git fetch origin stats && git worktree add --detach stats FETCH_HEAD`; after a later fetch, `git -C stats checkout --detach origin/stats`.

### Grafana

`infra/grafana/walldye.json` charts the last three months from Analytics Engine and the history from `all.json`. To set it up in Grafana Cloud:

1. Install the plugins "Altinity plugin for ClickHouse" (`vertamedia-clickhouse-datasource`) and "Infinity" (`yesoreyeram-infinity-datasource`).
2. Create a Cloudflare API token with only Account / Account Analytics / Read, apart from `CLOUDFLARE_ANALYTICS_TOKEN` so each can be revoked alone.
3. Add an Altinity ClickHouse data source with the URL `https://api.cloudflare.com/client/v4/accounts/<account id>/analytics_engine/sql`, every auth option off, and the custom HTTP header `Authorization: Bearer <token>`.
4. Add an Infinity data source with no authentication.
5. Import the dashboard (Dashboards > New > Import) and pick the two data sources.

A change to `BLOBS` or `DOUBLES` needs the dashboard's queries changed too; `tests/unit/grafana.test.ts` checks them.

## What is set up

GitHub:
- The public repository `nickolaj-jepsen/walldye`, the `origin` remote, with walldye.com as its website. The About page links to it, and every "Run it yourself" command clones it.
- A ruleset keeps `main` from being deleted or force-pushed. Secret scanning with push protection and Dependabot alerts are on.
- Runs from outside contributors wait for approval (Settings > Actions > General).
- Repository secrets: `CLOUDFLARE_API_TOKEN`, a token scoped to Account / Workers Scripts / Edit, plus Zone / Workers Routes / Edit and Zone / Zone / Read for walldye.com, which `wrangler deploy` needs for the custom domain, and `CLOUDFLARE_ACCOUNT_ID`. Previews of branches in this repository need them too, so they are not limited to `main`.
- Environments `production`, which only `main` may deploy to, and `preview`. They record the deploys and hold no secrets.
- Every action in the workflows is pinned to a commit SHA, and Dependabot (`.github/dependabot.yml`) bumps them. Its security updates are off.
- For `stats.yml`: the secret `CLOUDFLARE_ANALYTICS_TOKEN`, a token scoped to Account / Account Analytics / Read, which reads both Web Analytics and Analytics Engine.

Cloudflare:
- walldye.com is registered with Cloudflare Registrar, and its zone is in the account.
- The Worker `walldye` serves `dist/` as static assets. Its script, `src/worker/`, answers `/e`. The deploy job gets it as one bundled file from `build` and checks out only `wrangler.jsonc`, so wrangler is the only package installed next to the API token. `wrangler.jsonc` sets its routing: paths that match no file get `404.html` with status 404, and `/about/` and `/about.html` redirect to `/about`. `public/_headers` sets the cache headers and `public/_redirects` the renames.
- walldye.com is the Worker's custom domain, declared in `wrangler.jsonc`, so `wrangler deploy` keeps its DNS record and certificate. It serves whatever `main` last deployed. Production has no workers.dev URL. Previews and version URLs do, and they are sent with `X-Robots-Tag: noindex` (Cloudflare adds it to Previews, `public/_headers` to every workers.dev host), so only walldye.com gets indexed.
- www.walldye.com redirects to the apex through the Worker in `infra/www-redirect/`, on a Workers custom domain.
- Web Analytics is on for the walldye.com hostname with automatic setup: Cloudflare injects the beacon into the pages as it serves them, so the source has no snippet, and Previews are not measured. The beacon sets no cookies, so the site needs no consent banner.
- Product events (architecture.md, The site) go to the Analytics Engine dataset `walldye_events`, and from Previews to `walldye_events_preview`, both bound as `EVENTS`. A dataset is created on its first write and keeps rows for three months. The SQL API reads them with `CLOUDFLARE_ANALYTICS_TOKEN`; the columns are `BLOBS` and `DOUBLES` in `src/lib/events.ts`, and `index1` is the event name. Events sent from a version URL land in `walldye_events`.
- Workers Logs keeps the Worker's own output: one object per stored event and its errors. Invocation logs are off, since they would record each request's headers and location. Workers & Pages > walldye > Observability queries them, grouped by any field, with a distinct count of `visitor`.
- The daily visitor key is derived from the secret `EVENTS_KEY`. Production and the Previews base configuration each hold their own random value (`openssl rand -hex 32`), set from the repository root with `pnpm dlx wrangler@4.143.0 secret put EVENTS_KEY` and `pnpm dlx wrangler@4.143.0 preview base-config secret put EVENTS_KEY`. The base configuration reaches only Previews created after it changes; an existing one takes `pnpm dlx wrangler@4.143.0 preview secret put EVENTS_KEY --name pr-<number>`. Without the secret, `/e` answers 503 and the deploy's check fails.
- Email Routing is on for walldye.com: takedown@walldye.com, the contact in the fan-work disclaimer, forwards to the owner's own address. The zone's MX records point at `route1`, `route2` and `route3.mx.cloudflare.net`.

## Check that it works

- walldye.com loads, recolors when the theme changes, and exports a PNG from a detail page.
- `curl -sI 'https://www.walldye.com/loose-squares?t=nord'` answers `301` with `location: https://walldye.com/loose-squares?t=nord`.
- `https://walldye.com/robots.txt` ends with `Sitemap: https://walldye.com/sitemap-index.xml`, and the sitemap it names lists every published piece.
- A template under `/t/` is served with `cache-control: public, max-age=31536000, immutable`, and a page with `max-age=0, must-revalidate`.
- `https://walldye.com/no-such-piece` answers `404` with the site's own Not found page.
- An export on walldye.com shows up in Workers Logs within a minute, with `event: "export"` and the piece's `slug`.
- A page's HTML on walldye.com includes the Web Analytics beacon (`static.cloudflareinsights.com/beacon.min.js`), and the dashboard counts the visit.
- A pull request from a branch in this repository: once `build` and `e2e` pass, a comment links the Preview, later pushes edit the same comment, and closing the pull request deletes the Preview (Workers & Pages > walldye > Previews).
- After a `stats.yml` run that finds a new day, `stats` has a commit named after it, a `ci.yml` run on `main` has deployed, and the index sort offers "popular" and "most viewed".
- The day after the first export on walldye.com, a `stats.yml` run writes `events/<that day>.json` on `stats`, with the piece under `downloads`, and `events/all.json`.
- A test mail to takedown@walldye.com arrives in the owner's inbox.

## Changing things

- The www Worker: edit `infra/www-redirect/`, then run `, wrangler deploy` in that directory.
- A renamed wallpaper: add `/<old-slug> /<new-slug> 301` to `public/_redirects`.
- The site Worker's settings: edit `wrangler.jsonc`. A Preview takes them from its pull request, except the custom domain, which changes only when `main` deploys, and the workers.dev settings, which come from whichever Preview or deploy creates the Worker and from `main`'s deploys after that.
- The API token: create a new one with the scopes above, store it with `gh secret set CLOUDFLARE_API_TOKEN`, then delete the old token in the dashboard. The analytics token the same way, scoped to Account / Account Analytics / Read, with `gh secret set CLOUDFLARE_ANALYTICS_TOKEN`, and Grafana's in its data source's `Authorization` header.
- The Worker locally: `EVENTS_KEY=dev` in `.dev.vars` (gitignored), `pnpm build`, then `pnpm dlx wrangler@4.143.0 dev`, which serves `dist/` and prints each stored event.
- The events and their fields in `src/lib/events.ts`: a field whose type changes takes a new name; the day files on `stats` need no change.
- The events key: set a new value with the commands above. Visitor keys change with it, so that day's visitors count twice.
- A manual deploy of a local build, if CI is down: `pnpm build`, then `pnpm dlx wrangler@4.143.0 deploy` from the repository root, pinned to the version CI deploys with.
