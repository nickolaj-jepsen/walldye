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
    """Review state, taxonomy.yaml, featured.yaml and labels.ts in a scratch repo."""
    files = tmp_path / "repo"
    files.mkdir()
    monkeypatch.setattr(review, "STATE_FILE", files / ".walldye-review.json")
    monkeypatch.setattr(review, "LABELS", files / "labels.ts")
    monkeypatch.setattr(common, "TAXONOMY", files / "taxonomy.yaml")
    monkeypatch.setattr(common, "FEATURED", files / "featured.yaml")
    return files
