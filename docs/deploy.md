# Deploy

How walldye.com is built, deployed and hosted, and how to check or change each part. architecture.md (CI) explains why CI renders the catalog itself.

`,` in the commands below is comma, which runs a tool from nixpkgs without installing it; elsewhere, `pnpm dlx wrangler` does the same.

## CI

Three workflows run on pushes to `main`, on pull requests and on manual runs (Actions > <workflow> > Run workflow), and one when a pull request closes:

| Workflow | Runs | Does |
|---|---|---|
| `lint.yml` | on every change | `ruff format --check` (Markdown's ` ```python ` blocks included) and `ruff check`, and `biome ci` for the TypeScript |
| `python.yml` | when a path in its `paths` list changes: the library, its tests, the designs and their meta.yaml, taxonomy.yaml or the Python environment | Pyrefly on the library at the strictest preset and on the designs at the design level, then pytest |
| `ci.yml` | unless the change touches only `docs/`, Markdown, `.claude/`, `infra/` or `LICENSES/` | the jobs below |
| `preview-cleanup.yml` | when a pull request that `ci.yml` deploys closes | cancels a `ci.yml` run still going for it, then deletes its Preview, since the free plan keeps 100 Previews per Worker |

`ci.yml`'s jobs:

| Job | Does |
|---|---|
| `build` | Checks out `stats/`, restores main's last build from the Actions cache, runs `walldye build --all --published`, then `walldye build --all` for the drafts, which never fails the job, saves the cache on `main`, lists the pieces whose templates changed, runs `regen.py`, `pnpm test`, `pnpm check` and `pnpm astro build`, and uploads `dist/` and the e2e inputs. A pull request with built drafts also gets a `preview/` built with `WALLDYE_DRAFTS=1` |
| `e2e` | Playwright on Chromium against that `dist/` |
| `deploy` | After `build` and `e2e` pass: a push to `main` goes to production with `wrangler deploy`, and a pull request from a branch in this repository goes to its Preview `pr-<number>` with `wrangler preview`, at `https://pr-<number>-walldye.<subdomain>.workers.dev`. The Preview deploys `preview/` when there is one, so it shows the drafts. A comment on the PR links it and lists the pieces that draw differently from main's last build and the drafts it shows; later pushes edit it. The job then requests the deployed site: a missing page must answer 404 with the 404 page, a template under `/t/` must be cached as immutable, `/about` must revalidate, a GET of `/e` must answer 405 from the Worker, and on walldye.com `/` must carry the Web Analytics beacon. Pull requests from forks or Dependabot never deploy, since neither gets the secrets, and a manual run deploys only on `main` with `deploy` ticked |

GitHub drops a cache that goes unread for 7 days (the daily redeploy reads it on any day with views), and the next run then renders the whole catalog, which the 120-minute timeout allows for. A render cut short is saved as it stands, and the next run on `main` picks up from there. A toolchain change takes about a third of the time of a full render.

## Page views

`views.yml` runs daily at 02:23 UTC and on manual runs. `scripts/views/fetch.ts` writes each finished UTC day's page views by slug to `stats/views/<YYYY-MM-DD>.json`. The job pushes new files to the `stats` branch, then starts `ci.yml` on `main` with `deploy` ticked, since a push made with the workflow's token starts no workflow. The next run picks up a missed day, sampled if it is a few days old by then.

To build locally with the views: `git fetch origin stats && git worktree add --detach stats FETCH_HEAD`; after a later fetch, `git -C stats checkout --detach origin/stats`.

## What is set up

GitHub:
- The public repository `nickolaj-jepsen/walldye`, the `origin` remote, with walldye.com as its website. The About page links to it, and every "Run it yourself" command clones it.
- A ruleset keeps `main` from being deleted or force-pushed. Secret scanning with push protection and Dependabot alerts are on.
- Runs from outside contributors wait for approval (Settings > Actions > General).
- Repository secrets: `CLOUDFLARE_API_TOKEN`, a token scoped to Account / Workers Scripts / Edit, plus Zone / Workers Routes / Edit and Zone / Zone / Read for walldye.com, which `wrangler deploy` needs for the custom domain, and `CLOUDFLARE_ACCOUNT_ID`. Previews of branches in this repository need them too, so they are not limited to `main`.
- Environments `production`, which only `main` may deploy to, and `preview`. They record the deploys and hold no secrets.
- Every action in the workflows is pinned to a commit SHA, and Dependabot (`.github/dependabot.yml`) bumps them. Its security updates are off.
- For `views.yml`: the secret `CLOUDFLARE_ANALYTICS_TOKEN`, a token scoped to Account / Account Analytics / Read.

Cloudflare:
- walldye.com is registered with Cloudflare Registrar, and its zone is in the account.
- The Worker `walldye` serves `dist/` as static assets. Its script, `src/worker/`, runs first for `/e` (`run_worker_first`). It also runs, as a billed request, for a request that matches no file and is not a page navigation, such as a probe or a missing image, and hands it to the assets. The deploy job bundles it from a sparse checkout of the files it imports, so a new import into it needs a line in that checkout. `wrangler.jsonc` sets its routing: paths that match no file get `404.html` with status 404, and `/about/` and `/about.html` redirect to `/about`. `public/_headers` sets the cache headers and `public/_redirects` the renames.
- walldye.com is the Worker's custom domain, declared in `wrangler.jsonc`, so `wrangler deploy` keeps its DNS record and certificate. It serves whatever `main` last deployed. Production has no workers.dev URL. Previews and version URLs do, and they are sent with `X-Robots-Tag: noindex` (Cloudflare adds it to Previews, `public/_headers` to every workers.dev host), so only walldye.com gets indexed.
- www.walldye.com redirects to the apex through the Worker in `infra/www-redirect/`, on a Workers custom domain.
- Web Analytics is on for the walldye.com hostname with automatic setup: Cloudflare injects the beacon into the pages as it serves them, so the source has no snippet, and Previews are not measured. The beacon sets no cookies, so the site needs no consent banner.
- Product events (architecture.md, The site) go to the Analytics Engine dataset `walldye_events`, and from Previews to `walldye_events_preview`, both bound as `EVENTS` in `wrangler.jsonc`. A dataset is created on its first write and keeps rows for three months. The Analytics Engine SQL API reads them with a token that has Account / Account Analytics / Read, such as `CLOUDFLARE_ANALYTICS_TOKEN`; the row layout is `BLOBS` and `DOUBLES` in `src/lib/events.ts`, with the event name as `index1`. A version URL runs with production's bindings, so events sent from one land in `walldye_events`.
- Workers Logs is on for the Worker with invocation logs off (`observability` in `wrangler.jsonc`), since those would record each request's headers and location. What remains is the Worker's own output: one object per stored event, with the same fields as the row, and its errors. Workers & Pages > walldye > Observability queries them; the Query Builder can group by any field (`format`, `theme`, `country`) and count distinct `visitor`.
- The secret `EVENTS_KEY`, the key the daily visitor key is derived from, is set for production and in the Previews base configuration, each to a random value of its own (`openssl rand -hex 32`): `pnpm dlx wrangler@4.143.0 secret put EVENTS_KEY` and `pnpm dlx wrangler@4.143.0 preview base-config secret put EVENTS_KEY`, both from the repository root, each prompting for the value. The base configuration reaches only Previews created after it changes; an existing one takes `pnpm dlx wrangler@4.143.0 preview secret put EVENTS_KEY --name pr-<number>`. Without the secret, `/e` answers every request with 503 and logs an error, so the deploy's check of `/e` fails.
- Email Routing is on for walldye.com: takedown@walldye.com, the contact in the fan-work disclaimer, forwards to the owner's own address. The zone's MX records point at `route1`, `route2` and `route3.mx.cloudflare.net`.

## Check that it works

- walldye.com loads, recolors when the theme changes, and exports a PNG from a detail page.
- `curl -sI 'https://www.walldye.com/loose-squares?t=nord'` answers `301` with `location: https://walldye.com/loose-squares?t=nord`.
- `https://walldye.com/robots.txt` ends with `Sitemap: https://walldye.com/sitemap-index.xml`, and the sitemap it names lists every published piece.
- A template under `/t/` is served with `cache-control: public, max-age=31536000, immutable`, and a page with `max-age=0, must-revalidate`.
- `https://walldye.com/no-such-piece` answers `404` with the site's own Not found page.
- An export from a detail page on walldye.com shows up in Workers Logs (Workers & Pages > walldye > Observability) within a minute, as an object with `event: "export"`, a 16-digit `visitor` and the piece's `slug`.
- A page's HTML on walldye.com includes the Web Analytics beacon (`static.cloudflareinsights.com/beacon.min.js`), and the dashboard counts the visit.
- A pull request from a branch in this repository: once `build` and `e2e` pass, a comment links the Preview, later pushes edit the same comment, and closing the pull request deletes the Preview (Workers & Pages > walldye > Previews).
- After a `views.yml` run that finds a new day, `stats` has a commit named after it, a `ci.yml` run on `main` has deployed, and the index sort offers "popular" and "most viewed".
- A test mail to takedown@walldye.com arrives in the owner's inbox.

## Changing things

- The www Worker: edit `infra/www-redirect/`, then run `, wrangler deploy` in that directory.
- A renamed wallpaper: add `/<old-slug> /<new-slug> 301` to `public/_redirects`.
- The site Worker's settings: edit `wrangler.jsonc`. A Preview takes them from its pull request, except the custom domain, which changes only when `main` deploys, and the workers.dev settings, which come from whichever Preview or deploy creates the Worker and from `main`'s deploys after that.
- The API token: create a new one with the scopes above, store it with `gh secret set CLOUDFLARE_API_TOKEN`, then delete the old token in the dashboard. The analytics token the same way, scoped to Account / Account Analytics / Read, with `gh secret set CLOUDFLARE_ANALYTICS_TOKEN`.
- The Worker locally: put `EVENTS_KEY=dev` in `.dev.vars` (gitignored), then `pnpm build` and `pnpm dlx wrangler@4.143.0 dev`, which serves `dist/` with `/e` and prints each stored event.
- The events key: set a new value with the commands above. Visitor keys change with it, so that day's visitors count twice.
- A manual deploy of a local build, if CI is down: `pnpm build`, then `pnpm dlx wrangler@4.143.0 deploy` from the repository root, pinned to the version CI deploys with.
