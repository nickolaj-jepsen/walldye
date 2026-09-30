"""walldye check: the gate `walldye build` runs before writing anything.

The parent process loads every design once and runs the static steps (the design lint and the
meta.yaml and data/ rules); each (slug, variant) is then checked by
check_variant, in a process pool when several pieces are checked. Workers return plain data
and never write files.
"""

import multiprocessing
import os
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from walldye._design import RenderSpec
from walldye._document import Document
from walldye._params import describe
from walldye._theme import REGIMES, Regime
from walldye.tools import determinism, hashing, knobs, lint, loader, metadata, paths, raster, themes
from walldye.tools.coefs import TEMPLATE_THEMES, Entry, first_diff, label, serialize_aspect
from walldye.tools.similar import near_clones

SLOW: Final = 120.0  # seconds; a variant whose check takes longer gets a warning


class DesignError(Exception):
    """Importing or drawing the design raised; the message says where."""


def design_error(e: BaseException, what: str) -> DesignError:
    """`what failed: <type>: <message> (design.py line N)` for an exception from a design."""
    frames = [
        f for f in traceback.extract_tb(e.__traceback__) if Path(f.filename).name == "design.py"
    ]
    where = f" (design.py line {frames[-1].lineno})" if len(frames) > 0 else ""
    return DesignError(f"{what} failed: {type(e).__name__}: {e}{where}")


@dataclass(frozen=True)
class Task:
    """One (slug, variant) to check. `wallpapers` is paths.WALLPAPERS in the parent, which
    pool workers adopt; with `probes`, the check stops early when the variant's fresh probe
    hashes equal them (build's test for unchanged renders)."""

    wallpapers: str
    slug: str
    variant: str
    paranoid: bool = False
    probes: Mapping[str, str] | None = None


@dataclass
class Result:
    """What checking one (slug, variant) found and made; templates, entries, cells, probes
    and focus are complete only when errors is empty."""

    slug: str
    variant: str
    errors: list[str] = field(default_factory=list[str])
    warnings: list[str] = field(default_factory=list[str])
    templates: dict[str, str] = field(default_factory=dict[str, str])  # file name -> svg
    entries: dict[str, Entry] = field(default_factory=dict[str, Entry])  # "<aspect>/<regime>"
    cells: list[float] = field(default_factory=list[float])
    probes: dict[str, str] = field(default_factory=dict[str, str])
    focus: tuple[float, float] | None = None
    seconds: float = 0.0
    unchanged: bool = False  # build: the probes matched, so nothing else was checked


@dataclass
class Report:
    """One piece's check: its own errors, warnings and notes plus each variant's result."""

    slug: str
    errors: list[str] = field(default_factory=list[str])
    warnings: list[str] = field(default_factory=list[str])
    notes: list[str] = field(default_factory=list[str])
    results: dict[str, Result] = field(default_factory=dict[str, Result])

    def add(self, result: Result) -> None:
        """Take in a variant's result, prefixing its messages with a named variant's name."""
        prefix = "" if result.variant == "default" else f"{result.variant}: "
        self.errors += [prefix + e for e in result.errors]
        self.warnings += [prefix + w for w in result.warnings]
        self.results[result.variant] = result


@dataclass
class Target:
    """A piece after the static steps: its report so far, its design (None when it failed to
    load) and the variants to check."""

    slug: str
    report: Report
    piece: loader.Piece | None = None
    variants: tuple[str, ...] = ()


def prepare(slug: str, variant: str | None = None) -> Target:
    """Load `slug`, apply the meta.yaml rules (including variants:) and warn for each named
    variant value outside its knob's soft range. `variant` limits the variants to check;
    UsageError when the design does not declare it."""
    t = Target(slug, Report(slug))
    try:
        meta = metadata.load_meta(slug)
    except (OSError, ValueError) as e:
        t.report.errors.append(str(e))
        return t
    try:
        t.piece = load(slug)
    except DesignError as e:
        t.report.errors.append(str(e))
    names = (
        ("default", *metadata.meta_variants(meta)) if t.piece is None else t.piece.variant_names()
    )
    try:
        taxonomy = lint.piece.load_taxonomy()
    except ValueError as e:
        t.report.errors.append(str(e))
        taxonomy = None
    errors, warnings = lint.piece.meta(slug, meta, taxonomy, names)
    t.report.errors += errors
    t.report.warnings += warnings
    if t.piece is not None:
        if variant is not None:
            loader.variant_of(t.piece, slug, variant)
        t.variants = t.piece.variant_names() if variant is None else (variant,)
        infos = describe(t.piece.params_type)
        for v, params in t.piece.variants.items():
            if v not in t.variants:
                continue
            for info in infos:
                if (w := knobs.outside(info, getattr(params, info.name))) is not None:
                    t.report.warnings.append(f"{v}: {w}")
    return t


