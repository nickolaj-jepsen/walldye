# DOM contract for the client modules

The hooks the server-rendered pages give the client code in `src/client/`. The pages render fireproof, the build's first sort, no filters, 16:9 and the default export choices, so the client changes only what the visitor changed. Behavior and look are in `docs/site.md`. The client reads required hooks with `must()` from `dom.ts`, which throws when one is missing.

## Script hooks

`site.ts` loads on every page from `src/layouts/Base.astro`, after `<Picker />`; `index/page.ts` from `src/pages/index.astro`; `detail/page.ts` from `src/pages/[slug].astro`.

Both page modules show their grids of Plate.astro plates with `grid.ts`. `src/server/inline-script.ts` bundles the inline scripts: `Base.astro` inlines `theme/boot.ts` as the first script in `<head>` and `transition/boot.ts` after it, `index.astro` inlines `index/shape-boot.ts` as the first child of `section.plates`, and `[slug].astro` inlines `detail/shape-boot.ts` as the first child of `.spread` and `detail/panel-boot.ts` (`script#panel-boot`) right after the controls.

## Every page

### Theme variables

The theme boot (`applyTheme()` in `theme/store.ts`) sets the color properties, `data-regime` and `data-theme` on `<html>`, and repoints `link#favicon`, which must come before it in `<head>`. Swatches read `--seed-bg`, `--seed-fg` and `--seed-accent`, so they follow on their own.

### Plate transition

`transition/boot.ts` names the carried plate by `.spread .plate[data-plate=<slug>]` or `.grid > li[data-slug=<slug>] .plate`; nothing else may set a view-transition-name. `[slug].astro` holds its first render until `#panel-boot` is parsed (`<link rel=expect blocking=render>`).

### Page name

`events.ts` names the page from `link[rel=canonical]`; `Base.astro` leaves it out only on the 404 page.

### Header (`src/components/Masthead.astro`)

| Hook | Element | Client does |
|---|---|---|
| `#theme-button` | `button.seeds[popovertarget=picker]` | Set `aria-label` to `presetLabel()` from `src/lib/presets.ts`, and `aria-expanded` from `#picker`'s `toggle` event. |
| `[data-theme-name]` | `span.name` inside `#theme-button` | Set the text to the preset name, or `custom`. |
| `#shared` | `p.shared[hidden]` | Unhide it while the session theme from `?t=` differs from the saved one. |
| `#shared [data-action=keep-shared]` | button "Keep it" | Save the session theme. |
| `#shared [data-action=drop-shared]` | button "Back to yours" | Drop the session theme. |

### Picker (`src/components/Picker.astro`)

| Hook | Element | Notes |
|---|---|---|
| `#picker` | `div[popover][role=dialog]` | Opened natively by any `[popovertarget=picker]`. |
| `#picker .presets li` | one per family, in `FAMILIES` order (`src/lib/presets.ts`) | A family with a light preset has `button.family[data-family]` (its name) and one `button.swatch[data-preset][aria-label][title]` per preset; a lone preset is one `button.single[data-preset]`. Set `aria-pressed="true"` on the visitor's choice only (`ownChoice()`, or the shared theme's preset while it differs): a family, or a fixed preset. The server marks the fireproof family. |
| `#seed-bg`, `#seed-fg`, `#seed-accent` | `input[data-seed=bg\|fg\|accent][required][pattern]` | Prefilled with the fireproof seeds; the pattern is `SEED_PATTERN` from `src/lib/theme.ts`, padded with whitespace. While a field is `:user-invalid` set `aria-invalid` and `aria-describedby="seed-msg"`; otherwise the bg and fg fields point at `faint-msg` while it shows, and the accent field at `accent-bg-msg` or `accent-fg-msg`. |
| `.hexfield .chip` | `span.chip` before each input | `style="--c:var(--seed-…)"`. Override `--c` while an unapplied edit is shown. |
| `.hexfield .chip input[type=color]` | the native color picker, invisible over the swatch | Keep its value on the swatch's color. Its `input` fills the hex field as an edit, its `change` commits it. |
| `#seed-msg`, `#faint-msg`, `#accent-bg-msg`, `#accent-fg-msg` | `p.msg` inside the `aria-live` `.msgs`, all but `#seed-msg` `[hidden]` | site.css shows `#seed-msg` while a field is `:user-invalid`. Unhide the others for the contrast warning, and for an accent within `NEAR_ACCENT` of the background (first) or the foreground. |
| `#theme-import` | `input` under the hex fields | On paste, read the clipboard text whole with `seedsFromText()` from `src/lib/import-theme.ts`; on change, the typed value. Seeds fill the three fields as an edit; none unhide `#import-msg`. |
| `#import-msg` | `p.msg[hidden]` inside `.msgs` | "No colors found in that text." |
| `[data-action=copy-link]` | button "Copy link" (also on the detail page) | Copy the current URL with `?t=<token>`. |

