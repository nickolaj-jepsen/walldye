import json
import queue
import re
import threading
import urllib.error
import urllib.request

import pytest
from tools_support import VERSION_LABELS, built, versions

from walldye.tools import cli, lint, metadata, paths, recolor, review
from walldye.tools.errors import UsageError
from walldye.tools.review.state import Step
from walldye.tools.themes import parse_seeds

RING = '''"""A ring round a dot."""

from walldye import ACCENT, UI, Canvas, P, design


@design(aspects="any")
def draw(s: Canvas) -> None:
    s.stroke(P().circle(s.center, 200), UI, 2)
    s.fill(P().circle(s.center, 20), ACCENT)
'''
TAXONOMY = """# Facet vocabulary.
technique:
  drafting: technical drawing
subject:
  flora-fauna: plants and animals
lineage: {}
models:
  claude-opus-5-5: Claude Opus 5.5
"""


def piece(wallpapers, slug, **meta):
    d = wallpapers / slug
    d.mkdir()
    (d / "design.py").write_text(RING)
    fields = {
        "title": slug.capitalize(),
        "description": "A test piece.",
        "technique": [],
        "subject": [],
        "lineage": [],
        "model": "claude-opus-5-5",
        "draft": True,
    }
    metadata.write_meta(slug, {k: v for k, v in {**fields, **meta}.items() if v is not None})


def meta(slug):
    return metadata.load_meta(slug)


def vocabulary():
    paths.TAXONOMY.write_text(TAXONOMY)


# --- the queue and the words -----------------------------------------------------------------


def test_queue_orders_versions(wallpapers, capsys):
    piece(wallpapers, "a")
    versions(wallpapers, "b", draft=False)
    piece(wallpapers, "c", draft=False)
    drafts = [Step("a", "default", False), Step("b", "late", False), Step("b", "bare", False)]
    assert review.state.queue([]) == drafts
    assert review.state.queue([], everything=True) == [
        *drafts,
        Step("b", "default", True),
        Step("c", "default", True),
    ]
    assert review.state.queue(["c", "b"]) == [
        Step("c", "default", True),
        Step("b", "default", True),
        Step("b", "late", False),
        Step("b", "bare", False),
    ]
    assert review.state.drafts() == ["a", "b"]


def test_the_repo_taxonomy_has_labels_and_models():
    taxonomy = lint.piece.load_taxonomy()
    assert taxonomy is not None
    assert taxonomy.facets["technique"]["dither"] == "dithering"
    assert taxonomy.facets["lineage"]["early-computer-art"] == "early computer art"
    assert taxonomy.models["claude-opus-5-5"] == "Claude Opus 5.5"


def test_edited_applies_words_facets_and_versions():
    before = {
        "title": "Clock",
        "description": "A disc.",
        "technique": ["drafting"],
        "subject": [],
        "draft": True,
        "proposed_facets": {"technique": ["weave", "stipple"], "subject": ["moon"]},
        "variants": {
            "default": {"label": "Two"},
            "late": {"label": "Eight", "draft": True},
            "bare": {"label": "Five", "description": "No ring.", "draft": True},
        },
    }
    entry = {
        "edits": {
            "title": "  A   clock ",
            "notes": "Line one.  \n\nLine two.\n\n",
            "subject": ["sea"],
            "variants": {"late": {"label": "Late", "description": "Later on."}, "bare": {"description": " "}},
        },
        "facets": {"technique": {"weave": "accept", "stipple": "decline"}},
    }  # fmt: skip
    m = review.state.edited(before, entry)
    assert list(m) == [
        "title",
        "description",
        "notes",
        "technique",
        "subject",
        "draft",
        "proposed_facets",
        "variants",
    ]
    assert (m["title"], m["notes"]) == ("A clock", "Line one.\n\nLine two.\n")
    assert (m["technique"], m["subject"]) == (["drafting", "weave"], ["sea"])
    assert m["proposed_facets"] == {"subject": ["moon"]}
    assert m["variants"] == {
        "default": {"label": "Two"},
        "late": {"label": "Late", "description": "Later on.", "draft": True},
        "bare": {"label": "Five", "draft": True},
    }
    assert before["variants"]["bare"]["description"] == "No ring." and "notes" not in before
    assert "notes" not in review.state.edited(m, {"edits": {"notes": "  "}})


