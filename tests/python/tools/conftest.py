import pytest

from walldye.tools import common


@pytest.fixture
def wallpapers(tmp_path, monkeypatch):
    """An empty wallpapers/ directory that the tools resolve slugs against."""
    root = tmp_path / "wallpapers"
    root.mkdir()
    monkeypatch.setattr(common, "WALLPAPERS", root)
    return root

