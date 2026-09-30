import io
import re
import tokenize

from walldye.tools import paths

# Vec's three tuple overrides and s.data's Any are the only sanctioned ignores.
SANCTIONED = [
    ("walldye/_canvas.py", "explicit-any"),
    ("walldye/_vec.py", "bad-override"),
    ("walldye/_vec.py", "bad-override"),
    ("walldye/_vec.py", "bad-override"),
]
SUPPRESSION = re.compile(r"#\s*(?:type|pyrefly)\s*:\s*ignore(?:\[([\w-]+)\])?")


def test_library_suppresses_only_the_sanctioned_errors():
    """A bare `# type: ignore` passes Pyrefly silently, so the comments themselves are counted."""
    found = []
    for path in sorted((paths.ROOT / "walldye").rglob("*.py")):
        tokens = tokenize.generate_tokens(io.StringIO(path.read_text()).readline)
        for t in tokens:
            if t.type == tokenize.COMMENT and (m := SUPPRESSION.search(t.string)) is not None:
                found.append((path.relative_to(paths.ROOT).as_posix(), m.group(1)))
    assert found == SANCTIONED
