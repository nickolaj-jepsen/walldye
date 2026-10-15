# walldye site

How walldye.com looks and what it says. `src/styles/site.css` holds the values; this file explains them, so a change stays inside the system. [architecture.md](architecture.md) (The site) covers routing, theming and export internals.

## 1. Principles

- An exhibition catalog in the manner of the 1968 computer-art catalogs: hairline rules instead of cards, type-only chrome, and the plates carry all the color.
- Legibility first: EB Garamond's small x-height makes the 22, 20 and 19px of §3 read like 17, 16 and 15px in a sans.
- Text is `--text` (fg) or `--text-2` (fg_alt), at 4.5:1 or better in every theme (§2). muted draws only the dot leaders; rules, frames and controls use the ui grays.
- Accent appears only in the focus ring, the footnote markers and target bar, error text and the invalid-field underline, and the listing's keywords and strings.
- Italic marks titles of works and nothing else.
- One convention for "current": text color plus a 1px underline 0.3em below the baseline on any chosen or current text control; under swatch buttons, a 1px `--text` line under the swatches. Resting in-text links carry a 1px underline in `--link-line`.
- Every vertical measure is a multiple of the 8px unit (§4), and rules take no layout space.
- No border radius, no drop shadow, no tinted surface to mark state.

## 2. Color roles

`cssVars()` in `src/lib/theme.ts` computes every color property for each theme, and `GUARDED` lists each guarded one with its token, ground and minimum: 4.5:1 for text, including the listing's, and 3:1 for controls, link underlines and focus. The raw seeds draw only wallpapers and plate grounds, and dot leaders, rules and the plate edge are exempt. site.css repeats the fireproof values in `:root`, and flexoki-light's under `prefers-color-scheme: light`, for visitors without JavaScript.

## 3. Type

### Faces

- EB Garamond, roman and italic, weights 400 to 800, for everything but data. Walldye Mono, a renamed Monaspace Krypton subset, weights 400 to 700, for data: seeds, colors, sizes, file names.
- Self-hosted woff2 through Astro's fonts API, `display: swap`, with fallback metric overrides so the swap does not re-wrap captions. The roman and the mono are preloaded.
- The subsets come from `scripts/fonts/` and keep only the OpenType features `FEATURES` in `subset.py` lists. No face has U+202F, and the mono lacks U+2009, U+200A, U+2011 and U+2060, so keep those out of mono text and hold a thin-spaced group together with `.nowrap`.

### Scale

Garamond runs at weight 400 on light grounds and 450 on dark ones (`--wt`), because grayscale smoothing thins its hairlines on a dark ground. Roles marked +100 take 500 and 550.

| Role | Face | Size and line | Color |
|---|---|---|---|
| Prose: notes, About, the detail description | Garamond | 22px (21 on phones), 32 | `--text` |
| Detail title | Garamond, lining figures | 40px (34), 48 | `--text` |
| "Source code" heading | Garamond | 28px (22), 40 | `--text` |
| Masthead "Walldye" | Garamond +100, small caps | 28px (22 on phones), 32 | `--text` |
| UI text, the default: facet entries, search, sort, results line, controls, attribution, picker | Garamond | 20px, 32 | `--text-2`; hovered, checked or current `--text` |
| Small-caps heads: legends, section heads, nav, picker heads | Garamond all-small-caps | 19px, 32 | `--text-2`; current nav `--text` |
| Secondary lines: captions, facts, credit, footnotes, listing head | Garamond | 19px, 24 in captions and footnotes, 32 elsewhere | `--text-2`; fact values `--text` |
| Plate caption title | Garamond +100 | 20px, 24 | `--text` |
| Inline data: hex values, counts, sizes, shapes, file names | Mono | `--mono-em`, line-height 1 | its context's |
| Listing and run command | Mono | 16px, 24 | the listing roles |
| Footnote marker | Garamond 600, lining figures | 0.62em, raised 0.55em | `--link` |

### Figures, caps and data

- Running text uses old-style figures. Lining figures go wherever an old-style 1 or 0 would read as ı or o: titles ("Rule 30"), footnotes, model names ("Opus 5.5"), identifiers ("Z64") and measurements. The notes renderer wraps such tokens in `.lnum`.
- Inline mono at `--mono-em` matches the serif's x-height, and `line-height: 1` keeps it from growing the line. Mono ligatures are off, so `->` stays as typed.
- Acronyms in running text are `<abbr>` in all-small-caps. The export format choices are UI labels and stay roman.
- Small caps come from the font only (`font-synthesis-small-caps: none`), and never go on text with figures: the small-cap 1 and 0 read as I and O.
- The prose measure holds 58 to 72 characters, with `text-wrap: pretty`. Hyphenation is for prose only, limited by `hyphenate-limit-chars`.
- Foreign titles carry `lang`, as in `<i lang="de">`.

