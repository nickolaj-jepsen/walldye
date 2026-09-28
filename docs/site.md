# walldye site: visual reference

How walldye.com looks and what it says: the visual system, the components and the rules for visible copy. [design.md](design.md) (Site) covers routing, behaviour, theming and export. `src/styles/site.css` holds the actual values; this file explains them, so that a change stays inside the system. Section numbers are stable, and code cites them as `docs/site.md §6.4`. `src/scripts/DOM.md` lists the hooks the client code relies on.

## 1. Principles

- An exhibition catalogue in the manner of the 1968 computer-art catalogues: hairline rules instead of cards, type-only chrome, and the plates carry all the colour. No plate numbers.
- Legibility first. Prose is 22px, UI text 20px and secondary lines 19px. EB Garamond's x-height is 0.405em, so these read like 17, 16 and 15px in a sans.
- Text is `--text` (fg) or `--text-2` (fg_alt) and nothing lighter. muted draws only the dot leaders; rules, frames and controls use the ui greys.
- Accent appears only in the focus ring, the footnote markers and the footnote target bar, error text and the invalid-field underline, and the listing's keywords (accent) and strings (accent_hi).
- Italic marks titles of works and nothing else: *Schotter*, *Generative Computergraphik*.
- One convention for "current": text colour plus a 1px underline 0.3em below the baseline, for the nav, sort, the export choices, the versions, the pressed preset and the open theme button. Resting in-text links carry a 1px underline in `--link-line`.
- Every vertical measure is a multiple of the 8px unit (§4), and rules take no layout space.
- Every text role meets 4.5:1 against its ground in every theme, through the contrast guard (§2).

## 2. Colour roles

Before first paint the theme boot writes these custom properties inline on `<html>`, with `data-regime="dark|light"`. `cssVars()` in `src/lib/theme.ts` computes them and `GUARDED` lists the guarded ones. site.css repeats the fireproof values in `:root`, and flexoki-light's under `prefers-color-scheme: light`, for visitors without JavaScript.

| Property | Token | Guard | fireproof | flexoki-light |
|---|---|---|---|---|
| `--seed-bg`, `--seed-fg`, `--seed-accent` | the raw seeds | none: wallpapers and plate grounds | `#1C1B1A` `#DAD8CE` `#CF6A4C` | `#FFFCF0` `#100F0F` `#BC5215` |
| `--bg`, `--bg-alt` | bg, bg_alt | grounds | `#1C1B1A` `#282726` | `#FFFCF0` `#E7E4D9` |
| `--text` | fg | 4.5:1 on bg | 12.03 | 18.62 |
| `--text-2` | fg_alt | 4.5:1 on bg | 8.37 | 10.90 |
| `--text-dim` | fg_alt faded a quarter towards bg | 4.5:1 on bg | `#908E88` 5.25 | `#6D6B66` 5.18 |
| `--link` | accent | 4.5:1 on bg | `#CF6A4C` 4.77 | `#BC5215` 4.69 |
| `--control`, `--link-line` | ui_hi | 3:1 on bg | `#676764` 3.03 | `#888680` 3.54 |
| `--focus` | accent | 3:1 on bg | as `--link` | as `--link` |
| `--leader` | muted | none: dot leaders are not text | `#878580` | `#787771` |
| `--rule` | ui_alt (dark), ui (light) | exempt | `#403E3C` | `#CFCCC3` |
| `--rule-strong` | ui_hi (dark), ui_alt (light) | exempt | `#575653` | `#B7B4AC` |
| `--plate-edge` | ui | exempt | `#343331` | `#CFCCC3` |
| `--shiki-background` | bg_alt | ground of the listing | `#282726` | `#E7E4D9` |
| `--shiki-foreground`, `-function`, `-link`, `-constant`, `-parameter` | fg | 4.5:1 on bg_alt | 10.43 | 15.03 |
| `--shiki-token-keyword` | accent | 4.5:1 on bg_alt | `#D27457` 4.53 | `#A94913` 4.52 |
| `--shiki-token-string`, `-string-expression` | accent_hi | 4.5:1 on bg_alt | `#E08A6E` 5.70 | `#8C3F13` 5.82 |
| `--shiki-token-comment`, `-punctuation`, `--listing-gutter` | fg_alt | 4.5:1 on bg_alt | 7.26 | 8.80 |

