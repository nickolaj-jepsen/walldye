# walldye site

How walldye.com looks and what it says. `src/styles/site.css` holds the values; this file explains them, so a change stays inside the system. [architecture.md](architecture.md) (The site) covers routing, theming and export internals, and `src/client/DOM.md` the hooks the client code relies on.

## 1. Principles

- An exhibition catalog in the manner of the 1968 computer-art catalogs: hairline rules instead of cards, type-only chrome, and the plates carry all the color.
- Legibility first: EB Garamond's small x-height makes the 22, 20 and 19px of §3 read like 17, 16 and 15px in a sans.
- Text is `--text` (fg) or `--text-2` (fg_alt), at 4.5:1 or better in every theme (§2). muted draws only the dot leaders; rules, frames and controls use the ui grays.
- Accent appears only in the focus ring, the footnote markers and target bar, error text and the invalid-field underline, and the listing's keywords and strings.
- Italic marks titles of works and nothing else.
- One convention for "current": text color plus a 1px underline 0.3em below the baseline (nav, sort, shape, export choices, versions, the pressed theme name, the open theme button); under swatch buttons (the index's and the picker's), a 1px `--text` line under the swatches. Resting in-text links carry a 1px underline in `--link-line`.
- Every vertical measure is a multiple of the 8px unit (§4), and rules take no layout space.
- No border radius, no drop shadow, no tinted surface to mark state.

## 2. Color roles

`cssVars()` in `src/lib/theme.ts` computes these for each theme, and `GUARDED` lists the guarded ones. site.css repeats the fireproof values in `:root`, and flexoki-light's under `prefers-color-scheme: light`, for visitors without JavaScript.

| Property | Token | Guard |
|---|---|---|
| `--seed-bg`, `--seed-fg`, `--seed-accent` | the raw seeds | none: wallpapers and plate grounds |
| `--bg`, `--bg-alt` | bg, bg_alt | grounds |
| `--text` | fg | 4.5:1 on bg |
| `--text-2` | fg_alt | 4.5:1 on bg |
| `--text-dim` | fg_alt faded a quarter towards bg | 4.5:1 on bg |
| `--link` | accent | 4.5:1 on bg |
| `--control`, `--link-line` | ui_hi | 3:1 on bg |
| `--focus` | accent | 3:1 on bg |
| `--leader` | muted | none: dot leaders are not text |
| `--rule` | ui_alt (dark), ui (light) | exempt |
| `--rule-strong` | ui_hi (dark), ui_alt (light) | exempt |
| `--plate-edge` | ui | exempt |
| `--shiki-background` | bg_alt | ground of the listing |
| `--shiki-foreground`, `-function`, `-link`, `-constant`, `-parameter` | fg | 4.5:1 on bg_alt |
| `--shiki-token-keyword` | accent | 4.5:1 on bg_alt |
| `--shiki-token-string`, `-string-expression` | accent_hi | 4.5:1 on bg_alt |
| `--shiki-token-comment`, `-punctuation`, `--listing-gutter` | fg_alt | 4.5:1 on bg_alt |

## 3. Type

### Faces

- EB Garamond, roman and italic, weights 400 to 800, for everything but data. Walldye Mono, a renamed Monaspace Krypton subset, weights 400 to 700, for data: seeds, colors, sizes, file names.
- Self-hosted woff2 through Astro's fonts API, `display: swap`, with fallback metric overrides so the swap does not re-wrap captions. The roman and the mono are preloaded.
- The subsets come from `scripts/fonts/` and keep smcp, c2sc, onum, lnum, pnum, tnum and case. No face has U+202F, and the mono lacks U+2009, U+200A, U+2011 and U+2060, so keep those out of mono text and hold a thin-spaced group together with `.nowrap`.

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
| Inline data: hex values, counts, sizes, shapes, file names | Mono | 0.79em, line-height 1 | its context's |
| Listing and run command | Mono | 16px, 24 | the listing roles |
| Footnote marker | Garamond 600, lining figures | 0.62em, raised 0.55em | `--link` |

