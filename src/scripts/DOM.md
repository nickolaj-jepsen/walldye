# DOM contract for the client modules

The hooks the server-rendered pages give the client code in `src/scripts/*.ts`. The pages render fireproof, the default sort, no filters, 16:9 and the default export choices, so the client changes only what the visitor changed. Behaviour and look are in `docs/site.md`.

## Script hooks

| File | Loaded by | Does |
|---|---|---|
| `site.ts` | `src/layouts/Base.astro`, after `<Picker />` | Theme button, shared-theme line, picker, "Copy link", the detail colour list |
| `index.ts` | `src/pages/index.astro` | Filters, results line, lazily recoloured plates |
| `detail.ts` | `src/pages/[slug].astro` | Versions, drawing (with `live.ts` and the module worker `draw-worker.ts`), plate, crop window, export panel, run command, the `f` key, "Copy" |

`Base.astro` inlines `src/lib/theme-boot.ts`, bundled by `src/lib/theme-boot-script.ts`, as the first script in `<head>`; a boot that does not build fails the build.

## Every page

### Theme variables

The theme boot sets every property from `cssVars()` in `src/lib/theme.ts` inline on `<html>`, plus `data-regime="dark|light"`. The swatches read `--seed-bg`, `--seed-fg` and `--seed-accent`, so they follow on their own. It applies the theme again, dispatching the theme event, when the system colour scheme changes and when the page returns from the back/forward cache.

When storage cannot be written, `src/lib/theme-store.ts` keeps the token on `<html>` as `data-theme-shared` or `data-theme-saved`, so it holds for the rest of the page in every bundle.

### Header (`src/components/Masthead.astro`)

| Hook | Element | Client does |
|---|---|---|
| `#theme-button` | `button.seeds[popovertarget=picker]` | Set `aria-label` to `presetLabel()` from `src/components/presets.ts`, and `aria-expanded` from `#picker`'s `toggle` event. |
| `[data-theme-name]` | `span.name` inside `#theme-button` | Set the text to the preset name, or `custom`. |
| `#shared` | `p.shared[hidden]` | Unhide it while the session theme from `?t=` differs from the saved one. |
| `#shared [data-action=keep-shared]` | button "Keep it" | Save the session theme. |
| `#shared [data-action=drop-shared]` | button "Back to yours" | Drop the session theme. |

### Picker (`src/components/Picker.astro`)

| Hook | Element | Notes |
|---|---|---|
| `#picker` | `div[popover][role=dialog]` | Opened natively by any `[popovertarget=picker]`. |
| `#picker .presets button[data-preset]` | one per preset, in `walldye/_theme.py` order | Set `aria-pressed="true"` on the current one only; the server marks fireproof. |
| `#seed-bg`, `#seed-fg`, `#seed-accent` | `input[data-seed=bg\|fg\|accent]` | Prefilled with the fireproof seeds. On an invalid value set `aria-invalid` and `aria-describedby="seed-msg"`; while the contrast warning shows, the bg and fg fields point at `faint-msg` instead. |
| `.hexfield .chip` | `span.chip` before each input | `style="--c:var(--seed-…)"`. Override `--c` while an unapplied edit is shown. |
| `#seed-msg`, `#faint-msg` | `p.msg[hidden]` inside the `aria-live` `.msgs` | Unhide for invalid input and for the contrast warning. |
| `[data-action=copy-link]` | button "Copy link" (also on the detail page) | Copy the current URL with `?t=<token>`. |

## Index (`src/pages/index.astro`)

### Filters

| Hook | Element | Notes |
|---|---|---|
| `details.filter` | the filter disclosure | An inline script after it opens it at `min-width: 60.0625rem` and closes it below, before first paint. Keep it in step with that media query. |
| `.filter > summary .state` | empty span | The active terms, e.g. `“moon”, dithering`. |
| `#facets` | `form[action="/"][method=get][role=search]` | Stop `submit`. On `reset`, defer the re-apply by one task. |
| `#q` | `input[type=search][name=q]` | Normalise with `normaliseSearch()` from `src/lib/content.ts` and match against `data-search`. |
| `#facets input[name=sort]` | radios `newest` (checked), `popular`, `views` and `title` | `popular` and `views` are there only when a piece has a recorded view. |
| `#facets input[type=checkbox][name=<facet>][value=<value>]` | inside `label.entry` | `<facet>` is `technique`, `subject`, `lineage` or `other`; `other` takes `references`, `any-screen`, `source-code`, `claude` or `human-made`. |
| `label.entry .count` | `span.count` | Starts at the unfiltered count. Disable a box when its live count is 0 and it is not checked. |
| `#result-count` | `span`, the one live region | Starts as "N wallpapers". Add `role=status` after the first render from the query string, so a filtered load is not announced; then write it only when the text changes. |
| `.results-line .clear` | `button[type=reset][form=facets][hidden]` | Show it while any box is checked or the search is not empty. |
| `.plates .empty` | `p[hidden]` | Show it when nothing matches. |

