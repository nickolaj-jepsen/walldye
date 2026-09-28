"""scripts/port/sheets.py: scores, ordering and the review page, on a tiny fake layout."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def sheets() -> ModuleType:
    spec = importlib.util.spec_from_file_location("port_sheets", ROOT / "scripts/port/sheets.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def svg(*shapes: str) -> str:
    body = "".join(shapes)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" '
        f'height="1080"><rect x="0" y="0" width="1920" height="1080" fill="#1C1B1A"/>{body}</svg>'
    )


DOT = '<path d="M900 540h120v120h-120z" fill="#CF6A4C"/>'
MOVED = '<path d="M300 540h120v120h-120z" fill="#CF6A4C"/>'


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def layout(tmp_path: Path) -> Path:
    nixos, walls = tmp_path / "nixos", tmp_path / "wallpapers"
    for slug in ("same", "moved", "unbuilt", "patent"):
        write(nixos / f"{slug}.svg", svg(DOT))
    write(walls / "same" / "build" / "16x9.svg", svg(DOT))
    write(walls / "moved" / "build" / "16x9.svg", svg(MOVED))
    write(walls / "moved" / "build" / "late" / "16x9.svg", svg(DOT, MOVED))
    write(walls / "moved" / "build" / "early" / "16x9.svg", svg(DOT))
    write(walls / "moved" / "build" / "old" / "16x9.svg", svg(DOT))  # not in meta.yaml
    write(walls / "patent-branch" / "build" / "16x9.svg", svg(DOT))
    write(walls / "stray" / "build" / "16x9.svg", svg(DOT))
    meta = {
        "title": "Moved square",
        "description": "A square left of centre.",
        "variants": {
            "default": {"label": "Left"},
            "late": {"label": "Both", "draft": True},
            "early": {"label": "Centre", "draft": True},
        },
    }
    for slug in ("same", "moved", "unbuilt", "patent-branch", "stray"):
        write(walls / slug / "meta.yaml", json.dumps(meta if slug == "moved" else {"title": slug}))
    write(walls / "moved" / "design.py", '"""A square, moved."""\n')
    return tmp_path


def run(sheets: ModuleType, layout: Path) -> dict[str, dict[str, Any]]:
    args = ["--nixos", str(layout / "nixos"), "--wallpapers", str(layout / "wallpapers")]
    assert (
        sheets.main([*args, "--out", str(layout / "review"), "--width", "320", "--jobs", "1"]) == 0
    )
    summary = json.loads((layout / "review" / "summary.json").read_text())
    return {p["slug"]: p for p in summary["pieces"]}


def test_compare_scores_identical_and_changed_rasters(sheets: ModuleType) -> None:
    a = Image.new("RGB", (40, 20), (28, 27, 26))
    b = a.copy()
    assert sheets.compare(a, b)[:3] == (0.0, 0.0, 1.0)
    b.paste((207, 106, 76), (0, 0, 10, 20))  # a quarter of the pixels
    score, mad, ssim, diff = sheets.compare(a, b)
    assert score == 25.0
    assert mad > 0 and ssim < 1
    assert diff.size == a.size


def test_pieces_are_ordered_by_score_with_statuses(sheets: ModuleType, layout: Path) -> None:
    pieces = run(sheets, layout)
    order = list(pieces)
    assert order[:3] == ["moved", "patent-branch", "same"]  # same score: slug order
    assert pieces["moved"]["score"] > 0
    assert pieces["same"]["score"] == 0 and pieces["same"]["ssim"] == 1.0
    assert pieces["patent-branch"]["status"] == "compared"  # compared with patent.svg
    assert pieces["unbuilt"]["status"] == "not-built"
    assert pieces["stray"]["status"] == "no-original"
    assert [v["name"] for v in pieces["moved"]["variants"]] == ["late", "early"]  # meta order
    assert pieces["moved"]["copy"]["docstring"] == "A square, moved."


def test_the_review_page_has_every_card_and_its_images(sheets: ModuleType, layout: Path) -> None:
    pieces = run(sheets, layout)
    page = (layout / "review" / "index.html").read_text()
    cards = [page.index(f'<article id="{slug}"') for slug in pieces]
    assert cards == sorted(cards)
    assert "version late: Both (draft)" in page
    assert "A square left of centre." in page
    assert 'e.key === "j"' in page
    for rel in (pieces["moved"]["before"], pieces["moved"]["after"], pieces["moved"]["diff"]):
        assert (layout / "review" / str(rel)).exists()


def test_recolour_follows_the_slot_coefficients(sheets: ModuleType) -> None:
    template = svg(DOT)
    entry = {  # slot 0 is the background, slot 1 the accent
        "coefs": [[1, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0]],
        "occ": [0, 1],
    }
    out = sheets.recolour(template, entry, ("#FFFCF0", "#100F0F", "#BC5215"))
    assert 'fill="#FFFCF0"' in out and 'fill="#BC5215"' in out
