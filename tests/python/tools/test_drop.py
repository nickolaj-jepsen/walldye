import pytest
from tools_support import piece

from walldye.tools import cli, review


def test_drop(wallpapers, review_files, monkeypatch, capsys):
    piece(wallpapers, "a")
    piece(wallpapers, "b")
    review.state.save_state({"a": {"status": "rejected"}, "b": {"note": "hm"}})
    featured = review_files / "featured.yaml"
    featured.write_text("# first\n- b\n- 'a'  # lead\n- ab\n")
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert cli.main(["drop", "a"]) == 1
    assert (wallpapers / "a").is_dir() and not (wallpapers / "index.json").exists()
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    assert cli.main(["drop", "a"]) == 0
    assert not (wallpapers / "a").exists()
    assert (
        review.state.load_state() == {"b": {"note": "hm"}} and (wallpapers / "index.json").exists()
    )
    assert featured.read_text() == "# first\n- b\n- ab\n"
    assert "took a off featured.yaml" in capsys.readouterr().out

    def no_prompt(prompt):
        raise AssertionError("--yes must not prompt")

    monkeypatch.setattr("builtins.input", no_prompt)
    assert cli.main(["drop", "b", "--yes"]) == 0
    assert not (wallpapers / "b").exists() and review.state.load_state() == {}
    with pytest.raises(SystemExit) as e:
        cli.main(["drop", "b"])
    assert e.value.code == 2