# --- apply --------------------------------------------------------------------------------------


def test_apply_publishes_with_new_facet_values(wallpapers, review_files):
    vocabulary()
    piece(
        wallpapers,
        "b",
        technique=["drafting"],
        proposed_facets={"technique": ["weave"], "subject": ["moon"]},
    )
    piece(wallpapers, "c")
    state = {
        "b": {
            "versions": {"default": {"status": "keep", "note": "calm"}},
            "facets": {"technique": {"weave": "accept"}, "subject": {"moon": "accept"}},
            "labels": {"technique": {"weave": "woven grids"}},
        },
        "c": {"versions": {"default": {"status": "keep"}}},
    }  # fmt: skip
    result = review.state.apply(review.state.queue([]), state)
    assert result["refused"] == [
        {"slug": "b", "reason": "subject: moon needs the words visitors see"}
    ]
    assert result["published"] == ["c"] and result["new_facets"] == []
    assert meta("b")["draft"] is True and paths.TAXONOMY.read_text() == TAXONOMY
    assert "facets" in review.state.load_state()["b"]

    # A label typed on any piece serves every piece.
    state["c"]["labels"] = {"subject": {"moon": "the moon"}}
    result = review.state.apply([Step("b", "default", False)], state)
    assert result == {
        "published": ["b"],
        "published_variants": [],
        "unpublished": [],
        "refused": [],
        "edits": [
            {"slug": "b", "variant": "default", "field": "technique", "before": ["drafting"], "after": ["drafting", "weave"]},
            {"slug": "b", "variant": "default", "field": "subject", "before": [], "after": ["moon"]},
        ],
        "new_facets": [
            {"facet": "technique", "value": "weave", "label": "woven grids"},
            {"facet": "subject", "value": "moon", "label": "the moon"},
        ],
    }  # fmt: skip
    b = meta("b")
    assert "draft" not in b and "proposed_facets" not in b
    assert (b["technique"], b["subject"]) == (["drafting", "weave"], ["moon"])
    assert paths.TAXONOMY.read_text() == TAXONOMY.replace(
        "technical drawing\n", "technical drawing\n  weave: woven grids\n"
    ).replace("plants and animals\n", "plants and animals\n  moon: the moon\n")
    assert review.state.load_state() == {
        "b": {"versions": {"default": {"status": "keep", "note": "calm"}}},
        "c": {"versions": {"default": {"status": "keep"}}, "labels": {"subject": {"moon": "the moon"}}},
    }  # fmt: skip
    assert (wallpapers / "index.json").read_text() == "{}\n"  # nothing built


def test_apply_unpublishes_and_asks_again(wallpapers, review_files):
    versions(wallpapers, "v", draft=False)
    labels = {**VERSION_LABELS, "late": {"label": "Eight o'clock", "draft": False}}
    metadata.write_meta("v", {**meta("v"), "variants": labels})
    piece(wallpapers, "p", draft=None)
    state = {
        "v": {"versions": {"default": {"status": "keep"}, "late": {"status": "drop", "note": "too dark"}, "bare": {"status": "keep"}}},
        "p": {"versions": {"default": {"status": "drop"}}},
    }  # fmt: skip
    result = review.state.apply(review.state.queue(["v", "p"]), state)
    assert result["unpublished"] == [
        {"slug": "v", "variant": "late"},
        {"slug": "p", "variant": "default"},
    ]
    assert (result["published"], result["published_variants"]) == (
        [],
        [{"slug": "v", "variant": "bare"}],
    )
    v = meta("v")
    assert v["draft"] is False and v["variants"]["late"]["draft"] is True
    assert "draft" not in v["variants"]["bare"] and meta("p")["draft"] is True
    assert list(meta("p"))[-2:] == ["model", "draft"]
    assert review.state.load_state() == {
        "v": {"versions": {"default": {"status": "keep"}, "late": {"note": "too dark"}, "bare": {"status": "keep"}}}
    }  # fmt: skip
    assert review.state.queue([]) == [Step("p", "default", False), Step("v", "late", False)]


