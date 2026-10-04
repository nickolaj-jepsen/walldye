---
name: walldye
description: Design procedural SVG wallpapers for the walldye catalog, one per subject the owner names, and take each from `walldye new` through preview, an independent critique, check, build and review; also reworks a published piece from the owner's note. Use when asked to make, design, add, draw or rework a wallpaper or desktop background in this repo, including a list of named subjects. To invent new pieces from research, use the wallpaper-batch workflow.
---

# walldye

A wallpaper is a folder `wallpapers/<slug>/` holding a `design.py` that draws with the `walldye`
library and a `meta.yaml`. docs/wallpapers.md has the rules for the folder, meta.yaml, copy and
licensing, docs/api.md the design API and the CLI, and docs/architecture.md how build, check,
versions and the light ladder work. This skill is what an agent does on top of them.

Run commands from the repo root as `uv run walldye <command>`; `-h` on any command lists its
flags.

## Ground rules

- Edit only `wallpapers/<slug>/design.py`, `meta.yaml` and `data/` by hand, plus the lines
  steps 2 and 12 name. `walldye build` writes `build/` and rewrites `wallpapers/index.json`;
  both are gitignored, and CI renders its own. Never edit `walldye/`, other pieces, anything in
  `build/`, or `taxonomy.yaml` beyond the model line step 2 names.
- Always name the slug; never `--all`.
- Previews go to `$WALLDYE_PREVIEW`, never into the repo.
- A check or build takes from a few seconds to about half a minute per piece (a dense
  `aspects="any"` piece with variants, or a heavy simulation, is the slow end), so give each a
  600000 ms Bash timeout. Work that takes seconds and doesn't depend on the shape or regime goes
  in a module-level `@cached` def (docs/api.md §9.1).
- Leave the work uncommitted (step 13).

## Several pieces

When the owner names several subjects, start one builder subagent per subject at once, each
running steps 1 to 8 on its own slug. Run step 9 for each piece as its builder returns, and send
the critic's fixes back to that builder with SendMessage. Then build the pieces together
(`uv run walldye build a b c` with `run_in_background`), run
`uv run walldye check --similar a b c`, and hold one `uv run walldye review a b c`. Steps 11 to
13 run once, over the whole set.

## Steps

1. Brief, then dedupe. Pin the idea down to one line: subject, composition, technique. With no
   brief, start from references/taste.md and the seeds in references/ideas.md. A subject that
   needs `franchise:` is off limits unless the owner's brief names that franchise (taste.md,
   Fan work). Then check it doesn't exist yet:
   ```bash
   uv run walldye list | rg -i '<word>'
   ```
   If it does, or references/ideas.md lists it as dropped, change the subject or the
   composition, not the parameters.
2. Scaffold, with your own model id, such as `claude-opus-5-5` (drop a context suffix such as
   `[1m]` from the id):
   ```bash
   uv run walldye new <slug> --model <model id>
   ```
   If `walldye check` says the model needs a credit name, add `<model id>: <display name>`
   under `models:` in taxonomy.yaml, the one line of that file you write.
3. Write design.py, starting from the nearest piece in Examples and references/api.md. Use
   `@design(aspects="any")` whenever the composition can follow `s.pick`, `s.frac` and
   `s.inset`; leave it out for 16:9 only, and the site crops other screen shapes from that.
4. Preview for at least three rounds. Each run prints lint lines, `regime:`,
   `light geometry:` and, last, the PNG path. Read the PNG, critique it against the checklist
   in references/principles.md, revise.
   ```bash
   uv run walldye preview <slug>
   uv run walldye preview <slug> --crop X,Y,W,H          # canvas units, the busiest area
   uv run walldye preview <slug> --aspect 32:9           # with aspects, also 9:19.5 and 10:16
   uv run walldye preview <slug> --theme flexoki-light   # from round 2 on, and --theme nord
   uv run walldye preview <slug> --width 400             # thumbnail size, how it is mostly seen
   uv run walldye sheet <slug> --seeds 0..7              # choosing a seed
   uv run walldye sheet <slug> --wedge sweep=0..360..45  # choosing a knob's value
   ```
   `--set k=v` tries one params value in preview, render or sheet without publishing it.
