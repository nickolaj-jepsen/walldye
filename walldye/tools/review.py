"""`walldye review` (approve drafts in a localhost page) and `walldye drop` (delete pieces)."""

from __future__ import annotations

import itertools
import json
import re
import shutil
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

import walldye
from walldye.tools import common
from walldye.tools.new import dump_yaml, write_meta
from walldye.tools.sheet import themed

STATE_FILE = common.ROOT / ".walldye-review.json"
PAGE = Path(__file__).with_name("review.html")
DECISIONS = ("accept", "decline")


def load_state() -> dict:
    """Review state {slug: {status?, note?, facets?: {facet: {value: accept|decline}}}}; {} if unreadable."""
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")


def drafts() -> list[str]:
    """Slugs whose meta.yaml says `draft: true`; an unreadable meta.yaml is skipped with a note on stderr."""
    out = []
    for slug in common.slugs():
        try:
            if common.is_draft(common.load_meta(slug)):
                out.append(slug)
        except (OSError, ValueError) as e:
            print(f"review: skipped {slug}: {e}", file=sys.stderr)
    return out


def _licence(meta: dict) -> str:
    from walldye.tools.lint import license_of

    licence = license_of(meta)
    if licence is None:
        return "missing (walldye check says why)"
    return licence if meta.get("license") else f"{licence} (default)"


def _card(slug: str) -> dict:
    from walldye.tools.build import load_slots

    meta = common.load_meta(slug)
    b = common.build_dir(slug)
    if (b / "16x9.light.svg").exists():
        light, caption = f"svg/{slug}/16x9.light.svg", "light template"
    elif "16:9/light" not in load_slots(slug):
        light, caption = f"light/{slug}.svg", "dark-only: flexoki-light with bg and fg swapped"
    else:
        light, caption = f"light/{slug}.svg", "16x9.svg recoloured to flexoki-light"
    strip = [
        a for a in walldye.SITE_ASPECTS if a != "16:9" and (b / walldye.template_name(a)).exists()
    ]
    return {
        "slug": slug,
        "title": meta.get("title") or "",
        "description": meta.get("description") or "",
        "sources": meta.get("sources") or [],
        "license": _licence(meta),
        "proposed": meta.get("proposed_facets") or {},
        "dark": f"svg/{slug}/16x9.svg",
        "light": light,
        "lightCaption": caption,
        "strip": [{"aspect": a, "src": f"svg/{slug}/{walldye.template_name(a)}"} for a in strip],
    }


def summarise(slugs: list[str], state: dict) -> dict:
    """The decisions in `state` for `slugs`: {approved, rejected: [{slug, note}], undecided, notes}."""
    status = {s: (state.get(s) or {}).get("status", "undecided") for s in slugs}
    return {
        "approved": [s for s in slugs if status[s] == "approved"],
        "rejected": [
            {"slug": s, "note": state[s].get("note", "")} for s in slugs if status[s] == "rejected"
        ],
        "undecided": [s for s in slugs if status[s] == "undecided"],
        "notes": {s: state[s]["note"] for s in slugs if (state.get(s) or {}).get("note")},
    }


def apply(slugs: list[str], state: dict) -> dict:
    """Publish the approved `slugs`: settle their proposed facets, set `draft: false`, rewrite index.json.

    An accepted facet value is appended to its list in taxonomy.yaml (created if missing; only
    its leading comment lines survive the rewrite) and to the piece's own facet list; a declined
    one is dropped. A piece with any proposed facet still undecided is refused and left
    untouched. Everything is decided before the first write. Returns {published, refused:
    [{slug, reason}]}. ValueError if a taxonomy.yaml facet is not a list or a meta.yaml is
    unreadable.
    """
    text = common.TAXONOMY.read_text() if common.TAXONOMY.exists() else ""
    taxonomy = yaml.safe_load(text) or {}
    grown, published, refused = False, {}, []
    for slug in summarise(slugs, state)["approved"]:
        meta = common.load_meta(slug)
        proposed = meta.pop("proposed_facets", None) or {}
        decided = state[slug].get("facets") or {}
        pending = [
            f"{f}: {v}"
            for f, vs in proposed.items()
            for v in vs
            if (decided.get(f) or {}).get(v) not in DECISIONS
        ]
        if pending:
            refused.append(
                {"slug": slug, "reason": "proposed facets undecided: " + ", ".join(pending)}
            )
            continue
        for facet, values in proposed.items():
            for v in values:
                if decided[facet][v] != "accept":
                    continue
                known = taxonomy.setdefault(facet, [])
                if not isinstance(known, list):
                    raise ValueError(f"{common.TAXONOMY}: {facet} must be a list of values")
                if v not in known:
                    known.append(v)
                    grown = True
                own = meta.get(facet) or []
                if v not in own:
                    meta[facet] = [*own, v]
        meta["draft"] = False
        published[slug] = meta
    if grown:
        header = "".join(
            itertools.takewhile(lambda line: line.startswith("#"), text.splitlines(keepends=True))
        )
        common.TAXONOMY.write_text(header + dump_yaml(taxonomy, flow_lists=False))
    for slug, meta in published.items():
        write_meta(slug, meta)
    if published:
        from walldye.tools.build import write_index

        write_index()
    return {"published": list(published), "refused": refused}


