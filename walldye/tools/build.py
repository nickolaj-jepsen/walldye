"""walldye build: check pieces, then write each variant's build/ templates and slots.json;
also wallpapers/index.json."""

import json
import shutil
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from walldye._aspect import SITE_ASPECTS
from walldye.tools import check, hashing, lint, metadata, paths, slotfile
from walldye.tools.paths import TEMPLATE_NAME


def _current(slug: str, variant: str, slots: slotfile.Slots, design_sha: str) -> bool:
    """Whether `slots` still describe the variant's inputs: same design_sha and walldye
    version, and every template it names present with its recorded sha256. The render inputs
    are compared separately, through `render_lib` and the probes."""
    d = paths.build_dir(slug, variant)
    return slots.current(design_sha) and all(
        (d / e["file"]).exists() and hashing.sha256((d / e["file"]).read_bytes()) == e["sha256"]
        for e in slots.entries.values()
    )


def _name(slug: str, variant: str) -> str:
    return slug if variant == "default" else f"{slug} ({variant})"


def _write(slug: str, variant: str, design_sha: str, lib_sha: str, r: check.Result) -> list[str]:
    """Write a checked variant's templates and slots.json, removing the templates it no
    longer has; returns the written files relative to build/."""
    d = paths.build_dir(slug, variant)
    d.mkdir(parents=True, exist_ok=True)
    for stale in d.glob("*.svg"):
        if TEMPLATE_NAME.fullmatch(stale.name) is not None and stale.name not in r.templates:
            stale.unlink()
    for name, text in r.templates.items():
        (d / name).write_bytes(text.encode())
    slots: dict[str, object] = {"design_sha": design_sha}
    if variant != "default":
        slots["variant"] = variant
    focus = r.focus if r.focus is not None else (0.5, 0.5)
    slots |= {"focus": list(focus), "cells": r.cells, "probes": r.probes}
    slots |= {"render_lib": lib_sha, "checked": slotfile.version()}
    for k, e in r.entries.items():
        sha = hashing.sha256(r.templates[e["file"]].encode())
        entry: slotfile.Entry = {
            "file": e["file"],
            "sha256": sha,
            "n": e["n"],
            "coefs": e["coefs"],
            "occ": e["occ"],
        }
        slots[k] = entry
    (d / "slots.json").write_text(slotfile.dump(slots))
    prefix = "" if variant == "default" else f"{variant}/"
    return [f"{prefix}{n}" for n in (*r.templates, "slots.json")]


def _prune(slug: str, names: Sequence[str]) -> None:
    """Remove build/<dir>/ for every directory that is not a declared variant."""
    b = paths.build_dir(slug)
    if not b.is_dir():
        return
    for p in b.iterdir():
        if p.is_dir() and p.name not in names:
            shutil.rmtree(p)
            print(f"{slug}: removed build/{p.name}/, not a declared variant")


def _restamp(slug: str, variant: str, lib_sha: str) -> None:
    """Record in a variant's slots.json that its templates hold under render inputs `lib_sha`."""
    slots = slotfile.load(slug, variant)
    assert slots is not None
    (paths.build_dir(slug, variant) / "slots.json").write_text(
        slots.restamped(render_lib=lib_sha).dump()
    )


def _drafts(slug: str) -> tuple[bool, set[str]]:
    """Whether meta.yaml marks `slug` a draft, and its draft named variants; (False, set())
    when meta.yaml cannot be read, so the check reports it."""
    try:
        m = metadata.load_meta(slug)
    except (OSError, ValueError):
        return False, set()
    named = metadata.meta_variants(m).items()
    return metadata.is_draft(m), {v for v, e in named if v != "default" and e.get("draft") is True}


@dataclass
class _Plan:
    """A piece to build: its check so far, what each variant needs, and its tasks."""

    target: check.Target
    lib_sha: str
    shas: dict[str, str] = field(default_factory=dict[str, str])
    current: list[str] = field(default_factory=list[str])
    tasks: list[check.Task] = field(default_factory=list[check.Task])