- When a colour falls short, the guard moves it towards black or white, whichever contrasts more with the surface, by the smallest amount that passes (design.md, Site theming). In fireproof that nudges `--control` (ui_hi `#575653` is under 3:1) and the listing keyword (accent is 4.13:1 on bg_alt).
- Rules step up one grey in the light regime, because ui_alt on a light ground is too faint to read as a rule.
- Text sits on `--bg`, except in the listing, which sits on `--bg-alt`. No other tinted surface carries text.

## 3. Type

### Faces

- EB Garamond, roman and italic, weights 400 to 800, for everything but data. Walldye Mono, a renamed subset of Monaspace Krypton with weights 400 to 700, for data.
- Self-hosted woff2 through Astro's fonts API with `fontProviders.local()` (astro.config.mjs), `display: swap`, with the fallback metric overrides kept so the swap does not re-wrap captions. The roman and the mono are preloaded, the italic is not. The CSS variables are `--serif` and `--mono`.
- The subset (design.md, Site > Direction; `scripts/fonts/`) keeps smcp, c2sc, onum, lnum, pnum, tnum and case, and both Garamond faces carry the thin space, the hair space and U+2060. No face has U+202F, and the mono has none of U+2009, U+200A, U+2011 or U+2060, so keep those characters out of mono text and hold a thin-spaced group together with `.nowrap`.
- `sups` is left out: it costs about 19 kB per Garamond face for one footnote marker.
- The OFL notices ship inside the woff2 files, so the site shows no font credit.

### Scale

Garamond runs at weight 400 on light grounds and 450 on dark ones (`--wt`), because grayscale smoothing thins its hairlines on a dark ground. The roles marked +100 take 500 and 550. Nothing is smaller than 19px except inline mono and the footnote marker.

| Role | Face | Size and line | Colour |
|---|---|---|---|
| Prose: notes, About, the detail description | Garamond | 22px (21 on phones), 32 | `--text` |
| Detail title | Garamond, lining figures, -0.005em | 40px (34), 48 | `--text` |
| "Source code" heading | Garamond | 28px (22), 40 | `--text` |
| Masthead "Walldye" | Garamond +100, small caps, 0.06em | 28px (22, and 20 at 320px), 32 | `--text` |
| UI text, the body default: facet entries, search, sort, the results line, controls, attribution, picker, shared-theme line | Garamond | 20px, 32 | `--text-2`; hovered, checked or current `--text` |
| Small-caps heads: legends, section heads, nav, picker heads | Garamond all-small-caps, 0.08em | 19px, 32 | `--text-2`; the current nav entry `--text` |
| Secondary lines: caption lines, facts, credit, footnotes, listing head | Garamond | 19px, 24 in captions and footnotes, 32 elsewhere | `--text-2`; fact values `--text` |
| Plate caption title | Garamond +100 | 20px, 24 | `--text` |
| Inline data: hex values, counts, sizes, shapes, file names, preset names | Mono | 0.79em of its context, line-height 1 | its context's |
| Listing and run command | Mono | 16px, 24 | the listing roles, `--text` |
| Footnote marker | Garamond 600, lining figures | 0.62em, raised 0.55em | `--link` |

### Figures, caps and data

- Running text uses old-style proportional figures. Lining figures go wherever an old-style 1 or 0 would read as ı or o: titles ("Rule 30"), footnotes, model names and numbers in prose ("Opus 5.5", "Z64"), measurements. The notes renderer wraps such tokens in `.lnum` by itself.
- Mono is for standalone data. Inline mono is set at `--mono-em`, 0.79em, which gives it the serif's x-height (0.514em against 0.405em), and at `line-height: 1`, so it cannot grow the line. Ligatures are off in mono text, so `->` and `==` stay as typed.
- Acronyms in running text are `<abbr>` in all-small-caps (SVG, PNG, JPEG). The export format choices are UI labels and stay roman.
- Small caps come from the font only (`font-synthesis-small-caps: none`). WebKit on Linux otherwise draws scaled capitals about a quarter smaller.
- Never set small caps on text with figures: EB Garamond's small-cap 1 and 0 read as I and O, which is why the results line is plain text.
- The prose measure is 28em, 58 to 72 characters at 22px, with `text-wrap: pretty`. Never size a measure in `ch`, which in Garamond is the narrow tabular zero.
- Hyphenation is on for prose only, limited by `hyphenate-limit-chars: 7 3 3`.
- Foreign titles carry `lang`, as in `<i lang="de">`.