def lint_source(t: Target) -> None:
    """Add the design lint and the data/ rules of t.slug to its report; a design that does
    not parse is left to the import error prepare() reported."""
    path = paths.piece_dir(t.slug) / "design.py"
    if not path.exists():
        return
    try:
        errors, warnings = lint.source.design(path)
    except SyntaxError:
        return
    t.report.errors += errors + lint.piece.data(t.slug)
    t.report.warnings += warnings


def load(slug: str) -> loader.Piece:
    """loader.load(slug), with anything the import raises turned into a DesignError."""
    try:
        return loader.load(slug)
    except Exception as e:  # whatever the import raises fails the check
        raise design_error(e, "import") from e


def draw(piece: loader.Piece, spec: RenderSpec) -> Document:
    """An uncached draw, with anything the design raises turned into a DesignError."""
    try:
        return loader.draw(piece, spec, cache=False)
    except Exception as e:  # whatever a design raises fails the check
        raise design_error(e, f"{spec.aspect} {spec.regime}: draw") from e


def probe_hashes(docs: Mapping[tuple[str, Regime], Document]) -> dict[str, str]:
    """slots.json `probes`: sha256 of the 16:9 dark document under fireproof, and of each
    regime's 16:9 document under its sample theme."""
    probes = {"fireproof": determinism.sample_sha(docs["16:9", "dark"], TEMPLATE_THEMES["dark"])}
    for regime in REGIMES:
        probes[regime] = determinism.sample_sha(docs["16:9", regime], themes.SAMPLE[regime])
    return probes


def check_variant(task: Task) -> Result:
    """Check one (slug, variant): determinism (two in-process draws per native aspect and
    regime, then a PYTHONHASHSEED subprocess), viewBox, the templates and their slot tables, the
    constant-slot rule, the template limits, pixel origins, probes and focus,
    and with task.paranoid a fresh import per serialization. A determinism failure stops it
    before any geometry step; so does an exception from the design."""
    paths.WALLPAPERS = Path(task.wallpapers)
    start = time.perf_counter()
    r = Result(task.slug, task.variant)
    try:
        _check(task, r)
    except DesignError as e:
        r.errors.append(str(e))
    r.seconds = time.perf_counter() - start
    if r.seconds > SLOW and not r.unchanged:
        r.warnings.append(f"the check took {r.seconds:.0f} s, over {SLOW:.0f} s")
    return r


def _check(task: Task, r: Result) -> None:
    slug, variant = task.slug, task.variant
    piece = load(slug)
    params = piece.params(variant)
    docs: dict[tuple[str, Regime], Document] = {}
    if task.probes is not None:
        for regime in REGIMES:
            docs["16:9", regime] = draw(piece, RenderSpec(variant, params, "16:9", regime))
        r.probes = probe_hashes(docs)
        if r.probes == dict(task.probes):
            r.unchanged = True
            return

    keys = {
        (aspect, regime): paths.key(slug, variant, aspect, regime)
        for aspect in piece.aspects
        for regime in REGIMES
    }
    # The fresh process draws while this one does; it only needs the keys.
    fresh = determinism.start_fresh(list(keys.values()))
    try:
        expected: dict[str, str] = {}
        for (aspect, regime), k in keys.items():
            spec = RenderSpec(variant, params, aspect, regime)
            first = docs[aspect, regime] if (aspect, regime) in docs else draw(piece, spec)
            docs[aspect, regime] = first
            tokens = themes.tokens_of(themes.SAMPLE[regime])
            a, b = first.to_svg(tokens), draw(piece, spec).to_svg(tokens)
            if a != b:
                r.errors.append(
                    f"{aspect} {regime}: two draws differ, {first_diff(a, b)}: does draw change"
                    " module-level state, or use randomness outside s.rng?"
                )
            expected[k] = hashing.sha256(a.encode())
        if len(r.errors) > 0:
            return
        out, err = fresh.communicate()
        done = subprocess.CompletedProcess(fresh.args, fresh.wait(), out, err)
    finally:
        if fresh.returncode is None:
            fresh.kill()
            fresh.wait()
    r.errors += determinism.fresh_errors(done, expected)
    if len(r.errors) > 0:
        return

    for (aspect, regime), doc in docs.items():
        r.errors += [
            f"{aspect} {regime}: {e}" for e in lint.templates.viewbox(doc.skeleton(), aspect)
        ]
    for aspect in piece.aspects:
        templates, entries, errors = serialize_aspect({g: docs[aspect, g] for g in REGIMES}, aspect)
        r.templates.update(templates)
        r.entries.update(entries)
        r.errors += errors
    for name, text in r.templates.items():
        errors, warnings = lint.templates.svg(text)
        r.errors += [f"{name}: {e}" for e in errors]
        r.warnings += [f"{name}: {w}" for w in warnings]
    for aspect in piece.aspects:
        grids = [g for regime in REGIMES for g in docs[aspect, regime].pixel_grids]
        r.warnings += [f"{aspect}: {w}" for w in lint.templates.pixel_origins(grids)]
    r.cells = sorted({cell for doc in docs.values() for cell, _, _ in doc.pixel_grids})
    r.probes = probe_hashes(docs)
    dark = r.templates.get("16x9.svg")
    if dark is not None:
        r.focus = raster.focus(raster.rasterize(dark, raster.FOCUS_WIDTH), raster.background(dark))
    if task.paranoid and not isinstance(piece, loader.LegacyPiece):
        r.errors += _paranoid(slug, variant, docs)