def _plan(slug: str, variant: str | None, lib_sha: str, force: bool, published: bool) -> _Plan:
    """What `slug` needs: variants whose slots.json is current are skipped while its
    render_lib matches `lib_sha`, else re-drawn only for their probes; the rest are checked.
    With `published`, draft named variants are left out."""
    t = check.prepare(slug, variant)
    if published:
        _, drafts = _drafts(slug)
        t.variants = tuple(v for v in t.variants if v not in drafts)
    plan = _Plan(t, lib_sha)
    if t.piece is None or len(t.report.errors) > 0:
        return plan
    for v in t.variants:
        plan.shas[v] = hashing.design_sha(slug, v)
        try:
            old = None if force else slotfile.load(slug, v)
        except ValueError as e:
            print(f"{_name(slug, v)}: {e}; rebuilding")
            old = None
        task = check.Task(str(paths.WALLPAPERS), slug, v)
        if old is not None and _current(slug, v, old, plan.shas[v]):
            if old.text("render_lib") == lib_sha:
                plan.current.append(v)
                continue
            task = check.Task(task.wallpapers, slug, v, probes=old.probes())
        plan.tasks.append(task)
    return plan


def run(
    slugs: Sequence[str],
    all: bool = False,
    force: bool = False,
    variant: str | None = None,
    published: bool = False,
    jobs: int | None = None,
) -> int:
    """`walldye build`: check each variant of `slugs` (every piece with `all`), or only
    `variant`, and write a piece's build files when every checked variant passes; then
    regenerate index.json. Unchanged variants are skipped as _plan() decides unless `force`;
    `published` skips drafts. Without `variant`, build/ directories that are not declared
    variants are removed. Returns 1 if any piece failed, 2 if there is nothing to build, else 0.
    UsageError for an undeclared `variant`.
    """
    targets = paths.slugs() if all else list(slugs)
    if published:
        drafts = [s for s in targets if _drafts(s)[0]]
        targets = [s for s in targets if s not in drafts]
        if len(drafts) > 0:
            print(f"skipped {len(drafts)} draft pieces")
    if len(targets) == 0:
        print("nothing to build: name a slug or pass --all", file=sys.stderr)
        return 2
    lib_sha = hashing.render_lib_sha()
    plans = [_plan(slug, variant, lib_sha, force, published) for slug in targets]
    # The static steps for what is checked afresh, and for pieces that already failed.
    for p in plans:
        if len(p.target.report.errors) > 0 or any(t.probes is None for t in p.tasks):
            check.lint_source(p.target)
    tasks = [task for p in plans for task in p.tasks]
    results = check.run_tasks(check.check_variant, tasks, check.workers(jobs, len(tasks)))
    failed = [p.target.slug for p in plans if not _finish(p, results, variant)]
    write_index()
    return 1 if len(failed) > 0 else 0


def _finish(plan: _Plan, results: Iterator[check.Result], variant: str | None) -> bool:
    """Collect a piece's results, print, and write when it passed."""
    t = plan.target
    for _ in plan.tasks:
        t.report.add(next(results))
    checked = {v: r for v, r in t.report.results.items() if not r.unchanged}
    if len(checked) > 0 or len(t.report.errors) > 0:
        check.print_report(t.report)
    if len(t.report.errors) > 0 or t.piece is None:
        print(f"{t.slug}: not written")
        return False
    for v in plan.current:
        print(f"{_name(t.slug, v)}: up to date")
    for v, r in t.report.results.items():
        if r.unchanged:
            _restamp(t.slug, v, plan.lib_sha)
            print(
                f"{_name(t.slug, v)}: up to date (probe renders unchanged under the new render inputs)"
            )
        else:
            written = _write(t.slug, v, plan.shas[v], plan.lib_sha, r)
            print(f"{_name(t.slug, v)}: wrote {', '.join(written)}")
    if variant is None:
        _prune(t.slug, t.piece.variant_names())
    return True


def write_index() -> None:
    """Regenerate wallpapers/index.json without importing designs; license
    is null when meta.yaml breaks the license rules. A piece whose meta.yaml or slots.json cannot
    be read is left out, with a note on stderr."""
    index: dict[str, object] = {}
    for slug in paths.slugs():
        try:
            slots = slotfile.load(slug)
            if slots is None:
                continue
            m = metadata.load_meta(slug)
            keys = slots.entries
        except (OSError, ValueError) as e:
            print(f"index.json: left out {slug}: {e}", file=sys.stderr)
            continue
        variants: dict[str, object] = {}
        for name, entry in metadata.meta_variants(m).items():
            if name != "default":
                label = entry.get("label")
                variants[name] = {
                    "draft": entry.get("draft") is True,
                    "label": label if isinstance(label, str) else "",
                }
        index[slug] = {
            "aspects": [a for a in SITE_ASPECTS if any(k.startswith(f"{a}/") for k in keys)],
            "draft": metadata.is_draft(m),
            "license": lint.license_of(m),
            "title": m.get("title"),
            "variants": variants,
        }
    (paths.WALLPAPERS / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False, default=str) + "\n"
    )