## 4. Grid, spacing and breakpoints

- The unit is `--u`, 8px, and `--l` (4u, 32px) is the line for UI text and prose. Captions, footnotes and listings run on 3u lines, the detail title on 6u and the "Source code" heading on 5u. Margins and paddings are whole units, from 1u to 10u; the masthead grows to 14u or 18u while the shared-theme line takes a row of its own.
- Rules are 1px background gradients inside an existing padding, so they add no height.
- Plate boxes round their height up to the unit (`round(up, 100cqw * 9 / 16, u)`) and letterbox the 0 to 7px remainder with the plate ground. Nothing is cropped.
- The page is at most 110rem wide, with a side gutter of `clamp(1rem, 4vw, 3.5rem)`, a 10u bottom padding and no footer.
- The masthead, the index and About share one column pair, `18rem | 1fr` with a 4rem gap, so the nav, the plate grid and About's prose share a left edge. At 18rem the longest facet entry still gets a leader.
- The plate grid is `repeat(auto-fill, minmax(min(100%, 24rem), 1fr))` with a 4u column gap and a 6u row gap (5u on phones): one column up to about 1024px wide, two from 1280, three from about 1680.
- On the detail page the plate spans the content width, capped by the viewport height at `min(100%, max(20rem, (100svh - 29u) * 16 / 9))`, so the plate and the first two lines of the label fit one screen. Below it is a `1fr | 30rem` grid with a 6rem gap: the label on the left, at most 42rem wide, and the controls on the right. The controls start 2u lower, so their 32px rows share baselines with the label's rows after the 48px title.

| Query | Changes |
|---|---|
| `max-width: 84rem` | The shared-theme line moves to a second header row, under the nav. |
| `max-width: 60rem` | Phones and small tablets: the theme button shows only its swatches, with a 44px target; the filter becomes a disclosure, in two columns from about 600px; one plate column; the detail page stacks label, controls and notes; prose 21px, title 34px, column gap 3u. |
| `max-width: 22rem` | 320px screens: a 20px brand and tighter header gaps keep brand, nav and swatches on one row. |
| `pointer: coarse` | Hex fields at 16px, since iOS zooms in on a focused field below 16px. |
| `prefers-reduced-motion: no-preference` | The 0.2s fade when a plate is recoloured; none otherwise. |
| `scripting: none` | §6.13. |
| `forced-colors: active` | §6.12. |

## 5. Rules, borders and focus

| Element | Drawn as | Colour |
|---|---|---|
| Masthead bottom | 1px background at the bottom | `--rule-strong` |
| `.hair-t` rules: facts, Notes and Sources heads, picker groups, the Export head, the phone controls and filter summary | 1px background at the top | `--rule` |
| "Source code" heading | 1px background at the top | `--rule-strong` |
| Plate frame | `inset 0 0 0 1px` box-shadow on `.plate::after`, since paint containment clips anything drawn outside | `--plate-edge` |
| Picker | 1px border, its top edge on the masthead rule | `--rule-strong` |
| Text fields | 1px underline; 2px when invalid | `--control`; invalid `--link` |
| Facet checkbox | 12px square, 1px border; filled when checked | `--control`; checked `--text` |
| Dot leaders | radial-gradient dots 0.45em apart | `--leader` |
| Swatch ring | `0 0 0 1px` box-shadow | `--control` |
| Focus | `outline: 2px solid`, offset 2px; plate links draw a 2px inset ring on the plate and underline the title instead | `--focus` |

There is no border radius and no drop shadow anywhere. The only box-shadows are 1px rings, inset frames and the picker's matte in the page colour.

## 6. Components

Class names match site.css. Each subsection names the component that renders it.

### 6.1 Header

`src/components/Masthead.astro`: the brand, the nav (Index, About), the shared-theme line and the theme button.

