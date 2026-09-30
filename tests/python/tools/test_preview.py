import pytest
from PIL import Image
from tools_support import FLAT, TINY, legacy, piece

from walldye.tools import cli, common, preview


def test_preview_writes_png_and_reports(wallpapers, tmp_path, monkeypatch, capsys):
    piece(wallpapers, "tiny")
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path / "prev"))
    args = ["preview", "tiny", "--theme", "flexoki-light", "--aspect", "9:19.5", "--width", "400"]
    assert cli.main(args) == 0
    lines = capsys.readouterr().out.splitlines()
    png = tmp_path / "prev/tiny-flexoki-light-9x19.5.png"
    assert lines == [
        "lint: ok",
        "regime: light (flexoki-light)",
        "light geometry: differs from dark (build writes a light template for each native aspect)",
        str(png),
    ]
    assert Image.open(png).size == (185, 401)  # --width is the long side, up to rounding
    assert cli.main(["preview", "tiny", "--crop", "0,0,300,600", "--width", "300"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert Image.open(lines[-1]).size == (150, 300)
    assert lines[-1].endswith("tiny-fireproof-16x9-crop-0-0-300-600.png")
    assert "regime: dark (fireproof)" in lines


def test_preview_prints_lint_lines(wallpapers, tmp_path, monkeypatch, capsys):
    design = TINY.replace("from walldye import", "import random\n\nfrom walldye import").replace(
        "    if s.light:",
        "    # a crimson rim\n    s.pixel_path(P().rect(0.5, 3, 4, 4), UI, cell=4, origins=[(0.5, 3)])\n    if s.light:",
    )
    piece(wallpapers, "loud", design, description="A crimson disc.")
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["preview", "loud", "--theme", "nord", "--width", "64"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("error: line 3: imports random;")
    assert lines[1:4] == [
        "warning: color words in docstrings or comments: crimson (name tokens or roles, never hues)",
        "warning: color words in meta.yaml copy: crimson (describe the shape or what it picks out, without naming colors)",
        "warning: pixel grid origin (0.5, 3) is not a whole unit; snap it to the 4-unit cell grid",
    ]
    assert lines[4] == "lint: 1 error(s), 3 warning(s)"


def test_preview_undeclared_aspect(wallpapers, tmp_path, monkeypatch, capsys):
    piece(wallpapers, "flat", FLAT)
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["preview", "flat", "--aspect", "21:9", "--width", "200"]) == 0
    out = capsys.readouterr().out
    assert "warning: flat declares aspects=('16:9',); rendered 21:9 anyway" in out
    assert "light geometry: same as dark" in out


def test_preview_legacy_piece(wallpapers, tmp_path, monkeypatch, capsys):
    legacy(wallpapers)
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["preview", "old", "--theme", "nord", "--width", "64"]) == 0
    assert capsys.readouterr().out.splitlines()[:3] == [
        "lint: ok",
        "regime: dark (nord)",
        "light geometry: same as dark (one template serves both regimes)",
    ]


def test_lint_checks_the_viewbox(wallpapers):
    piece(wallpapers, "tiny")
    svg = common.render("tiny", "fireproof")
    assert preview.lint("tiny", svg, "16:9", []) == ([], [])
    assert preview.lint("tiny", svg, "21:9", [])[0] == ['viewBox is not "0 0 2520 1080"']


def test_crop_parsing():
    assert preview.parse_crop("1,2.5,3,4") == (1, 2.5, 3, 4)
    for bad in ("1,2,3", "1,2,0,4", "a,b,c,d", "1,2,3,-4"):
        with pytest.raises(ValueError):
            preview.parse_crop(bad)
