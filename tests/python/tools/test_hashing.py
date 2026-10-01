import importlib.metadata
import platform
from pathlib import Path

from fixtures import pieces
from tools_support import legacy

import walldye
from walldye.tools import hashing


def test_design_lines(wallpapers):
    pieces.install(wallpapers, "collision")
    design = (wallpapers / "collision/design.py").read_bytes()
    assert hashing.design_lines("collision") == [
        f"wallpapers/collision/design.py\t{hashing.sha256(design)}",
    ]
    legacy(wallpapers)
    assert [line.split("\t")[0] for line in hashing.design_lines("old")] == [
        "wallpapers/old/source.svg",
        "wallpapers/old/palette.yaml",
    ]


def test_data_files_and_variants_join_the_design_sha(wallpapers):
    points = "[[960, 540], [1200, 300]]\n"
    pieces.install(wallpapers, "data", data={"points.json": points, "b.txt": "x\n"})
    lines = hashing.design_lines("data")
    assert lines[1:] == [
        f"wallpapers/data/data/b.txt\t{hashing.sha256(b'x\n')}",
        f"wallpapers/data/data/points.json\t{hashing.sha256(points.encode())}",
    ]
    default = hashing.design_sha("data")
    assert default == hashing.digest(lines)
    assert hashing.design_sha("data", "late") == hashing.digest([*lines, "variant\tlate"])
    assert hashing.design_sha("data", "late") != default
    (wallpapers / "data/data/points.json").write_text("[]\n")
    assert hashing.design_sha("data") != default


def test_toolchain_lines():
    lines = hashing.toolchain_lines()
    keys = [line.split("\t")[0] for line in lines]
    for key in ("walldye/__init__.py", "walldye/_theme.py", "walldye/tools/coefs.py"):
        assert key in keys
    assert "walldye/tools/cli.py" not in keys
    assert not any(k.startswith(("walldye/tools/lint/", "walldye/tools/review/")) for k in keys)
    assert not any("__pycache__" in k or k.endswith(".pyc") for k in keys)
    deps = [line for line in lines if line.startswith("dep\t")]
    assert deps == [f"dep\t{n}=={v}" for n, v in sorted(hashing.runtime_dists().items())]
    names = hashing.runtime_dists()
    assert {"numpy", "resvg-py", "scikit-image"} <= names.keys()
    assert names["numpy"] == importlib.metadata.version("numpy")
    assert "pytest" not in names and "walldye" not in names
    assert f"python\tcpython {platform.python_version()} {platform.machine()}" in lines


def test_neutral_names_existing_modules():
    package = Path(walldye.__file__).parent
    for name in hashing.NEUTRAL:
        path = package.parent / name
        assert path.is_dir() if name.endswith("/") else path.is_file(), name


def test_requirement_names():
    assert hashing._requirement_name("numpy>=2.5.3") == "numpy"
    assert hashing._requirement_name("resvg-py (>=0.5)") == "resvg-py"
    assert hashing._requirement_name('tomli; python_version < "3.11"') == "tomli"
    assert hashing._requirement_name('pytest>=8; extra == "test"') is None


def test_code_line_ignores_comments_docstrings_and_layout(tmp_path):
    a, b, c = tmp_path / "a.py", tmp_path / "b.py", tmp_path / "c.py"
    a.write_text('"""Module."""\n\n\ndef f(x):\n    """Doubles."""\n    return x * 2\n')
    b.write_text("# a note\ndef f(x):  # why\n    return (x *\n            2)\n")
    c.write_text("def f(x):\n    return x * 3\n")
    code = [hashing.code_line("k", p).split("\t")[1] for p in (a, b, c)]
    assert code[0] == code[1] != code[2]
    svg = tmp_path / "x.svg"
    svg.write_text("<svg/>")
    assert hashing.code_line("k", svg) == hashing.file_line("k", svg)
