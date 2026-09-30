# Workflows

## wallpaper-batch

Invents a batch of new wallpapers (research, curation, building and pruning) and leaves them as `draft: true` folders under `wallpapers/`. When you already know the subjects, ask for them by name instead: the walldye skill (`.claude/skills/walldye/`) builds each one without the research and curation.

Start it by asking Claude to run the `wallpaper-batch` workflow, for example with `{"count": 20}`. A bare number works too.

| arg | meaning |
|---|---|
| `count` | Finished pieces wanted. The curator picks `count` x 1.25 ideas, because critique, the set pass and review all drop some. Required. |
| `brief` | The look in the owner's words: mood, subjects, what to avoid. Naming a franchise here is what allows fan pieces from it. Defaults to the skill's `references/taste.md`. |
| `lenses` | Research lenses. Each entry is a default lens key (`retro-tech`), free text naming a territory (`"ANSI and BBS art"`), or `{key, territory}`. Defaults to the seven lenses at the top of `wallpaper-batch.js`. |
| `licenses` | `{slug: "CC0-1.0"}` per piece, and optionally `"*"` as the owner's answer for every piece that recreates a specific work. |
| `stop` | `"ideas"` stops after curation and returns the list for the owner to look over. |
| `cut` | Idea names to skip, used when resuming after `stop: "ideas"`. |
| `review` | `false` skips `walldye review` at the end, for unattended runs. |

### What runs

1. Setup: one agent lists every existing piece (`walldye list`) into `existing.txt`, sheets about 30 pieces in the house style as the family reference and the whole catalog as small thumbnails for spotting look-alikes, and reads `taxonomy.yaml`. Scratch files go to `$WALLDYE_PREVIEW/batch` (`/tmp/walldye/batch` by default).
2. Research: one agent per lens searches the web and proposes ideas, each with facets and leads (`{kind, title or topic, author, year, url}`).
3. Curate: one art director merges near-duplicates and picks the set, with at most 10% of it sharing any one technique facet. The script then drops names that collide with existing ones or are reserved, fan work whose franchise the brief doesn't name, and anything over the cap.
4. Design: batches of three go through a builder (the walldye skill's steps 2 to 8: `walldye new`, `design.py`, `meta.yaml`, then check, ruff and Pyrefly), a read-only critic that also judges the flexoki-light and nord renders, the copy and any proposed variant, and a fixer when the critic asked for anything. Builders propose variants only where a piece has a natural one, at most three, always as `draft: true` (the variant policy in the walldye skill); the fixer removes the variants the critic rejected. Batches run concurrently, up to the harness's agent limit.
5. Set: one agent builds the kept drafts, runs the near-clone pass of `walldye check --similar` on them (without repeating the check that build just ran), and looks at contact sheets in a dark and a light theme. Its polish list goes through a rework agent and an independent judge per piece. Duplicates, judged-out pieces and failed builds are deleted with `walldye drop --yes`; the owner never saw them.
6. Sources: one agent per three pieces fetches every lead, drops the ones that don't check out, and writes `sources:`.
7. Copy: one agent edits all new titles, descriptions, alt texts, notes and docstrings side by side.
8. Build: if a piece now has a `kind: recreation` source and `licenses` has no answer for it, the run stops here with `status: "needs-license"` and the steps to finish by hand. Otherwise one agent writes the `license:` lines and runs `walldye build` over the pieces.
9. Review: `walldye review <slugs>` on port 8742 (the log prints the URL), waiting until the owner presses Apply, then one agent turns the notes and the owner's own edits to the copy into `proposed_lessons`: changes to the skill's `principles.md` or `taste.md` for the owner to approve before anyone writes them. Review decides each draft version on its own: accept, edit (sent back with a note) or remove. The versions sent back are listed under `next` with their notes, for a later rework.

The drafts are built twice, once before the set pass and again at the end, because `walldye check --similar` and `walldye sheet` read `build/16x9.svg`, and rework and copy change some pieces after the first build. Sources are fetched only after the set pass, which skips fetching for pieces it drops and keeps `kind: recreation` out of `meta.yaml` until the license question.

Per 100 finished pieces expect roughly 195 agents: 42 builders, about 42 critics and 35 fixers, a dozen reworks and judges, about 38 source checkers, and single agents for the rest.

The run never commits (its `next` offers a commit that stages only the new folders), never edits `walldye/` or `taxonomy.yaml`, and never drops a piece the owner has seen. Rejected pieces from the review are listed under `next` with the `drop` command to run once the owner confirms.

### Checkpoints

To look at the ideas before anything is built, run with `stop: "ideas"`, then relaunch with `resumeFromRunId` and the same args without `stop`, adding `cut` for ideas to skip. Setup, research and curation come back from the cache.

The license question can't be asked mid-run. Either pass `licenses` up front, or answer after a `needs-license` result: add the `license:` lines, then run the commands in the result's `next` list.
