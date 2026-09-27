"""Content hashes that tell `walldye build` when templates are stale.

Every hash is the sha256 of UTF-8 lines `<key>\\t<value>\\n`, sorted by line; for a file the
key is its posix path relative to the repo root and the value the sha256 of its bytes.
"""

import hashlib
import subprocess
import tomllib
from collections.abc import Sequence
from pathlib import Path

from walldye.tools import common

RENDER_DEPS = ("numpy", "scipy", "shapely", "scikit-image")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(lines: Sequence[str]) -> str:
    """sha256 of `lines` sorted, each terminated by a newline."""
    return sha256("".join(f"{line}\n" for line in sorted(lines)).encode())


def file_line(key: str, path: Path) -> str:
    """`<key>\\t<sha256 of the bytes at path>`; `key` is the file's repo-relative posix path."""
    return f"{key}\t{sha256(path.read_bytes())}"


def data_files(slug: str) -> list[Path]:
    """The files in wallpapers/<slug>/data/, sorted by name ([] without the folder)."""
    d = common.piece_dir(slug) / "data"
    return sorted(p for p in d.iterdir() if p.is_file()) if d.is_dir() else []


def design_lines(slug: str) -> list[str]:
    """Hash lines of a piece: design.py (or source.svg and palette.yaml) and every file in
    data/."""
    d = common.piece_dir(slug)
    names = ["source.svg", "palette.yaml"] if common.is_legacy(slug) else ["design.py"]
    return [
        *(file_line(f"wallpapers/{slug}/{n}", d / n) for n in names),
        *(file_line(f"wallpapers/{slug}/data/{p.name}", p) for p in data_files(slug)),
    ]


def design_sha(slug: str, variant: str = "default") -> str:
    """The digest of design_lines(slug), plus `variant\\t<name>` for a named variant."""
    lines = design_lines(slug)
    return digest(lines if variant == "default" else [*lines, f"variant\t{variant}"])


def _git_files() -> list[str]:
    """The files under walldye/ that git tracks or would track (untracked but not ignored)."""
    run = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "walldye"],
        cwd=common.ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [p for p in run.stdout.split("\0") if p != ""]


def render_lib_lines() -> list[str]:
    """Hash lines of the render inputs: the walldye/ files git tracks or would track, minus
    walldye/tools/** and __pycache__; the RENDER_DEPS versions pinned in uv.lock; and
    .python-version."""
    files = sorted({
        p for p in _git_files()
        if not p.startswith("walldye/tools/") and "__pycache__" not in p.split("/") and (common.ROOT / p).is_file()
    })  # fmt: skip
    lock: object = tomllib.loads((common.ROOT / "uv.lock").read_text()).get("package")
    packages = common.as_list(lock)
    if packages is None:
        raise ValueError("uv.lock has no [[package]] tables")
    pinned: dict[str, str] = {}
    for package in packages:
        p = common.as_dict(package)
        if p is not None and p.get("name") in RENDER_DEPS:
            pinned[str(p["name"])] = str(p.get("version"))
    if len(missing := set(RENDER_DEPS) - pinned.keys()) > 0:
        raise ValueError(f"uv.lock pins none of: {', '.join(sorted(missing))}")
    deps = [f"dep\t{name}=={version}" for name, version in sorted(pinned.items())]
    python = (common.ROOT / ".python-version").read_text().strip()
    return [*(file_line(p, common.ROOT / p) for p in files), *deps, f"python\t{python}"]


def render_lib_sha() -> str:
    return digest(render_lib_lines())
