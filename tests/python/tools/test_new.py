import datetime

import pytest
from tools_support import meta, piece

from walldye.tools import check, cli, loader, new


def test_new_scaffolds_a_draft(wallpapers, capsys):
    args = ["new", "ring-one", "--model", "claude-opus-5-5"]
    assert cli.main(args) == 0
    d = wallpapers / "ring-one"
    assert capsys.readouterr().out.strip() == str(d)
    text = (d / "meta.yaml").read_text()
    assert "license" not in text
    assert "technique: []\n" in text and "proposed_facets: {}\n" in text
    m = meta("ring-one")
    assert m["draft"] is True and m["model"] == "claude-opus-5-5" and "author" not in m
    assert m["added"] == datetime.datetime.now().astimezone().date()
    assert (d / "design.py").read_text() == new.DESIGN
    assert "A240 240" in loader.render("ring-one", "nord")
    assert loader.load("ring-one").aspects == ("16:9",)
    # The template passes the design lint as written.
    t = check.prepare("ring-one")
    check.lint_source(t)
    assert t.report.errors == ["meta.yaml needs a description", "meta.yaml needs alt text"]


def test_new_credits_an_author(wallpapers):
    assert cli.main(["new", "ring-two", "--author", "Ada"]) == 0
    m = meta("ring-two")
    assert m["author"] == "Ada" and "model" not in m and "license" not in m


@pytest.mark.parametrize("credit", [[], ["--model", "m", "--author", "Ada"]])
def test_new_takes_one_credit(wallpapers, credit):
    with pytest.raises(SystemExit) as e:
        cli.main(["new", "ring-three", *credit])
    assert e.value.code == 2


@pytest.mark.parametrize(
    "slug", ["about", "sitemap-index", "og", "Bad_Slug", "-x", "a--b", "taken"]
)
def test_new_refuses(wallpapers, slug):
    (wallpapers / "taken").mkdir()
    with pytest.raises(SystemExit) as e:
        cli.main(["new", slug, "--model", "m"])
    assert e.value.code == 2


def test_meta_yaml_round_trips_in_house_style(wallpapers):
    piece(wallpapers, "styled", notes="Line one.\n\nLine two.\n", technique=["drafting", "weave"],
          sources=[{"kind": "recreation", "title": "Schotter", "year": 1968}])  # fmt: skip
    text = (wallpapers / "styled/meta.yaml").read_text()
    assert "notes: |\n  Line one.\n\n  Line two.\n" in text
    assert "technique: [drafting, weave]\n" in text
    assert "sources:\n  - kind: recreation\n    title: Schotter\n    year: 1968\n" in text
    assert meta("styled")["notes"] == "Line one.\n\nLine two.\n"
