# DOM contract for the client modules

What the server-rendered pages give the client code in `src/scripts/*.ts`. The pages render fireproof, the default sort, no filters, 16:9 and the default export choices, so the client only changes what the visitor changed. Behaviour is specified in `docs/design.md` and `docs/site.md`; this file lists the hooks. Selectors marked "id" are unique per page.

## Script hooks

Each page loads its module with a processed `<script>`; Astro bundles and deduplicates them, so the one in `Base.astro` runs once on every page.

| File | Loaded by | Does |
|---|---|---|
| `src/scripts/site.ts` | `src/layouts/Base.astro`, after `<Picker />` | Theme button, shared-theme line, picker, "Copy link", the detail colour list |
| `src/scripts/index.ts` | `src/pages/index.astro` | Filters, results line, lazily recoloured plates |
| `src/scripts/detail.ts` | `src/pages/[slug].astro` | Versions, plate, crop window, export panel, run command, the `f` key, "Copy" |

They share `current-theme.ts` (the applied seeds), `plates.ts` (fetch limit, template cache, recolour and image swap), `filter.ts` and `export-svg.ts` (pure, unit-tested), `export.ts` with the module worker `export-worker.ts` and `raster.ts` (resvg-wasm, PNG), and `clipboard.ts`.

`Base.astro` inlines `src/lib/theme-boot.ts`, bundled by `src/lib/theme-boot-script.ts`, as the first script in `<head>`; a boot that does not build fails the build.

## Every page

### Theme variables

The theme boot sets every token and role property inline on `<html>` with `style.setProperty`, plus `data-regime="dark|light"`. The property list is `cssVars()` in `src/lib/theme.ts`: the `:root` block of `src/styles/site.css`, plus `--text-dim` (the label of a disabled control). The seed chips read `--seed-bg`, `--seed-fg` and `--seed-accent`, so they follow on their own. It applies the theme again when the system colour scheme changes and when the page comes back from the back/forward cache, each time dispatching the theme event.

When sessionStorage or localStorage cannot be written, `src/lib/theme-store.ts` keeps the token on `<html>` as `data-theme-shared` or `data-theme-saved` instead, so it holds for the rest of the page in every bundle.

Without JavaScript (`@media (scripting: none)`), `site.css` hides what needs it: the theme button, the filter, the colours and export column and the source "Copy". Plates then get fireproof's ground, since the `<noscript>` image is always the fireproof template.

### Header (`src/components/Masthead.astro`)

| Hook | Element | Client does |
|---|---|---|
| `#theme-button` | `button.seeds[popovertarget=picker]` | Set `aria-label` to `presetLabel()` from `src/components/presets.ts` ("fireproof theme: background #1C1B1A, foreground …, accent …", or "custom theme: …"). Set `aria-expanded` from `#picker`'s `toggle` event; the underline follows it. |
| `[data-theme-name]` | `span.name` inside `#theme-button` | Set the text to the preset name, or `custom`. |
| `#shared` | `p.shared[hidden]` | Unhide it while the session theme from `?t=` differs from the saved one. |
| `#shared [data-action=keep-shared]` | button "Keep it" | Save the session theme. |
| `#shared [data-action=drop-shared]` | button "Back to yours" | Drop the session theme. |

### Picker (`src/components/Picker.astro`)

| Hook | Element | Notes |
|---|---|---|
| `#picker` | `div[popover][role=dialog]` | Opened natively by any `[popovertarget=picker]`. |
| `#picker .presets button[data-preset]` | one per preset, in `walldye/_theme.py` order | `data-preset` is the preset name. Set `aria-pressed="true"` on the current one only; the server marks fireproof. |
| `#seed-bg`, `#seed-fg`, `#seed-accent` | `input[data-seed=bg\|fg\|accent]` | Prefilled with the fireproof seeds. There is no `maxlength`, so a pasted theme token fills all three. Set `aria-invalid` on a field holding an invalid value, with `aria-describedby="seed-msg"` on those fields only; while the contrast warning shows, the bg and fg fields point at `faint-msg` instead (docs/site.md §6.3). |
| `.hexfield .chip` | the `span.chip` just before each input | `style="--c:var(--seed-…)"`. Override `--c` while an unapplied edit is shown. |
| `#seed-msg`, `#faint-msg` | `p.msg[hidden]` inside the `aria-live` `.msgs` | Unhide them for invalid input and for the contrast warning. |
| `[data-action=copy-link]` | button "Copy link" (also on the detail page) | Copy the current URL with `?t=<token>`. |