def test_apply_leaves_the_versions_of_a_dropped_piece(wallpapers, review_files):
    versions(wallpapers)
    state = {"versions": {"versions": {"default": {"status": "drop"}, "late": {"status": "keep"}}}}
    result = review.state.apply(review.state.queue([]), state)
    assert result["published_variants"] == [] and meta("versions")["variants"] == VERSION_LABELS
    assert review.state.summarize(review.state.queue([]), state) == {
        "approved": [],
        "rejected": [{"slug": "versions", "note": ""}],
        "undecided": [],
        "notes": [],
        "edit": [],
        "variants": {"approved": [], "rejected": [], "undecided": []},
    }


def test_apply_sends_edits_back_and_asks_again(wallpapers, review_files):
    versions(wallpapers, "v", draft=False)
    piece(wallpapers, "a")
    state = {
        "v": {"versions": {"default": {"status": "edit", "note": "thinner rings"}, "late": {"status": "edit"}, "bare": {"status": "keep", "note": "more like this"}}},
        "a": {"versions": {"default": {"status": "edit", "note": "less dense"}}, "edits": {"title": "Ring"}},
    }  # fmt: skip
    steps = review.state.queue(["v", "a"])
    assert review.state.summarize(steps, state) == {
        "approved": [],
        "rejected": [],
        "undecided": [],
        "notes": [
            {"slug": "v", "variant": "default", "note": "thinner rings"},
            {"slug": "v", "variant": "bare", "note": "more like this"},
            {"slug": "a", "variant": "default", "note": "less dense"},
        ],
        "edit": [
            {"slug": "v", "variant": "default", "published": True, "note": "thinner rings"},
            {"slug": "v", "variant": "late", "published": False, "note": ""},
            {"slug": "a", "variant": "default", "published": False, "note": "less dense"},
        ],
        "variants": {"approved": [{"slug": "v", "variant": "bare"}], "rejected": [], "undecided": []},
    }  # fmt: skip
    result = review.state.apply(steps, state)
    assert (result["published"], result["published_variants"], result["unpublished"]) == (
        [],
        [{"slug": "v", "variant": "bare"}],
        [],
    )
    assert meta("v")["draft"] is False and meta("v")["variants"]["late"]["draft"] is True
    assert meta("a")["draft"] is True and meta("a")["title"] == "Ring"
    assert review.state.load_state() == {
        "v": {"versions": {"bare": {"status": "keep", "note": "more like this"}}}
    }
    assert review.state.queue([]) == [Step("a", "default", False), Step("v", "late", False)]


def test_apply_refuses_edits_that_break_the_lint(wallpapers, review_files):
    piece(wallpapers, "a")
    before = (wallpapers / "a/meta.yaml").read_text()
    state = {"a": {"versions": {"default": {"status": "keep"}}, "edits": {"title": " "}}}
    result = review.state.apply(review.state.queue(["a"]), state)
    assert result["refused"] == [{"slug": "a", "reason": "meta.yaml needs a title"}]
    assert result["published"] == [] and (wallpapers / "a/meta.yaml").read_text() == before
    assert review.state.load_state() == state
    assert review.state.check_entry("a", state["a"], {})["fresh"] == ["meta.yaml needs a title"]


def test_summarize_lists_notes_and_versions():
    steps = [Step("a", "default", False), Step("b", "default", True), Step("b", "x", False)]
    state = {
        "a": {"versions": {"default": {"note": "look again"}}},
        "b": {"versions": {"default": {"status": "keep", "note": "fine"}, "x": {"status": "drop", "note": "a nudge"}}},
    }  # fmt: skip
    assert review.state.summarize(steps, state) == {
        "approved": [],
        "rejected": [],
        "undecided": ["a"],
        "edit": [],
        "notes": [
            {"slug": "a", "variant": "default", "note": "look again"},
            {"slug": "b", "variant": "default", "note": "fine"},
            {"slug": "b", "variant": "x", "note": "a nudge"},
        ],
        "variants": {
            "approved": [],
            "rejected": [{"slug": "b", "variant": "x", "note": "a nudge"}],
            "undecided": [],
        },
    }