## Index (`src/pages/index.astro`)

### Filters

| Hook | Element | Notes |
|---|---|---|
| `details.filter` | the filter disclosure | An inline script after it opens it at `min-width: 60.0625rem` and closes it below, before first paint. Keep it in step with that media query. |
| `.filter > summary .state` | empty span | The active terms, e.g. `“moon”, dithering`. |
| `#facets` | `form[action="/"][method=get][role=search]` | Stop `submit`. On `reset`, defer the re-apply by one task. |
| `#q` | `input[type=search][name=q]` | Normalize with `normalizeSearch()` from `src/lib/content.ts` and match against `data-search`. |
| `#facets input[name=sort]` | radios `featured`, `newest`, `popular`, `views` and `title` | `featured` is there only when a piece is featured, and `popular` and `views` only when a piece has a recorded view. The server checks `defaultSort()`'s order, so the checked one's `defaultChecked` is it. |
| `#facets input[name=shape]` | radios `16x9` (checked), `16x10`, `21x9`, `32x9`, `9x19.5`, `10x16` | `index/shape-boot.ts` checks the address's shape, else `deviceAspect()`, before first paint, and make it the reset value; "clear" keeps the checked one. |
| `#facets input[type=checkbox][name=<facet>][value=<value>]` | inside `label.entry` | `<facet>` is `technique`, `subject`, `lineage` or `other` (the computed values of `facetPairs()`). |
| `label.entry .count` | `span.count` | Starts at the unfiltered count. Disable a box when its live count is 0 and it is not checked. |
| `#result-count` | `span`, the one live region | Starts as "N wallpapers". Add `role=status` after the first render from the query string, so a filtered load is not announced; then write it only when the text changes. |
| `#show-results` | `button.show` after `#facets`, inside the disclosure | "Show N wallpapers", N as in `#result-count`; not a live region. On click, close the disclosure and focus and scroll to its summary. site.css shows it on phones only. |
| `.results-line .clear` | `button[type=reset][form=facets]` | site.css shows it while any box is checked or the search is not empty. |
| `.plates .empty` | `p` | site.css shows it while every `li` is hidden. |

The query string is the form's GET serialization (`index/filter.ts`), minus the first sort and the device's shape; detail pages link their facts the same way. The client ignores values with no control and writes the form's `FormData`, so a new control reaches the address without client changes.

### Color row

`.themes[role=group]` above the results line: `h2#themes-h`, one button per family, `[aria-pressed][aria-label][title]`, then `button[popovertarget=picker]` "Your own". A family with a light preset is `button[data-family]` holding both presets' swatches as `.chips.for-dark` and `.chips.for-light`, which site.css shows by `prefers-color-scheme`; a lone preset is `button[data-preset]`. `site.ts` handles them with the picker's buttons.

### Plates

`section.plates[data-shape]` holds `ul.grid > li` in `defaultSort()`'s order. The shape boot and `grid.ts` mark the shown shape on it with `markShape()` (`16:9` until then).