### Figures, caps and data

- Running text uses old-style figures. Lining figures go wherever an old-style 1 or 0 would read as ı or o: titles ("Rule 30"), footnotes, model names ("Opus 5.5"), identifiers ("Z64") and measurements. The notes renderer wraps such tokens in `.lnum`.
- Inline mono at 0.79em (`--mono-em`) matches the serif's x-height, and `line-height: 1` keeps it from growing the line. Mono ligatures are off, so `->` stays as typed.
- Acronyms in running text are `<abbr>` in all-small-caps. The export format choices are UI labels and stay roman.
- Small caps come from the font only (`font-synthesis-small-caps: none`), and never go on text with figures: the small-cap 1 and 0 read as I and O.
- The prose measure is 28em, 58 to 72 characters, with `text-wrap: pretty`. Hyphenation is for prose only, limited by `hyphenate-limit-chars: 7 3 3`.
- Foreign titles carry `lang`, as in `<i lang="de">`.

## 4. Grid, spacing and breakpoints

- The unit is `--u`, 8px; `--l` (4u) is the line for UI text and prose. Captions, footnotes and listings run on 3u lines, the detail title on 6u and the "Source code" heading on 5u. Margins and paddings are whole units.
- Rules are 1px background gradients inside an existing padding, so they add no height.
- Plate boxes round their height up to the unit: the picture keeps its exact shape at the top, and the remainder below it is plate ground, outside the frame. Nothing is cropped.
- The page is at most 110rem wide, with a side gutter of `clamp(1rem, 4vw, 3.5rem)` and no footer.
- The masthead, the index and About share one `18rem | 1fr` column pair, so the nav, the plate grid and About's prose share a left edge.
- Grid columns are at least 18rem (`--track`): two from about 1045px, three from about 1390 and four from about 1710. A grid in another shape (§6.4) sets `--ratio` and `--track`: 26rem for 21:9, 40rem for 32:9 and 12rem for the tall shapes, which take two columns on phones.
- On the detail page the plate spans the content width, capped so the plate and the label's first three lines (title, attribution, Download) fit one screen. On phones a tall shape takes the plate's shape instead, capped so the title, an attribution of up to two lines and Download fit under it (§6.6). Below it, the label (at most 42rem) sits left and the controls (30rem) right, starting 2u lower so their rows share baselines with the label's.

| Query | Changes |
|---|---|
| `max-width: 84rem` | The shared-theme line moves under the nav. |
| `max-width: 60rem` | Phones and small tablets: the theme button shows only its swatches, with a 44px target; the filter becomes a disclosure; one plate column, two for tall shapes down to 320px; the detail page stacks label, controls and notes, shows a tall shape in the plate; prose 21px, title 34px. |
| `max-width: 60rem` and `pointer: coarse` | The index's color row is one line that scrolls sideways. |
| `max-width: 28rem` | Narrow phones: the nav takes a row of its own under the brand and the swatches. |
| `pointer: coarse` | Hex fields at 16px, since iOS zooms in on a smaller focused field. |
| `prefers-reduced-motion: no-preference` | The 0.2s fade when a plate is recolored, and the plate carried between a grid and its page (§6.6). |

## 5. Rules, borders and focus

| Element | Drawn as | Color |
|---|---|---|
| Masthead bottom, "Source code" heading | 1px background rule | `--rule-strong` |
| `.hair-t` rules: facts, Notes and Sources heads, picker groups, the Export head, phone controls and filter summary | 1px background rule at the top | `--rule` |
| Plate frame | `inset 0 0 0 1px` box-shadow on `.plate::after`, since paint containment clips anything outside; the picture's height, not the rounded plate's | `--plate-edge` |
| Picker | 1px border, its top edge on the masthead rule | `--rule-strong` |
| Text fields | 1px underline; 2px when invalid | `--control`; invalid `--link` |
| Facet checkbox | 12px square, 1px border; filled when checked | `--control`; checked `--text` |
| Dot leaders | radial-gradient dots 0.45em apart | `--leader` |
| Swatch ring | 1px box-shadow | `--control` |
| Focus | 2px outline, offset 2px; plate links draw a 2px inset ring and underline the title | `--focus` |

