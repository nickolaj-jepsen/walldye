import shutil

import pytest
from PIL import Image
from tools_support import FLAT, built, piece, versions

from walldye._theme import parse_seeds
from walldye.tools import cli, common, sheet


def test_sheet_recolors_through_slots(wallpapers, tmp_path, capsys):
    piece(wallpapers, "tiny")
    piece(wallpapers, "flat", FLAT)
    versions(wallpapers)
    piece(wallpapers, "unbuilt")
    built(capsys, "tiny", "flat", "versions")
    out = tmp_path / "s.png"
    args = [
        "sheet",
        "tiny",
        "flat",
        "unbuilt",
        "--theme",
        "flexoki-light",
        "--cols",
        "1",
        "--thumb",
        "160",
        "-o",
        str(out),
    ]
    assert cli.main(args) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == str(out)
    assert captured.err == "skip unbuilt: not built (run walldye build unbuilt)\n"
    assert Image.open(out).size == (8 + 160 + 8, 2 * (90 + 8 + 22) + 8)
    args = [
        "sheet",
        "tiny",
        "versions",
        "--variant",
        "late",
        "--aspect",
        "10:16",
        "--thumb",
        "90",
        "-o",
        str(out),
    ]
    assert cli.main(args) == 0
    assert capsys.readouterr().err == "skip tiny: no variant late\n"
    assert Image.open(out).size == (8 + 90 + 8, 144 + 8 + 22 + 8)
    shutil.rmtree(common.build_dir("versions", "late"))
    with pytest.raises(SystemExit, match="nothing to put on a sheet"):
        cli.main([a for a in args if a != "tiny"])
    assert (
        capsys.readouterr().err
        == "skip versions: not built (run walldye build versions --variant late)\n"
    )


def test_themed_matches_a_render(wallpapers, capsys):
    piece(wallpapers, "tiny")
    built(capsys, "tiny")
    template = (common.build_dir("tiny") / "16x9.svg").read_text()
    assert sheet.themed("tiny", parse_seeds("1C1B1A-DAD8CE-CF6A4C")) == template
    light = parse_seeds("flexoki-light")
    assert sheet.themed("tiny", light) == common.render("tiny", "flexoki-light")
    with pytest.raises(KeyError):
        sheet.themed("tiny", parse_seeds("nord"), aspect="4:3")


def test_sheet_default_path(wallpapers, tmp_path, monkeypatch, capsys):
    piece(wallpapers, "flat", FLAT)
    built(capsys, "flat")
    monkeypatch.setenv("WALLDYE_PREVIEW", str(tmp_path))
    assert cli.main(["sheet", "--all", "--thumb", "64"]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "sheet-fireproof.png")
    with pytest.raises(SystemExit, match="nothing to put on a sheet"):
        sheet.run([], parse_seeds(None), 4, 64, None)
