import pytest
from tools_support import FLAT, piece, versions

from walldye._aspect import SITE_ASPECTS
from walldye.tools import build, check, cli


def test_check_and_build_wiring(wallpapers, monkeypatch):
    piece(wallpapers, "tiny")
    checks, builds = [], []
    monkeypatch.setattr(check, "run", lambda slugs, **kw: checks.append((slugs, kw)) or 3)
    monkeypatch.setattr(build, "run", lambda slugs, **kw: builds.append((slugs, kw)) or 0)
    assert cli.main(["check", "tiny", "--similar", "--variant", "late", "--jobs", "2"]) == 3
    assert cli.main(["check", "--all", "--paranoid"]) == 3
    assert checks == [
        (
            ["tiny"],
            {"all": False, "variant": "late", "paranoid": False, "similar": True, "jobs": 2},
        ),
        ([], {"all": True, "variant": None, "paranoid": True, "similar": False, "jobs": None}),
    ]
    assert cli.main(["build", "tiny", "--force", "--variant", "late"]) == 0
    assert cli.main(["build", "--all", "--published", "--jobs", "4"]) == 0
    assert builds == [
        (
            ["tiny"],
            {"all": False, "force": True, "variant": "late", "published": False, "jobs": None},
        ),
        ([], {"all": True, "force": False, "variant": None, "published": True, "jobs": 4}),
    ]
    for bad in (
        ["check"],
        ["check", "--all", "tiny"],
        ["build"],
        ["sheet"],
        ["check", "missing"],
        ["check", "Bad"],
    ):
        with pytest.raises(SystemExit) as e:
            cli.main(bad)
        assert e.value.code == 2


def test_hashes_hands_off_to_check(monkeypatch):
    seen = []
    monkeypatch.setattr(check, "hashes_main", lambda args: seen.append(args) or 0)
    assert cli.main(["_hashes", "/w", "tiny@default@16:9@dark", "tiny@late@9:19.5@light"]) == 0
    assert seen == [["/w", "tiny@default@16:9@dark", "tiny@late@9:19.5@light"]]
    assert "_hashes" not in cli._parser().format_help()


def test_list(wallpapers, capsys):
    piece(wallpapers, "tiny", title="Tiny\tring", description="A ring,\n  drawn once.")
    piece(wallpapers, "flat", FLAT, draft=False)
    versions(wallpapers)
    assert cli.main(["list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "flat\tFlat\tA test piece.\t-\t16:9\t",
        f"tiny\tTiny ring\tA ring, drawn once.\tdraft\t{','.join(SITE_ASPECTS)}\t",
        "versions\tFixture\tA synthetic design for the build tests.\tdraft\t16:9,10:16\tlate,bare",
    ]


def test_themes_lists_presets(capsys):
    assert cli.main(["themes"]) == 0
    assert "fireproof          #1C1B1A #DAD8CE #CF6A4C  dark (default)" in capsys.readouterr().out


def test_themes_prints_tokens(capsys):
    assert cli.main(["themes", "--theme", "nord"]) == 0
    assert "  ACCENT_3     #5B7A88" in capsys.readouterr().out