5. Light ladder (docs/architecture.md, Designs draw in formulas): stop at the first step that
   gives a good flexoki-light render. references/principles.md, Light themes, says what
   changes on paper.
6. Variants, only where the piece has a natural one (Variant policy). Each is a `Params`
   instance in `@design(variants=...)`, previewed with `--variant <name>` and listed in
   meta.yaml with `draft: true`. Most pieces have none.
7. Fill in meta.yaml and the copy (meta.yaml and Copy below).
8. Check, format and type-check. All three must report no errors:
   ```bash
   uv run walldye check <slug>
   uv run ruff format wallpapers/<slug> && uv run ruff check --fix wallpapers/<slug>
   uv run pyrefly check -c wallpapers/pyrefly.toml wallpapers/<slug>/design.py
   ```
   `check` covers every variant. Its warnings are judgment calls, except color words and
   fractional grid origins: fix those.
9. Independent critique (below). Go on only with a score of 8 or more.
10. `uv run walldye build <slug>`, then `uv run walldye check --similar <slug>`: after running
    the whole check again, it prints `similar (0.95): a ~ b` for each built piece whose
    thumbnail nearly matches yours. A match is a duplicate: change the subject or the
    composition.
11. Review. Run `uv run walldye review <slug>` with `run_in_background`: it serves a local page,
    blocks until the owner presses Apply, then prints JSON (docs/api.md §12.3). Act on it:
    - A note on an approved version usually asks for more, such as another version like it.
    - Rework each version in `edit` as its note says, then run steps 8 to 11 for it again. It
      keeps its draft flag until then.
    - `edits` shows the copy the owner wants.
    - Review never edits design.py: remove a rejected variant from design.py and meta.yaml by
      hand.
    - Confirm with the owner before `uv run walldye drop <slug> --yes` on a rejected piece; an
      unpublished piece is not a rejection.