| Attribute on `li` | Value |
|---|---|
| `data-slug` | slug |
| `data-aspects` | space-separated shapes with a template of their own; any other shape is shown as a crop of 16:9 |
| `data-focus` | the 16:9 template's focus, `x y` as fractions of the canvas |
| `data-title` | display title |
| `data-added` | `YYYY-MM-DD` |
| `data-views` | page views, all of them |
| `data-recent` | page views and downloads weighted towards the last few days (`recent` in `src/server/stats.ts`), to 0.01 |
| `data-featured` | place on featured.yaml from 0, only on featured pieces |
| `data-facets` | space-separated `facet:value` pairs, the computed `other:*` included (`facetPairs()`) |
| `data-search` | normalized title, description and source authors and titles (`searchText()`) |

Inside each `li`: `a[href="/<slug>"][aria-labelledby=t-<slug>]`, with `aria-describedby` listing `v-<slug>` and `a-<slug>` when present; set the href to `/<slug>?shape=<w>x<h>` while the shown shape is not the device's, never anything else. Then `figure` with the default version's `.plate` (below) and `figcaption` holding `h2#t-<slug>` (`h3` in "See also"), `span.v#v-<slug>` ("N versions", N counting the default) and `span.a#a-<slug>`. A plate shown as a crop gets `--pos`, the CSS `object-position` of the crop at the focus (`focusPosition()`).

## Plate box (`src/components/PlateBox.astro`, index and detail)

```html
<div class="plate" data-plate="dither-moon"
     data-templates='{"16:9/dark":"/t/9c3c8499b388.svg","16:9/light":"/t/e26df4754421.svg"}'
     data-slots="/t/a1422a6b6f79.slots.json" data-alt="…alt text…"
     [data-variants='{"default":{"templates":{…},"slots":"…","alt":"…","description":"…"},"late":{…}}']>
  <noscript><img src="/t/9c3c8499b388.svg" alt="…" width="1920" height="1080" …></noscript>
  <!-- detail only: <div class="crop" data-axis="x" hidden><span class="handle"></span></div> -->
</div>
```

- `data-templates` maps slots.json keys (`<aspect>/<regime>`) to template URLs: only `16:9/*` in grids, every key on the spread; `templateUrl()` derives the rest.
- `data-slots` is the URL of the piece's `build/slots.json`, fetched once per piece.
- `data-alt` is the piece's alt text, for the `alt` of the inserted `<img>`.
- `data-variants` (detail page, pieces with versions only) maps each version, `default` first, to its `templates`, `slots`, `alt` and `description`. The client reads these attributes once and never writes them.
- Insert `<img alt width height decoding="async" data-aspect>` into `.plate`, before any `.crop`. `width` and `height` are the template canvas; set the plate's `--shape` to their ratio, which the CSS frames a non-16:9 template with. `PlateBox.astro` already gives the empty plate the image's height, so inserting it moves nothing.
- While an image fades in over the one it replaces, `site.css` stacks the second `img` over the first.

## Detail (`src/pages/[slug].astro`)

The page keeps its state in the query string (`detail/state.ts`), written with `history.replaceState` only once the visitor changes something, so the screen's own shape stays out of the address.

### Spread and label

| Hook | Element | Notes |
|---|---|---|
| `.spread` | `figure` | Marked with `markShape(spread, 'aspect', …)`; the shape boot sets the first one before first paint (`startAspect()` in `detail/panel.ts`), and the page module starts on the same. |
| `.spread .plate` | Plate box with every aspect | Set `--pos`, the `object-position` of the crop, for the phone view of a tall cropped shape, where a sideways drag on the plate moves the crop. |
| `.spread .crop` | `div.crop[data-axis=x\|y][hidden]` with `span.handle` | Show it for a cropped shape; set `data-axis` and position it in % of the plate. |
| `#quick-download` | `button.download.quick` after the attribution | Mirrors `#download`. |
| `[data-part=format\|size\|yours]` | spans inside both Download buttons (`DownloadSummary.astro`) | The format's label; the size as `w×h`, or the shape for SVG; " for your screen", which site.css shows for a raster at the `screen` size. The panel boot sets them, with the Shape and Size rows, for the start state before first paint (`renderPanel()` in `detail/panel.ts`, which the page module renders with too). |
| `#desc` | `p.desc` | Set it to the shown version's description (`data-variants[name].description`). |