- The theme button shows the preset name, or "custom" when the colours match none, next to three swatches. Its accessible name starts with the same word and spells out the colours: "fireproof theme: background #1C1B1A, foreground #DAD8CE, accent #CF6A4C" (WCAG 2.5.3). `aria-expanded` follows the popover's `toggle` event and drives the underline.
- The first header row is fixed at 4u, so baseline alignment of the 28px brand cannot grow it.
- The shared-theme line reads "You're looking at a shared theme." followed by "Keep it · Back to yours". It sits beside the theme button from 84rem up, under the nav below that, and across the full width on phones, where the two buttons drop to a line of their own.
- On phones the preset name is hidden, and negative margins give the button a 44px target without growing the header row.

### 6.2 Swatches

Three squares of 0.875rem (0.7em in the preset list), 3px apart, each with a 1px `--control` ring, so a swatch the colour of the page stays visible. They are `<span>`s: an empty `<i>` would still be italic.

### 6.3 Picker

`src/components/Picker.astro`, a `popover` with `role=dialog`. "Themes" lists the presets as index entries (the name in mono, a leader, three swatches, `aria-pressed`); "Colours" has the Background, Foreground and Accent hex fields, each with its swatch; "Copy link" ends it.

- It is fixed, right-aligned to the gutter (full width between the gutters on phones), with its top border laid on the masthead rule. A matte in the page colour clears the captions beside and below it, in place of a drop shadow.
- The fields have no `maxlength`, so a pasted theme token fills all three.
- An invalid field gets `aria-invalid`, a 2px accent underline and `aria-describedby` pointing at "Use a hex colour, like #CF6A4C.", set in accent. When background and foreground fall under 3:1, "The background and foreground are too close, so wallpapers will be hard to see." appears in `--text`, so it does not read as a failure. Both sit in one polite live region.
- Escape reverts unapplied edits before the popover closes. Nothing on the page says so.
- There is no readout of light or dark, or of contrast.

### 6.4 Filter and results

`src/pages/index.astro`: search, sort, the facet fieldsets and the results line.

- It is set like a book index: 20px entries in `--text-2` with dot leaders and mono counts, under 19px small-caps legends. Each 32px row is one full-width target. Entries are lowercase and sorted by label.
- The groups are Technique, Subject, "Inspired by" (the lineage facet) and Other. Labels come from `src/lib/labels.ts`; taxonomy.yaml keeps the slugs. homage and fan-work get no entry: the caption's "after ..." line and the fan-tribute line already cover them.
- Other holds the computed facets: "has references", "works in light themes", "fits any screen", "has source code", "made with Claude" and "human-made". An entry that matches every piece or none is left out, since it cannot narrow the grid.
- Counts are live. Each shows how many pieces its box would add given the other checked boxes (OR within a facet, AND across facets). A box that would add none is disabled: box and leader at 0.75 opacity, the term in `--text-dim`, the count hidden.
- The results line is the page's one live region (`role=status`, set after the first render, and written only when its text changes). It shows at every width and reads "234 wallpapers" or "4 of 234 wallpapers" in plain text with lining figures. When nothing matches, "Try fewer filters or a shorter search." appears under it. "clear" shows while anything is checked or searched; it is a `type=reset` button tied to the form by `form=`.
- From 60rem up the disclosure is held open and its summary hidden. On phones it starts closed, and the summary shows "Filter", the active terms and a plus or minus sign whose alternative text is empty.
- Search matches the title, the description and the sources' authors and titles, through `data-search`.

### 6.5 Plate and caption

`src/components/Plate.astro` and `PlateBox.astro`.

- One `<li>` per piece: a link named by its title (`aria-labelledby`) around a figure. The image's alt text is the description.
- The caption is a tombstone: the title (an `h2`), "N versions" when the piece has published named variants ("(N draft)" is added in `astro dev`), the dark-only note when it applies ("Made for dark themes, shown here with your colours swapped"), then the attribution. `aria-describedby` points at the version count and the attribution.
- A dark-only piece under light colours gets `data-dark-only`, and its plate ground becomes `--seed-fg` to match its swapped render.
- Before JavaScript runs, a plate is an empty 16:9 box on `--seed-bg`, with a `<noscript>` image of the untouched template.
- Grid items use `content-visibility: auto` with an intrinsic block size only, so the track can still shrink to 320px (WCAG 1.4.10).
- The frame is an inset box-shadow on `.plate::after`. Keyboard focus draws a 2px inset ring on the plate and underlines the title.

### 6.6 Detail spread and crop window

`src/pages/[slug].astro`.

