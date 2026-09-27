# Deploy setup

`.github/workflows/ci.yml` builds and tests every push to `main` and every pull request, then deploys: `main` to production, and each pull request from a branch in this repo to a preview at `https://<branch>.walldye.pages.dev`, linked from a comment on the PR. Pull requests from forks get the checks but never a deploy. CI runs only Node, never Python.

The repo is private on GitHub's Free plan, which shapes CI: minutes are metered and each job is billed in whole minutes, so there are three jobs (build, e2e, deploy), pull requests run the browser tests in Chromium only, `main` and manual runs use Chromium, Firefox and WebKit, and changes that only touch `docs/`, Markdown, `.claude/`, `infra/`, `LICENSES/` or `.lycheeignore` skip CI. Free private repos have no deployment environments or branch protection, so the Cloudflare secrets are repository secrets.

## Done

- walldye.com is registered with Cloudflare and its zone is in the account.
- The Pages project `walldye` exists (Direct Upload, production branch `main`): `, wrangler pages project create walldye --production-branch main`.
- The private repo `nickolaj-jepsen/walldye` exists and is the `origin` remote.
- The repository secret `CLOUDFLARE_ACCOUNT_ID` is set.
- www.walldye.com redirects to the apex with a 301, keeping path and query. It is a small Worker in `infra/www-redirect/` on a Workers custom domain, which also owns the `www` DNS record and certificate. Redeploy it by hand after editing: `cd infra/www-redirect && , wrangler deploy`.
- walldye.com is attached to the Pages project (set in the dashboard; wrangler has no command for Pages domains). It serves whatever `main` last deployed.
- Web Analytics is enabled on the project. The beacon is injected into each deployment and sets no cookies, so the site needs no consent banner.

## To do

- Add the repository secret `CLOUDFLARE_API_TOKEN` (Account / Cloudflare Pages / Edit). It was missing on 2026-09-27, so the `deploy` job cannot authenticate until it is set.

## Check that it works

- Push to `main`: the `deploy` job publishes to walldye.pages.dev and walldye.com.
- Open a PR from a branch in this repo: when `build` and `e2e` pass, a comment links the preview, and later pushes edit the same comment.
- Actions > Links (weekly) > Run workflow: broken links end up in an issue titled "Broken links in wallpaper sources", which the next clean run closes.

## Link checks

The `build` job checks the URLs in every `wallpapers/*/meta.yaml` a change touches. A broken one fails a PR; on `main` it is reported without holding back the deploy. `links-weekly.yml` checks every piece on Mondays and never blocks anything. The same check locally:

```sh
nix run nixpkgs#lychee -- --max-retries 3 --accept 200..=299,403,429 'wallpapers/*/meta.yaml'
```

`.lycheeignore` says when an exception is worth adding.
