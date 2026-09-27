"""walldye check: the gate `walldye build` runs before writing anything (check list steps 1-8)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

import walldye
from walldye import _basis
from walldye._basis import Theme
from walldye._theme import SEEDS
from walldye.tools import common, fit, hashing, lint

HASHES_CMD = [sys.executable, "-m", "walldye", "_hashes"]
HASH_SEED = "4242"
NEAR_CLONE = 0.93


@dataclass
class Report:
    """One piece's check result: errors and warnings and, when errors is empty, its templates,
    slots.json entries, pixel cell sizes and probe hashes."""

    slug: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    templates: dict[str, str] = field(default_factory=dict)  # build/ file name -> normalised svg
    entries: dict[str, dict] = field(default_factory=dict)  # "<aspect>/<regime>" -> {file, n, coefs, occ}
    cells: list[float] = field(default_factory=list)
    probes: dict[str, str] = field(default_factory=dict)


def theme_spec(theme: str | Theme) -> str | dict[str, str]:
    """A preset name or seed triple as common.render() takes it."""
    return theme if isinstance(theme, str) else dict(zip(SEEDS, theme))


def aspects(slug: str) -> list[str]:
    """The aspects a piece is built at: its native SITE_ASPECTS, plus 16:9 always."""
    native = walldye.native_aspects(common.design_aspects(slug))
    return native if "16:9" in native else ["16:9", *native]


def regimes(meta: dict) -> list[str]:
    """["dark"] for a `themes: [dark]` piece, else ["dark", "light"]."""
    return ["dark"] if hashing.themes(meta) == ["dark"] else ["dark", "light"]


def probe_hashes(render_16x9: Callable[[str | Theme], str], regimes: list[str]) -> dict[str, str]:
    """slots.json `probes`: sha256 of the piece's 16:9 render (`render_16x9(theme)`) under
    fireproof and under the first basis theme of each regime."""
    probes = {"fireproof": hashing.sha256(render_16x9("fireproof").encode())}
    for regime in regimes:
        probes[regime] = hashing.sha256(render_16x9(_basis.BASIS[regime][0]).encode())
    return probes


class DesignError(Exception):
    """A render of the piece raised; the message says under which theme, at which aspect, and where in design.py."""


def render(slug: str, theme: str | Theme, aspect: str) -> str:
    """common.render() of a piece under a preset name or seed triple; DesignError if the design raises."""
    try:
        return common.render(slug, theme_spec(theme), aspect)
    except Exception as e:  # whatever a design raises fails the check
        frames = [f for f in traceback.extract_tb(e.__traceback__) if Path(f.filename).name == "design.py"]
        where = f" (design.py line {frames[-1].lineno})" if frames else ""
        raise DesignError(f"{aspect}: render under {fit.label(theme)} failed: {type(e).__name__}: {e}{where}") from e


class _Renders:
    """One piece's renders, cached by (aspect, theme), with the pixel grids of each."""

    def __init__(self, slug: str):
        self.slug = slug
        self.svg: dict = {}
        self.grids: dict = {}

    def __call__(self, aspect: str, theme: str | Theme) -> str:
        key = (aspect, theme)
        if key not in self.svg:
            self.svg[key] = render(self.slug, theme, aspect)
            self.grids[key] = walldye.pixel_grids()
        return self.svg[key]


def hashes_main(args: list[str]) -> int:
    """`python -m walldye _hashes <wallpapers dir> <slug>@<aspect>@<theme token>...`: print a JSON
    object mapping each key to the sha256 of that render, made in this process. Render errors
    propagate (non-zero exit)."""
    common.WALLPAPERS = Path(args[0])
    out = {}
    for key in args[1:]:
        slug, aspect, token = key.split("@")
        out[key] = hashing.sha256(common.render(slug, token, aspect).encode())
    print(json.dumps(out))
    return 0


