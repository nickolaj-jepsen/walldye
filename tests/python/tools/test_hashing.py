import importlib.metadata

from fixtures import regen
from tools_support import legacy

from walldye.tools import common, hashing


def test_design_lines(wallpapers):
    regen.install(wallpapers, "collision")
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
    regen.install(wallpapers, "data", data={"points.json": points, "b.txt": "x\n"})
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


def test_render_lib_lines():
    lines = hashing.render_lib_lines()
    keys = [line.split("\t")[0] for line in lines]
    assert "walldye/__init__.py" in keys and "walldye/_check_themes.py" in keys
    assert not any(k.startswith("walldye/tools/") or "__pycache__" in k for k in keys)
    assert [line for line in lines if line.startswith("dep\t")] == [
        f"dep\t{name}=={importlib.metadata.version(name)}"
        for name in ("numpy", "scikit-image", "scipy", "shapely")
    ]
    assert f"python\t{(common.ROOT / '.python-version').read_text().strip()}" in lines
