import pytest

from walldye.tools import paths
from walldye.tools.paths import TEMPLATE_NAME, parse_template_name, template_name

NORD = {"bg": "#2E3440", "fg": "#ECEFF4", "accent": "#88C0D0"}
FIREPROOF_SEEDS = {"bg": "#1C1B1A", "fg": "#DAD8CE", "accent": "#CF6A4C"}

# --- template names ------------------------------------------------------------


@pytest.mark.parametrize(
    ("aspect", "light", "name"),
    [("16:9", False, "16x9.svg"), ("16:10", False, "16x10.svg"), ("21:9", True, "21x9.light.svg"),
     ("32:9", False, "32x9.svg"), ("9:19.5", True, "9x19.5.light.svg"), ("10:16", False, "10x16.svg")],
)  # fmt: skip
def test_template_names(aspect, light, name):
    assert template_name(aspect, light) == name
    assert parse_template_name(name) == (aspect, light)
    assert TEMPLATE_NAME.fullmatch(name)


@pytest.mark.parametrize(
    "name",
    [
        "16x9",
        "16x9.dark.svg",
        "slots.json",
        "16:9.svg",
        "x9.svg",
        "9x19.5.light.svg.bak",
        "16x9.light.light.svg",
        "16x9.svg\n",
    ],
)
def test_template_name_rejects(name):
    assert not TEMPLATE_NAME.fullmatch(name)
    with pytest.raises(ValueError):
        parse_template_name(name)


def test_cache_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("WALLDYE_CACHE", "off")
    assert paths.cache_dir() is None
    monkeypatch.setenv("WALLDYE_CACHE", str(tmp_path))
    assert paths.cache_dir() == tmp_path
    monkeypatch.delenv("WALLDYE_CACHE")
    assert paths.cache_dir() == paths.ROOT / ".cache" / "cached"
