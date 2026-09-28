"""Load and draw converted designs once each, to see which run under API v2.

    uv run python scripts/port/smoke.py DIR [--svg-dir OUT] [--jobs N] [--timeout S] [--json FILE]

DIR holds `<slug>/design.py` files (the codemod's --out, or wallpapers/). Each design is imported
and drawn in its own subprocess (default variant, 16:9, dark regime) and serialised under
fireproof; with --svg-dir the SVG is written to OUT/<slug>.svg, which `sheets.py --after-dir`
compares with the nixos original before anything is built. Prints one line per design and a
count per status: ok, import (the module fails to import), not-design (no @design draw), draw
(drawing raised) or timeout.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


class Failed(Exception):
    """A design that failed at one stage ("import", "not-design" or "draw")."""

    def __init__(self, stage: str, error: str) -> None:
        super().__init__(error)
        self.stage, self.error = stage, error


def one(path: Path, svg_out: Path | None) -> dict[str, object]:
    """Import and draw `path` in this process; the result as a JSON-able dict. Raises Failed."""
    from walldye._design import Design, RenderSpec
    from walldye._theme import parse_theme

    slug = path.parent.name
    start = time.perf_counter()
    try:
        spec = importlib.util.spec_from_file_location(f"_walldye_{slug.replace('-', '_')}", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception as exc:  # whatever the import raises is the result
        raise Failed("import", _describe(exc, path)) from exc
    design = getattr(module, "draw", None)
    if not isinstance(design, Design):
        raise Failed("not-design", "draw is not a @design")
    try:
        doc = design.draw(RenderSpec("default", design.params(), "16:9", "dark"))
        svg = doc.to_svg(parse_theme("fireproof"))
    except Exception as exc:  # whatever the design raises is the result
        raise Failed("draw", _describe(exc, path)) from exc
    if svg_out is not None:
        svg_out.mkdir(parents=True, exist_ok=True)
        (svg_out / f"{slug}.svg").write_text(svg)
    return {
        "slug": slug,
        "status": "ok",
        "seconds": round(time.perf_counter() - start, 2),
        "bytes": len(svg),
    }


def _describe(exc: BaseException, path: Path) -> str:
    """The exception with the deepest frame inside the design file, if any."""
    where = ""
    for frame in traceback.extract_tb(exc.__traceback__):
        if frame.filename == str(path):
            where = f" (design.py:{frame.lineno}: {frame.line})"
    return f"{type(exc).__name__}: {exc}{where}"[:400]


def run(path: Path, svg_out: Path | None, timeout: float) -> dict[str, object]:
    args = [sys.executable, __file__, "--one", str(path)]
    if svg_out is not None:
        args += ["--svg-dir", str(svg_out)]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        done = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, env=env, check=False
        )
    except subprocess.TimeoutExpired:
        return {"slug": path.parent.name, "status": "timeout", "error": f"over {timeout:g} s"}
    lines = done.stdout.strip().splitlines()
    if done.returncode or not lines:
        tail = done.stderr.strip().splitlines()[-1:] or ["no output"]
        return {"slug": path.parent.name, "status": "draw", "error": tail[0][:400]}
    return json.loads(lines[-1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("dir", type=Path, help="a directory of <slug>/design.py")
    parser.add_argument("--svg-dir", type=Path, help="write the fireproof SVGs here")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--json", type=Path, help="write the results here")
    parser.add_argument("--one", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.one:
        try:
            result = one(args.dir, args.svg_dir)
        except Failed as f:
            result = {"slug": args.dir.parent.name, "status": f.stage, "error": f.error}
        print(json.dumps(result))
        return 0
    paths = sorted(args.dir.glob("*/design.py"))
    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda p: run(p, args.svg_dir, args.timeout), paths))
    for r in results:
        print(f"{r['slug']}: {r['status']}" + (f" {r['error']}" if "error" in r else ""))
    counts = Counter(str(r["status"]) for r in results)
    print(", ".join(f"{k} {n}" for k, n in counts.most_common()))
    if args.json:
        args.json.write_text(json.dumps(results, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
