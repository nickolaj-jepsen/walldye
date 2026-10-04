# Workflows

## wallpaper-batch

Researches, builds and prunes a batch of new wallpapers, leaving them as `draft: true` folders. For subjects you already have in mind, use the walldye skill instead.

Ask Claude to run `wallpaper-batch` with args, e.g. `{"count": 20}` or just `20`.

| arg | meaning |
|---|---|
| `count` | Finished pieces wanted (required). The curator picks 1.25x as many ideas to allow for drops. |
| `brief` | The look you want, in your words. Naming a franchise allows fan pieces from it. Default: the skill's `references/taste.md`. |
| `lenses` | Research lenses: a default key (`retro-tech`), free text (`"ANSI and BBS art"`) or `{key, territory}`. Default: the seven in `wallpaper-batch.js`. |
| `licenses` | `{slug: "CC0-1.0"}`, plus `"*"` for every piece that recreates a specific work. |
| `stop` | `"ideas"` stops after curation so you can look over the list. |
| `cut` | Idea names to skip when resuming. |
| `review` | `false` skips the final `walldye review`. |

### Steps

1. Setup: list existing pieces and sheet the catalog for reference.
2. Research: one agent per lens proposes ideas with sources.
3. Curate: merge duplicates and pick the set, at most 10% per technique.
4. Design: batches of three, each through a builder, a critic and, if needed, a fixer.
5. Set: build the drafts, drop near-clones and weak pieces, polish the rest.
6. Sources: check every lead and write `sources:`.
7. Copy: edit all the new words side by side.
8. Build: write `license:` lines and build. Stops with `needs-license` if a recreation has no answer in `licenses`.
9. Review: `walldye review` on port 8742, then proposed changes to the skill from your notes.

Expect about 195 agents per 100 finished pieces.

The run never commits, never edits `walldye/`, and never drops a piece you've seen. Its `next` lists a commit command, the pieces you rejected with their `drop` command, and the versions you sent back.

### Resuming

After `stop: "ideas"`, rerun with `resumeFromRunId`, the same args without `stop`, and `cut` for ideas to skip. After `needs-license`, add the `license:` lines and run the commands in `next`.
