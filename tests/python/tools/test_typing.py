import io
import re
import subprocess
import tokenize

import pytest

from walldye.tools import common

EXAMPLES = sorted((common.ROOT / ".claude/skills/walldye/examples").glob("*.py"))
# docs/api.md 15.3: Vec's three tuple overrides and s.data's Any are the only ignores.
SANCTIONED = [
    ("walldye/_canvas.py", "explicit-any"),
    ("walldye/_vec.py", "bad-override"),
    ("walldye/_vec.py", "bad-override"),
    ("walldye/_vec.py", "bad-override"),
]
SUPPRESSION = re.compile(r"#\s*(?:type|pyrefly)\s*:\s*ignore(?:\[([\w-]+)\])?")


def pyrefly(*args: str) -> subprocess.CompletedProcess[str]:
    exe = common.tool("pyrefly")
    assert exe is not None, "pyrefly is a dev dependency: uv sync"
    return subprocess.run(
        [str(exe), "check", "--output-format", "min-text", *args],
        cwd=common.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_library_is_clean_at_the_strictest_preset():
    """Project mode: walldye/, tools included, at preset "all" (pyproject.toml)."""
    run = pyrefly()
    assert run.returncode == 0, run.stdout + run.stderr


def test_library_suppresses_only_the_sanctioned_errors():
    """A bare `# type: ignore` passes Pyrefly silently, so the comments themselves are counted."""
    found = []
    for path in sorted((common.ROOT / "walldye").rglob("*.py")):
        tokens = tokenize.generate_tokens(io.StringIO(path.read_text()).readline)
        for t in tokens:
            if t.type == tokenize.COMMENT and (m := SUPPRESSION.search(t.string)) is not None:
                found.append((path.relative_to(common.ROOT).as_posix(), m.group(1)))
    assert found == SANCTIONED


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_skill_examples_are_clean_at_the_design_level(path):
    run = pyrefly("-c", str(common.DESIGN_PYREFLY), str(path))
    assert run.returncode == 0, run.stdout + run.stderr