# --- the page -----------------------------------------------------------------------------------


def serve(monkeypatch, capsys, slugs, timeout=60):
    """Run review.run in a thread; returns (base url, finish() -> printed JSON)."""
    urls: queue.Queue[str] = queue.Queue()
    monkeypatch.setattr(review.server.webbrowser, "open", urls.put)
    codes = []
    t = threading.Thread(target=lambda: codes.append(review.server.run(slugs, timeout, 0, True)))
    t.start()
    url = urls.get(timeout=10)

    def finish(code=0):
        t.join(timeout=10)
        assert codes == [code]
        out = capsys.readouterr().out
        return json.loads(out[out.index("{") :])

    return url, finish


def http(url, data=None):
    body = None if data is None else json.dumps(data).encode()
    method = "POST" if body is not None else "GET"
    with urllib.request.urlopen(urllib.request.Request(url, data=body, method=method)) as r:
        return r.read()


def test_review_round_trip(wallpapers, review_files, monkeypatch, capsys):
    piece(
        wallpapers,
        "a",
        sources=[{"kind": "inspiration", "title": "</script><b>x", "author": "Someone"}],
        model=None,
        author="A. Person",
        license="CC0-1.0",
    )
    versions(wallpapers, "c", draft=False)
    piece(wallpapers, "published", draft=False)
    built(capsys, "a", "c", "published")
    other = {"other": {"versions": {"default": {"status": "drop"}}}}
    review.state.save_state(other)

    url, finish = serve(monkeypatch, capsys, [])  # the drafts: a, and c's two versions
    page = http(url).decode()
    m = re.search(r"const CFG = (.*);\n", page)
    assert m is not None and "</script><b>" not in page
    cfg = json.loads(m.group(1))
    assert cfg["steps"] == [
        {"slug": "a", "variant": "default", "published": False},
        {"slug": "c", "variant": "late", "published": False},
        {"slug": "c", "variant": "bare", "published": False},
    ]
    a, c = cfg["pieces"]["a"], cfg["pieces"]["c"]
    assert a["sources"][0]["title"] == "</script><b>x"
    assert a["license"] == "CC0-1.0"
    assert len(a["versions"]["default"]["aspects"]) == 6
    assert c["versions"]["late"] == {
        "label": "Eight o'clock",
        "description": "",
        "aspects": ["16:9", "10:16"],
    }
    assert cfg["themes"][0] == {
        "name": "fireproof",
        "bg": "#1C1B1A",
        "fg": "#DAD8CE",
        "accent": "#CF6A4C",
    }
    assert cfg["state"] == other
    assert b"init();" in http(url + "review.js")
    assert cfg["facets"][2] == ["lineage", "Inspired by"]
    assert [t[0] for t in cfg["text"]] == ["title", "description", "notes"]

    template = (paths.build_dir("c", "late") / "16x9.svg").read_bytes()
    assert http(url + "img/c/late/16x9/fireproof.svg") == template
    # The default of a queued version, for comparing, though it is not a step itself.
    assert http(url + "img/c/default/10x16/nord.svg").decode() == recolor.themed(
        "c", parse_seeds("nord"), aspect="10:16"
    )
    for missing in (
        "img/published/default/16x9/fireproof.svg",
        "img/a/default/16x9/nope.svg",
        "img/a/default/4x3/nord.svg",
        "img/c/late/21x9/nord.svg",
        "img/a/default/..%2F..%2Fmeta.yaml/nord.svg",
        "review.py",
        "nope",
    ):
        with pytest.raises(urllib.error.HTTPError):
            http(url + missing)

    lint = json.loads(http(url + "lint", {"slug": "a", "entry": {"edits": {"title": ""}}}))
    assert lint["fresh"] == ["meta.yaml needs a title"]
    assert "meta.yaml needs a title" in lint["errors"]
    with pytest.raises(urllib.error.HTTPError):
        http(url + "lint", {"slug": "other", "entry": {}})

    state = {
        "a": {"versions": {"default": {"status": "keep", "note": "keep"}}, "edits": {"description": "A ring and a dot."}},
        "c": {"versions": {"late": {"status": "keep"}, "bare": {"status": "drop", "note": "empty"}}},
    }  # fmt: skip
    assert http(url + "state", state) == b"ok"
    assert review.state.load_state() == {**state, **other}
    done = json.loads(http(url + "apply", {}))
    printed = finish()
    assert printed == done
    assert printed == {
        "approved": ["a"],
        "rejected": [],
        "undecided": [],
        "notes": [
            {"slug": "a", "variant": "default", "note": "keep"},
            {"slug": "c", "variant": "bare", "note": "empty"},
        ],
        "edit": [],
        "variants": {
            "approved": [{"slug": "c", "variant": "late"}],
            "rejected": [{"slug": "c", "variant": "bare", "note": "empty"}],
            "undecided": [],
        },
        "published": ["a"],
        "published_variants": [{"slug": "c", "variant": "late"}],
        "unpublished": [],
        "refused": [],
        "edits": [
            {"slug": "a", "variant": "default", "field": "description", "before": "A test piece.", "after": "A ring and a dot."}
        ],
        "new_facets": [],
        "finished": True,
    }  # fmt: skip
    assert "draft" not in meta("a") and meta("a")["description"] == "A ring and a dot."
    assert "draft" not in meta("c")["variants"]["late"]
    assert meta("c")["variants"]["bare"]["draft"] is True
    index = json.loads((wallpapers / "index.json").read_text())
    assert index["c"]["variants"]["late"] == {"draft": False, "label": "Eight o'clock"}
    assert review.state.load_state() == {
        "a": {"versions": {"default": {"status": "keep", "note": "keep"}}},
        "c": state["c"],
        **other,
    }