## 6. Components

Class names match site.css.

### 6.1 Header

`src/components/Masthead.astro`: the brand, the nav (Index, About, GitHub), the shared-theme line and the theme button.

- The theme button shows the preset name, or "custom" when the colors match none, next to three swatches, and opens the picker. Its accessible name starts with the same word and spells out the colors: "fireproof theme: background #1C1B1A, foreground #DAD8CE, accent #CF6A4C" (WCAG 2.5.3). On phones only the swatches show.
- The shared-theme line reads "You're looking at a shared theme." then "Keep it · Back to yours".

### 6.2 Swatches

Three squares of 0.875rem (0.7em in the preset list), 3px apart, each with a 1px `--control` ring, so a swatch the color of the page stays visible. They are `<span>`s: an empty `<i>` would be italic.

### 6.3 Picker

`src/components/Picker.astro`, a `popover` with `role=dialog`. "Themes" lists the families as index entries (name in mono, leader, swatches, `aria-pressed`); "Colors" has the Background, Foreground and Accent hex fields, each with its swatch, then "Import"; "Copy link" ends it.

- A family with a light preset shows its name, which follows the system scheme, then a swatch button for each preset in a dark column and a light column. A lone preset is one button, its swatches in the dark column.
- Right-aligned to the gutter (full width on phones), its top border on the masthead rule, with a matte in the page color in place of a shadow.
- Fields take 3 or 6 digits, with or without `#`, and a pasted theme token fills all three. Valid input applies after 250 ms; Escape reverts unapplied edits. Each swatch opens the browser's color picker, whose choice fills the field; its hit area is 24px, its focus ring the swatch's.
- Import reads a pasted terminal or base16 theme into the three fields, which then apply as typed (`src/lib/import-theme.ts`); the hex fields accept the same paste. Text with no colors gets an error line in accent.
- An invalid field, once the visitor leaves it, gets a 2px accent underline and an error line in accent. Background and foreground under 3:1, or an accent within `NEAR_ACCENT` of either, get a warning in `--text`, so it does not read as a failure. All these messages sit in one polite live region.

### 6.4 Filter and results

`src/pages/index.astro`: search, sort, the facet fieldsets and the results line.

- Set like a book index: 20px entries with dot leaders and mono counts under small-caps legends, each row one full-width target, lowercase and sorted by label.
- The groups are Technique, Subject, "Inspired by" (the lineage facet) and Other, which holds the computed facets: "has references", "fits any screen", "has source code", "made with Claude" and "human-made". Labels come from `src/lib/labels.ts`. An entry that matches no piece or more than nine in ten (`NARROW_SHARE`) is left out, since it would barely narrow the grid.
- Counts are live: each shows how many pieces its box would add (OR within a facet, AND across facets). A box that would add none is disabled, its term in `--text-dim` and its count hidden.
- Search matches the title, the description and the sources' authors, titles and topics. Sort is featured, newest, popular (views, recent ones weighted up), most viewed or title (`comparePieces()` and `defaultSort()` in `src/lib/content.ts`); featured is left out when nothing is listed, and the view orders when there are no views.
- Shape (16:9, 16:10, 21:9, 32:9, 9:19.5, 10:16, in mono) shows every plate in that shape: a piece's own template when it composes for it, else its 16:9 template cropped around its focus, as the export would crop it. Plate links then open the piece in that shape. Phones start on their screen's nearest shape, and "clear" keeps the shape.
- Above the results line, "Colors" lists the families as swatch buttons (the family name is the accessible name and the tooltip), each showing the preset it would pick under the system scheme, then "Your own", which opens the picker. A click chooses the family, as its name does in the picker.
- The results line is the page's one live region: "234 wallpapers" or "4 of 234 wallpapers", with "Try fewer filters or a shorter search." under it when nothing matches. "clear" shows while anything is checked or searched.
- On phones the filter is a closed disclosure whose summary shows "Filter" and the active terms. It ends in "Show 25 wallpapers", which closes it and scrolls to its summary. The color row stays above the grid, one line that scrolls sideways on touch screens.

