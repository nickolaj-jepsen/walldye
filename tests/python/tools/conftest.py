import pytest

from walldye.tools import paths, review


@pytest.fixture(autouse=True)
def no_disk_cache(monkeypatch):
    """Commands that turn on the @cached disk layer leave the checkout's .cache/ alone."""
    monkeypatch.setenv("WALLDYE_CACHE", "off")


@pytest.fixture
def wallpapers(tmp_path, monkeypatch):
    """An empty wallpapers/ directory that the tools resolve slugs against."""
    root = tmp_path / "wallpapers"
    root.mkdir()
    monkeypatch.setattr(paths, "WALLPAPERS", root)
    return root


@pytest.fixture
def review_files(tmp_path, monkeypatch):
    """Review state, taxonomy.yaml and featured.yaml in a scratch repo."""
    files = tmp_path / "repo"
    files.mkdir()
    monkeypatch.setattr(review.state, "STATE_FILE", files / ".walldye-review.json")
    monkeypatch.setattr(paths, "TAXONOMY", files / "taxonomy.yaml")
    monkeypatch.setattr(paths, "FEATURED", files / "featured.yaml")
    return files
