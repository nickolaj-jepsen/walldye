# Workflows

## wallpaper-batch

Makes a batch of new wallpapers in one run and leaves them as `draft: true` folders under `wallpapers/`. Use it for about ten or more pieces; for one or a few, the walldye skill (`.claude/skills/walldye/`) is quicker. It ports the branch's `references/batch.md` with the changes listed in `docs/design.md` under "Batch workflow".

Start it by asking Claude to run the `wallpaper-batch` workflow, for example with `{"count": 20}`. A bare number works too.

| arg | meaning |
|---|---|
| `count` | Finished pieces wanted. The curator picks `count` x 1.25 ideas, because critique, the set pass and review all drop some. Required. |
| `brief` | The look in the owner's words: mood, subjects, what to avoid. Defaults to the taste notes in `references/taste.md`. |
| `lenses` | Research lenses. Each entry is a default lens key (`retro-tech`), free text naming a territory (`"ANSI and BBS art"`), or `{key, territory}`. Defaults to the seven lenses from the branch. |
| `lessons` | What earlier reviews approved and rejected, and why. The last run's `lessons` output goes here. |
| `licenses` | `{slug: "CC0-1.0"}` per piece, and optionally `"*"` as the owner's answer for every piece that recreates a specific work. |
| `stop` | `"ideas"` stops after curation and returns the list for the owner to look over. |
| `cut` | Idea names to skip, used when resuming after `stop: "ideas"`. |
| `review` | `false` skips `walldye review` at the end, for unattended runs. |

### What runs

1. Setup: one agent collects every existing name (`walldye list` plus, until the M2 import, the designs and backgrounds in `~/nixos`), writes `existing.txt`, renders reference sheets and reads `taxonomy.yaml`. Scratch files go to `$WALLDYE_PREVIEW/batch` (`/tmp/walldye/batch` by default).
2. Research: one agent per lens searches the web and proposes ideas, each with facets and leads (`{kind, title, author, year, url}`).
3. Curate: one art director merges near-duplicates and picks the set, with at most 10% of it sharing any one technique facet. The script then drops names that collide with existing ones or are reserved, and enforces the cap again.
4. Design: batches of three go through a builder (`walldye new`, `design.py`, `meta.yaml`, `walldye check`), a read-only critic that also judges the flexoki-light and nord renders and the copy, and a fixer when the critic asked for anything. Batches run concurrently, up to the harness's agent limit.
5. Set: one agent builds the kept drafts, runs the near-clone pass of `walldye check --set` on them (without repeating the check that build just ran), and looks at contact sheets in the dark and a light theme. Its polish list goes through a rework agent and an independent judge per piece. Duplicates, judged-out pieces and failed builds are deleted with `walldye drop --yes`; the owner never saw them.
6. Sources: one agent per three pieces fetches every lead, drops the ones that don't check out, and writes `sources:`.
7. Copy: one agent edits all new titles, descriptions, notes and docstrings side by side.
8. Build: if a piece now has a `kind: recreation` source and `licenses` has no answer for it, the run stops here with `status: "needs-license"` and the steps to finish by hand. Otherwise one agent writes the `license:` lines, runs `walldye build` on each piece and then `walldye build --verify`.
9. Review: `walldye review <slugs>` on port 8742 (the log prints the URL), waiting until the owner presses Done, then one agent turns the decisions into `lessons`.

Per 100 finished pieces expect roughly 195 agents: 42 builders, about 42 critics and 35 fixers, a dozen reworks and judges, about 38 source checkers, and single agents for the rest. `walldye check` and `walldye build` take from about 15 seconds to 5 minutes per piece; hitomezashi is the quick end and ribbons, with `ASPECTS = ["any"]`, the slow one. So the set pass and the final build run eight single-piece builds at a time in the background. Built that way, the eight skill examples took about six minutes on a 16-core machine, roughly what ribbons takes alone.

The run never commits, never edits `walldye/` or `taxonomy.yaml`, and never drops a piece the owner has seen. Rejected pieces from the review are listed under `next` with the `drop` command to run once the owner confirms.

### Checkpoints

To look at the ideas before anything is built, run with `stop: "ideas"`, then relaunch with `resumeFromRunId` and the same args without `stop`, adding `cut` for ideas to skip. Setup, research and curation come back from the cache.

The licence question can't be asked mid-run. Either pass `licenses` up front, or answer after a `needs-license` result: add the `license:` lines, then run the commands in the result's `next` list.

### Differences from the branch batch

`walldye check --set` and `walldye sheet` read `build/16x9.svg`, so the drafts are built once before the set pass and again at the end, after rework and copy changed some of them. Sources are fetched after the set pass, which keeps `kind: recreation` out of `meta.yaml` until the licence question, and skips fetching for pieces the set pass drops.
