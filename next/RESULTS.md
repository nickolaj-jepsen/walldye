# Results: walldye on Next.js 16.4

Measured on 2026-10-15 against PLAN.md's success criteria. Three builds of the same 194 published pieces (no drafts):

- astro: today's site, `pnpm astro build --outDir` into a scratch folder (the working tree was not touched).
- export: `pnpm build:export`, the static export in `out/`.
- open: `pnpm build`, the OpenNext Worker in `.open-next/`.

Each was served locally by wrangler 4.151.0 (`wrangler dev`, or `opennextjs-cloudflare preview` for open), on WSL2. Nothing was deployed. Browser numbers are Playwright 1.63's Chromium, headless. The heavy detail page is dither-sun: its templates are the largest in the catalog (621 KB, 169 KB gzipped) and it has a motif.

## Client code

Code lines exclude blanks and comments (tokei 14). "Browser graph" is every first-party file esbuild reaches from the code that runs in the browser: for astro the page scripts, inline boots and the export worker; for the PoC every `'use client'` module, the theme and index boots and the export worker. Tests and generated files are left out.

| | Files | Code lines |
|---|---:|---:|
| astro `src/client` + `src/lib` | 37 | 3491 |
| astro browser graph | 36 | 3437 |
| PoC browser graph | 69 | 4838 |
| astro whole `src` (TS and .astro, no CSS) | 67 | 4842 |
| PoC whole `src` (TS and TSX, no CSS) plus codegen, cards and worker.ts | 93 | 6248 |

Client code did not shrink. The browser graph grew 41%, partly because the PoC's TSX carries markup that astro kept in server-only `.astro` files (654 lines in all of them). Counting every `.astro` line on astro's side still leaves 4091 against 4838.

By concern, browser graph only:

| Concern | astro | PoC |
|---|---:|---:|
| Plate rendering | 676 | 356 (248 without the catalog types) |
| Index and grids | 291 | 721 |
| Detail page and source view | 676 | 1115 |
| Export | 248 | 821 (418 of it is the tokenizer and bake, now loaded only on export) |
| Theme and picker | 667 | 946 |
| Shared pure lib, copied unchanged | 879 | 879 |

### What disappeared from the browser, and why

All of it went with the per-theme recolor. A plate is now `<svg><use href="/t/<hash>.svg#…-base"/></svg>`, and the template's colors read seed custom properties, so a theme change is a style change on `:root`.

- `queue.ts` (52 lines): the viewport-ordered queue that capped plates at 6 fetches and 6 recolors at a time. No plate does any work per theme, so nothing needs scheduling.
- The template LRU in `plates.ts` (8 MiB budget, eviction by bytes) and the slots.json cache. The HTTP cache holds the files. `template-text.ts` keeps text only for the templates with `<defs>`, which are inlined (305 of 1299 files).
- The blob: URL lifecycle: `createObjectURL`/`revokeObjectURL`, generation counters per plate, decode-then-swap with a timed fade, and `keyedShow`. Nothing is rendered to an image.
- `prepareTemplate`/`recolor` and the tokenizer at page load. Codegen (`template-vars.ts`) does the rewrite once at build, and the tokenizer is now in the lazily loaded export chunk.
- Live motif layers (`client/detail/motif.ts`, 136 lines): cutting the picture into "ground" and "motif alone" blob images when a drag starts, and redrawing on release. Codegen splits every template into `#base` and `#motif` parts, and a drag is a CSS transform on the motif's `<g>`.
- The 463-line imperative `detail/page.ts` controller. It became React components over `detail-context.tsx`.

### What is new

- `template-vars.ts` (242 lines): the var-template rewrite at codegen, and `bake()` to turn it back into hex for export and the social cards.
- The inline/external split. External `<use>` does not inherit custom properties into `<defs>` in any engine, and WebKit drops masks and clip paths there. So a template with `<defs>` is fetched and inlined into the plate (`PlateLayers`, `template-text.ts`), and the plate also needs a fetch beside every external `<use>` to see a failed load, since `<use>` has no load event.
- `detail-context.tsx` (229 lines): each part that reads the address renders twice, as the prerendered Suspense fallback and again from nuqs. That is what static prerender plus URL state costs in React.
- `IntentLink.tsx`, `worker.ts` and an OpenNext patch: prefetch policy for Partial Prefetching, and two OpenNext 1.20.11 gaps (below).

