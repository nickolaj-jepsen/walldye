"""walldye build: check a piece, then write its build/ templates and slots.json; also the
drift check (--verify), wallpapers/index.json and the Python reference of the browser recolour."""

from __future__ import annotations

import importlib.metadata
import json
import sys

import walldye
from walldye import _basis
from walldye._theme import (
    PRESETS,
    SEEDS,
    hex_to_rgb,
    is_light,
    normalise_seed,
    rgb_to_hex,
)
from walldye.tools import check, common, fit, hashing, lint
from walldye.tools.tokenize import find_colours, normalise, substitute

FOCUS_WIDTH = 480
_FIREPROOF = {k: PRESETS["fireproof"][k] for k in SEEDS}


def version() -> str:
    return importlib.metadata.version("walldye")


def dump_slots(slots: dict) -> str:
    """slots.json text: one top-level key per line, each value compact JSON."""
    return (
        "{\n"
        + ",\n".join(
            f"{json.dumps(k)}: {json.dumps(v, separators=(',', ':'))}" for k, v in slots.items()
        )
        + "\n}\n"
    )


def load_slots(slug: str) -> dict | None:
    """Parsed build/slots.json of `slug`, None when absent; ValueError naming the file unless it holds a JSON object."""
    path = common.build_dir(slug) / "slots.json"
    if not path.exists():
        return None
    try:
        slots = json.loads(path.read_text())
    except ValueError as e:
        raise ValueError(f"{path}: not valid JSON: {e}") from e
    if not isinstance(slots, dict):
        raise ValueError(f"{path}: not a JSON object")
    return slots


def _current(slug: str, slots: dict, design_sha: str) -> bool:
    """Whether committed `slots` still describe the piece: same design_sha and walldye version,
    and every template it names present with its recorded sha256."""
    d = common.build_dir(slug)
    entries = [v for v in slots.values() if isinstance(v, dict) and "file" in v]
    return (
        slots.get("design_sha") == design_sha
        and slots.get("checked") == version()
        and all(
            (d / e["file"]).exists() and hashing.sha256((d / e["file"]).read_bytes()) == e["sha256"]
            for e in entries
        )
    )


def _write(report: check.Report, design_sha: str) -> None:
    d = common.build_dir(report.slug)
    d.mkdir(exist_ok=True)
    for stale in d.glob("*.svg"):
        if walldye.TEMPLATE_NAME.match(stale.name) and stale.name not in report.templates:
            stale.unlink()
    for name, text in report.templates.items():
        (d / name).write_bytes(text.encode())
    image = common.rasterise(report.templates[walldye.template_name("16:9")], FOCUS_WIDTH)
    slots = {
        "design_sha": design_sha,
        "focus": list(common.focus(image, _FIREPROOF["bg"])),
        "cells": report.cells,
        "probes": report.probes,
        "checked": version(),
    }
    for key, e in report.entries.items():
        sha = hashing.sha256(report.templates[e["file"]].encode())
        slots[key] = {
            "file": e["file"],
            "sha256": sha,
            "n": e["n"],
            "coefs": e["coefs"],
            "occ": e["occ"],
        }
    (d / "slots.json").write_text(dump_slots(slots))


def _build(slug: str, lib_sha: str, stamped: str | None, force: bool) -> bool:
    try:
        design_sha = hashing.design_sha(slug)
        meta = common.load_meta(slug)
    except (OSError, ValueError) as e:
        print(f"{slug}: {e}")
        return False
    # meta.yaml and taxonomy.yaml are outside design_sha, so their rules run even for current templates.
    errors, _ = lint.meta(slug, meta, lint.load_taxonomy())
    if errors:
        check.print_report(check.Report(slug, errors=errors))
        print(f"{slug}: not written")
        return False
    old = None
    if not force:
        try:
            old = load_slots(slug)
        except ValueError as e:
            print(f"{slug}: {e}; rebuilding")
    if old and _current(slug, old, design_sha):
        if stamped == lib_sha:
            print(f"{slug}: up to date")
            return True
        try:
            unchanged = check.probe_hashes(
                lambda t: check.render(slug, t, "16:9"), check.regimes(meta)
            ) == old.get("probes")
        except check.DesignError:
            unchanged = False  # check_slug below reports it
        if unchanged:
            print(f"{slug}: up to date (probe renders unchanged under the new render inputs)")
            return True
    report = check.check_slug(slug)
    check.print_report(report)
    if report.errors:
        print(f"{slug}: not written")
        return False
    _write(report, design_sha)
    print(f"{slug}: wrote {', '.join(report.templates)}, slots.json")
    return True


def verify_templates(slugs: list[str]) -> int:
    """Re-render every committed template of `slugs` under its template theme and compare it
    with the committed bytes, writing nothing. Returns 1 on any difference, missing build or
    render error, else 0."""
    bad = 0
    for slug in slugs:
        d = common.build_dir(slug)
        files = sorted(f for f in d.glob("*.svg") if walldye.TEMPLATE_NAME.match(f.name))
        if not files:
            print(f"{slug}: not built (run walldye build {slug})")
            bad += 1
            continue
        problems = []
        for f in files:
            aspect, light = walldye.parse_template_name(f.name)
            theme = fit.TEMPLATE_THEMES["light" if light else "dark"]
            try:
                fresh = normalise(check.render(slug, theme, aspect))
            except check.DesignError as e:
                problems.append(str(e))
                continue
            committed = f.read_bytes().decode()
            if fresh != committed:
                problems.append(
                    f"{f.name} differs from a fresh render under {theme}, {fit.first_diff(committed, fresh)}"
                )
        print(f"{slug}: " + ("ok" if not problems else "DRIFT"))
        for p in problems:
            print(f"  {p}")
        bad += bool(problems)
    print(f"verify: {len(slugs) - bad}/{len(slugs)} match")
    return 1 if bad else 0