## 4. Grid, spacing and breakpoints

- The unit is `--u`, 8px; `--l` (4u) is the line for UI text and prose. Captions, footnotes and listings run on 3u lines, the detail title on 6u and the "Source code" heading on 5u. Margins and paddings are whole units.
- Rules are 1px background gradients inside an existing padding, so they add no height.
- Plate boxes round their height up to the unit: the picture keeps its exact shape at the top, and the remainder below it is plate ground, outside the frame. Nothing is cropped.
- The page has a maximum width, a side gutter (`--gutter`) and no footer.
- The masthead, the index and About share one column pair (`--index-col` and the rest), so the nav, the plate grid and About's prose share a left edge.
- Grid columns are at least `--track` wide. A grid in another shape sets `--ratio` and its own `--track`, wider for the wide shapes and narrower for the tall ones, which take two columns on phones.
- On the detail page the plate spans the content width, capped so the plate and the label's first three lines (title, attribution, Download) fit one screen. On phones a tall shape takes the plate's shape instead, capped so the title, an attribution of up to two lines and Download fit under it (§6.3). Below it, the label sits left and the controls right, starting 2u lower so their rows share baselines with the label's.

| Query | Changes |
|---|---|
| `max-width: 84rem` | The shared-theme line moves under the nav. |
| `max-width: 60rem` | Phones and small tablets, what this file means by "on phones". The theme button, showing only its swatches, keeps a 44px target. |
| `max-width: 60rem` and `pointer: coarse` | The index's color row is one line that scrolls sideways. |
| `max-width: 28rem` | Narrow phones: the nav takes a row of its own under the brand and the swatches. |
| `pointer: coarse` | Hex fields at 16px, since iOS zooms in on a smaller focused field. |
| `prefers-reduced-motion: no-preference` | The fade when a plate is recolored, and the plate carried between a grid and its page (§6.3). |

## 5. Rules, borders and focus

| Element | Drawn as | Color |
|---|---|---|
| Masthead bottom, "Source code" heading | 1px background rule | `--rule-strong` |
| `.hair-t` rules between sections | 1px background rule at the top | `--rule` |
| Plate frame | `inset 0 0 0 1px` box-shadow on `.plate::after`, since paint containment clips anything outside; the picture's height, not the rounded plate's | `--plate-edge` |
| Picker | 1px border, its top edge on the masthead rule | `--rule-strong` |
| Text fields | 1px underline; 2px when invalid | `--control`; invalid `--link` |
| Facet checkbox | Square, 1px border; filled when checked | `--control`; checked `--text` |
| Dot leaders | radial-gradient dots | `--leader` |
| Swatch ring | 1px box-shadow | `--control` |
| Focus | 2px outline, offset 2px; plate links draw a 2px inset ring and underline the title | `--focus` |

## 6. Components

The rules each component keeps; what it does is in its `.astro` file and its client module. Class names match site.css.

### 6.1 Header and picker

- The theme button shows the preset name, or "custom", next to three swatches; its accessible name starts with the same word and spells out the colors: "fireproof theme: background #1C1B1A, foreground #DAD8CE, accent #CF6A4C" (WCAG 2.5.3). On phones only the swatches show.
- Swatches are small squares, each with a 1px `--control` ring so a swatch the color of the page stays visible. They are `<span>`s: an empty `<i>` would be italic.
- The picker is right-aligned to the gutter (full width on phones), its top border on the masthead rule, with a matte in the page color in place of a shadow.
- An invalid field, once left, gets a 2px accent underline and an error line in accent. Low contrast between the seeds is a warning in `--text`, so it does not read as a failure. All these messages share one polite live region.

### 6.2 Filter and results

- Set like a book index: entries with dot leaders and mono counts under small-caps legends, each row one full-width target, lowercase and sorted by label.
- An entry that matches no piece, or a share of them above `NARROW_SHARE`, is left out. A box that would add none is disabled, its term in `--text-dim` and its count hidden.
- The results line is the page's one live region: "234 wallpapers" or "4 of 234 wallpapers".
- On phones the filter is a closed disclosure whose summary lists the active terms; the color row stays above the grid, one line that scrolls sideways.

### 6.3 Plates and the detail spread

