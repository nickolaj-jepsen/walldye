"""The project's dev tools, for the tests that type-check designs."""

import shutil
import sys
from pathlib import Path
from typing import Final

from walldye.tools.paths import ROOT

DESIGN_PYREFLY: Final = ROOT / "wallpapers" / "pyrefly.toml"  # the level designs are checked at


def tool(name: str) -> Path | None:
    """The dev tool `name` (ruff, pyrefly) of walldye's environment: next to sys.executable,
    else on PATH (under `uv run --with`, sys.executable is an overlay environment without the
    project's tools, and uv puts the project's .venv/bin on PATH). None when neither has it."""
    beside = Path(sys.executable).with_name(name)
    if beside.exists():
        return beside
    found = shutil.which(name)
    return None if found is None else Path(found)