## Performance

### JavaScript and HTML per page

Gzip level 6 over each response body, everything a fresh load fetches until the network is idle.

| Page | astro JS | export JS | open JS | astro HTML | export HTML | open HTML |
|---|---:|---:|---:|---:|---:|---:|
| index | 16.9 KB, 5 files | 165.1 KB, 9 files | 177.9 KB, 11 files | 58.1 KB | 109.8 KB | 110.0 KB |
| dither-sun | 22.3 KB, 5 files | 177.8 KB, 11 files | 177.9 KB, 11 files | 15.5 KB | 23.1 KB | 23.3 KB |
| about | 7.3 KB | | 165.3 KB | 7.1 KB | 10.1 KB | 10.1 KB |

About 132 KB of the PoC's JS is the framework (React DOM with the RSC client 72 KB, the Next router 46 KB, Next's bootstrap and the Turbopack runtime 14 KB); the app code and nuqs are about 46 KB. OpenNext's index also loads the detail route's chunks for the App Shell prefetch. The HTML roughly doubles because the RSC payload is inlined beside the markup: 340 KB of inline script on the index (astro: 10 KB), and the detail page's Shiki listing appears twice. The largest page, nautical-chart, is 1.15 MB raw against 523 KB.

Lighthouse's total byte weight on mobile: index 514 KB (astro) against 1032 KB and 985 KB; dither-sun 1.31 MB against 1.73 MB and 1.72 MB.

### Time to the finished plate

From a CDP screencast: the time from navigation start until a plate's area matches its final picture (mean channel difference under 2 of 255). Medians of 7 runs unthrottled and 3 throttled. Viewport 1440×900 (a 16:10 screen) unless marked.

| | astro | export | open |
|---|---:|---:|---:|
| Unthrottled: first contentful paint, index | 88 ms | 92 ms | 100 ms |
| Unthrottled: first plate done, index | at first paint | at first paint | at first paint |
| Unthrottled: all 9 visible plates done, index | 320 ms | 325 ms | 337 ms |
| Unthrottled: dither-sun plate done | 283 ms | 254 ms | 261 ms |
| Throttled: all visible plates done, index | 2.82 s | 4.15 s | 4.32 s |
| Throttled: first grid plate (dither-moon) done | 2.56 s | 3.57 s | 3.54 s |
| Throttled: dither-sun plate done, 16:10 screen | 4.21 s | 5.98 s | 5.95 s |
| Throttled: dither-sun plate done, 1600×900 (16:9) | 4.20 s | 3.25 s | 3.39 s |

Throttled is 4× CPU, 1.6 Mbps down, 150 ms RTT. Unthrottled the three are at parity. Throttled, the PoC draws a 16:9 plate sooner, because an external `<use>` draws without JavaScript, slots.json or a recolor. It loses on the index and on any screen that isn't 16:9, for three reasons:

- dither-moon, the first grid plate, is one of the two pieces with a separate light file, which the PoC draws only after hydration, behind about 165 KB of JS.
- The prerendered detail page is 16:9. Astro's pre-paint shape boot was not ported, so on a 16:10 screen the 169 KB 16:9 template downloads first and the 16:10 one after hydration.
- Link prefetches compete for bandwidth during load: the export fetched the index's 72 KB RSC payload from a detail page.

### Lighthouse 13, performance category

Median of 3 runs, simulated throttling. LCP is not comparable: astro's LCP element is the plate `<img>`, while an SVG `<use>` is no LCP candidate, so the PoC's LCP is text.