The query string is the form's own GET serialisation: `q=<text>`, `sort=<order>` (left out for `newest`) and repeated `<facet>=<value>` keys, e.g. `/?technique=drafting&technique=dither&other=any-screen`. Detail pages link their facts the same way. Ignore values that have no checkbox or radio.

### Plates

`ul.grid > li`, in default order (newest first, ties by slug):

| Attribute on `li` | Value |
|---|---|
| `data-slug` | slug |
| `data-title` | display title; sort with `comparePieces()` from `src/lib/content.ts` |
| `data-added` | `YYYY-MM-DD` |
| `data-views` | page views, all of them |
| `data-recent` | page views weighted towards the last few days, to 0.01 |
| `data-facets` | space-separated `facet:value` pairs, the computed `other:*` included (`facetPairs()`) |
| `data-search` | normalised title, description and source authors and titles (`searchText()`) |

Inside each `li`: `a[href="/<slug>"][aria-labelledby=t-<slug>]`, with `aria-describedby` listing `v-<slug>` and `a-<slug>` when present; the href never changes. Then `figure` with the default version's `.plate` (below) and `figcaption` holding `h2#t-<slug>`, `span.v#v-<slug>` ("N versions", N counting the default) and `span.a#a-<slug>`.

## Plate box (`src/components/PlateBox.astro`, index and detail)

```html
<div class="plate" data-plate="dither-moon"
     data-templates='{"16:9/dark":"/t/9c3c8499b388.svg","16:9/light":"/t/e26df4754421.svg"}'
     data-slots="/t/a1422a6b6f79.slots.json" data-alt="…description…"
     [data-variants='{"default":{"templates":{…},"slots":"…","alt":"…"},"late":{…}}']>
  <noscript><img src="/t/9c3c8499b388.svg" alt="…" width="1920" height="1080" …></noscript>
  <!-- detail only: <div class="crop" data-axis="x" hidden><span class="handle"></span></div> -->
</div>
```

- `data-templates` maps each slots.json key (`<aspect>/<regime>`) to a template URL: only the `16:9/*` keys on the index, every key on the detail page. The URL hash is `slots[key].sha256.slice(0, 12)`. Under the exact fireproof seeds, use the template URL itself as `img.src`.
- `data-slots` is the piece's `build/slots.json`, byte for byte (`focus`, `cells`, and per key `{file, sha256, n, coefs, occ}`), fetched once per piece. If `n` does not match, show the untouched template.
- `data-alt` is the description, for the `alt` of the inserted `<img>`.
- `data-variants` (detail page, pieces with versions only) maps each version, `default` first, to its `templates`, `slots` and `alt`. Switching versions copies an entry into the three attributes above, so everything reading the plate follows.
- Insert `<img alt width height decoding="async" data-aspect>` into `.plate`, before any `.crop`. `width` and `height` are the template canvas; the CSS frames a non-16:9 template from `data-aspect`. `PlateBox.astro` already gives the empty plate the image's height, so inserting it moves nothing.
- When the template or slots.json fails to load, an empty plate gets the untouched template (`showTemplate()`), and the recolour is retried on the `RETRY_MS` schedule and on the `online` event.

## Detail (`src/pages/[slug].astro`)

The page keeps its state in the query string, written with `history.replaceState` when the visitor changes it: `v=<variant>` (left out for the default), the edits to the drawing (`<knob>=<value>` for each changed knob, then `draw=<n>`), `shape=<w>x<h>` (left out for 16:9) and `crop=<0..1>` (cropped shapes only). The phone default for size is never written. A `v` that names no version on the page shows the default; an edit that does not parse, or equals the version's value, is ignored.

### Spread and label

| Hook | Element | Notes |
|---|---|---|
| `.spread .plate` | Plate box with every aspect | While a draw runs, set `data-busy="load\|draw"` and `aria-busy`, and `--progress` (0 to 1) as Pyodide downloads. For a piece with drag knobs, set `data-drag` to their axes (`x`, `y` or `xy`); dragging on it, outside the crop window, moves them, adding `.dragging`. |
| `.spread .plate > .drawbar` | `span[aria-hidden]` | The hairline the busy states style. |
| `.spread .crop` | `div.crop[data-axis=x\|y][hidden]` with `span.handle` | Show it for a cropped shape; set `data-axis` and position it in % of the plate. |
| `#desc` | `p.desc` | Set it to the shown version's description (`data-variants[name].alt`). |

### Versions, drawing, colours and export (`src/components/Controls.astro`)

