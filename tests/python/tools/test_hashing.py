import importlib.metadata
import json

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


def test_hash_vector_fixture():
    fixture = json.loads((regen.SHARED / "hash-vector.json").read_text())
    assert [v["name"] for v in fixture["vectors"]] == ["design", "variant-with-data"]
    for v in fixture["vectors"]:
        lines = [
            *(f"{p}\t{hashing.sha256(t.encode())}" for p, t in v["files"].items()),
            *v["lines"],
        ]
        assert hashing.digest(lines) == v["sha256"]
        assert hashing.sha256(v["text"].encode()) == v["sha256"]
    variant = fixture["vectors"][1]
    assert "wallpapers/example/data/points.json" in variant["files"]
    assert variant["lines"] == ["variant\tlate"]


def test_hash_vector_is_design_sha(wallpapers):
    """The variant-with-data vector is what design_sha computes for that folder."""
    files, _ = regen.HASH_VECTORS["variant-with-data"]
    for path, text in files.items():
        target = wallpapers.parent / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    (wallpapers / "example/meta.yaml").write_text("title: Example\n")
    vector = json.loads(regen.hash_vector())["vectors"][1]
    assert hashing.design_sha("example", "late") == vector["sha256"]


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
