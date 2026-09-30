# Wallpapers

What goes in a wallpaper's folder, and the rules for its metadata, words and license. [api.md](api.md) covers design.py, and [architecture.md](architecture.md) how a piece is built and shown.

## A wallpaper folder

```
wallpapers/<slug>/
  design.py     # one @design function (api.md)
  data/         # optional .json, .txt and .npy files, read with s.data()
  meta.yaml
  build/        # written by `walldye build`; gitignored
```

Legacy pieces have `source.svg` and `palette.yaml` in place of design.py (architecture.md, Legacy pieces). `uv run walldye new <slug> --model <model id>` scaffolds a folder with a starter design and a draft meta.yaml.

## meta.yaml

```yaml
title: Loose squares
description: A grid of squares grows more random column by column, after a 1968 plotter drawing by Georg Nees.
alt: Columns of square outlines, orderly at the left, tilt and scatter toward the right, where one filled square has broken away.
notes: |                     # optional Markdown, shown on the detail page
  ...
technique: [drafting]        # facets, from taxonomy.yaml
subject: []
lineage: [early-computer-art]
sources:
  - kind: inspiration        # recreation | inspiration | reference | data
    title: Schotter          # a work
    author: Georg Nees
    year: 1968
    url: https://...         # optional
    lang: de                 # optional, for a title or topic in another language
  - kind: reference
    topic: Random walk       # anything that is not a work
added: 2026-09-27
model: claude-opus-5-5       # a human-made piece has author: instead
license: CC-BY-4.0           # see Licensing
draft: true                  # until review approves it
proposed_facets: {}          # only while draft
variants:                    # only when design.py declares named variants
  default: {label: Sideways}
  settled: {label: Settled, alt: ..., draft: true}
```

- Facets: `technique`, `subject` and `lineage` take values from taxonomy.yaml, which gives each value the words the site shows for it. Agents never add values. They write `proposed_facets`, which `walldye review` accepts or declines, asking for the new value's label. The site adds computed facets of its own, such as "fits any screen" and "made with Claude".
- Sources: a work (a game, film, book, paper, artwork or named series of them) is a `title`, set in italics. Anything else (a technique, phenomenon, place, product, program or logo) is a `topic`, set upright, following Wikipedia's rule for italics. A source never has both. A maker with no single work is an `author` with neither. A folder with `data/` needs a `data` or `recreation` source saying where its files came from. URLs are optional; fetch each one before writing it, and CI checks them.
- Credit: exactly one of `model`, a model id with a credit name under `models:` in taxonomy.yaml, shown as "Made with Claude Opus 5.5", or `author`, shown as "Made by {author}".
- Variants: the keys are exactly `default` plus the names design.py declares. Each needs a `label` of one to four plain words, unique within the piece, naming what that version shows. A named variant has its own `alt`, since it draws something else, and may add `draft` and a `description`, which replaces the piece's while that version is shown, for when the version is a different thing (another sky) rather than another view of it.
- Slugs: lowercase words joined by single hyphens. The site's routes reserve about, index, t, og, fonts, 404, robots, sitemap*, favicon and anything starting with `_`.

`walldye check` enforces these rules at build; the content schema (`src/server/catalog/schema.ts`) checks only what a page needs to render.

## Copy

These rules cover everything a visitor reads that a wallpaper supplies: meta.yaml's titles, descriptions, alt texts, notes and version labels, and design.py's docstring and comments, since the page shows the source. The site's own text follows the same rules and the voice in site.md §7. Claude drafts the words; the owner approves them.

A visitor can see the picture, so nothing but the alt text describes it. Every field has one job:

- Title: the name a visitor would search for, the subject plus the technique when the technique is the point ("Dithered sun"). No imagery words (veil, whirling, struck) unless they are the subject's own name. The slug follows the title.
- Description: one sentence of at most 20 words saying what the piece is and the one thing about it worth knowing: how the subject works, what it is for, where or when it comes from. The method is the fact only when the method is the subject (a dither specimen). A plain label is the last resort, never "X in technique Y". Credit goes in `sources:` and the notes, so no "after X". It never describes the picture or its highlight. It is also the meta description.
- Alt text (`alt`): one sentence of at most 25 words saying what is visible, in plain literal words: the subject, where it sits, and the one thing set apart, told by what it is or shows ("one clock reads 11:22", "a light where the struts meet") rather than by "picked out" or "filled in". No technique names ("grainy", not "Floyd-Steinberg"), no "image of", no figurative verbs (frays, breaks ranks, gathers). Each named version has its own.
- Notes: how the subject works, how the drawing is made, and what comes from an inspiration and what changes, in at most two short paragraphs. A technical term gets one clause saying what it does. They never describe the picture again or repeat the description, and are left out when there is nothing to add.
- Docstring: one line naming the subject and the technique, the way a programmer labels a function.

In every field:

- A fact is checkable: it follows from a source in `sources:` or is stated in any encyclopedia. No invented numbers and no claims about what a piece means, evokes or is about.
- Strictly neutral: no opinion, humor, mood or metaphor, and no gesture phrases (a take on, nods to, in the spirit of, evokes, homage). Name an inspiration and say what comes from it.
- Use plain words a visitor would use. Never: internal terms (regime, seed, token, native, hand-tuned, light-ready, preset, variant, param, slot, template, derived, guard, "has script", "AI-generated", "generator lost", "Appendix"), license names and identifiers (CC0, GPL, SPDX, OFL, LicenseRef-*), or machinery numbers (contrast ratios, color tolerances, pixel sizes). Visitors see variants as "versions".
- Stay theme-neutral: no color names ("terracotta") and no theme roles as nouns ("the accent"). Say what is picked out, filled in or lit. Comments in design.py name tokens or roles, never hues.
- No evaluative adjectives (stunning, mesmerizing, elegant, timeless), and nothing the avoid-ai-tropes check flags.
- Italics only for titles of works.