| Hook | Element | Notes |
|---|---|---|
| `#versions` | `div.seg.versions[role=radiogroup]` | Pieces with versions only. One `label > input[type=radio][name=v][value=<name>] + span` per version, the default (checked) first. On change: swap the plate data, set `#desc` and the alt, reload focus and cells from that version's slots.json (moving a crop the visitor has not placed), rename the download and the run command, write `v`, and drop the edits to the drawing. |
| `#drawing` | `section[data-drawing]` | Pieces the page can redraw only. `data-drawing` is JSON: `versions` (each version's `params` and `redraw`), `knobs` (the shown knobs, `src/lib/controls.ts` `Knob`) and `data` (`{name, url}` per data file). The design is `#raw-source`. |
| `#drawing input[data-knob]` | a `.range` per range knob, radios `name=knob-<name>` per choice knob, a checkbox per bool, an `input.textknob[maxlength]` per text knob | Rendered at the default version's values. Set them from the version and the edits (a text field being typed in keeps its text); a range's `input` moves its readout and redraws while draws are quick, text redraws once typing pauses and sets `aria-invalid` while empty or not printable ASCII, and `change` on any of them redraws. |
| `[data-readout=<knob>]` | `span.mono.readout` | Ranges of int and degree knobs only: the value, from `readout()`. |
| `[data-action=redraw]` | "Draw another" | Hidden for a version whose `redraw` is false. |
| `[data-action=restore]` | "Back to the original", `hidden` | Shown while there are edits; drops them and focuses "Draw another" or the first knob. |
| `#draw-status` | `span.sub.msg` in a polite live row | "Getting ready to draw…" while Pyodide downloads, "Drawing…" after 300 ms of a draw, or the failure message with `.err`. |
| `.seedlist [data-seed=bg\|fg\|accent]` | `span.mono` | The uppercase `#RRGGBB` seed. |
| `button[popovertarget=picker]` | "Change" | Native. |
| `[data-action=copy-link]` | "Copy link" | As in the picker, plus `crop` when set. |
| `#export` | `section[data-license]` | Prefetch the rasteriser and probe WebP support when it scrolls into view. `data-license` goes into the SVG download's `<desc>`. |
| `#format-hint` | `span.hint[hidden]` | Shown, with the WebP radio disabled, when the browser cannot encode WebP. |
| `#export input[name=fmt]` | radios `svg`, `png` (checked), `webp`, `jpeg` | `data-ext` is the file extension. |
| `#export input[name=asp]` | radios `16:9` (checked), `16:10`, `21:9`, `32:9`, `9:19.5`, `10:16` | `data-native` marks shapes with their own template; the rest crop 16:9. |
| `#shape-hint` | `span.hint[hidden]` | Show it for cropped shapes. |
| `#crop-row`, `#crop` | `div.row[hidden]` and `input[type=range]` 0 to 1 | Show for cropped shapes. The value is the position along the crop's travel (0 left or top). It starts centred on `focus` (clamped) or at `?crop=`, and is kept when the new shape crops along the same axis. |
| `#sizes` | radiogroup | Rendered with the 16:9 sizes, 2560×1440 checked, `screen` last. On a shape change, re-render from `EXPORT_SIZES` (values `<w>x<h>`, labels `<span class="mono">w×h</span>`). Picking `screen` switches to the nearest shape; leaving that shape drops it for the default size. Phones (`(max-width: 60rem) and (pointer: coarse)`) start on it. |
| `#size-limit` | `span.hint[hidden]` | Shown while a size is disabled for the canvas limits; disabled radios point at it with `aria-describedby`. |
| `#cell-note` | `span.hint.lnum[hidden]` | Pieces with `cells`, raster formats only: shown when cells land on uneven pixel widths. |
| `#download` | `button.download` | Runs the export; its `.k` reads "Preparing…" with `aria-busy` meanwhile. |
| `#export-error` | `span.msg.err` in a polite live row | Set when an export fails. |
| `#download-name` | `span.mono` | The file name, from `downloadName()` in `src/lib/content.ts`. |

### Source code (`src/components/SourceCode.astro`)

| Hook | Element | Notes |
|---|---|---|
| `[data-action=copy-source]` | "Copy" | Copy `#raw-source`. |
| `#raw-source` | `template` | The design.py text. |
| `#run-render[data-slug]` | `span` with the `uv run walldye render …` command | Set it with `renderCommand()` (docs/site.md §6.10). |

Script-less pieces have `p.lost` instead, and none of these hooks.

## Shared helpers

`src/lib/content.ts` has no Node or Astro runtime imports, so client code can import it: `SITE_ASPECTS`, `CANVAS`, `EXPORT_SIZES`, `DEFAULT_SIZE_INDEX`, `FORMATS`, `DEFAULT_VARIANT`, `aspectLabel`, `normaliseSearch`, `fileStem`, `downloadName` and `comparePieces` (takes `{slug, title, added}`, such as an `li`'s dataset). `src/lib/labels.ts` has the facet labels.