### Versions, export and colors (`src/components/Controls.astro`)

| Hook | Element | Notes |
|---|---|---|
| `#versions` | `div.seg.versions[role=radiogroup]` | Pieces with versions only. One `label > input[type=radio][name=v][value=<name>] + span` per version, the default (checked) first, then `span.plate.thumb[data-version=<name>][aria-hidden=true]`: show that version's 16:9 template in the current theme. On change: swap the plate data, set `#desc` and the alt, reload focus and cells from that version's slots.json (moving a crop the visitor has not placed), rename the download and the run command, write `v`. |
| `.seedlist [data-seed=bg\|fg\|accent]` | `span.mono` | The uppercase `#RRGGBB` seed. |
| `button[popovertarget=picker]` | "Change" | Native. |
| `[data-action=copy-link]` | "Copy link" | As in the picker, so with the page's `v`, `shape` and `crop`. |
| `#export` | `section[data-license]` | Prefetch the rasterizer and probe WebP support when it scrolls into view. `data-license` goes into the SVG download's `<desc>`. |
| `#format-hint` | `span.hint[hidden]` | Shown, with the WebP radio disabled, when the browser cannot encode WebP. |
| `#export input[name=fmt]` | radios `svg`, `png` (checked), `webp`, `jpeg` | |
| `#export input[name=asp]` | radios `16:9` (checked), `16:10`, `21:9`, `32:9`, `9:19.5`, `10:16` | `data-native` marks shapes with their own template; the rest crop 16:9. |
| `#shape-hint` | `span.hint` | site.css shows it while the checked `asp` radio has no `data-native`. |
| `#crop-row`, `#crop` | `div.row` and `input[type=range]` 0 to 1 | site.css shows the row as `#shape-hint`. The value is the position along the crop's travel (0 left or top). |
| `.crop-map` | `span.plate[aria-hidden]` above `#crop`, holding a `.crop` like the spread's | While the plate shows a tall crop itself (phones), show the 16:9 template in the current version and theme, and place and drag its window as the spread's. site.css shows it in that view only. |
| `#sizes` | radiogroup | One `label[data-aspect=<aspect>]` per size of every shape in `EXPORT_SIZES` (value `<w>x<h>`, label `<span class="mono">w×h</span>`), then `screen`. Only the 16:9 ones are shown and enabled at first, 2560×1440 checked; the client shows and enables the chosen shape's. |
| `#size-limit` | `span.hint[hidden]` | Shown while a size is disabled for the canvas limits; disabled radios point at it with `aria-describedby`. |
| `#cell-note` | `span.hint.lnum[hidden]` | Pieces with `cells`, raster formats only: shown when cells land on uneven pixel widths. |
| `#download` | `button.download` | Runs the export; its `.k` reads "Preparing…" with `aria-busy` meanwhile. Set its `title` to the file name, from `downloadName()` in `src/lib/content.ts`. |
| `#export-error` | `span.msg.err` in a polite live row | Set when an export fails. |

### See also

`section.related` (absent when nothing is related): `h2#related-h`, then `ul.grid` of `li`s as on the index (Plates), with h3 titles, shown with `grid.ts` in the page's shape.

### Source code (`src/components/SourceCode.astro`)

`details.appendix`, closed, whose `summary` holds `h2#appendix-h`; the hooks below are inside it.

| Hook | Element | Notes |
|---|---|---|
| `[data-action=copy-source]` | "Copy" | Copy `#raw-source`. |
| `#raw-source` | `template` | The design.py text. |
| `#run-render[data-slug]` | `span` with the `uv run walldye render …` command | Set it with `renderCommand()` (docs/site.md §6.11). |

Script-less pieces have `p.lost` instead, and none of these hooks.