def test_review_reports_a_failed_apply(wallpapers, review_files, monkeypatch, capsys):
    piece(wallpapers, "a")
    built(capsys, "a")
    paths.TAXONOMY.write_text("technique: [drafting]\n")
    review.state.save_state({"a": {"versions": {"default": {"status": "keep"}}}})
    url, finish = serve(monkeypatch, capsys, ["a"])
    with pytest.raises(urllib.error.HTTPError) as e:
        http(url + "apply", {})
    assert e.value.code == 500
    sent = json.loads(e.value.read())
    printed = finish(code=1)
    assert printed == sent
    assert printed["finished"] is False and printed["published"] == []
    assert printed["approved"] == ["a"]
    assert (
        printed["error"] == "ValueError: taxonomy.yaml: technique must map each value to its words"
    )
    assert meta("a")["draft"] is True


def test_review_timeout_applies_nothing(wallpapers, review_files, monkeypatch, capsys):
    piece(wallpapers, "a")
    built(capsys, "a")
    review.state.save_state({"a": {"versions": {"default": {"status": "keep"}}}})
    _, finish = serve(monkeypatch, capsys, ["a"], timeout=0.2)
    out = finish()
    assert out["finished"] is False and out["approved"] == ["a"] and out["published"] == []
    assert meta("a")["draft"] is True


def test_review_refuses_unbuilt_and_empty(wallpapers, review_files, capsys):
    piece(wallpapers, "a")
    versions(wallpapers)
    built(capsys, "a")
    built(capsys, "versions", variant="late")
    piece(wallpapers, "raw")
    with pytest.raises(
        SystemExit,
        match=r"not built: versions, versions \(bare\), raw \(run walldye build versions raw\)",
    ):
        review.server.run(["a", "versions", "raw"], 1, 0, False)
    for slug in ("raw", "versions"):
        (wallpapers / slug / "meta.yaml").unlink()
    metadata.write_meta("a", {**meta("a"), "draft": False})
    with pytest.raises(UsageError, match="no drafts"):
        review.server.run([], 1, 0, False)
    with pytest.raises(SystemExit) as e:
        cli.main(["review", "a", "--all"])
    assert e.value.code == 2