- Source order is label, controls, notes, so on a phone the export panel comes straight after the label.
- A shape the piece composes for shows its own template, centred in the 16:9 box inside a 1px `--text` frame.
- Any other shape shows the crop window: a 1px `--text` frame with everything outside it dimmed by 55% `--bg`. For shapes narrower than 16:9 it spans the full height and moves sideways, with its handle on the bottom edge; for wider ones it spans the full width and moves up and down, with the handle on the right edge. Dragging it moves the range input, which stays the keyboard control.
- In fullscreen (the `f` key) the plate shows the wallpaper alone, centred.

### 6.7 Label

- In order: the title, the dark-only note, the attribution with its footnote markers, the description at 22px, the credit, a licence line when there is one, and the facts.
- Every row after the 48px title is a whole 32px line, so the label shares baselines with the controls.
- The credit is "Made with Claude Opus 5.5", taken from meta.yaml's `author`, or "Made by" and a name for a human-made piece. Figures in the name take lining numerals.
- A CC0 piece shows no licence. A fan work shows the disclaimer from design.md (Metadata) under the credit, and any other licence shows its plain-words line from `LICENCE_LINES` in `src/lib/labels.ts` (a CC BY recreation: "Free to use, with credit as given above."). No licence names or identifiers appear.
- The facts are Technique, Inspired by, Shape and Added, with keys in `--text-2` and values in `--text`. A facet value links to the index filtered by it when the index offers that filter. Shape reads "Any screen", or the composed shapes in mono followed by "(cropped for other screens)".
- There are no previous and next links. The header's Index link is the way back.

### 6.8 Footnotes

`src/components/Footnotes.astro`: the sources under "Sources", numbered, each "{author}, {title}, {year}." with the title linked when the source has a URL. Entries carry no kind label, since the caption already says which source the piece recreates. The numbers hang from a CSS counter in lining figures, on 24px lines 8px apart. A source cited in the caption gets a "Back to text" link that never wraps away from the entry's last word. The `:target` entry gets a 2px `--link` bar in the margin and a `--link` number, never a tinted background.

### 6.9 Versions, colours and export

`src/components/Controls.astro`, a labelled `section` rather than an `aside`, because these are primary controls.

- Versions, when the piece has published named variants: a radio group headed "Versions", one label per line, the default first.
- Colours: the three colours as swatch, hex value and role, then "Change", which opens the picker, and "Copy link".
- Export: rows on a `6.5rem | 1fr` key and value grid (6rem on phones) for Format, Shape, Crop (only for a cropped shape) and Size, then Download. "cropped from 16:9" shows under Shape for a cropped shape. The sizes change with the shape, and "your screen" is always last.
- Hints under a row, in `--text-2`: "This browser can't make WebP files.", "This browser can't draw a file that large.", and for pixel pieces whose squares will not land on whole pixels, "At this size the squares come out 3 or 4 pixels wide." Choices the browser cannot make fade to `--text-dim`.
- Download is one row of text, not a box: the underlined word in the key column and the file name as the value, which may wrap anywhere.
- Export errors go to a polite live region below it.

### 6.10 Source code

`src/components/SourceCode.astro` and `highlight.ts`.

- An appendix under the 28px "Source code" heading: the file path and line count with "Copy", the listing, then "Run it yourself" with its two commands.
- The listing is Shiki with a CSS-variables theme (§2): keywords in accent, strings in accent_hi, comments, docstrings, punctuation, operators and line numbers in fg_alt, everything else in fg. Two overrides keep accent rare: `keyword.operator` takes the punctuation colour (logical operators stay keywords), and `meta.function-call.arguments` takes the foreground.
- Line numbers come from a CSS counter on `.line`, and "Copy" reads the raw source from a `<template>`.
- Both `pre` blocks scroll sideways, are focusable named regions and take their focus outline at offset 0. On phones each command wraps with a hanging indent.
- A piece without a script shows "The script for this wallpaper has been lost." in place of all of this.
- Nothing under the run command says how closely a local render matches the site.

### 6.11 About and 404

- About's heading is a side head in the index column (19px small caps in `--text-2`), since the nav already names the page, and the prose starts level with it. Paragraphs after the first are indented, as in every prose block.
- The text is the maintainer in the first person, at most 110 words (design.md, Site > About).
- The 404 page uses the same layout: "Not found", one sentence and a link to the index.

### 6.12 Forced colours

