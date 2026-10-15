# Contracts for the feature agents

The foundation of the Next.js port: what exists, what each module promises, and which files each feature owns. PLAN.md holds the settled decisions; this file records how they were built and where the spike forced a change.

## Commands

Run everything inside `next/` with pnpm. pnpm runs `pre*` scripts, so codegen runs before every dev and build.

| Command | What it does |
|---|---|
| `pnpm codegen` | scripts/codegen.ts: templates, catalog, boot, favicon. Incremental, about 0.4 s when nothing changed, 8 s from scratch. |
| `pnpm dev` | Codegen with drafts, then `next dev`. Pick a port with `PORT=…` when another agent may be running one. |
| `pnpm build` | Codegen, then `opennextjs-cloudflare build` (it runs `next build` itself, see open-next.config.ts). |
| `pnpm build:export` | Codegen, then `NEXT_OUTPUT=export next build` into `out/`. |
| `pnpm preview` / `pnpm preview:export` | wrangler dev on `.open-next/` or `out/` (workerd runs on this machine). |
| `pnpm lint` / `pnpm typecheck` | Biome (site.css is excluded, module CSS is linted), `next typegen && tsc`. |
| `scripts/with-browsers.sh <cmd>` | Runs `<cmd>` with Playwright 1.63's browsers from the repo flake and Mesa EGL for WebKit. Unsets a profile `LD_LIBRARY_PATH` that breaks Chromium. |
| `scripts/with-browsers.sh pnpm exec tsx scripts/check/render.ts <url>` | Smoke test of a running server in Chromium, Firefox and WebKit: plates drawn, `?t=` taken, a live theme change with no fetch, console errors. |
| `scripts/with-browsers.sh pnpm exec tsx scripts/check/smoke.ts <url>` | End-to-end check of a running server in the three engines: index filters, theme, detail, motif (mouse and pinch), export, view transitions, 404, card. Exits non-zero on a failure. |
| `pnpm spike`, `pnpm spike:bulk` | The external `<use>` spike and the all-pieces check (below). Wrap them in with-browsers.sh. |

`next build` and `next dev` must not run at the same time in this folder; neither may two builds.

## Recolor model (what the spike changed)

The spike ran every piece's 16:9 template through Chromium, Firefox and WebKit and compared it to recolor() shown as an `<img>`:

- External `<use href="/t/x.svg#…">` inherits the page's custom properties for ordinary shapes in all three engines (151 of 194 pieces pixel-identical).
- It does not for anything in `<defs>`. Paint servers (gradients, patterns) are resolved in the external document, where the seed variables don't exist, in all three engines; WebKit also drops masks and clip paths there. So a template with `<defs>` (305 of 1299 files, 43 of the 194 16:9 plates) is fetched and inlined into the plate's own `<defs>`, and the plate uses a same-document `<use href="#…">`. That passes everywhere.
- A `display:none` external `<use>`, or one in a hidden `<svg>`, is fetched anyway, and every external `<use>` on a page is fetched at load in all engines (60 of 60 offscreen). Grid plates therefore set their `href` only once near the view (`lazy`).
- The two regimes share a build file in all but two pieces (1267 of the 1299 var templates serve both), so one var template serves both: each color reads `--dk`/`--lt` (1/0) to pick the dark or light coefficient row. Only dither-moon and obra-still-life have separate light files; their plates draw only the applied regime's file, and only after hydration.
- Live theme change: setting the `:root` variables repaints within a frame or two, with zero requests.

## Generated files

All gitignored, written by `pnpm codegen` from `../wallpapers`:

