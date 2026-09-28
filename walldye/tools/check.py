"""walldye check: the gate `walldye build` runs before writing anything.

The parent process loads every design once and runs the static steps (the design lint, the
meta.yaml and data/ rules, ruff and Pyrefly); each (slug, variant) is then checked by
check_variant, in a process pool when several pieces are checked. Workers return plain data
and never write files.
"""

import json
import multiprocessing
import os
import re
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np
from numpy.typing import NDArray

from walldye import _check_themes
from walldye._aspect import canvas_size
from walldye._design import RenderSpec
from walldye._document import Document
from walldye._params import describe
from walldye.tools import common, hashing, knobs, lint
from walldye.tools.coefs import TEMPLATE_THEMES, Entry, first_diff, label, serialise_aspect
from walldye.tools.common import Regime

HASH_SEED: Final = "4242"
NEAR_CLONE: Final = 0.93
SLOW: Final = 120.0  # seconds; a variant whose check takes longer gets a warning
INK_WIDTH: Final = 256
FOCUS_WIDTH: Final = 480
_PRIVATE: Final = re.compile(r"\bwalldye\.(_[a-z]+)\.")
# The public module a private one's names are exported from, when it is not walldye itself.
_PUBLIC: Final = {"_affine": "walldye.geom.", "_noise": "walldye.field."}

type Ink = NDArray[np.float64]


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
    """One (slug, variant) to check. `wallpapers` is common.WALLPAPERS in the parent, which
    pool workers adopt; with `probes`, the check stops early when the variant's fresh probe
    hashes equal them (build's test for unchanged renders)."""

    wallpapers: str
    slug: str
    variant: str
    paranoid: bool = False
    probes: Mapping[str, str] | None = None


@dataclass
class Result:
    """What checking one (slug, variant) found and made; templates, entries, cells, probes,
    focus and ink are complete only when errors is empty."""

    slug: str
    variant: str
    errors: list[str] = field(default_factory=list[str])
    warnings: list[str] = field(default_factory=list[str])
    templates: dict[str, str] = field(default_factory=dict[str, str])  # file name -> svg
    entries: dict[str, Entry] = field(default_factory=dict[str, Entry])  # "<aspect>/<regime>"
    cells: list[float] = field(default_factory=list[float])
    probes: dict[str, str] = field(default_factory=dict[str, str])
    focus: tuple[float, float] | None = None
    ink: Ink | None = None  # the 16:9 dark template's ink map
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
    piece: common.Piece | None = None
    variants: tuple[str, ...] = ()


def prepare(slug: str, variant: str | None = None) -> Target:
    """Load `slug`, apply the meta.yaml rules (including variants:) and warn for each named
    variant value outside its knob's soft range. `variant` limits the variants to check;
    UsageError when the design does not declare it."""
    t = Target(slug, Report(slug))
    try:
        meta = common.load_meta(slug)
    except (OSError, ValueError) as e:
        t.report.errors.append(str(e))
        return t
    try:
        t.piece = load(slug)
    except DesignError as e:
        t.report.errors.append(str(e))
    names = ("default", *common.meta_variants(meta)) if t.piece is None else t.piece.variant_names()
    errors, warnings = lint.meta(slug, meta, lint.load_taxonomy(), names)
    t.report.errors += errors
    t.report.warnings += warnings
    if t.piece is not None:
        if variant is not None:
            common.variant_of(t.piece, slug, variant)
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
    path = common.piece_dir(t.slug) / "design.py"
    if not path.exists():
        return
    try:
        errors, warnings = lint.design(path)
    except SyntaxError:
        return
    t.report.errors += errors + lint.data(t.slug)
    t.report.warnings += warnings


def load(slug: str) -> common.Piece:
    """common.load(slug), with anything the import raises turned into a DesignError."""
    try:
        return common.load(slug)
    except Exception as e:  # whatever the import raises fails the check
        raise design_error(e, "import") from e


def draw(piece: common.Piece, spec: RenderSpec) -> Document:
    """An uncached draw, with anything the design raises turned into a DesignError."""
    try:
        return common.draw(piece, spec, cache=False)
    except Exception as e:  # whatever a design raises fails the check
        raise design_error(e, f"{spec.aspect} {spec.regime}: draw") from e


def _json(run: subprocess.CompletedProcess[str], what: str) -> list[dict[str, object]]:
    try:
        data: object = json.loads(run.stdout)
    except ValueError:
        said = run.stderr if run.stderr != "" else run.stdout
        raise RuntimeError(f"{what} failed: {said.strip()[-600:]}") from None
    if (d := common.as_dict(data)) is not None:
        data = d.get("errors")
    items = common.as_list(data)
    if items is None:
        raise RuntimeError(f"{what} printed no list of findings")
    return [e for e in map(common.as_dict, items) if e is not None]


