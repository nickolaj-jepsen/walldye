# Workflows

## wallpaper-batch

Makes a batch of new wallpapers in one run and leaves them as `draft: true` folders under `wallpapers/`. Use it for about ten or more pieces; for one or a few, the walldye skill (`.claude/skills/walldye/`) is quicker.

Start it by asking Claude to run the `wallpaper-batch` workflow, for example with `{"count": 20}`. A bare number works too.

| arg | meaning |
|---|---|
| `count` | Finished pieces wanted. The curator picks `count` x 1.25 ideas, because critique, the set pass and review all drop some. Required. |
| `brief` | The look in the owner's words: mood, subjects, what to avoid. Defaults to the taste notes in `references/taste.md`. |
| `lenses` | Research lenses. Each entry is a default lens key (`retro-tech`), free text naming a territory (`"ANSI and BBS art"`), or `{key, territory}`. Defaults to the seven lenses at the top of `wallpaper-batch.js`. |
| `lessons` | What earlier reviews approved and rejected, and why. The last run's `lessons` output goes here. |
| `licenses` | `{slug: "CC0-1.0"}` per piece, and optionally `"*"` as the owner's answer for every piece that recreates a specific work. |
| `stop` | `"ideas"` stops after curation and returns the list for the owner to look over. |
| `cut` | Idea names to skip, used when resuming after `stop: "ideas"`. |
| `review` | `false` skips `walldye review` at the end, for unattended runs. |

### What runs

1. Setup: one agent lists every existing piece (`walldye list`) into `existing.txt`, sheets about 30 pieces in the house style as the family reference and the whole catalogue as small thumbnails for spotting look-alikes, and reads `taxonomy.yaml`. Scratch files go to `$WALLDYE_PREVIEW/batch` (`/tmp/walldye/batch` by default).
2. Research: one agent per lens searches the web and proposes ideas, each with facets and leads (`{kind, title, author, year, url}`).
3. Curate: one art director merges near-duplicates and picks the set, with at most 10% of it sharing any one technique facet. The script then drops names that collide with existing ones or are reserved, and enforces the cap again.
4. Design: batches of three go through a builder (`walldye new`, `design.py`, `meta.yaml`, `walldye check`), a read-only critic that also judges the flexoki-light and nord renders, the copy and any proposed variant, and a fixer when the critic asked for anything. Builders propose variants only where a piece has a natural one, at most three, always as `draft: true` (the variant policy in the walldye skill); the fixer removes the variants the critic rejected. Batches run concurrently, up to the harness's agent limit.
5. Set: one agent builds the kept drafts, runs the near-clone pass of `walldye check --similar` on them (without repeating the check that build just ran), and looks at contact sheets in a dark and a light theme. Its polish list goes through a rework agent and an independent judge per piece. Duplicates, judged-out pieces and failed builds are deleted with `walldye drop --yes`; the owner never saw them.
6. Sources: one agent per three pieces fetches every lead, drops the ones that don't check out, and writes `sources:`.
7. Copy: one agent edits all new titles, descriptions, notes and docstrings side by side.
8. Build: if a piece now has a `kind: recreation` source and `licenses` has no answer for it, the run stops here with `status: "needs-license"` and the steps to finish by hand. Otherwise one agent writes the `license:` lines, runs `walldye build` over the pieces and then `walldye build --verify`.
9. Review: `walldye review <slugs>` on port 8742 (the log prints the URL), waiting until the owner presses Apply, then one agent turns the decisions, notes and the owner's own edits to the copy into `lessons`. Review decides each draft version on its own.

The drafts are built twice, once before the set pass and again at the end, because `walldye check --similar` and `walldye sheet` read `build/16x9.svg`, and rework and copy change some pieces after the first build. Sources are fetched only after the set pass, which skips fetching for pieces it drops and keeps `kind: recreation` out of `meta.yaml` until the licence question.

Per 100 finished pieces expect roughly 195 agents: 42 builders, about 42 critics and 35 fixers, a dozen reworks and judges, about 38 source checkers, and single agents for the rest. `walldye check` and `walldye build` draw each version once per aspect and regime and write that drawing under every theme, so a piece takes from about 2 seconds (hitomezashi) to about 30 (ribbons, with `aspects="any"`); heavy simulations take longer. Over several pieces they run in a process pool across the cores: the eight skill examples check in about 40 seconds on a 16-core machine. The set pass and the final build each start one build over all their pieces in the background.

The run never commits, never edits `walldye/` or `taxonomy.yaml`, and never drops a piece the owner has seen. Rejected pieces from the review are listed under `next` with the `drop` command to run once the owner confirms.

### Checkpoints

To look at the ideas before anything is built, run with `stop: "ideas"`, then relaunch with `resumeFromRunId` and the same args without `stop`, adding `cut` for ideas to skip. Setup, research and curation come back from the cache.

The licence question can't be asked mid-run. Either pass `licenses` up front, or answer after a `needs-license` result: add the `license:` lines, then run the commands in the result's `next` list.
