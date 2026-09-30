import pytest
from PIL import Image
from tools_support import FLAT, TINY, piece, versions

from walldye.tools import cli, common


def test_render_names_file_after_slug_variant_token_and_aspect(
    wallpapers, tmp_path, monkeypatch, capsys
):
    piece(wallpapers, "tiny")
    versions(wallpapers)
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.chdir(out)
    assert cli.main(["render", "tiny", "--theme", "2E3440-ECEFF4-88C0D0", "--aspect", "21:9"]) == 0
    assert capsys.readouterr().out.strip() == "tiny-nord-21x9.svg"
    text = (out / "tiny-nord-21x9.svg").read_text()
    assert text == common.render("tiny", "nord", "21:9") and 'viewBox="0 0 2520 1080"' in text

    assert cli.main(["render", "versions", "--variant", "late", "--theme", "flexoki-light"]) == 0
    assert capsys.readouterr().out.strip() == "versions--late-flexoki-light-16x9.svg"
    assert (out / "versions--late-flexoki-light-16x9.svg").read_text() == common.render(
        "versions", "flexoki-light", variant="late"
    )

    args = ["render", "tiny", "--theme", "1c1b1b-dad8ce-cf6a4c", "--crop", "100,50,400,300"]
    assert cli.main(args) == 0
    cropped = (out / "tiny-1c1b1b-dad8ce-cf6a4c-16x9-crop.svg").read_text()
    assert cropped.startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="100 50 400 300" width="400" height="300">'
    )
    capsys.readouterr()
    assert cli.main(["render", "tiny", "-o", "-"]) == 0
    assert capsys.readouterr().out == common.render("tiny", "fireproof")
    assert cli.main(["render", "tiny", "-o", "new/dir/tiny.svg"]) == 0
    assert (out / "new/dir/tiny.svg").exists()


def test_render_to_stdout_keeps_design_prints_out(wallpapers, capsys):
    piece(wallpapers, "chatty", TINY.replace("-> None:\n", "-> None:\n    print('debug')\n"))
    assert cli.main(["render", "chatty", "-o", "-"]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("<svg") and captured.err == "debug\n"


def test_render_theme_from_env(wallpapers, tmp_path, monkeypatch):
    piece(wallpapers, "tiny")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WALLDYE_THEME", "flexoki-light")
    assert cli.main(["render", "tiny"]) == 0
    assert (tmp_path / "tiny-flexoki-light-16x9.svg").exists()
    monkeypatch.setenv("WALLDYE_THEME", "nord,accent=#D08770")
    with pytest.raises(SystemExit) as e:
        cli.main(["render", "tiny"])
    assert e.value.code == 2


def test_render_refuses_build_dirs_and_undeclared_aspects(wallpapers, tmp_path, capsys):
    piece(wallpapers, "tiny")
    piece(wallpapers, "flat", FLAT)
    (wallpapers / "tiny/build").mkdir()
    with pytest.raises(SystemExit, match="only walldye build"):
        cli.main(["render", "tiny", "-o", str(wallpapers / "tiny/build/16x9.svg")])
    assert not (wallpapers / "tiny/build/16x9.svg").exists()
    with pytest.raises(SystemExit) as e:
        cli.main(["render", "flat", "--aspect", "21:9", "-o", str(tmp_path / "x.svg")])
    assert e.value.code == 2
    assert "declares aspects=('16:9',), not 21:9" in capsys.readouterr().err
    for bad in (
        ["render", "nope"],
        ["render", "tiny", "--aspect", "wide"],
        ["render", "tiny", "--aspect", "inf:1"],
        ["render", "tiny", "--aspect", "16:-9"],
        ["render", "tiny", "--crop", "1,2,3"],
        ["preview", "tiny", "--width", "0"],
        ["sheet", "--all", "--cols", "0"],
        ["sheet", "--all", "--thumb", "-5"],
        ["check", "--all", "--jobs", "0"],
    ):
        with pytest.raises(SystemExit) as e:
            cli.main(bad)
        assert e.value.code == 2


def test_render_fit_cuts_undeclared_aspects_from_16_9(wallpapers, capsys):
    piece(wallpapers, "tiny")
    piece(wallpapers, "flat", FLAT)
    # The square sits top left, so both crops clamp to that corner.
    assert cli.main(["render", "flat", "--aspect", "21:9", "--fit", "-o", "-"]) == 0
    assert capsys.readouterr().out.startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 822.857"'
        ' width="1920" height="822.857">'
    )
    assert cli.main(["render", "flat", "--aspect", "9:19.5", "--fit", "-o", "-"]) == 0
    assert 'viewBox="0 0 498.462 1080"' in capsys.readouterr().out
    # A declared aspect is drawn for, not cut.
    assert cli.main(["render", "tiny", "--aspect", "21:9", "--fit", "-o", "-"]) == 0
    assert capsys.readouterr().out == common.render("tiny", "fireproof", "21:9")
    with pytest.raises(SystemExit) as e:
        cli.main(["render", "flat", "--aspect", "21:9", "--fit", "--crop", "0,0,10,10"])
    assert e.value.code == 2


def test_render_png_at_exact_pixel_sizes(wallpapers, tmp_path):
    piece(wallpapers, "tiny")
    piece(wallpapers, "flat", FLAT)
    for args, size in (
        (["tiny", "--aspect", "3440x1440", "--width", "3440"], (3440, 1440)),
        (["tiny", "--aspect", "21:9"], (2520, 1080)),
        # 1080 / 2340 of the 16:9 canvas is 498.46 wide: the rounding must not cost a pixel.
        (["flat", "--aspect", "1080x2340", "--fit", "--width", "1080"], (1080, 2340)),
        (["flat", "--aspect", "3440x1440", "--fit", "--width", "3440"], (3440, 1440)),
    ):
        out = tmp_path / "wall.png"
        assert cli.main(["render", *args, "-o", str(out)]) == 0
        with Image.open(out) as img:
            assert (img.size, img.mode) == (size, "RGB")
    with pytest.raises(SystemExit) as e:
        cli.main(["render", "tiny", "--width", "100", "-o", str(tmp_path / "x.svg")])
    assert e.value.code == 2


def test_fit_crop_centers_on_the_focus_within_the_canvas():
    assert common.fit_crop("16:9", (0.1, 0.9)) == (0.0, 0.0, 1920.0, 1080.0)
    x, y, w, h = common.fit_crop("21:9", (0.5, 1.0))
    assert (x, w) == (0.0, 1920.0) and h == pytest.approx(822.857, abs=1e-3)
    assert y == pytest.approx(1080 - h)
    x, y, w, h = common.fit_crop("9:19.5", (0.5, 0.5))
    assert (y, h) == (0.0, 1080.0) and x == pytest.approx((1920 - w) / 2)