## Index (`src/pages/index.astro`)

### Filters

| Hook | Element | Notes |
|---|---|---|
| `details.filter` | the filter disclosure | An inline script right after it opens it at `min-width: 60.0625rem` and closes it below, before first paint. Keep it in step on `change` of that media query. |
| `.filter > summary .state` | empty span | The active terms, e.g. `“moon”, dithering`. |
| `#facets` | `form[action="/"][method=get][role=search]` | Stop `submit`. On `reset`, defer the re-apply by one task. |
| `#q` | `input[type=search][name=q]` | Search text. Normalise the query with `normaliseSearch()` from `src/lib/content.ts` and match it against `data-search`. |
| `#facets input[name=sort]` | radios `newest` (checked) and `title` | |
| `#facets input[type=checkbox][name=<facet>][value=<value>]` | inside `label.entry` | `<facet>` is `technique`, `subject`, `lineage` or `other`. `other` takes `references`, `light-themes`, `any-screen`, `source-code`, `claude` or `human-made`; the labels are in `src/lib/labels.ts`. Entries that match every piece or none are not rendered. |
| `label.entry .count` | `span.count` | Starts at the unfiltered count. Disable a box when its live count is 0 and it is not checked. |
| `#result-count` | `span`, the one live region | Starts as "N wallpapers". After the first render from the query string, add `role=status`, so a filtered load is not announced; from then on write it only when the text changes. |
| `.results-line .clear` | `button[type=reset][form=facets][hidden]` | Show it while any box is checked or the search is not empty. |
| `.plates .empty` | `p[hidden]` | Show it when nothing matches. |

The query string uses the form's own GET serialisation: `q=<text>`, `sort=title` (left out for `newest`), and repeated `<facet>=<value>` keys, OR within a facet and AND across facets, for example `/?technique=drafting&technique=dither&other=any-screen`. Detail pages link their facts in this format (`/?technique=drafting`). Ignore values that have no checkbox.

### Plates

`ul.grid > li`, in default order (newest first, ties by slug):

| Attribute on `li` | Value |
|---|---|
| `data-slug` | slug |
| `data-title` | display title; sort with `comparePieces()` from `src/lib/content.ts` |
| `data-added` | `YYYY-MM-DD` |
| `data-facets` | space-separated `facet:value` pairs, the computed `other:*` included (`facetPairs()`) |
| `data-search` | normalised title, description and source authors and titles (`searchText()`) |

Inside each `li`: `a[href="/<slug>"][aria-labelledby=t-<slug>]`, with `aria-describedby` listing `v-<slug>` when the piece has published versions and `a-<slug>` when there is an attribution. Add `x-<slug>` to it only while the dark-only note is visible. The href never changes. Then come `figure`, the `.plate` of the default version (see Plate box below), and `figcaption` holding `h2#t-<slug>`, `span.v#v-<slug>` ("N versions", only when the piece has published named variants; N counts the default; under `astro dev` draft versions count too and the text ends in " (N draft)"), `span.x#x-<slug>[data-dark-note][hidden]` (dark-only pieces only) and `span.a#a-<slug>`.

## Plate box (index and detail, `src/components/PlateBox.astro`)

```html
<div class="plate" data-plate="dither-moon"
     data-templates='{"16:9/dark":"/t/9c3c8499b388.svg","16:9/light":"/t/e26df4754421.svg"}'
     data-slots="/t/a1422a6b6f79.slots.json" data-alt="…description…"
     [data-variants='{"default":{"templates":{…},"slots":"…","alt":"…"},"late":{…}}'] [data-dark-only]>
  <noscript><img src="/t/9c3c8499b388.svg" alt="…" width="1920" height="1080" …></noscript>
  <!-- detail only: <div class="crop" data-axis="x" hidden><span class="handle"></span></div> -->
</div>
```