def run(slugs: list[str], timeout: float, port: int, open_browser: bool) -> int:
    """Serve the review page for `slugs` (default: the drafts) on 127.0.0.1:`port` (0 picks one)
    and block until Done or `timeout` seconds; then print summarise() plus apply()'s result and
    `finished` as JSON. Decisions persist in STATE_FILE; only Done applies approvals. When
    apply() raises, the JSON says `error` (also sent to the page) and the run returns 1, else 0.
    Exits without serving when a piece lacks build/16x9.svg or build/slots.json."""
    slugs = slugs or drafts()
    if not slugs:
        sys.exit("no drafts to review; name slugs to review other pieces")
    missing = [
        s
        for s in slugs
        if not all((common.build_dir(s) / f).exists() for f in ("16x9.svg", "slots.json"))
    ]
    if missing:
        sys.exit(f"not built: {', '.join(missing)} (run walldye build {' '.join(missing)})")

    lock, done, result = threading.Lock(), threading.Event(), {}
    light_cache: dict[str, bytes] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code: int, body: bytes, ctype: str = "text/plain") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                cfg = {"cards": [_card(s) for s in slugs], "state": load_state()}
                # </script> inside meta text must not end the inline script.
                page = PAGE.read_text().replace(
                    "__CONFIG__", json.dumps(cfg, default=str).replace("</", "<\\/")
                )
                return self._send(200, page.encode(), "text/html; charset=utf-8")
            if (m := re.fullmatch(r"/svg/([a-z0-9-]+)/([^/]+)", self.path)) and m.group(1) in slugs:
                f = common.build_dir(m.group(1)) / m.group(2)
                if walldye.TEMPLATE_NAME.match(m.group(2)) and f.exists():
                    return self._send(200, f.read_bytes(), "image/svg+xml")
            if (m := re.fullmatch(r"/light/([a-z0-9-]+)\.svg", self.path)) and m.group(1) in slugs:
                slug = m.group(1)
                if slug not in light_cache:
                    light_cache[slug] = themed(slug, walldye.parse_seeds("flexoki-light")).encode()
                return self._send(200, light_cache[slug], "image/svg+xml")
            self._send(404, b"not found")

        def do_POST(self):
            try:
                data = json.loads(
                    self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}"
                )
            except ValueError:
                return self._send(400, b"bad json")
            if self.path == "/state" and isinstance(data, dict):
                with lock:
                    state = load_state()
                    for s in slugs:
                        if isinstance(data.get(s), dict) and data[s]:
                            state[s] = data[s]
                        else:
                            state.pop(s, None)
                    save_state(state)
                return self._send(200, b"ok")
            if self.path == "/done":
                with lock:
                    if not done.is_set():
                        state = load_state()
                        result.update(summarise(slugs, state))
                        try:
                            result.update(apply(slugs, state), finished=True)
                        except Exception as e:  # the wait must end and the page must hear why
                            result.update(
                                published=[],
                                refused=[],
                                error=f"{type(e).__name__}: {e}",
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
            result.update(summarise(slugs, load_state()), published=[], refused=[], finished=False)
    server.shutdown()
    server.server_close()
    print(json.dumps(result, indent=1))
    return 1 if "error" in result else 0


def drop(slugs: list[str], yes: bool) -> int:
    """Delete wallpapers/<slug>/ for each of `slugs` after a y/N prompt (skipped with `yes`), then
    regenerate index.json and forget their review state. Returns 1 when the prompt is declined."""
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