def _row(finding: dict[str, object], key: str) -> int:
    location = common.as_dict(finding.get(key))
    row = finding.get("line") if location is None else location.get("row")
    return row if isinstance(row, int) else 0


def _pyrefly_message(finding: dict[str, object]) -> str:
    """A Pyrefly finding's full description on one line: the first line, the closest overload
    of a no-matching-overload error and the reason, with walldye's private modules named by the
    public module that exports them."""
    text = str(finding.get("description", finding.get("concise_description", "")))
    lines = text.split("\n")
    parts = [lines[0]]
    for line in lines[1:]:
        s = line.strip()
        if s.endswith("[closest match]"):
            parts.append(f"closest overload {s.removesuffix('[closest match]').strip()}")
        elif s != "Possible overloads:" and not line.startswith("    "):
            parts.append(s)
    return _PRIVATE.sub(lambda m: _PUBLIC.get(m.group(1), "walldye."), "; ".join(parts))


def tool_findings(paths: Sequence[Path]) -> dict[Path, list[str]]:
    """Errors from `ruff format --check`, `ruff check` (with the repo's pyproject.toml) and
    `pyrefly check` (with wallpapers/pyrefly.toml) for design files `paths`, keyed by resolved
    path, each tool run once over all of them. A tool common.tool() cannot find, or one
    printing no findings it can parse, is an error for every file."""
    out: dict[Path, list[str]] = {p.resolve(): [] for p in paths}
    if len(paths) == 0:
        return out
    files = [str(p) for p in paths]
    config = common.ROOT / "pyproject.toml"
    runs = {
        "ruff format": ("ruff", "format", "--check", "--config", str(config)),
        "ruff check": ("ruff", "check", "--no-fix", "--config", str(config)),
        "pyrefly": ("pyrefly", "check", "-c", str(common.DESIGN_PYREFLY)),
    }
    for what, (program, *args) in runs.items():
        exe = common.tool(program)
        if exe is None:
            for messages in out.values():
                messages.append(f"{what}: {program} not found; run walldye through uv run")
            continue
        run = subprocess.run(
            [str(exe), *args, "--output-format", "json", *files],
            cwd=common.ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            findings = _json(run, what)
        except RuntimeError as e:
            for messages in out.values():
                messages.append(str(e))
            continue
        for f in findings:
            name = f.get("filename", f.get("path"))
            path = (common.ROOT / str(name)).resolve()
            if path not in out or f.get("severity", "error") != "error":
                continue
            code = f.get("code")
            if what == "ruff format" and code == "unformatted":
                text = f"ruff format: the file would be reformatted (run uv run ruff format {name})"
            elif what == "pyrefly":
                text = f"line {_row(f, 'line')}: pyrefly [{f.get('name')}]: {_pyrefly_message(f)}"
            else:
                text = f"line {_row(f, 'location')}: ruff {code}: {f.get('message')}"
            out[path].append(text)
    return out


def source_checks(targets: Sequence[Target]) -> None:
    """Add ruff and Pyrefly findings for the design.py of each of `targets` to its report."""
    paths = {
        (common.piece_dir(t.slug) / "design.py").resolve(): t
        for t in targets
        if (common.piece_dir(t.slug) / "design.py").exists()
    }
    for path, messages in tool_findings(list(paths)).items():
        paths[path].report.errors += messages


def probe_hashes(docs: Mapping[tuple[str, Regime], Document]) -> dict[str, str]:
    """slots.json `probes`: sha256 of the 16:9 dark document under fireproof, and of each
    regime's 16:9 document under its sample theme."""
    probes = {"fireproof": _sha(docs["16:9", "dark"], TEMPLATE_THEMES["dark"])}
    for regime in common.REGIMES:
        probes[regime] = _sha(docs["16:9", regime], _check_themes.SAMPLE[regime])
    return probes


def _sha(doc: Document, theme: common.Theme) -> str:
    return hashing.sha256(doc.to_svg(common.tokens_of(theme)).encode())


def check_variant(task: Task) -> Result:
    """Check one (slug, variant): determinism (two in-process draws per native aspect and
    regime, then a PYTHONHASHSEED subprocess), viewBox, the templates and their slot tables, the
    constant-slot rule, the template limits, pixel origins, probes, focus and the ink map,
    and with task.paranoid a fresh import per serialisation. A determinism failure stops it
    before any geometry step; so does an exception from the design."""
    common.WALLPAPERS = Path(task.wallpapers)
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
        for regime in common.REGIMES:
            docs["16:9", regime] = draw(piece, RenderSpec(variant, params, "16:9", regime))
        r.probes = probe_hashes(docs)
        if r.probes == dict(task.probes):
            r.unchanged = True
            return

    keys = {
        (aspect, regime): common.key(slug, variant, aspect, regime)
        for aspect in piece.aspects
        for regime in common.REGIMES
    }
    # The fresh process draws while this one does; it only needs the keys.
    fresh = _start_fresh(list(keys.values()))
    try:
        expected: dict[str, str] = {}
        for (aspect, regime), k in keys.items():
            spec = RenderSpec(variant, params, aspect, regime)
            first = docs[aspect, regime] if (aspect, regime) in docs else draw(piece, spec)
            docs[aspect, regime] = first
            tokens = common.tokens_of(_check_themes.SAMPLE[regime])
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
    r.errors += _fresh_errors(done, expected)
    if len(r.errors) > 0:
        return

    for (aspect, regime), doc in docs.items():
        w, h = canvas_size(aspect)
        if (got := common.viewbox(doc.skeleton())) != f"0 0 {w} {h}":
            r.errors.append(f'{aspect} {regime}: viewBox must be "0 0 {w} {h}", not {got!r}')
    for aspect in piece.aspects:
        templates, entries, errors = serialise_aspect(
            {g: docs[aspect, g] for g in common.REGIMES}, aspect
        )
        r.templates.update(templates)
        r.entries.update(entries)
        r.errors += errors
    for name, text in r.templates.items():
        errors, warnings = lint.svg(text)
        r.errors += [f"{name}: {e}" for e in errors]
        r.warnings += [f"{name}: {w}" for w in warnings]
    for aspect in piece.aspects:
        grids = [g for regime in common.REGIMES for g in docs[aspect, regime].pixel_grids]
        r.warnings += [f"{aspect}: {w}" for w in lint.pixel_origins(grids)]
    r.cells = sorted({cell for doc in docs.values() for cell, _, _ in doc.pixel_grids})
    r.probes = probe_hashes(docs)
    dark = r.templates.get("16x9.svg")
    if dark is not None:
        bg = common.background(dark)
        r.focus = common.focus(common.rasterise(dark, FOCUS_WIDTH), bg)
        r.ink = common.ink_map(common.rasterise(dark, INK_WIDTH), bg)
    if task.paranoid and not isinstance(piece, common.LegacyPiece):
        r.errors += _paranoid(slug, variant, docs)


def _start_fresh(keys: Sequence[str]) -> subprocess.Popen[str]:
    """A running `python -m walldye _hashes` subprocess under PYTHONHASHSEED for `keys`; read
    it with communicate() and judge it with _fresh_errors()."""
    return subprocess.Popen(
        [sys.executable, "-m", "walldye", "_hashes", str(common.WALLPAPERS), *keys],
        env={**os.environ, "PYTHONHASHSEED": HASH_SEED},
        cwd=common.ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _fresh_errors(run: subprocess.CompletedProcess[str], expected: Mapping[str, str]) -> list[str]:
    """Errors for the keys the finished _start_fresh() subprocess `run` drew differently from
    `expected` {key: sha256}."""
    if run.returncode != 0:
        return [f"determinism subprocess failed: {run.stderr.strip()[-600:]}"]
    try:
        got = common.as_dict(json.loads(run.stdout))
    except ValueError:
        got = None
    if got is None:
        return [f"determinism subprocess printed {run.stdout[:200]!r}"]
    errors: list[str] = []
    for k, sha in expected.items():
        if got.get(k) != sha:
            _, _, aspect, regime = k.split("@")
            errors.append(
                f"{aspect} {regime}: a fresh process with PYTHONHASHSEED={HASH_SEED} draws it"
                " differently (iterating a set of strings? hash()?)"
            )
    return errors


def _paranoid(slug: str, variant: str, docs: Mapping[tuple[str, Regime], Document]) -> list[str]:
    """Errors where a fresh import of the design, drawn for one serialisation, differs from
    the shared document serialised under the same theme."""
    errors: list[str] = []
    for (aspect, regime), doc in docs.items():
        rest = _check_themes.PROBES[regime] + _check_themes.HELD_OUT[regime]
        for theme in [TEMPLATE_THEMES[regime], *rest]:
            tokens = common.tokens_of(theme)
            try:
                piece = common.fresh(slug)
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


def hashes_main(args: Sequence[str]) -> int:
    """`python -m walldye _hashes <wallpapers dir> <slug@variant@aspect@regime>...`: print a
    JSON object mapping each key to the sha256 of that draw serialised under the regime's
    sample theme, made in this process. Design errors propagate (non-zero exit)."""
    common.WALLPAPERS = Path(args[0])
    out: dict[str, str] = {}
    for k in args[1:]:
        slug, variant, aspect, regime = k.split("@")
        if regime not in ("dark", "light"):
            raise ValueError(f"bad key {k!r}")
        piece = common.load(slug)
        spec = RenderSpec(
            variant, piece.params(variant), aspect, "light" if regime == "light" else "dark"
        )
        out[k] = _sha(common.draw(piece, spec, cache=False), _check_themes.SAMPLE[spec.regime])
    print(json.dumps(out))
    return 0


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


def committed_ink(slug: str, variant: str) -> Ink | None:
    """The ink map of a variant's committed build/[<variant>/]16x9.svg, measured from its own
    background; None when not built."""
    path = common.build_dir(slug, variant) / "16x9.svg"
    if not path.exists():
        return None
    svg = path.read_text()
    return common.ink_map(common.rasterise(svg, INK_WIDTH), common.background(svg))


def siblings(report: Report, names: Sequence[str], fresh: Mapping[str, Ink | None]) -> None:
    """The variant sibling rule over the versions `names` of report.slug: two 16:9 dark
    templates with an ink-map cosine of NEAR_CLONE or more are an error when at least one of
    them was checked afresh (a key of `fresh`); the other is fresh too or committed. Pairs of
    committed templates are not compared again. A version with neither is skipped with a note;
    one whose fresh check failed (None) is skipped silently."""
    if all(ink is None for ink in fresh.values()):
        return
    maps: dict[str, Ink] = {}
    for name in names:
        ink = fresh[name] if name in fresh else committed_ink(report.slug, name)
        if ink is not None:
            maps[name] = ink
        elif name not in fresh:
            report.notes.append(
                f"{name} is not built yet, so the other versions were not compared with it"
            )
    ordered = list(maps)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            if a not in fresh and b not in fresh:
                continue
            if (sim := float(maps[a] @ maps[b])) >= NEAR_CLONE:
                report.errors.append(
                    f"versions {a} and {b} look alike (ink-map cosine {sim:.2f}, must be below"
                    f" {NEAR_CLONE}): a variant must change what is depicted"
                )


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


def near_clones(slugs: Sequence[str]) -> None:
    """`check --similar`: print pairs involving `slugs` whose committed default build/16x9.svg
    ink maps have cosine >= NEAR_CLONE, most similar first, then the `slugs` that have no
    committed template."""
    maps: dict[str, Ink] = {}
    skipped: list[str] = []
    for slug in sorted(set(common.slugs()) | set(slugs)):
        ink = committed_ink(slug, "default")
        if ink is not None:
            maps[slug] = ink
        elif slug in slugs:
            skipped.append(slug)
    names = list(maps)
    pairs = [
        (sim, a, b) for i, a in enumerate(names) for b in names[i + 1 :]
        if (a in slugs or b in slugs) and (sim := float(maps[a] @ maps[b])) >= NEAR_CLONE
    ]  # fmt: skip
    for sim, a, b in sorted(pairs, reverse=True):
        print(f"similar ({sim:.2f}): {a} ~ {b}")
    if len(skipped) > 0:
        print(f"similar: skipped, no build/16x9.svg: {', '.join(skipped)}")


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
    targets = [prepare(s, variant) for s in (common.slugs() if all else slugs)]
    if len(targets) == 0:
        print("nothing to check: name a slug or pass --all", file=sys.stderr)
        return 2
    for t in targets:
        lint_source(t)
    source_checks(targets)
    tasks = [Task(str(common.WALLPAPERS), t.slug, v, paranoid) for t in targets for v in t.variants]
    results = run_tasks(check_variant, tasks, workers(jobs, len(tasks)))
    failed = 0
    for t in targets:
        for _ in t.variants:
            t.report.add(next(results))
        if t.piece is not None:
            fresh = {v: r.ink for v, r in t.report.results.items()}
            siblings(t.report, t.piece.variant_names(), fresh)
        print_report(t.report)
        failed += len(t.report.errors) > 0
    if similar:
        near_clones([t.slug for t in targets])
    print(f"{len(targets) - failed}/{len(targets)} ok")
    return 1 if failed > 0 else 0
