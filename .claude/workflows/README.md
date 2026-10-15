# Workflows

## wallpaper-batch

Researches, builds and prunes a batch of new wallpapers, leaving them as `draft: true` folders. For subjects you already have in mind, use the walldye skill instead.

Ask Claude to run `wallpaper-batch` with args, e.g. `{"count": 20}` or just `20`.

| arg | meaning |
|---|---|
| `count` | Finished pieces wanted (required). The curator picks extra ideas to allow for drops. |
| `brief` | The look you want, in your words. Naming a franchise allows fan pieces from it. Default: the skill's `references/taste.md`. |
| `lenses` | Research lenses: a default key (`retro-tech`), free text (`"ANSI and BBS art"`) or `{key, territory}`. Default: `LENSES` in `wallpaper-batch.js`. |
| `licenses` | `{slug: "CC0-1.0"}`, plus `"*"` for every piece that recreates a specific work. |
| `stop` | `"ideas"` stops after curation so you can look over the list. |
| `cut` | Idea names to skip when resuming. |
| `review` | `false` skips the final `walldye review`. |

### Steps

`meta.phases` in `wallpaper-batch.js` lists the phases. The build stops with `needs-license` if a recreation has no answer in `licenses`, and the run ends on a `walldye review` page, then proposes changes to the skill from your notes.

The run never commits, never edits `walldye/`, and never drops a piece you've seen. Its `next` lists a commit command, the pieces you rejected with their `drop` command, and the versions you sent back.

### Resuming

After `stop: "ideas"`, rerun with `resumeFromRunId`, the same args without `stop`, and `cut` for ideas to skip. After `needs-license`, add the `license:` lines and run the commands in `next`.