- A plate is a link named by its title around a figure with the piece's alt text; the caption is a tombstone (title, version count, attribution).
- Before JavaScript runs, a plate is an empty box of the grid's shape on `--seed-bg`, and an inline script sets the shape before first paint, so nothing reflows.
- Detail source order is label, controls, notes, so on a phone the export panel comes straight after the label.
- A composed shape sits in a 1px `--text` frame. A cropped one shows the crop window: a 1px `--text` frame with everything outside dimmed by 55% `--bg`; the range input stays the keyboard control.
- A piece with a motif has an invisible handle over it on the plate, framed 1px `--text` while hovered or touched, with a corner square that resizes the motif about the opposite corner. Only the handle takes `touch-action: none`, and the rest of the plate `pan-y`, so one finger elsewhere scrolls the page and two pinch the motif. The Across, Down and Scale ranges are the keyboard control; on phones they sit just under the plate, which shrinks so they share the first screen with it. Each range's button has a fixed slot, so the range never changes width, and a button that hides under focus hands it to its range.
- Only the carried plate gets a view transition; every other link changes the page at once.

### 6.4 Label, footnotes and controls

- Every row after the title is a whole `--l` line, so the label shares baselines with the controls.
- Attribution: a recreation reads "after {author}, *{title}*, {year}"; an inspiration, when there is no recreation, "inspired by {author}, *{title}*". Several are joined "A, B and C", a repeated author is left out ("Mark Rothko, *No. 61* and *Seagram murals*"), and missing fields are dropped. References and data appear only as footnotes.
- The credit is "Made with {model credit name}" or "Made by {author}". A CC0 piece shows no license line; a fan work shows the fan-work disclaimer (wallpapers.md, Licensing).
- Footnotes are numbered in lining figures, with no kind label; a topic stands in a title's place, in roman. The `:target` entry gets a 2px `--link` bar in the margin.
- Download is a row of text: the underlined word, then the format and size ("PNG, 2560×1440"), then "for your screen" when it is. The page starts on the visitor's screen size as PNG. Hints sit under their row in `--text-2`; choices the browser can't make fade to `--text-dim`.

### 6.5 Source code

- A disclosure that starts closed, its summary the heading with a mono "+" at the right.
- Shiki with a CSS-variables theme (§2). To keep accent to keywords and strings, `keyword.operator` takes the punctuation color and `meta.function-call.arguments` the foreground.
- Both `pre` blocks scroll sideways and are focusable named regions.

### 6.6 About and 404

- About: a few short paragraphs. No piece counts, colophon or font credits; the site has no footer.
- The 404 page uses the same layout: "Not found", one sentence and a link to the index.

### 6.7 Forced colors and no JavaScript

- The forced-colors block redraws what backgrounds and box-shadows draw with system colors; rules become real borders, shifting the rhythm by a pixel in that mode only.
- `@media (scripting: none)` hides every control that needs JavaScript. Plates take fireproof's ground, because the `<noscript>` image is always the fireproof template.

## 7. Voice

Visible copy is the page text, aria-labels, alt text and meta descriptions, plus what each wallpaper supplies. The word rules, the banned terms and their enforcement are in wallpapers.md (Copy); this section adds the site's voice.

- Use the words a visitor would use: theme, colors, shape, your screen, versions, source code.
- UI text is a label or one plain sentence. No semicolon chains or "a · b · c" strings; a middle dot only separates buttons.
- No hint lines and no readouts the visitor did not ask for: no keyboard hints, contrast ratios, light or dark mode, or how closely an export matches the screen.
- Licenses are named once, on About; only a piece under another license says anything on its own page.
- Filter entries, sort options and "clear" are lowercase; headings, buttons and messages are in sentence case.

## 8. Rejected patterns

Beyond what §1 and §7 rule out:

- Hero sections, taglines with calls to action, cards, gradient text, icon libraries, pill chips, plate numbers, a footer.
- Boxed buttons: a text button, Download included, is underlined text.
- Serif text under 19px, other than the footnote marker.
- Full capitals for headings or acronyms, and synthesized small caps.
- Focus suppression without a replacement.
- `display: none` on a live region at any width.
- A `<div>` with `aria-label` (the name is dropped), an `aside` for primary controls, unnamed `fieldset`s.
- `maxlength` on the hex fields: it truncates a pasted token before any handler runs.
- `content-visibility` with an intrinsic inline size: the grid track could no longer shrink to 320px (WCAG 1.4.10).
- Measures in `ch` (in Garamond, the narrow tabular zero), and `hyphens: auto` without limits.
- Cropping a plate to fit the grid, or framing it with an outline or outside stroke. A plate cropped to the Shape the visitor chose shows what that export would be, and is not this.
- Inline SVG plates (architecture.md, Recoloring).
- A detail image with `alt=""` plus `aria-describedby`: an empty alt makes the image presentational, and the description goes with it.