Forced-colours mode drops backgrounds, gradients and box-shadows, and those draw the rules, the checkbox state, the slider, the field underlines, the swatches and the plate's focus ring. The block at the end of site.css redraws them with system colours. Rules become real borders there, so the rhythm shifts by a pixel in that mode only.

### 6.13 Without JavaScript

`@media (scripting: none)` hides what cannot work: the theme button, the filter, the colours and export column, and the source "Copy". Plates take fireproof's ground, because the `<noscript>` image is always the fireproof template.

## 7. Voice

Visible copy covers the page text, aria-labels, alt text and meta descriptions, and also meta.yaml's titles, descriptions and notes and the design.py source each page shows. Claude drafts it and the owner approves it. design.md (Copy rules) has the rules for descriptions and how they are enforced.

- Use the words a visitor would use: theme, colours, shape, your screen, versions, source code. Never describe how the site works inside.
- UI text is a label or one plain sentence. No semicolon chains, stacked colon clauses or "a · b · c" strings of terms; a middle dot only separates buttons, as in "Keep it · Back to yours".
- No hint lines. Escape in the picker and `f` on a detail page work without being advertised.
- No readouts the visitor did not ask for: contrast ratios, light or dark mode, how closely an export matches the screen.
- Licences in plain words, once. About says the wallpapers are "free to use unless their page says otherwise", and only a piece under another licence says anything on its own page.
- About is the maintainer speaking in the first person. Everything else is neutral.
- Descriptions are also the alt text, the detail page's lede and the meta description. One or two short sentences, at most 30 words, saying what is drawn and how, with the sentence shape varied from piece to piece. They are theme-neutral: no colour names, and no theme roles as nouns ("the accent"); say what is picked out, filled in or lit.
- Italic only for titles of works, never for hints, notes, placeholders, messages or labels.
- Filter entries, sort options and "clear" are lowercase. Headings, buttons and messages are in sentence case.

Never in visible copy:
- internal terms: regime, seed, token, native, hand-tuned, light-ready, preset, variant, param, slot, template, derived, guard, "has script", "AI-generated", "generator lost", "Appendix";
- licence names and identifiers: CC0, GPL, SPDX, OFL, LicenseRef-*;
- machinery numbers: contrast ratios, colour tolerances, pixel sizes in descriptions;
- keyboard hint lines;
- evaluative adjectives (stunning, mesmerising, elegant, timeless and the rest of the copy lint's list), and anything the avoid-ai-tropes check flags.

## 8. Rejected patterns

- Hero sections, taglines with calls to action, cards of any kind (rounded, shadowed or boxed), gradient text, icon libraries, pill chips, plate numbers.
- A site footer. The fonts need no visible credit, and About covers use.
- Boxed buttons. Download, Copy, Change, Copy link, clear, Keep it and Back to yours are all underlined text.
- Drop shadows (§5).
- Text in muted, or any text under 4.5:1 on its ground.
- Serif text under 19px, other than the footnote marker. Mono is sized by x-height instead.
- Italic for anything but titles of works.
- Small caps on text with figures, and full capitals for headings or acronyms. Use the font's own small caps, never synthesised ones; the subset must keep `smcp` and `c2sc`.
- Old-style figures in identifiers, titles and model numbers.
- Accent anywhere outside the places in §1.
- Tinted surfaces to mark state, such as a footnote target or a checked entry. They lower the contrast of the text on them; use a bar, a colour or an underline.
- Filter entries that cannot narrow the grid.
- `a:focus-visible { outline: none }`, or any focus suppression without a replacement.
- `display: none` on a live region at any width.
- A generic `<div>` with `aria-label` (the name is dropped), an `aside` for primary controls, unnamed `fieldset`s.
- `maxlength` on the hex fields: it truncates a pasted token before any handler runs.
- `content-visibility` with an intrinsic inline size.
- Measures in `ch`, and `hyphens: auto` without limits.
- Cropping a plate to fit the grid. Round the box up and letterbox it with the plate ground.
- Outlines or outside strokes for plate frames, which paint containment clips.
- Inline SVG plates: ids such as `lg1` repeat across templates (design.md, Recolouring pipeline).
- A detail image with `alt=""` plus `aria-describedby`. An empty alt makes the image presentational, and the description goes with it.
- Neighbour links or arrow-key navigation between pieces.