- `public/t/<hash>.svg`: var templates. `<hash>` is the first 12 hex digits of sha256 over TEMPLATE_FORMAT, the build file's sha256 and the coefficient rows of each regime it serves. Served immutable (`public/_headers`).
- `src/generated/catalog.json`: the `Catalog` (src/lib/catalog.ts), about 420 KB. Server code only, through src/server/catalog.ts.
- `src/generated/rows.json`: `BakeRows` by hash, for export and social cards (about 700 KB). `getRows(hashes)` reads it from disk, so only during `next build`.
- `src/generated/scripts/<slug>.py`: each design.py, read from disk by `getScript(slug)`, also only during `next build`.
- `src/generated/known-paths.json`: `about` and every slug, the one-segment paths `worker.ts` passes to Next.
- `public/sitemap.xml`, `public/robots.txt`: for `SITE_URL` (default https://walldye.com).
- `src/generated/boot.ts`: `THEME_BOOT`, the minified theme boot for the layout.
- `public/favicon.svg`: the static icon.

Drafts are included with `pnpm dev` or `WALLDYE_DRAFTS=1`; `catalog.drafts` says which.

### Var template format (src/lib/template-vars.ts)

```
<svg viewBox="0 0 W H" width height>
<g id="t<hash>-base" style="--c0:rgb(…);--c1:rgb(…)">  everything but the motif; <defs> lives here
</g>
<g data-motif="" transform="translate(x y)">          only when the piece has a motif
<g id="t<hash>-motif" style="--c0:…">…</g>            motif-local units, its own `-m` copy of defs it uses
</g>
</svg>
```

Every id is namespaced `t<hash>-`, so inlined templates can share a page. `--c<k>` is `rgb(calc(var(--dk,1)*(dark row) + var(--lt,0)*(light row)) …)` over `var(--bg-r,28)` and friends; the fallbacks make the file render on its own in the colors it was drawn in. Slots become `style="fill:var(--c<k>)"`; constant (mask) rows stay literal hex.

## CSS variables

Set inline on `<html>` by the boot and by `applyTheme()`; site.css repeats the fireproof and flexoki-light values for visitors without JavaScript.

| Variables | Meaning |
|---|---|
| `--bg-r --bg-g --bg-b --fg-r … --ac-b` | Seed channels, 0 to 255 (`seedVars()` in src/lib/seed-vars.ts). Plates read only these. |
| `--dk`, `--lt` | 1/0 in the dark regime, 0/1 in the light one. |
| `--seed-bg --seed-fg --seed-accent`, `--bg`, `--text`, `--link`, `--rule`, `--shiki-*` … | The site roles of `cssVars()`, unchanged from the Astro site (docs/site.md §2). |
| `<html data-regime="dark|light" data-theme="<token>">` | Regime and canonical token. |

## Modules

### Pure (`src/lib/`, any side may import)

Copied from the Astro site, unchanged unless noted: theme.ts, presets.ts, tokenize.ts, recolor.ts, motif.ts, shape.ts, labels.ts, typeset.ts, favicon.ts, import-theme.ts, content.ts (its `Piece` is now the catalog's; `sortPieces` still expects Astro's `{ data }` entries, so sort with `comparePieces`).

New:

- `catalog.ts`: `Catalog`, `Piece`, `Version`, `Plates` (always has `'16:9'`), `PlateRef { dark, light }` (hashes, equal when shared), `TemplateInfo { inline, canvas, motif? }`, `ResolvedTemplate`, `PlateData { dark, light }`, `Source`, `Taxonomy`; helpers `defaultVersion`, `allVersions`, `versionOf(p, name)`, `partId(hash, part)`, `templateUrl(hash)`, `sharedPlate`. `Piece.versions` keeps Astro's meaning: `[]` without named variants, so use `allVersions()`.
- `seed-vars.ts`: `SEED_VARS`, `REGIME_VARS`, `seedVars(seeds)`. Small, safe for the boot.
- `template-vars.ts`: `toVarTemplate()` (codegen), `bake(svg, rows, seeds, place?)` (export: var template text to a standalone SVG with the hex recolor() writes, motif placed), `rowHex`, `BakeRows`, `TEMPLATE_FORMAT`. It pulls in the tokenizer, so keep it out of anything but export and codegen; the same goes for recolor.ts and tokenize.ts.

### Server (`src/server/catalog.ts`, `server-only`)

`'use cache'` with `cacheLife('catalog')` (next.config.ts: never revalidates):

- `getPieces()`, `getPiece(slug)`, `getSlugs()`, `getRows(hashes)`, `getScript(slug)`.
- `resolvePlate(ref): PlateData` (sync), `facetLabel(facet, value)`, `modelName(model)`, `hasDrafts()`.

No `fs` at request time anywhere: the OpenNext Worker has none.

### Theme (`src/client/theme/`)

- `store.ts`: the Astro store, ported. `applyTheme(seeds)` now also sets `seedVars()`. `saveTheme`, `savePair`, `clearShared`, `sharedTheme`, `ownChoice`, `ownTheme`, `resolveTheme`, `sharedDiffers`, `THEME_EVENT`, `STORAGE_KEY`.
- `boot.ts`: bundled into `THEME_BOOT`; the root layout inlines it first in `<head>`.
- `use-theme.ts`: `useTheme(): { token, seeds, regime } | null`, `useThemeToken()`, `useRegime()`, all null during server rendering and hydration; `chooseTheme(seeds)` saves and applies.

### Plate (`src/components/plate/`)

`<Plate>` has no hooks or server-only imports, so server and client components can both render it:

```ts
interface PlateProps {
  slug: string;              // data-plate
  data: PlateData;           // resolvePlate(version.plates[aspect] ?? version.plates['16:9'])
  alt: string;               // aria-label of the <svg role="img">
  view?: Box;                // viewBox: the crop (cropBox(aspect, t)) of 16:9, else the whole canvas
  placement?: Placement | null;  // motif; absent = where the design drew it
  lazy?: boolean;            // grids: href only once within a viewport of the view
  className?: string; style?: CSSProperties;   // e.g. --ratio
  motifRef?: Ref<SVGGElement>;  // wrapper <g data-motif-layer>; move it with a CSS transform while dragging (client parent only)
  motifStyle?: CSSProperties;
  transitionName?: string;   // wraps the plate in React <ViewTransition name>
  children?: ReactNode;      // overlays after the picture: crop window, motif frame
}
```

Markup: `<div class="plate" data-plate><svg class="pic" viewBox role="img" aria-label><g>[<defs>inlined template</defs>]<use href=base/>[<g data-motif-layer><g transform="translate scale"><use href=motif/></g></g>]</g></svg>{children}</div>`. site.css sizes `.plate` from `--ratio` and lays `.pic` over the spacer. A viewBox of another ratio than `--ratio` centers the picture (a native shape inside a 16:9 spread).

`PlateLayers` is the client leaf. `useTemplateFile(hash, inline)` (template-text.ts) fetches every template file once per page through `retrying()` (src/client/retry.ts: 1, 3, 10 and 30 s, then on `online`), keeping the text of inlined ones; a lazy external plate sets its `<use>` once that fetch has warmed the HTTP cache, an eager one at once (the fetch beside it is a cache hit), and after a failed try the `<use>` reads `?r=<try>` so no engine reuses the failure. `useNear(ref, lazy)` is the IntersectionObserver; it observes the plate's grid row, because a row that `content-visibility` skips lays out nothing inside it.

Not drawn before hydration: lazy plates, inlined templates (after their fetch), and the two separate-light-file pieces. Without JavaScript those stay empty plate ground.

### Other components

- `components/grid/GridPlate.tsx`: one index entry (port of Plate.astro) with the `data-*` the filter reads; `eager` for the first rows.
- `components/Attribution.tsx`, `components/Chips.tsx`: ports.
- `components/masthead/Masthead.tsx` + `NavLink.tsx` (client, `usePathname` for `aria-current`).
- `components/picker/ThemeTools.tsx`, `components/picker/Picker.tsx`: placeholders the layout already renders.
- `app/layout.tsx`: fonts (`app/fonts.ts`, next/font/local as `--serif` and `--mono`), `<link id="favicon">`, the boot script, `NuqsAdapter`, masthead, `{children}`, `<Picker/>`. Pages render their own `<main id="main" className=…>`.
- `app/page.tsx` (stub index), `app/[slug]/page.tsx` (stub detail: params read inside `<Suspense>`, body cached), `app/about/page.tsx`, `app/not-found.tsx`.
- `src/client/screen.ts`: ported (`deviceAspect`, `markShape`, media queries).

## Rules that bite

- Cache Components forbids the segment configs `dynamic`, `dynamicParams` and `revalidate`. Reject unknown params with `notFound()`.
- Next 16.4 refuses `output: 'export'` together with Cache Components, so the export build turns `cacheComponents` off and keeps `use cache` through `experimental.useCache` (next.config.ts). Code must work in both: everything fully static, no `connection()`, no `instant` exports, no route handlers that need `dynamic = 'force-static'`. There are no route handlers: codegen writes the sitemap and robots.txt, and scripts/cards.ts the social cards, which keeps the app-route runtime out of the Worker.
- Read `params` inside `<Suspense>` (as app/[slug]/page.tsx does) or dev reports an instant-navigation error. Every nuqs or `useSearchParams` reader sits under `<Suspense>`.
- Unknown slugs: the export serves `404.html`. OpenNext 1.20 answers a `[slug]` param outside generateStaticParams with only the part streamed after the fallback shell, so `worker.ts` (the Worker's entry, wrapping `.open-next/worker.js`) serves the prerendered not-found page, which `pnpm build` copies to `.open-next/assets/404.html`, with a 404. It does so before Next runs for a one-segment path outside `known-paths.json` (static assets never reach the Worker), and for any page response marked `x-nextjs-postponed: 1`.
- Partial Prefetching shares one App Shell between all links to `/[slug]`, so a page's own content would arrive after the navigation's first commit and the plate could not morph. Grid links (`components/grid/IntentLink.tsx`) therefore prefetch the page on intent (pointer enter, focus, touch start): `prefetch={true}` on the OpenNext build (`WALLDYE_LINK_PREFETCH`, next.config.ts) and the default on the export, whose server-less `?_rsc` URLs would answer `prefetch={true}` with HTML. Before intent OpenNext loads only the shared App Shell and the export nothing. A full scroll of the index makes 9 Worker requests on OpenNext (it made about 200 with a per-link prefetch in view). The morph pairs once the link has rendered with its prefetch: on OpenNext from the first render after intent, on the export after about 300 ms of hover, so a click the instant the pointer arrives navigates without it.
- OpenNext 1.20.11 did not inline Next 16.4's `preview-props.json`, so any request reaching the Worker's Next server crashed. `patches/@opennextjs__cloudflare@1.20.11.patch` adds it to the inlined manifests.
- The Worker is about 1.26 MiB gzipped (1286 KiB, `wrangler deploy --dry-run`) of the 3 MiB free limit, with the catalog in it; rows and scripts stay on disk at build. Prerendered pages are served from Workers static assets (`staticAssetsIncrementalCache`, `enableCacheInterception`); no R2 or KV.
- `next/og` cannot draw a `<use>`: a social card bakes the template with `bake()` from `public/t/<hash>.svg` and `rows.json` at build time.
- Every component file follows AGENTS.md's comment and copy rules; site styling stays inside docs/site.md. site.css is ported whole, so most classes already exist; new component styles go in a co-located `.module.css`.

## Ownership hints

Shared foundation, edit only with a reason and keep the contracts above: `src/lib/*`, `src/server/catalog.ts`, `src/client/theme/*` (add files freely), `src/components/plate/*`, `app/layout.tsx`, `src/styles/site.css`, `scripts/codegen.ts`, `next.config.ts`, `package.json`.

| Feature | Owns |
|---|---|
| Index: filters, search, sort, shape, color row | `app/page.tsx`, `components/grid/*`, new `components/index/*` |
| Detail: versions, shapes, crop, motif move, resize and pinch, see also, label, footnotes, notes, source code | `app/[slug]/page.tsx`, new `components/detail/*` |
| Theme picker: presets, families, custom editor, import, copy link, shared line | `components/picker/*`, new hooks in `src/client/theme/` |
| Export: SVG, PNG, WebP, JPEG (bake, then resvg-wasm in a worker) | new `components/export/*`, `src/client/export/*` |
| Site extras: social cards, sitemap, robots, view transitions, about, 404 | `scripts/cards.ts`, the sitemap and robots in `scripts/codegen.ts`, `app/about/*`, `app/not-found.tsx`; view transitions through `Plate`'s `transitionName` (agree on names with the index and detail owners: the Astro site names only the carried plate, or the whole index flies into See also) |

## Detail state (`components/detail/detail-context.tsx`)

`<DetailLocal>` wraps the page and holds what the address does not (size, format, the download runner and busy flag, the drag preview). Each part that reads the address is a `<DetailPart piece>`, rendered twice: inside `<DetailDefaults>` as the Suspense fallback the prerender keeps (default version, 16:9), and inside `<DetailFromAddress>`, which reads `?v ?shape ?crop ?at ?size` through nuqs once the browser renders it. A bailed-out boundary is drawn again in full rather than hydrated, so the parts stay small: the spread, the label's Download and description, the controls, See also and the run command. The rest of the label, the notes, the sources and the listing are prerendered once and hydrated. Client components inside a part read `useDetail()`:

- Read: `piece`, `version`, `state` (`variant aspect crop at scale`), `native`, `source` (the template shape read), `data` (its `PlateData`), `motif`, `placement` (clamped, or null), `shape` (`ExportShape`: crop position defaults to the focus), `narrow`, `inPlace`, `screenPx`, `screenAspect`, `token`, `size`, `format`, `allowed(size)`.
- Write: `chooseVersion`, `chooseAspect` (the size follows, the motif anchor resets, a crop is kept along the same axis), `chooseSize` ("your screen" switches to the screen's shape), `chooseFormat`, `setCrop`, `setMotif({ at?, scale? })`.
- `download`: `{ busy, setBusy, run }`. The Export panel puts its runner in `run.current`; the Download under the label calls it.

`useMotifPreview()` holds the placement a drag shows before release; only the plate and the motif rows read it. The Export panel (`components/export/ExportPanel.tsx`) mounts in `components/detail/ExportSection.tsx` with `{ slug, version, shape, crop, placement }` and reads the rest from `useDetail()`; the page wraps everything in the export's `<ExportRows piece>`. `DownloadSummary`, `summaryOf()` and `fileNameOf()` (`components/detail/DownloadSummary.tsx`) serve both Download buttons.

The detail plate's view transition name is `plate-<slug>`, and so is each index grid plate's; See also plates have none. `Plate` gives a named plate `share="plate" default="none"`, so only a pair animates (site.css styles the `.plate` class). Grid entries drop `content-visibility` during a transition, or the arriving entry is skipped in the snapshot and never pairs. A history back or forward runs no transition.
