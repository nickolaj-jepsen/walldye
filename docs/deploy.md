# Deploy

How walldye.com is built, deployed and hosted, and how to check or change each part. design.md (Hosting and analytics) has the reasons behind the setup.

`,` in the commands below is comma, which runs a tool from nixpkgs without installing it; elsewhere, `pnpm dlx wrangler` does the same.

## CI

`.github/workflows/ci.yml` runs on pushes to `main`, on pull requests and on manual runs (Actions > CI > Run workflow). It never runs Python.

| Job | Does |
|---|---|
| `build` | Ruff's format check (the standalone binary), `pnpm check-artifacts`, `pnpm test`, `pnpm astro build`, uploads `dist/` as an artifact, then checks the links in the meta.yaml files the change touches |
| `e2e` | Playwright against that `dist/`: Chromium for pull requests; Chromium, Firefox and WebKit for `main` and manual runs |
| `deploy` | After `build` and `e2e` pass: a push to `main` goes to production, and a pull request from a branch in this repository goes to a preview at `https://<branch>.walldye.pages.dev`, linked from a comment on the PR that later pushes edit. Pull requests from forks never deploy, and manual runs build and test without deploying |

- A newer run cancels an older one on the same pull request or branch.
- Changes that touch only `docs/`, Markdown, `.claude/`, `infra/`, `LICENSES/` or `.lycheeignore` skip CI.
- The deploy job has no checkout. It runs `wrangler pages deploy dist --project-name=walldye --branch=<branch> --commit-hash=<sha>` through `cloudflare/wrangler-action`, so wrangler gets the commit explicitly.

`build` makes the one `dist/` that `e2e` tests and `deploy` uploads, so what ships is what was tested. Pull requests run the browser tests on Chromium alone to get an answer back quickly, and `main` runs all three engines before it deploys. This was set up for a private repository on the Free plan, where minutes are metered. Public repositories run Actions for free, so once this one is public, testing pull requests on all three engines is a one-line change to `ENGINES` in the `e2e` job.

## What is set up

GitHub:
- The repository `nickolaj-jepsen/walldye`, the `origin` remote. It stays private until going live (below).
- Fork pull requests: while the repository is private, their workflows do not run. Once it is public they always run, without the secrets and without deploying, and going live adds an approval step for outside contributors.
- Repository secrets: `CLOUDFLARE_API_TOKEN`, a token scoped to Account / Cloudflare Pages / Edit, and `CLOUDFLARE_ACCOUNT_ID`. They are repository secrets because private repositories on the Free plan have no deployment environments. Once the repository is public, they can move to an environment limited to `main`.

Cloudflare:
- walldye.com is registered with Cloudflare Registrar, and its zone is in the account.
- The Pages project `walldye`: Direct Upload, production branch `main`, created with `, wrangler pages project create walldye --production-branch main`.
- walldye.com is a custom domain of the Pages project, set in the dashboard (wrangler has no command for Pages domains). It serves whatever `main` last deployed. `public/_headers` sends `X-Robots-Tag: noindex` on walldye.pages.dev, and Pages adds the same header to every preview deployment, so only walldye.com gets indexed.
- www.walldye.com answers with a 301 to the apex, keeping path and query. It is the Worker in `infra/www-redirect/` on a Workers custom domain, which also owns the `www` DNS record and certificate. CI does not deploy it.
- Web Analytics is on for the Pages project. The beacon is injected into each deployment and sets no cookies, so the site needs no consent banner.
- Email Routing is on for walldye.com: takedown@walldye.com, the contact in the fan-work disclaimer, forwards to the owner's own address. The zone's MX records point at `route1`, `route2` and `route3.mx.cloudflare.net`.

## Going live

1. Land the work on `main`. The push deploys it to production; until then walldye.com has no deployment and answers 404.
2. Close the draft pull requests #1 and #2 if landing did not merge them, and delete the `m1` and `m2` branches. Both would become public with the repository.
3. Make the repository public: `gh repo edit nickolaj-jepsen/walldye --visibility public --accept-visibility-change-consequences`. The About page links to it, and every "Run it yourself" command clones it.
4. Make workflows from fork pull requests wait for approval: Settings > Actions > General > "Require approval for all external contributors", or `gh api -X PUT repos/nickolaj-jepsen/walldye/actions/permissions/fork-pr-contributor-approval -f approval_policy=all_external_contributors`. GitHub only offers this setting on public repositories.
5. Set the repository's website: `gh repo edit nickolaj-jepsen/walldye --homepage https://walldye.com`.
6. Run the checks below against walldye.com.

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
