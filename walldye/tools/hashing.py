"""Content hashes that tell CI and `walldye build` when templates are stale.

Every hash is the sha256 of UTF-8 lines `<key>\\t<value>\\n`, sorted by line; for a file the
key is its posix path relative to the repo root and the value the sha256 of its bytes.
src/lib/__fixtures__/hash-vector.json pins the definition for the TS side.
"""

from __future__ import annotations

import hashlib
import subprocess
import tomllib
from pathlib import Path

from walldye.tools import common

RENDER_DEPS = ("numpy", "scipy", "shapely", "scikit-image")
DEFAULT_THEMES = ["dark", "light"]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(lines: list[str]) -> str:
    """sha256 of `lines` sorted, each terminated by a newline."""
    return sha256("".join(f"{line}\n" for line in sorted(lines)).encode())


def file_line(key: str, path: Path) -> str:
    """`<key>\\t<sha256 of the bytes at path>`; `key` is the file's repo-relative posix path."""
    return f"{key}\t{sha256(path.read_bytes())}"


def themes(meta: dict) -> list[str]:
    """The regimes a piece's meta.yaml declares (`themes:`), DEFAULT_THEMES when absent."""
    return list(meta.get("themes") or DEFAULT_THEMES)


def design_lines(slug: str) -> list[str]:
    """Hash lines of a piece: design.py (or source.svg and palette.yaml) plus `themes\\t<a,b>`."""
    d = common.piece_dir(slug)
    names = ["source.svg", "palette.yaml"] if common.is_legacy(slug) else ["design.py"]
    return [*(file_line(f"wallpapers/{slug}/{n}", d / n) for n in names), "themes\t" + ",".join(sorted(themes(common.load_meta(slug))))]


def design_sha(slug: str) -> str:
    return digest(design_lines(slug))


def _git_files(*flags: str) -> list[str]:
    run = subprocess.run(["git", "ls-files", "-z", *flags, "--", "walldye"], cwd=common.ROOT, capture_output=True, text=True, check=True)
    return [p for p in run.stdout.split("\0") if p]


def render_lib_lines() -> list[str]:
    """Hash lines of the render inputs: the walldye/ files in the git index, minus
    walldye/tools/** and __pycache__; the RENDER_DEPS versions pinned in uv.lock; and
    .python-version. Untracked files never count (CI's checkout lacks them), except while
    nothing under walldye/ is tracked yet: then the files `git add walldye` would stage stand
    in, so a stamp written before the first commit matches the committed tree."""
    listed = _git_files("--cached") or _git_files("--others", "--exclude-standard")
    files = sorted({
        p for p in listed
        if not p.startswith("walldye/tools/") and "__pycache__" not in p.split("/") and (common.ROOT / p).is_file()
    })  # fmt: skip
    pinned = [p for p in tomllib.loads((common.ROOT / "uv.lock").read_text())["package"] if p["name"] in RENDER_DEPS]
    if missing := set(RENDER_DEPS) - {p["name"] for p in pinned}:
        raise ValueError(f"uv.lock pins none of: {', '.join(sorted(missing))}")
    deps = [f"dep\t{p['name']}=={p['version']}" for p in pinned]
    python = (common.ROOT / ".python-version").read_text().strip()
    return [*(file_line(p, common.ROOT / p) for p in files), *deps, f"python\t{python}"]


def render_lib_sha() -> str:
    return digest(render_lib_lines())


def render_lib_stamp() -> Path:
    return common.WALLPAPERS / ".render-lib.sha256"


def stamped_render_lib_sha() -> str | None:
    """The committed wallpapers/.render-lib.sha256, or None before the first stamp."""
    path = render_lib_stamp()
    return path.read_text().strip() if path.exists() else None