12. Lessons. For each note and each copy edit, ask whether it would apply to other pieces too.
    When it would, draft a one-line change to references/principles.md (a failure row or a
    checklist item, with this piece as the example) or references/taste.md, show it to the
    owner, and write it only once they approve. A note about this piece alone ("move the moon
    left") is not a lesson.
13. Hand off. List the files the run touched (the piece's folder, and any line added to
    taxonomy.yaml or the references), what review published, and the
    lessons written. Leave them uncommitted, and offer a commit,
    `feat(wallpapers): add <slug>` or `feat(wallpapers): rework <slug>`, that stages only those
    paths: the tree may hold unrelated work.

## Reworking a piece

When the owner sends a published piece back with a note:

1. Skip steps 1 and 2. Keep the slug, `added:`, `model:` and every `draft` flag as it is: the
   piece stays published, and review is where the owner hides it.
2. Before editing, preview the piece as it stands and keep that PNG as the before image.
3. Read the note against the checklist in references/principles.md, and say in one line what
   will change.
4. Run steps 3 to 13. The critic also gets the before image and the note. In review, name the
   slug so its published versions are in the queue.

## Independent critique

Your own previews are the most lenient review a piece gets. After step 8, start a fresh
subagent with the Agent tool as the critic, and give it no conversation history, only:

- the slug and the one-line brief (for a rework, also the before image and the owner's note);
- the renders: the 16:9 preview under fireproof, `--width 400`, a `--crop` of the busiest
  region, `--theme flexoki-light`, `--theme nord`, `--aspect 9:19.5` when the piece declares
  aspects, and each variant under `--variant <name>`;
- this brief: "Read .claude/skills/walldye/references/principles.md and
  .claude/skills/walldye/references/taste.md. Edit no files; you may run
  `uv run walldye preview` for more views and read design.py and meta.yaml. Score the piece 1
  to 10 by principles.md's scoring, and list concrete fixes (positions, sizes, tones, density),
  most important first. Judge each variant against the Variant policy in
  .claude/skills/walldye/SKILL.md: keep or drop, with the reason. Then score the copy 1 to 10
  on its own against Copy in docs/wallpapers.md, asking of each field: is its fact checkable,
  does anything but the alt text describe the picture, and would a person say it out loud?
  Quote any replacement text."

Apply the fixes, run step 8 again, and start a second fresh critic. If the piece still scores
under 8, stop before build: tell the owner the score and the critic's reasons, and ask whether
to review it anyway, rework the approach, or drop it.

A subagent without the Agent tool stops after step 8 and returns its render paths; the agent
that started it runs the critic and sends back the fixes.

## Variant policy

A variant is a named version of a piece (docs/architecture.md, Versions). Each one is built for
every aspect and regime, reviewed and kept, so the bar is high:

- It changes what is depicted (a moon phase, a rule number, a reaction regime, the moment of a
  sweep), or leaves out a layer that a plainer wallpaper does without (a construction
  drawing's dimensions, a chart's labels). It never just nudges a value. A new seed is a
  variant only when the result shows something different; seed ladders are for
  `sheet --seeds`, never for the site.
- Propose at most 3, always as `draft: true`; the owner approves each one in review.
- Every version reads as its subject as clearly as the default does.
- `check` does not compare versions, so judge by eye that each one differs: on a
  fine-textured piece a 4% nudge of one value changes the file but not the picture.

## meta.yaml

docs/wallpapers.md, meta.yaml, has every field and rule. On top of it:

- Keep the keys `walldye new` wrote, in that order, and add no comments: review rewrites the
  file.
- Facet values come from taxonomy.yaml. Put anything missing in `proposed_facets`
  (`{technique: [value]}`); the owner decides in review.
- Fetch every source URL with WebFetch before writing it, and keep it only when the page loads
  and shows what you cite. Never write a URL from memory, and leave out any field you can't
  confirm.
- Ask the owner before writing `license:` or `franchise:`.

## Copy

docs/wallpapers.md, Copy, has the rules for everything a visitor reads, including design.py's
docstring and comments. On top of them:

- A title is in sentence case, like "Radar sweep" or "One-bit moon".
- Write the alt text from the preview, and the description's fact from the sources; don't
  open a description the way the last few pieces do (`walldye list` shows them).
- Run the avoid-ai-tropes skill on every draft.
- The color-word lint is a plain word list that also matches plurals, so "black" and "grays"
  trip it ("golden ratio" and its kin do not). It does not know temperatures ("warm",
  "cool"); avoid those by hand.

## Examples

Start from the nearest of these published pieces, each at `wallpapers/<slug>/design.py`:

| Piece | Shows |
|---|---|
| `dither-moon` | blue-noise dither, an `s.light` geometry branch, a phase variant |
| `radar-sweep` | an instrument, grains bucketed by tone, a clip, a variant at a later moment |
| `glyph-terrain` | glyph roles, `by_regime` colors, a map turned for portrait screens |
| `pixel-invaders` | sprites stamped into one `Pixels` grid, dive trail included |
| `patent-lamp` | a patent figure placed by one transform, ruled shading and stipple |
| `noise-contours` | iso-lines in a clip, in under 50 lines |
| `flow-field-ribbons` | a flow field of collision-checked streamlines |
| `hitomezashi` | a stitch tiling that runs past every edge |
| `star-chart` | real data read with `s.data`, a `data` source, a variant for another sky |

## References

- references/api.md: worked examples (buckets, clips, masks, patterns, gradients, noise,
  fields, dither, glyphs), dither costs, glyph coverage, shapely and scipy recipes, and the
  size budget. docs/api.md has the signatures.
- references/principles.md: the house style, light themes, subjects, the critique checklist,
  scoring, and the failure modes with the reviews that taught them.
- references/taste.md: what the owner likes and rejects, and the fan-work rule.
- references/ideas.md: unbuilt seeds, and the ideas review dropped.