- `data-templates` is JSON from the slots.json key (`<aspect>/<regime>`) to a template URL. Index plates carry only the `16:9/*` keys, and the detail spread carries every key.
  - A dark-only piece has no `*/light` keys and carries `data-dark-only`. Under light seeds, use the `*/dark` template and coefficients with bg and fg swapped. The CSS then gives the plate the `--seed-fg` ground.
  - The URL hash is `sha256[:12]` of the template bytes and equals `slots[key].sha256.slice(0, 12)`.
  - Under the exact fireproof seeds, use the template URL itself as `img.src`, untouched.
- `data-slots` is the piece's `build/slots.json`, byte for byte: `focus` `[x, y]`, `cells`, and per key `{file, sha256, n, coefs, occ}`. It is fetched once per piece. If `n` does not match, show the untouched template.
- `data-alt` is the description. Put it in the `alt` of the `<img>` you insert.
- `data-variants` (detail spread only, and only for a piece with versions) maps each version's name, `default` first, to its `templates`, `slots` and `alt`, shaped like the three attributes above. The server renders the default into those attributes; switching versions copies another entry into them, so everything reading the plate follows. Every version has the same keys in `templates`.
- Insert `<img alt width height decoding="async" data-aspect>` as a child of `.plate`, before any `.crop`; the `<noscript>` may stay. `width` and `height` are the template canvas and `data-aspect` its aspect: the detail plate shows the chosen shape's own template when the piece has one, centred in the 16:9 box, and the page's CSS frames it (`.plate::before`) from `data-aspect`. A new image fades in over the old one, which is then removed. Until the plate holds an `<img>`, `PlateBox.astro` gives it the same rounded-up 16:9 height the image will take, so inserting the image moves nothing.
- When the template or slots.json fails to load, an empty plate gets the untouched template (`showTemplate()`), which keeps the alt text even if it fails too, and the recolour is retried after `RETRY_MS` and on the `online` event.
- `/t/*` is served `immutable`.

## Detail (`src/pages/[slug].astro`)

The detail page keeps its own state in the query string: `v=<variant>` (the version, left out for the default), `shape=<w>x<h>` (the aspect label, left out for 16:9) and `crop=<0..1>` (only for a cropped shape). They are written with `history.replaceState` when the visitor changes them, never for the phone default. A `v` that names no version on the page (unknown, or a draft outside `astro dev`) shows the default.

### Spread and label

| Hook | Element | Notes |
|---|---|---|
| `.spread .plate` | Plate box with every aspect | |
| `.spread .crop` | `div.crop[data-axis=x\|y][hidden]` with `span.handle` | Show it while a cropped shape is selected. Set `data-axis`, and position it in % of the plate (docs/site.md §6.6). |
| `#dark-note` | `p.attr[data-dark-note][hidden]` | Dark-only pieces only. Show it under light seeds. |
| `#desc` | `p.desc` | The default version's description. Set it to the shown version's (`data-variants[name].alt`). |

There are no neighbour links and no arrow-key shortcuts (docs/design.md, Detail); the label ends with the facts list. `f` toggles fullscreen on the plate.

### Versions, colours and export (`src/components/Controls.astro`)

