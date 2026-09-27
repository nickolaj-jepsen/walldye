from pathlib import Path

import pytest

import walldye
from walldye.tools import common

# Untracked M2 inputs and the nixos checkout; tests that need them skip when absent.
IMPORT = common.ROOT / "import"
NIXOS_BACKGROUNDS = Path.home() / "nixos/modules/desktop/dms/backgrounds"


@pytest.fixture(autouse=True)
def _default_theme_and_canvas():
    yield
    walldye.set_theme()
    walldye.set_canvas()


@pytest.fixture
def wallpapers(tmp_path, monkeypatch):
    """An empty wallpapers/ directory that common's slug helpers resolve against."""
    monkeypatch.setattr(common, "WALLPAPERS", tmp_path)
    return tmp_path