### 6.5 Plate and caption

`src/components/Plate.astro` and `PlateBox.astro`.

- One `<li>` per piece, showing the default version in the grid's shape: a link named by its title around a figure, with the piece's alt text. The same plates make up "See also" (§6.8), with h3 titles.
- The caption is a tombstone: the title, "N versions" when the piece has published named variants ("(N draft)" added in `astro dev`), then the attribution line of §6.7.
- Before JavaScript runs, a plate is an empty box of the grid's shape on `--seed-bg`, with a `<noscript>` image of the untouched 16:9 template. An inline script sets the index's shape before first paint, so the grid does not reflow.

### 6.6 Detail spread and crop window

`src/pages/[slug].astro`.

- Source order is label, controls, notes, so on a phone the export panel comes straight after the label.
- A shape the piece composes for shows its own template, centered in the 16:9 box inside a 1px `--text` frame.
- Any other shape is cropped from 16:9 and shows the crop window: a 1px `--text` frame, everything outside it dimmed by 55% `--bg`. It spans the full height and moves sideways for shapes narrower than 16:9, or the full width and moves up and down for wider ones, starting centered on the piece's focus. Dragging it moves the range input, which stays the keyboard control.
- On phones a tall shape (9:19.5, 10:16) sets the plate in that shape, centered. A cropped one shows the crop itself, which a sideways drag on the plate moves, and the crop window moves to a 16:9 map over the Crop range.
- `f` toggles fullscreen, showing the wallpaper alone. It ignores fields, sliders, focused code, editable content and modified keys.
- Opening a piece from a grid (the index or "See also") carries its plate onto the spread in 0.3s while the page crossfades, and going back to the index carries it to its place in the grid. The picture being carried stays whole, and the arriving one fades in over it once its colors are drawn. When the two show it in different shapes, the pictures are cropped to the moving frame. Every other link changes the page at once.

### 6.7 Label

- In order: the title, the attribution with its footnote markers, the Download line (§6.10), the description at 22px, the credit, a license line when there is one, the facts, then the notes as Markdown. Every row after the title is a whole 32px line, so the label shares baselines with the controls.
- The attribution: a recreation reads "after {author}, *{title}*, {year}"; an inspiration, when there is no recreation, "inspired by {author}, *{title}*". References and data appear only as footnotes. Several are joined "A, B and C", a work by the same author as the one before leaves the name out ("Mark Rothko, *No. 61* and *Seagram murals*"), and missing fields are dropped.
- The credit is "Made with Claude Opus 5.5", from the credit name taxonomy.yaml gives meta.yaml's `model`, or "Made by {author}".
- A CC0 piece shows no license. A fan work shows the fan-work disclaimer (wallpapers.md, Licensing); any other license shows its plain-words line from `LICENSE_LINES` in `src/lib/labels.ts`.
- The facts are Technique, Inspired by, Shape and Added. A facet value links to the index filtered by it when the index offers that filter. Shape reads "Any screen", or the composed shapes followed by "(cropped for other screens)".

### 6.8 See also

After the label, notes and sources, "See also" (a small-caps head over a `.hair-t` rule) shows up to four other pieces as index plates, those sharing the most facet values first (`relatedPieces()` in `src/lib/content.ts`); without any the section is left out. The plates follow the export panel's Shape, and so do their links.

### 6.9 Footnotes

`src/components/Footnotes.astro`: the sources under "Sources", numbered in lining figures, each "{author}, {title}, {year}." with the title linked when there is a URL; a topic stands in the title's place, in roman. No kind label. A source cited in the caption gets a "Back to text" link that never wraps away from the entry's last word. The `:target` entry gets a 2px `--link` bar in the margin and a `--link` number.

