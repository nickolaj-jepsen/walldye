import pytest

from walldye.tools import common, review


@pytest.fixture
def wallpapers(tmp_path, monkeypatch):
    """An empty wallpapers/ directory that the tools resolve slugs against."""
    root = tmp_path / "wallpapers"
    root.mkdir()
    monkeypatch.setattr(common, "WALLPAPERS", root)
    return root


@pytest.fixture
def review_files(tmp_path, monkeypatch):
    """Review state and taxonomy.yaml in a scratch repo."""
    files = tmp_path / "repo"
    files.mkdir()
    monkeypatch.setattr(review, "STATE_FILE", files / ".walldye-review.json")
    monkeypatch.setattr(common, "TAXONOMY", files / "taxonomy.yaml")
    return files