def write_index() -> None:
    """Regenerate wallpapers/index.json: slug -> {aspects, draft, license, title} for every piece,
    license resolved through lint.license_of (null when meta.yaml breaks the licence rules). A
    piece whose meta.yaml or design.py cannot be read is left out, with a note on stderr."""
    index = {}
    for slug in common.slugs():
        try:
            m = common.load_meta(slug)
            index[slug] = {
                "aspects": check.aspects(slug),
                "draft": common.is_draft(m),
                "license": lint.license_of(m),
                "title": m.get("title"),
            }
        except (OSError, ValueError, SyntaxError) as e:
            print(f"index.json: left out {slug}: {e}", file=sys.stderr)
    (common.WALLPAPERS / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n"
    )


def run(slugs: list[str], all: bool = False, verify: bool = False, force: bool = False) -> int:
    """`walldye build`: for each of `slugs` (every piece with `all`) run check and, when it
    passes, rewrite build/ and slots.json; then regenerate index.json.

    A piece whose design_sha, walldye version and templates are unchanged is skipped when the
    render-lib hash still matches wallpapers/.render-lib.sha256, or when its probe renders are
    unchanged under the new render inputs; `force` rebuilds regardless. The render-lib hash is
    restamped only after a run that covered every piece without failures. With `verify`, run
    verify_templates() on `slugs` (every piece when none are named) instead. Returns 1 if any piece
    failed or a basis' condition number exceeds _basis.MAX_COND (nothing built), 2 if there is
    nothing to build, else 0.
    """
    if verify:
        return verify_templates(common.slugs() if all or not slugs else list(slugs))
    targets = common.slugs() if all else list(slugs)
    if not targets:
        print("nothing to build: name a slug or pass --all", file=sys.stderr)
        return 2
    for regime, basis in _basis.BASIS.items():
        if (cond := _basis.condition_number(basis)) > _basis.MAX_COND:
            print(
                f"the {regime} basis has condition number {cond:.1f}, over {_basis.MAX_COND}: fits would be unstable",
                file=sys.stderr,
            )
            return 1
    lib_sha, stamped = hashing.render_lib_sha(), hashing.stamped_render_lib_sha()
    failed = [slug for slug in targets if not _build(slug, lib_sha, stamped, force)]
    write_index()
    if stamped != lib_sha:
        if not failed and set(common.slugs()) <= set(targets):
            hashing.render_lib_stamp().write_text(lib_sha + "\n")
            print(f"stamped {hashing.render_lib_stamp().name}")
        else:
            print(
                "render inputs changed since the last stamp: run `walldye build --all` to restamp"
            )
    return 1 if failed else 0


def select(slots: dict, aspect: str, seeds: dict[str, str]) -> tuple[str, dict[str, str]]:
    """(key, seeds to apply) for recolouring a piece at `aspect` under `seeds` ({bg, fg, accent}):
    key is the slots.json entry "<aspect>/<regime>" for the seeds' regime, except that a
    dark-only piece under light seeds uses its dark entry with bg and fg swapped. KeyError if
    the piece has no entry for `aspect`."""
    s = {k: normalise_seed(seeds[k]) for k in SEEDS}
    if is_light(s["bg"], s["fg"]):
        if f"{aspect}/light" in slots:
            return f"{aspect}/light", s
        s = {"bg": s["fg"], "fg": s["bg"], "accent": s["accent"]}
    key = f"{aspect}/dark"
    if key not in slots:
        raise KeyError(f"no {key} entry in slots.json")
    return key, s


def recolour(template_svg: str, slots_entry: dict, seeds: dict[str, str]) -> str:
    """The browser's recolour: `template_svg` (the file `slots_entry` names, with `slots_entry`
    and `seeds` as select() returns them) with slot i set to coefs[occ[i]] = [a, b, c, dr, dg,
    db] evaluated per channel as ((a*bg + b*fg) + c*accent) + d, rounded half to even and
    clamped. Exact fireproof seeds return the template unchanged, and so does a template whose
    slot count is not slots_entry["n"] (the browser's fallback)."""
    s = {k: normalise_seed(seeds[k]) for k in SEEDS}
    spans = find_colours(template_svg)
    if s == _FIREPROOF or len(spans) != slots_entry["n"]:
        return template_svg
    bg, fg, accent = (hex_to_rgb(s[k]) for k in SEEDS)
    rows = [
        rgb_to_hex(*(a * bg[i] + b * fg[i] + c * accent[i] + d[i] for i in range(3)))
        for a, b, c, *d in slots_entry["coefs"]
    ]
    return substitute(template_svg, [rows[o] for o in slots_entry["occ"]])