| | astro | export | open |
|---|---:|---:|---:|
| Mobile index: score, TBT | 85, 14 ms | 76, 458 ms | 87, 363 ms |
| Mobile dither-sun: score, TBT, CLS | 75, 8 ms, 0.041 | 83, 129 ms, 0.176 | 88, 148 ms, 0.176 |
| Desktop index: score | 98 | 99 | 99 |
| Desktop dither-sun: score | 93 | 100 | 100 |
| Mobile script bootup, index | 0.30 s | 1.21 s | 1.30 s |

The export and open runs ship the same client code, so their mobile index gap (76 against 87) is run variance in the simulated throttle (open's runs scored 81, 87 and 87). The PoC's CLS of 0.176 on mobile dither-sun is the spread changing to the phone shape after hydration, the same missing shape boot.

### Theme change on the index

Click the fourth Colors row button, then time until the viewport stops changing (screencast; includes about 40 ms of Playwright's click).

| | astro | export | open |
|---|---:|---:|---:|
| 1× CPU | 286 ms, 45 requests | 88 ms, 0 requests | 95 ms, 0 requests |
| 4× CPU | 637 ms, 45 requests, 294 ms of long frames | 202 ms, 0 requests, 83 ms | 243 ms, 0 requests, 91 ms |

### Motif drag on dither-sun

A circle of moves every 16 ms for 3 s on the handle, at 1600×900. Frame rate from requestAnimationFrame, long frames from the Long Animation Frames API, medians of 3.

| CPU | astro | export | open |
|---|---|---|---|
| 1× | 59.7 fps, no long frames | 59.7 fps, none | 59.7 fps, none |
| 4× | 59.1 fps; 68 ms frame at drag start, 75 ms after release | 59.5 fps, none | 59.5 fps, none |
| 6× | 58.0 fps; 106 ms at start, 114 ms after release | 59.6 fps, none | 59.8 fps, none |

Both keep up while dragging. Astro pays for cutting the live layers when the drag starts and for the recolored redraw on release; the PoC only commits a transform.

## Cost on Cloudflare

### OpenNext Worker bundle

`wrangler deploy --dry-run --outdir`: 6560 KiB raw, 1286 KiB gzipped, 42% of the 3 MiB free limit. Shares, from the server bundle's esbuild metafile and gzip of each part on its own:

| Part | Raw | Gzipped |
|---|---:|---:|
| Next's app-page runtime (vendored React server and RSC renderer) | 689 KiB | 203 KiB |
| react-dom/server (edge) | 286 KiB | 52 KiB |
| The catalog JSON | 411 KiB | 100 KiB |
| Shiki (core, JS regex engine, Python grammar) | 252 KiB | 67 KiB |
| Next's pages-router runtime and vendored jsonwebtoken | 242 KiB | 76 KiB |
| Social cards (`next/og`) | 0 | 0 |

The cards are PNGs that `scripts/cards.ts` writes at build, so `next/og` and its wasm stay out of the Worker. Shiki and the catalog are bundled though no request runs them: every page is prerendered. The catalog grows about 0.5 KiB gzipped per piece.

### CPU per request

workerd's user plus system CPU time from /proc over 150 to 300 warm requests, divided by the count. The local baseline of serving any static asset is 3.3 to 3.6 ms on all three targets (wrangler's proxy and asset worker), so the Worker's own cost is the difference.

| Request (open) | CPU per request | Above the static baseline |
|---|---:|---:|
| `/` (1.55 MB cache entry) | 14.3 ms | about 11 ms |
| `/dither-sun` | 7.4 ms | about 4 ms |
| `/about` | 6.3 ms | about 3 ms |
| `/nautical-chart` (2.83 MB cache entry) | 22.9 ms | about 19 ms |
| `/racing-mulsanne-night` | 19.2 ms | about 16 ms |
| Unknown one-segment path (worker.ts answers) | 4.4 ms | about 1 ms |
| RSC request for `/` | 13.6 ms | about 10 ms |
| RSC prefetch of a piece | 8.5 to 9.0 ms | about 5 ms |

The cost follows the size of the prerendered cache entry the Worker reads and parses from static assets. The free plan allows 10 ms of CPU per invocation; on this machine the index and the largest detail pages exceed it. Production CPU may differ, but nothing here suggests it will be lower by half.

Workers invoked per visit, on open: 9 for loading the index (the document, the index and about payloads, and App Shell prefetches for the entries in view), 5 for loading a detail page, 10 for index, open a piece, back. Astro and the export invoke none; static asset requests are free and unmetered. The free plan's 100,000 requests a day is therefore about 10,000 to 20,000 page views on open.

### Static assets

| | Files | Largest file | Total |
|---|---:|---|---:|
| astro | 1952 | 2.48 MB, resvg wasm | 150 MB |
| export | 2709 (198 HTML, 986 RSC .txt, 1299 templates, 194 cards) | 2.48 MB, resvg wasm; largest page 1.15 MB | 252 MB |
| open | 1528 plus 199 prerender cache entries, 1727 | 2.83 MB, the nautical-chart cache entry | 261 MB |

All well under 20,000 files and 25 MiB per file. Templates: 1299 var templates against astro's 1543 files (templates plus slots.json), since 1267 templates now serve both regimes.

## Verdict

### Clearer

- The plate. Rendering is 248 lines of components and hooks against 676 lines of queues, caches, blob lifetimes and recolors, and its behavior reads from the markup: an `<svg>` with a `<use>`. The motif is a `<g>` with a transform.
- Theme changes settle about 3× sooner, make no requests and need no code beyond setting variables. Motif drags have no long frames at either end.
- Data flow. Codegen produces one catalog, server components read it through `'use cache'`, and props carry everything a client island needs. Switching version, shape or theme never touches the server.

### Worse

- 8 to 10× the JavaScript on the index and detail pages and 23× on about (165 to 178 KB gzipped on every page, about 132 KB of it framework) and twice the HTML from the inlined RSC payload. Mobile TBT goes from under 15 ms to 130 to 460 ms.
- Total client code grew 41%. The recolor savings went into React state plumbing: double-rendered Suspense parts for address state, a template-file store, intent prefetching.
- Throttled loads on the index and on non-16:9 screens are 1 to 1.8 s slower, and mobile detail CLS is 0.176. Both follow from the missing pre-paint boots (detail shape) and the hydration gate on split-regime pieces, and both are fixable, at the cost of reintroducing inline boot scripts.
- Without JavaScript, lazy grid plates, inlined templates and the two split-regime pieces stay empty. Astro's `<img>` plates draw without it.
- The plate is invisible to LCP, so field data would not show how fast pictures arrive.

### Open risks

- External `<use>` is uneven across engines: paint servers in `<defs>` resolve in the external document everywhere (43 of 194 16:9 plates must be inlined), WebKit also drops masks and clip paths there, and a hidden external `<use>` is still fetched. Any new design that adds a gradient or mask silently moves to the inlined path. There is no load event, so failures are detected by a separate fetch.
- OpenNext 1.20.11 needed a patch to start at all (Next 16.4's `preview-props.json`), a Worker wrapper to answer unknown slugs (it streams a postponed render without its shell), and a per-target prefetch rule, because Partial Prefetching's shared App Shell breaks the view-transition pairing. Each Next or OpenNext upgrade can move these.
- Next 16.4 refuses `output: 'export'` with Cache Components, so the export runs without PPR (`experimental.useCache` only) and the two targets do not render the same way.
- The OpenNext Worker's CPU on large pages exceeds the free plan's 10 ms locally, and every view costs 5 to 10 metered invocations.
- Back and forward navigation runs no view transition.

### Recommendation

Keep Astro in production, and bring the recolor model over to it. The gain this PoC shows comes from the var templates, the `#base`/`#motif` split and the theme as CSS variables, none of which needs React. An Astro plate can be the same `<svg><use>` with the same codegen, which removes the queue, the LRU, the blob lifecycle, the live layers and most of `plates.ts`, without adding 130 KB of framework or a metered Worker. If the site moves to Next anyway, ship the static export: every route is static, so OpenNext adds request costs, CPU risk and three workarounds without adding a feature.
