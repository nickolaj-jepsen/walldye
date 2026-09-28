"""`walldye review` (approve drafts and their versions in a localhost page) and `walldye drop`
(delete pieces)."""

import itertools
import json
import re
import shutil
import sys
import threading
import webbrowser
from collections.abc import Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import override

import yaml

from walldye._aspect import SITE_ASPECTS, TEMPLATE_NAME, template_name
from walldye._theme import parse_seeds
from walldye.tools import common
from walldye.tools.new import dump_yaml, write_meta
from walldye.tools.sheet import themed

STATE_FILE = common.ROOT / ".walldye-review.json"
PAGE = Path(__file__).with_name("review.html")
DECISIONS = ("accept", "decline")

type State = dict[str, dict[str, object]]


def load_state() -> State:
    """Review state {slug: {status?, note?, facets?: {facet: {value: accept|decline}},
    variants?: {name: {status?, note?}}}}; {} if unreadable."""
    try:
        data: object = json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}
    state = common.as_dict(data)
    if state is None:
        return {}
    return {k: v for k, e in state.items() if (v := common.as_dict(e)) is not None}


def save_state(state: Mapping[str, object]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")


def variants(meta: common.Meta) -> dict[str, dict[str, object]]:
    """The named variants of meta.yaml `meta` in file order, as {name: entry}."""
    return {k: v for k, v in common.meta_variants(meta).items() if k != "default"}


def drafts() -> list[str]:
    """Slugs whose meta.yaml says `draft: true` or has a draft variant; an unreadable meta.yaml
    is skipped with a note on stderr."""
    out: list[str] = []
    for slug in common.slugs():
        try:
            meta = common.load_meta(slug)
        except (OSError, ValueError) as e:
            print(f"review: skipped {slug}: {e}", file=sys.stderr)
            continue
        if common.is_draft(meta) or any(e.get("draft") is True for e in variants(meta).values()):
            out.append(slug)
    return out


def _licence(meta: common.Meta) -> str:
    from walldye.tools.lint import license_of

    licence = license_of(meta)
    if licence is None:
        return "missing (walldye check says why)"
    return licence if isinstance(meta.get("license"), str) else f"{licence} (default)"


def _text(entry: Mapping[str, object], key: str) -> str:
    value = entry.get(key)
    return value if isinstance(value, str) else ""


def _dict(value: object) -> dict[str, object]:
    d = common.as_dict(value)
    return {} if d is None else d


def _list(value: object) -> list[object]:
    items = common.as_list(value)
    return [] if items is None else items


def _card(slug: str) -> dict[str, object]:
    from walldye.tools.build import load_slots

    meta = common.load_meta(slug)
    b = common.build_dir(slug)
    slots = load_slots(slug)
    if (b / "16x9.light.svg").exists():
        light, caption = f"svg/{slug}/16x9.light.svg", "light template"
    elif slots is None or "16:9/light" not in slots:
        light, caption = f"light/{slug}.svg", "dark-only: flexoki-light with bg and fg swapped"
    else:
        light, caption = f"light/{slug}.svg", "16x9.svg recoloured to flexoki-light"
    strip = [a for a in SITE_ASPECTS if a != "16:9" and (b / template_name(a)).exists()]
    return {
        "slug": slug,
        "title": _text(meta, "title"),
        "description": _text(meta, "description"),
        "sources": _list(meta.get("sources")),
        "license": _licence(meta),
        "proposed": _dict(meta.get("proposed_facets")),
        "dark": f"svg/{slug}/16x9.svg",
        "light": light,
        "lightCaption": caption,
        "strip": [{"aspect": a, "src": f"svg/{slug}/{template_name(a)}"} for a in strip],
        "variants": [
            {
                "name": name,
                "label": _text(entry, "label"),
                "description": _text(entry, "description"),
                "draft": entry.get("draft") is True,
                "src": f"svg/{slug}/{name}/16x9.svg",
            }
            for name, entry in variants(meta).items()
        ],
    }


def _variant_decisions(state: State, slug: str) -> dict[str, dict[str, object]]:
    decided = _dict(state.get(slug, {}).get("variants"))
    return {k: v for k, e in decided.items() if (v := common.as_dict(e)) is not None}


def summarise(
    slugs: Sequence[str], state: State, names: Mapping[str, Sequence[str]]
) -> dict[str, object]:
    """The decisions in `state` for `slugs` and their named variants `names`: {approved,
    rejected: [{slug, note}], undecided, notes, variants: {approved: [{slug, variant}],
    rejected: [{slug, variant, note}], undecided: [{slug, variant}]}}."""
    status = {s: state.get(s, {}).get("status", "undecided") for s in slugs}
    notes = {s: _text(state.get(s, {}), "note") for s in slugs}
    decided: dict[str, list[dict[str, str]]] = {"approved": [], "rejected": [], "undecided": []}
    for slug in slugs:
        chosen = _variant_decisions(state, slug)
        for name in names.get(slug, ()):
            d = chosen.get(name, {})
            kind = _text(d, "status")
            item = {"slug": slug, "variant": name}
            if kind == "rejected":
                item["note"] = _text(d, "note")
            decided[kind if kind in ("approved", "rejected") else "undecided"].append(item)
    return {
        "approved": [s for s in slugs if status[s] == "approved"],
        "rejected": [{"slug": s, "note": notes[s]} for s in slugs if status[s] == "rejected"],
        "undecided": [s for s in slugs if status[s] not in ("approved", "rejected")],
        "notes": {s: n for s, n in notes.items() if n != ""},
        "variants": decided,
    }


def _accepted(state: State, slug: str, facet: str, value: object) -> object:
    return _dict(_dict(state.get(slug, {}).get("facets")).get(facet)).get(str(value))


def apply(
    slugs: Sequence[str], state: State, names: Mapping[str, Sequence[str]]
) -> dict[str, object]:
    """Publish what `state` approves among `slugs` and their named variants `names`: approved
    pieces settle their proposed facets and get `draft: false`; approved variants get
    `draft: false` under `variants:`. Then rewrite index.json.

    An accepted facet value is appended to its list in taxonomy.yaml (created if missing; only
    its leading comment lines survive the rewrite) and to the piece's own facet list; a
    declined one is dropped. A piece with any proposed facet still undecided is refused and
    left a draft (its approved variants are still published). Everything is decided before
    the first write. Returns {published, refused: [{slug, reason}], published_variants:
    [{slug, variant}]}. ValueError if a taxonomy.yaml facet is not a list or a meta.yaml is
    unreadable.
    """
    text = common.TAXONOMY.read_text() if common.TAXONOMY.exists() else ""
    taxonomy = _dict(yaml.safe_load(text))
    grown = False
    changed: dict[str, common.Meta] = {}
    published: list[str] = []
    refused: list[dict[str, str]] = []
    published_variants: list[dict[str, str]] = []
    for slug in slugs:
        meta = common.load_meta(slug)
        own = _dict(meta.get("variants"))
        for name, d in _variant_decisions(state, slug).items():
            entry = common.as_dict(own.get(name))
            if d.get("status") == "approved" and entry is not None and name in names.get(slug, ()):
                own[name] = {**entry, "draft": False}
                published_variants.append({"slug": slug, "variant": name})
                meta["variants"] = own
                changed[slug] = meta
        if state.get(slug, {}).get("status") != "approved":
            continue
        proposed = {f: _list(vs) for f, vs in _dict(meta.get("proposed_facets")).items()}
        pending = [
            f"{f}: {v}"
            for f, vs in proposed.items()
            for v in vs
            if _accepted(state, slug, f, v) not in DECISIONS
        ]
        if len(pending) > 0:
            reason = "proposed facets undecided: " + ", ".join(pending)
            refused.append({"slug": slug, "reason": reason})
            continue
        meta.pop("proposed_facets", None)
        for facet, values in proposed.items():
            for v in values:
                if _accepted(state, slug, facet, v) != "accept":
                    continue
                known = common.as_list(taxonomy.setdefault(facet, []))
                if known is None:
                    raise ValueError(f"{common.TAXONOMY}: {facet} must be a list of values")
                if v not in known:
                    known.append(v)
                    grown = True
                facet_values = _list(meta.get(facet))
                if v not in facet_values:
                    meta[facet] = [*facet_values, v]
        meta["draft"] = False
        published.append(slug)
        changed[slug] = meta
    if grown:
        lines = text.splitlines(keepends=True)
        header = "".join(itertools.takewhile(lambda line: line.startswith("#"), lines))
        common.TAXONOMY.write_text(header + dump_yaml(taxonomy, flow_lists=False))
    for slug, meta in changed.items():
        write_meta(slug, meta)
    if len(changed) > 0:
        from walldye.tools.build import write_index

        write_index()
    return {"published": published, "refused": refused, "published_variants": published_variants}


def _missing(slug: str, names: Sequence[str]) -> list[str]:
    """`slug` and `slug (name)` for the versions without build/[name/]16x9.svg and slots.json."""
    need = [(common.build_dir(slug), slug)]
    need += [(common.build_dir(slug, n), f"{slug} ({n})") for n in names]
    files = ("16x9.svg", "slots.json")
    return [label for d, label in need if not all((d / f).exists() for f in files)]


def run(slugs: Sequence[str], timeout: float, port: int, open_browser: bool) -> int:
    """Serve the review page for `slugs` (default: the drafts) on 127.0.0.1:`port` (0 picks
    one) and block until Done or `timeout` seconds; then print summarise() plus apply()'s
    result and `finished` as JSON. Decisions persist in STATE_FILE; only Done applies them.
    When apply() raises, the JSON says `error` (also sent to the page) and the run returns 1,
    else 0. Exits without serving when a piece or one of its variants lacks
    build/[<variant>/]16x9.svg or slots.json."""
    slugs = list(slugs) if len(slugs) > 0 else drafts()
    if len(slugs) == 0:
        sys.exit("no drafts to review; name slugs to review other pieces")
    names = {s: list(variants(common.load_meta(s))) for s in slugs}
    missing = [m for s in slugs for m in _missing(s, names[s])]
    if len(missing) > 0:
        todo = " ".join(dict.fromkeys(m.split(" ")[0] for m in missing))
        sys.exit(f"not built: {', '.join(missing)} (run walldye build {todo})")

    lock, done = threading.Lock(), threading.Event()
    result: dict[str, object] = {}
    light_cache: dict[str, bytes] = {}

    class Handler(BaseHTTPRequestHandler):
        @override
        def log_message(self, format: str, *args: object) -> None:
            pass

        def _send(self, code: int, body: bytes, ctype: str = "text/plain") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                cfg = {"cards": [_card(s) for s in slugs], "state": load_state()}
                # </script> inside meta text must not end the inline script.
                config = json.dumps(cfg, default=str).replace("</", "<\\/")
                page = PAGE.read_text().replace("__CONFIG__", config)
                return self._send(200, page.encode(), "text/html; charset=utf-8")
            m = re.fullmatch(r"/svg/([a-z0-9-]+)/(?:([a-z0-9-]+)/)?([^/]+)", self.path)
            if m is not None and m.group(1) in slugs:
                slug, name = m.group(1), m.group(3)
                variant: str | None = m.group(2)
                if variant is None or variant in names[slug]:
                    d = common.build_dir(slug, "default" if variant is None else variant)
                    if TEMPLATE_NAME.fullmatch(name) is not None and (d / name).exists():
                        return self._send(200, (d / name).read_bytes(), "image/svg+xml")
            m = re.fullmatch(r"/light/([a-z0-9-]+)\.svg", self.path)
            if m is not None and m.group(1) in slugs:
                slug = m.group(1)
                if slug not in light_cache:
                    light_cache[slug] = themed(slug, parse_seeds("flexoki-light")).encode()
                return self._send(200, light_cache[slug], "image/svg+xml")
            self._send(404, b"not found")

        def do_POST(self) -> None:
            length = self.headers.get("Content-Length")
            body = self.rfile.read(0 if length is None else int(length))
            try:
                data = common.as_dict(json.loads(body if len(body) > 0 else b"{}"))
            except ValueError:
                return self._send(400, b"bad json")
            if self.path == "/state" and data is not None:
                with lock:
                    state = load_state()
                    for s in slugs:
                        entry = common.as_dict(data.get(s))
                        if entry is not None and len(entry) > 0:
                            state[s] = entry
                        else:
                            state.pop(s, None)
                    save_state(state)
                return self._send(200, b"ok")
            if self.path == "/done":
                with lock:
                    if not done.is_set():
                        state = load_state()
                        result.update(summarise(slugs, state, names))
                        try:
                            result.update(apply(slugs, state, names), finished=True)
                        except (OSError, ValueError, yaml.YAMLError) as e:
                            # The wait must end, and the page must hear why.
                            error = f"{type(e).__name__}: {e}"
                            result.update(
                                published=[],
                                refused=[],
                                published_variants=[],
                                error=error,
                                finished=False,
                            )
                        done.set()
                code = 500 if "error" in result else 200
                return self._send(code, json.dumps(result).encode(), "application/json")
            self._send(404, b"not found")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"review: {url}  (waiting up to {timeout / 60:g} min for Done)", flush=True)
    if open_browser:
        webbrowser.open(url)
    done.wait(timeout)
    with lock:  # a Done racing the timeout either applies fully or not at all
        if not done.is_set():
            done.set()
            late = summarise(slugs, load_state(), names)
            result.update(late, published=[], refused=[], published_variants=[], finished=False)
    server.shutdown()
    server.server_close()
    print(json.dumps(result, indent=1))
    return 1 if "error" in result else 0


def drop(slugs: Sequence[str], yes: bool) -> int:
    """Delete wallpapers/<slug>/ for each of `slugs` after a y/N prompt (skipped with `yes`),
    then regenerate index.json and forget their review state. Returns 1 when the prompt is
    declined."""
    dirs = [common.piece_dir(s) for s in slugs]
    if not yes:
        try:
            answer = input(f"Delete {', '.join(str(d) for d in dirs)}? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("nothing deleted")
            return 1
    for d in dirs:
        shutil.rmtree(d)
        print(f"removed {d}")
    state = load_state()
    if any(s in state for s in slugs):
        save_state({k: v for k, v in state.items() if k not in slugs})
    from walldye.tools.build import write_index

    write_index()
    return 0
