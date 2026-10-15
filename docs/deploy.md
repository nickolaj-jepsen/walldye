# Deploy

How walldye.com is built, deployed and hosted, and how to check or change each part.

`,` in the commands below is comma, which runs a tool from nixpkgs without installing it; elsewhere, `pnpm dlx wrangler` does the same.

## CI

The workflows in `.github/workflows/` say in their `on:` blocks and comments when they run and why. `checks.yml` lints, type-checks and runs pytest on every change. `ci.yml` renders the published pieces from main's last build in the Actions cache, tests and builds the site, and deploys it from `main`; drafts are never drawn in CI. `views.yml` writes each finished day's page views to the `stats` branch, then starts `ci.yml` with `deploy` ticked, which also keeps the render cache warm. To redeploy `main` by hand: Actions > CI > Run workflow on `main` with `deploy` ticked.

To build locally with the views: `git fetch origin stats && git worktree add --detach stats FETCH_HEAD`; after a later fetch, `git -C stats checkout --detach origin/stats`.

## What is set up

GitHub:
- The public repository `nickolaj-jepsen/walldye`, the `origin` remote, with walldye.com as its website. The About page links to it, and every "Run it yourself" command clones it.
- A ruleset keeps `main` from being deleted or force-pushed. Secret scanning with push protection and Dependabot alerts are on.
- Runs from outside contributors wait for approval (Settings > Actions > General).
- Repository secrets: `CLOUDFLARE_API_TOKEN`, a token scoped to Account / Workers Scripts / Edit, plus Zone / Workers Routes / Edit and Zone / Zone / Read for walldye.com, which `wrangler deploy` needs for the custom domain, and `CLOUDFLARE_ACCOUNT_ID`.
- The environment `production`, which only `main` may deploy to. It records the deploys and holds no secrets.
- Every action in the workflows is pinned to a commit SHA, and Dependabot (`.github/dependabot.yml`) bumps them. Its security updates are off.
- For `views.yml`: the secret `CLOUDFLARE_ANALYTICS_TOKEN`, a token scoped to Account / Account Analytics / Read.

Cloudflare:
- walldye.com is registered with Cloudflare Registrar, and its zone is in the account.
- The Worker `walldye` serves `dist/` as static assets, with no Worker script, on its custom domain walldye.com, which serves whatever `main` last deployed. `wrangler.jsonc` holds its settings and routing, `public/_headers` the cache and noindex headers, and `public/_redirects` the renames.
- www.walldye.com redirects to the apex through the Worker in `infra/www-redirect/`, on a Workers custom domain.
- Web Analytics is on for the walldye.com hostname, with the JS snippet, which `src/layouts/Base.astro` loads. The beacon sets no cookies, so the site needs no consent banner.
- Email Routing is on for walldye.com: takedown@walldye.com, the contact in the fan-work disclaimer, forwards to the owner's own address. The zone's MX records point at `route1`, `route2` and `route3.mx.cloudflare.net`.

## Check that it works

- walldye.com loads, recolors when the theme changes, and exports a PNG from a detail page.
- `curl -sI 'https://www.walldye.com/loose-squares?t=nord'` answers `301` with `location: https://walldye.com/loose-squares?t=nord`.
- `https://walldye.com/robots.txt` ends with `Sitemap: https://walldye.com/sitemap-index.xml`, and the sitemap it names lists every published piece.
- A template under `/t/` and a page are each served with the `Cache-Control` that `public/_headers` sets for them.
- `https://walldye.com/no-such-piece` answers `404` with the site's own Not found page.
- A page's HTML on walldye.com includes the Web Analytics beacon (`static.cloudflareinsights.com/beacon.min.js`), and the dashboard counts the visit.
- After a `views.yml` run, `stats` has a commit named after the last new day, a `ci.yml` run on `main` has deployed, and the index sort offers "popular" and "most viewed".
- A test mail to takedown@walldye.com arrives in the owner's inbox.

## Changing things

- The www Worker: edit `infra/www-redirect/`, then run `, wrangler deploy` in that directory.
- A renamed wallpaper: add `/<old-slug> /<new-slug> 301` to `public/_redirects`.
- The site Worker's settings: edit `wrangler.jsonc`; they apply when `main` next deploys.
- The API token: create a new one with the scopes above, store it with `gh secret set CLOUDFLARE_API_TOKEN`, then delete the old token in the dashboard. The analytics token the same way, with `gh secret set CLOUDFLARE_ANALYTICS_TOKEN`.
- A manual deploy of a local build, if CI is down: `pnpm build`, then `pnpm dlx wrangler@<version> deploy` from the repository root, with the `wranglerVersion` that `ci.yml` pins.