| Field | Before | After |
|---|---|---|
| Title | Struck pane | Cracked pane |
| Description | Sand marks the still lines of a vibrating plate: two diagonals and a ring of small loops around a lit one. | Sand on a vibrating plate collects along the lines that stay still. |
| Alt text | (the description) | Lines of dots form two diagonals and a ring of small loops around one solid loop at the center. |
| Alt text | (the description) | A wall of round clocks whose hands slant in one diagonal wave, except one clock that reads 11:22. |
| Description | A single-cylinder engine in hatched section at top dead center. A spray of dots lights the chamber under the spark plug. | A four-stroke cylinder at top dead center, its charge squeezed to the smallest volume. |
| Description | Nine bamboo stalks crowd the left edge, fainter the farther back they stand. One in the middle row is lit. | Bamboo is a grass, and its hollow stalks are closed off at every node. |
| Description | Looking up key 417 in a three-level B+-tree lights one pointer per level, then the key in its leaf. | Finding a key in a B+-tree reads one node per level, from the root to a leaf. |
| Description | Incense smoke rises from a lit ember as one braided thread, then curls and frays into dithered veils. | Incense smoke rises as a smooth thread, then turns turbulent. |
| Notes | A take on East Asian ink bamboo painting in flat shapes. [...] The late sun on that stalk nods to Kawase Hasui's shin-hanga landscapes. | East Asian ink bamboo painting, redrawn in flat shapes. The low sun on one stalk comes from Kawase Hasui's shin-hanga prints. |
| Docstring | A radio telescope at dusk in 1-bit Atkinson dither: an empty sky above, grain gathering in the bowl and along the horizon. | A radio telescope at dusk in one-bit Atkinson dither. |

`walldye check` rejects internal terms in version labels and a missing alt text, and warns on color words in design.py and on every copy problem in meta.yaml and the docstring: color words, banned adjectives, stock and gesture phrases, internal terms, license identifiers, machinery numbers, theme roles as nouns, imagery in a title, the highlight in a description, a named version without its own alt text, "after" in a description, "picked out" or "filled in" in an alt text, a description or alt text over its length, and a docstring over one line (`walldye/tools/lint/words.py`). pytest runs the same copy lint over the whole catalog and fails on any finding.

## Licensing

The library, the site and the tooling are GPL-3.0-or-later. Each wallpaper folder, build output included, has its own license:

- A piece a model made is CC0-1.0 and may leave out `license:`.
- A human-made piece, and any piece with a `recreation` source, sets `license:` to an SPDX id. A recreation of a work under an attribution license takes that license: nix-snowflake, after the CC BY 4.0 NixOS logo, is CC-BY-4.0.
- A fan piece sets `franchise: {title, owner}` instead of `license:`, which makes it `LicenseRef-fan-work`. No license is granted, use is non-commercial, and the page carries a disclaimer naming the owner and takedown@walldye.com. Fan pieces need the owner's approval.
- Third-party files in `data/` keep their upstream license, with the notice in `REUSE.toml`, and are credited as `data` sources.

Every license in use has its text in `LICENSES/`, named by SPDX id, and every license other than CC0 and fan work needs a plain-words line in `LICENSE_LINES` (`src/lib/labels.ts`), which the piece's page shows. The README has the table of what is licensed how.

## What a piece may draw

A piece is released as CC0 only when everything in it is ours to give away. The owner lives in the EU, where there is no fair use and copyright runs until 70 years after the author's death. A CC0 label on someone else's work would tell visitors they can sell prints of it. These rules keep the realistic worst case at a takedown request. They are the owner's policy, not legal advice.

- Styles, techniques, algorithms, genres and ideas are free to use. Credit the work that suggested one as an `inspiration`, and the piece stays CC0.
- A `recreation`, which redraws one specific work, is only for works that are public domain in both the EU and the US (US federal works such as NASA's count) or under an open license.
- Works still in copyright are never redrawn. A piece may keep a work's visual idea and feel, but it makes two or three deliberate departures of its own: orientation, proportion, count, where the change happens, a focal point, or an added element. schotter is the model: a grid of squares coming loose, turned sideways, with strays leading to one filled square. Someone who knows the original should think "in the spirit of it", not "that is it". The title is not the work's title, the notes may say what is taken and what is done differently, and the work is credited as an inspiration.
- Some looks stay off limits even as inspiration: game looks that courts have protected (the Tetris well, in *Tetris Holding v. Xio*, 2012) and single famous images such as album covers.
- Game and franchise pieces are fan work (Licensing above). Prefer drawing a subject over copying its assets: traced official renders, textures and logos come closer to redistribution than a depiction does. A rights holder's request is honored with `walldye drop`.

## Drafts and review

- Drafts live on main. A new piece or version starts as `draft: true`; it is built and reviewed locally and hidden from the production site (`astro dev` and a pull request's preview show it).
- Agents propose at most three versions per piece, always as drafts.
- `walldye review` opens a local page that goes through the versions one at a time. Accepting a draft removes `draft:`. Sending one back for an edit keeps it as a draft, with a note. Removing a published version sets it back to draft. The page also edits the piece's words and facets. api.md (CLI) has the details.
- A rejected piece is deleted with `walldye drop`, after the owner confirms.