| Hook | Element | Notes |
|---|---|---|
| `#versions` | `div.seg.versions[role=radiogroup]`, in the first section, headed "Versions" | Only for a piece with versions. One `label > input[type=radio][name=v][value=<name>] + span` per version, the default (checked) first, then meta.yaml order. Choosing one swaps the plate data from `data-variants`, sets `#desc` and the image alt, reloads the focus and cells from that version's slots.json (moving a crop the visitor has not placed), renames the download and the run command, and writes `v`. Theme, shape and a placed crop are kept. |
| `.seedlist [data-seed=bg\|fg\|accent]` | `span.mono` | Set the text to the uppercase `#RRGGBB` seed. |
| `button[popovertarget=picker]` | "Change" | Native. |
| `[data-action=copy-link]` | "Copy link" | As in the picker, plus `crop` when it is set. |
| `#export` | `section[data-license]` | Prefetch the rasteriser when it scrolls into view, and probe WebP support. `data-license` is the piece's licence id, written into the SVG download's `<desc>`. |
| `#format-hint` | `span.hint[hidden]` | Shown, with the WebP radio disabled, when the browser cannot encode WebP. |
| `#export input[name=fmt]` | radios `svg`, `png` (checked), `webp`, `jpeg` | `data-ext` is the file extension (`jpeg` becomes `jpg`). |
| `#export input[name=asp]` | radios with value `16:9` (checked), `16:10`, `21:9`, `32:9`, `9:19.5` and `10:16` | `data-native` marks the shapes the piece has its own template for. Any other shape is a crop of 16:9. |
| `#shape-hint` | `span.hint[hidden]` "cropped from 16:9" | Show it for cropped shapes only. |
| `#crop-row`, `#crop` | `div.row[hidden]` and `input[type=range]` from 0 to 1 | Show the row for cropped shapes. The value is the crop's position along its travel (0 left or top, 1 right or bottom). It starts where the crop is centred on `focus` (clamped), or at `?crop=`, and is kept when the new shape crops along the same axis. |
| `#sizes` | radiogroup | Rendered with the 16:9 sizes, 2560×1440 checked, and `screen` ("your screen") last. On a shape change, re-render it from `EXPORT_SIZES` in `src/lib/content.ts`: values `<w>x<h>`, labels `<span class="mono">w×h</span>`. Disable sizes over the limits and show the reason. "your screen" is the screen at device pixels; picking it switches the shape to the nearest aspect (`\|log ratio\|`), and leaving that shape drops it for the default size. Phones (`(max-width: 60rem) and (pointer: coarse)`) start on it. |
| `#size-limit` | `span.hint[hidden]` | Shown while a size is disabled for being over the browser's canvas limits; disabled radios point at it with `aria-describedby`. |
| `#cell-note` | `span.hint.lnum[hidden]` | For pieces with grid cells (`cells` in slots.json), raster formats only: shown when cells land on uneven pixel widths at the chosen size. |
| `#download` | `button.download` | Runs the export. Its `.k` reads "Preparing…" and it carries `aria-busy` while an export runs. |
| `#export-error` | `span.msg.err` in a polite live row | Says the file could not be made when an export fails. |
| `#download-name` | `span.mono` | The file name, from `downloadName()` in `src/lib/content.ts`: `<slug>[--<variant>]-…`. The SVG download's `<desc>` names `walldye.com/<slug>[?v=<variant>]`. |

### Source code (`src/components/SourceCode.astro`)

| Hook | Element | Notes |
|---|---|---|
| `[data-action=copy-source]` | "Copy" | Copy `#raw-source`. |
| `#raw-source` | `template` | The design.py text. |
| `#run-render[data-slug]` | `span` holding the whole `uv run walldye render …` command | Set its text to `uv run walldye render <slug> [--variant <name>] --theme <token> [--aspect A] [--crop x,y,w,h] -o <slug>[--<name>]-<token>-<aspect>.svg` (`renderCommand()`), using the preset name when the seeds match a preset, and the swapped token for a dark-only piece under light seeds. |

Script-less pieces have `p.lost` in place of the listing and run command, and none of these hooks.

## Shared helpers

`src/lib/content.ts` has no Node or Astro runtime imports, so client code can import from it: `SITE_ASPECTS`, `CANVAS`, `EXPORT_SIZES`, `DEFAULT_SIZE_INDEX`, `FORMATS`, `DEFAULT_VARIANT`, `aspectLabel`, `normaliseSearch`, `fileStem`, `downloadName` and `comparePieces` (takes `{slug, title, added}`, such as an `li`'s dataset). `src/lib/labels.ts` has the facet labels.