def _paranoid(slug: str, variant: str, docs: Mapping[tuple[str, Regime], Document]) -> list[str]:
    """Errors where a fresh import of the design, drawn for one serialization, differs from
    the shared document serialized under the same theme."""
    errors: list[str] = []
    for (aspect, regime), doc in docs.items():
        rest = themes.PROBES[regime] + themes.HELD_OUT[regime]
        for theme in [TEMPLATE_THEMES[regime], *rest]:
            tokens = themes.tokens_of(theme)
            try:
                piece = loader.fresh(slug)
            except Exception as e:  # whatever the import raises fails the check
                raise design_error(e, "fresh import") from e
            got = draw(piece, RenderSpec(variant, piece.params(variant), aspect, regime))
            want = doc.to_svg(tokens)
            got = got.to_svg(tokens)
            if got != want:
                errors.append(
                    f"{aspect} {regime}: a fresh import drawn for {label(theme)} differs from the"
                    f" shared document, {first_diff(want, got)}: draw depends on module state"
                )
                break
    return errors


def workers(jobs: int | None, tasks: int) -> int:
    """How many processes to run `tasks` (slug, variant) tasks in: 1 for a single task, else
    `jobs` (default: every core)."""
    if tasks <= 1:
        return 1
    if jobs is not None:
        return jobs
    cores = os.cpu_count()
    return 1 if cores is None else cores


def run_tasks[T, R](fn: Callable[[T], R], tasks: Sequence[T], jobs: int) -> Iterator[R]:
    """fn over `tasks`, results in task order: in this process when `jobs` is 1 or there is one
    task, else in a forkserver process pool of up to `jobs` workers."""
    if jobs <= 1 or len(tasks) <= 1:
        yield from map(fn, tasks)
        return
    context = multiprocessing.get_context("forkserver")
    with ProcessPoolExecutor(max_workers=min(jobs, len(tasks)), mp_context=context) as pool:
        yield from pool.map(fn, tasks)


def print_report(report: Report) -> None:
    status = f"{len(report.errors)} error(s)" if len(report.errors) > 0 else "ok"
    warned = f", {len(report.warnings)} warning(s)" if len(report.warnings) > 0 else ""
    print(f"{report.slug}: {status}{warned}")
    for e in report.errors:
        print(f"  error: {e}")
    for w in report.warnings:
        print(f"  warning: {w}")
    for n in report.notes:
        print(f"  note: {n}")


def run(
    slugs: Sequence[str],
    all: bool = False,
    variant: str | None = None,
    paranoid: bool = False,
    similar: bool = False,
    jobs: int | None = None,
) -> int:
    """`walldye check`: check `slugs` (every piece with `all`), every variant or only
    `variant`, print a report per piece in slug order and, with `similar`, the near-clone
    advisory. Returns 1 if any piece has errors, 2 if there is nothing to check, else 0
    (warnings, notes and the advisory never fail). UsageError for an undeclared `variant`."""
    targets = [prepare(s, variant) for s in (paths.slugs() if all else slugs)]
    if len(targets) == 0:
        print("nothing to check: name a slug or pass --all", file=sys.stderr)
        return 2
    for t in targets:
        lint_source(t)
    tasks = [Task(str(paths.WALLPAPERS), t.slug, v, paranoid) for t in targets for v in t.variants]
    results = run_tasks(check_variant, tasks, workers(jobs, len(tasks)))
    failed = 0
    for t in targets:
        for _ in t.variants:
            t.report.add(next(results))
        print_report(t.report)
        failed += len(t.report.errors) > 0
    if similar:
        near_clones([t.slug for t in targets])
    print(f"{len(targets) - failed}/{len(targets)} ok")
    return 1 if failed > 0 else 0
