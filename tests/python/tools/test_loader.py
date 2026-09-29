import sys

import pytest
from fixtures import regen
from tools_support import legacy

from walldye._design import Design, RenderSpec
from walldye._theme import mix, parse_theme
from walldye.tools import common


def test_load_imports_once_per_file_content(wallpapers):
    regen.install(wallpapers, "versions", "two-words")
    first = common.load("two-words")
    assert isinstance(first, Design)
    assert common.load("two-words") is first
    mod = sys.modules["_walldye_two_words"]
    assert mod.draw is first
    assert str(wallpapers) not in sys.path
    assert not (wallpapers / "two-words/__pycache__").exists()
    design = wallpapers / "two-words/design.py"
    design.write_text(design.read_text().replace("hour=8", "hour=9"))
    again = common.load("two-words")
    assert again is not first and again.params("late").hour == 9


def test_fresh_imports_anew_without_caching(wallpapers):
    regen.install(wallpapers, "leaky")
    loaded = common.load("leaky")
    a, b = common.fresh("leaky"), common.fresh("leaky")
    assert a is not b and a is not loaded
    assert not any(k.startswith("_walldye_leaky_fresh") for k in sys.modules)


def test_load_errors(wallpapers):
    regen.install(wallpapers, "collision", "v1-style")
    (wallpapers / "v1-style/design.py").write_text("def draw(s):\n    pass\n")
    with pytest.raises(ValueError, match=r"design.py must define @design\(\.\.\.\) def draw"):
        common.load("v1-style")
    regen.install(wallpapers, "collision", "broken")
    (wallpapers / "broken/design.py").write_text("def draw(s)\n    pass\n")
    with pytest.raises(SyntaxError):
        common.load("broken")
    (wallpapers / "empty").mkdir()
    with pytest.raises(FileNotFoundError):
        common.load("empty")
    with pytest.raises(ValueError):
        common.piece_dir("../etc")


def test_prints_go_to_stderr(wallpapers, capsys):
    regen.install(wallpapers, "collision", "chatty")
    design = wallpapers / "chatty/design.py"
    text = design.read_text().replace(
        "def draw(s: Canvas) -> None:\n", "def draw(s: Canvas) -> None:\n    print('drawing')\n"
    )
    design.write_text(text + "\nprint('imported')\n")
    common.render("chatty", "nord")
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "imported\ndrawing\n"


def test_render_serializes_the_regime_document(wallpapers):
    regen.install(wallpapers, "light-branch")
    dark = common.render("light-branch", "nord")
    assert f'fill="{parse_theme("nord")["accent"]}"' in dark and "A100 100" in dark
    light = common.render("light-branch", "flexoki-light", "10:16")
    assert 'viewBox="0 0 1080 1728"' in light and "A100 100" not in light
    by_seeds = common.render("light-branch", {"bg": "2e3440", "fg": "#ECEFF4", "accent": "88c0d0"})
    assert by_seeds == dark


def test_render_variants_and_overrides(wallpapers):
    regen.install(wallpapers, "versions")
    default = common.render("versions", "nord")
    late = common.render("versions", "nord", variant="late")
    assert late != default
    assert common.render("versions", "nord", overrides=["hour=8"]) == late
    with pytest.raises(KeyError):
        common.render("versions", "nord", variant="early")


def test_draw_caches_by_spec(wallpapers):
    regen.install(wallpapers, "collision")
    piece = common.load("collision")
    spec = RenderSpec("default", piece.params(), "16:9", "dark")
    doc = common.draw(piece, spec)
    assert common.draw(piece, spec) is doc
    assert common.draw(piece, spec, cache=False) is not doc


def test_variant_of(wallpapers):
    regen.install(wallpapers, "versions")
    piece = common.load("versions")
    assert common.variant_of(piece, "versions", "late") == "late"
    with pytest.raises(
        common.UsageError, match=r"versions has no variant 'x' \(have: default, late, bare\)"
    ):
        common.variant_of(piece, "versions", "x")


def test_legacy_piece(wallpapers):
    legacy(wallpapers)
    assert common.is_legacy("old")
    piece = common.load("old")
    assert isinstance(piece, common.LegacyPiece)
    assert piece.variant_names() == ("default",) and piece.aspects == ("16:9",)
    fire = common.render("old", "fireproof")
    assert 'fill="#1C1B1A"' in fire and 'fill="#CF6A4C"' in fire
    t = parse_theme("nord")
    nord = common.render("old", "nord")
    assert f'fill="{t["bg"]}"' in nord and f'fill="{t["accent"]}"' in nord
    assert f'stroke="{mix(t["bg_deep"], t["accent_8"], 0.68)}"' in nord
    assert common.render("old", "flexoki-light").count("#") == 3
    with pytest.raises(ValueError, match="only exists at 16:9"):
        common.render("old", "nord", "21:9")
    with pytest.raises(KeyError):
        piece.params("late")


def test_legacy_palette_maps_slots_not_hex_strings(wallpapers):
    source = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1920 1080">'
        '<defs><circle id="c0ffee" r="5" fill="#fff"/></defs><use xlink:href="#c0ffee"/>'
        '<use href="#c0ffee" stroke="white"/><rect fill="url(#c0ffee)" stroke="#C0FFEE"/></svg>'
    )
    legacy(wallpapers, source=source, palette='"#FFF": fg\n"#C0FFEE": accent\n')
    t = parse_theme("nord")
    assert common.render("old", "nord") == source.replace(
        'fill="#fff"', f'fill="{t["fg"]}"'
    ).replace('stroke="white"', f'stroke="{t["fg"]}"').replace(
        'stroke="#C0FFEE"', f'stroke="{t["accent"]}"'
    )


@pytest.mark.parametrize(
    ("palette", "error"),
    [
        ('"#1C1B1A": bg\n"#CF6A4C": accent\n', "does not map #201A18"),
        ('"#1C1B1A": bg\n"#CF6A4C": teal\n"#201A18": bg', "#CF6A4C: entries are a token"),
        ('"#1C1B1A": bg\n"#CF6A4C": [bg, fg]\n"#201A18": bg', "#CF6A4C: entries are a token"),
        ("- bg\n", "must map colors to tokens"),
    ],
)
def test_legacy_palette_errors(wallpapers, palette, error):
    legacy(wallpapers, palette=palette)
    with pytest.raises(ValueError, match=error):
        common.load("old")