### 6.10 Versions, export and colors

`src/components/Controls.astro`, a labeled `section`.

- Versions, when the piece has published named variants: a radio group headed "Versions", the default first, then meta.yaml order, each its 16:9 picture in the current colors over its name, in a row. The picture is hidden from assistive tech, so the radio is named by the version alone. Choosing one swaps the plate, the description, the alt text, the file names and the run command, and writes `?v=<name>`; theme, shape and a placed crop are kept. An unknown or draft `?v=` shows the default.
- Export: Shape, Crop (for a cropped shape only, with "cropped from 16:9" under Shape), Size and Format (SVG, PNG, WebP, JPEG), then Download. The sizes per shape come from `EXPORT_SIZES` in `src/lib/content.ts`, with "your screen" last: the screen size times the device pixel ratio, at the nearest shape by |log ratio|. The page starts on it, as PNG, so a visitor who changes nothing downloads a file that fits their screen; a screen past the canvas limits starts on 16:9 at the default size.
- Colors: swatch, hex value and role for each of the three, then "Change", which opens the picker, and "Copy link".
- Hints under a row, in `--text-2`, say when the browser can't make WebP, when a size is past the canvas limits (`MAX_AREA`, `MAX_SIDE` in `src/lib/shape.ts`), and when a pixel piece's squares miss whole pixels. Choices the browser cannot make fade to `--text-dim`.
- Download is a row of text: the underlined word, then what it makes: the format and the size ("PNG, 2560×1440", or an SVG's shape), then "for your screen" when the size is the screen's. The file name, from `downloadName()` in `src/lib/content.ts`, is its tooltip. An SVG gets a `<title>` and a `<desc>` with the page, license and theme. Errors go to a polite live region below.
- A second Download sits under the attribution, reading the same, so the first screen always holds one; below 28rem it leaves out "for your screen" to stay on one line. It runs the same export, and a failure scrolls to the panel's error.

### 6.11 Source code

`src/components/SourceCode.astro` and `src/server/highlight.ts`.

- An appendix under the "Source code" heading, a disclosure that starts closed: its summary is the heading with a mono "+" (a minus when open) at the right. Inside: the file path and line count with "Copy", the listing, then "Run it yourself": a `git clone` line and the `uv run walldye render` command for the version, shape, crop and theme on screen, saving under the SVG download's name (`renderCommand()` in `src/lib/shape.ts`).
- The listing is Shiki with a CSS-variables theme (§2): keywords in accent, strings in accent_hi, comments, punctuation, operators and line numbers in fg_alt, everything else in fg. To keep accent rare, `keyword.operator` takes the punctuation color and `meta.function-call.arguments` the foreground.
- Both `pre` blocks scroll sideways and are focusable named regions. On phones each command wraps with a hanging indent.
- A piece without a script shows "The script for this wallpaper has been lost." instead.

### 6.12 About and 404

- About's heading is a side head in the index column, and the prose starts level with it.
- Three short paragraphs: what the site is and how the three colors work, how the wallpapers are made and checked, and the licenses with a link to the code. No piece counts, colophon or font credits; the site has no footer.
- Then the side head "What the site counts" and one paragraph: who counts page views, what the site counts itself, no cookies or stored addresses, and Global Privacy Control. It changes with `src/lib/events.ts`.
- The 404 page uses the same layout: "Not found", one sentence and a link to the index.

### 6.13 Forced colors

The forced-colors block at the end of site.css redraws what backgrounds and box-shadows draw (rules, checkbox state, slider, field underlines, swatches, the plate's focus ring) with system colors; rules become real borders, shifting the rhythm by a pixel in that mode only.

### 6.14 Without JavaScript

`@media (scripting: none)` hides the theme button, the filter, the index's color row, the controls column, the Download under the attribution, and the source "Copy". Plates take fireproof's ground, because the `<noscript>` image is always the fireproof template.

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
- Boxed buttons: Download, Copy, Change, Copy link, clear, Keep it and Back to yours are underlined text.
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