def _determinism(slug: str, aspects: list[str], regimes: list[str], renders: _Renders) -> list[str]:
    errors, expected = [], {}
    for aspect in aspects:
        for regime in regimes:
            theme = _basis.BASIS[regime][0]
            first = renders(aspect, theme)
            if render(slug, theme, aspect) != first:
                errors.append(f"{aspect}: two renders under {fit.label(theme)} differ (unseeded randomness?)")
            expected[f"{slug}@{aspect}@{fit.label(theme)}"] = hashing.sha256(first.encode())
    if errors:
        return errors
    run = subprocess.run(
        [*HASHES_CMD, str(common.WALLPAPERS), *expected],
        env={**os.environ, "PYTHONHASHSEED": HASH_SEED}, cwd=common.ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    if run.returncode:
        return [f"determinism subprocess failed: {run.stderr.strip()[-600:]}"]
    got = json.loads(run.stdout)
    return [
        f"{key.split('@')[1]}: render under {key.split('@')[2]} differs in a fresh process with PYTHONHASHSEED={HASH_SEED} "
        "(iterating a set of strings? hash()?)"
        for key, sha in expected.items() if got.get(key) != sha
    ]  # fmt: skip


def check_slug(slug: str) -> Report:
    """Run check steps 1-7 on one piece (plus the meta.yaml rules), in order. A determinism
    failure stops the check before any geometry step; so does an exception from the design."""
    report = Report(slug)
    try:
        meta = common.load_meta(slug)
        legacy = common.is_legacy(slug)
        piece_aspects = aspects(slug)
    except (OSError, ValueError, SyntaxError) as e:
        report.errors.append(str(e))
        return report
    errors, warnings = lint.meta(slug, meta, lint.load_taxonomy())
    report.errors += errors
    report.warnings += warnings
    if not legacy:
        errors, warnings = lint.source(common.piece_dir(slug) / "design.py")
        report.errors += errors
        report.warnings += warnings
    piece_regimes = regimes(meta)
    template_themes = [fit.TEMPLATE_THEMES[r] for r in piece_regimes]
    renders = _Renders(slug)
    try:
        if errors := _determinism(slug, piece_aspects, piece_regimes, renders):
            report.errors += errors
            return report
        for aspect in piece_aspects:
            w, h = walldye.canvas_size(aspect)
            for theme in template_themes:
                if (got := common.viewbox(renders(aspect, theme))) != f"0 0 {w} {h}":
                    report.errors.append(f'{aspect}: viewBox under {theme} must be "0 0 {w} {h}", not {got!r}')
        for aspect in piece_aspects:
            templates, entries, errors = fit.fit_aspect(partial(renders, aspect), aspect, piece_regimes)
            report.templates.update(templates)
            report.entries.update(entries)
            report.errors += errors
        for name, text in report.templates.items():
            errors, warnings = lint.svg(text)
            report.errors += [f"{name}: {e}" for e in errors]
            report.warnings += [f"{name}: {w}" for w in warnings]
        grids = {a: [g for t in template_themes for g in renders.grids[(a, t)]] for a in piece_aspects}
        report.cells = sorted({cell for g in grids.values() for cell, _, _ in g})
        report.warnings += [f"{a}: {w}" for a, g in grids.items() for w in lint.pixel_origins(g)]
        report.probes = probe_hashes(partial(renders, "16:9"), piece_regimes)
    except DesignError as e:
        report.errors.append(str(e))
    return report


def print_report(report: Report) -> None:
    status = f"{len(report.errors)} error(s)" if report.errors else "ok"
    print(f"{report.slug}: {status}" + (f", {len(report.warnings)} warning(s)" if report.warnings else ""))
    for e in report.errors:
        print(f"  error: {e}")
    for w in report.warnings:
        print(f"  warning: {w}")


def near_clones(slugs: list[str]) -> None:
    """Check step 8: print pairs involving `slugs` whose committed build/16x9.svg ink maps have
    cosine >= NEAR_CLONE, most similar first, then the `slugs` that have no committed template."""
    bg = walldye.PRESETS["fireproof"]["bg"]
    maps, skipped = {}, []
    for slug in sorted(set(common.slugs()) | set(slugs)):
        template = common.build_dir(slug) / "16x9.svg"
        if template.exists():
            maps[slug] = common.ink_map(common.rasterise(template.read_text(), 256), bg)
        elif slug in slugs:
            skipped.append(slug)
    names = list(maps)
    pairs = [
        (sim, a, b) for i, a in enumerate(names) for b in names[i + 1 :]
        if (a in slugs or b in slugs) and (sim := float(maps[a] @ maps[b])) >= NEAR_CLONE
    ]  # fmt: skip
    for sim, a, b in sorted(pairs, reverse=True):
        print(f"similar ({sim:.2f}): {a} ~ {b}")
    if skipped:
        print(f"set: skipped, no build/16x9.svg: {', '.join(skipped)}")


def run(slugs: list[str], all: bool = False, set_mode: bool = False) -> int:
    """`walldye check`: check `slugs` (every piece with `all`), print a report per piece and,
    with `set_mode`, the near-clone advisory. Returns 1 if any piece has errors, 2 if there is
    nothing to check, else 0 (warnings and the advisory never fail)."""
    targets = common.slugs() if all else list(slugs)
    if not targets:
        print("nothing to check: name a slug or pass --all", file=sys.stderr)
        return 2
    failed = 0
    for slug in targets:
        report = check_slug(slug)
        print_report(report)
        failed += bool(report.errors)
    if set_mode:
        near_clones(targets)
    print(f"{len(targets) - failed}/{len(targets)} ok")
    return 1 if failed else 0
