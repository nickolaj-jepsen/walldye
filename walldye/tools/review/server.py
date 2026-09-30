"""The review's localhost page: it serves the queue, keeps the state as it changes, lints
edits as they are typed, and applies the decisions when asked."""

import json
import re
import sys
import threading
import webbrowser
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import override

import yaml

from walldye._aspect import SITE_ASPECTS
from walldye.tools import metadata
from walldye.tools.errors import UsageError
from walldye.tools.paths import aspect_label
from walldye.tools.recolor import themed
from walldye.tools.review.state import (
    RESULT_KEYS,
    apply,
    check_entry,
    config,
    load_state,
    mapping,
    queue,
    save_state,
    summarize,
    text_field,
    unbuilt,
    versions,
)
from walldye.tools.themes import PRESETS, parse_seeds

PAGE = Path(__file__).with_name("page")
STATIC = {"review.js": "text/javascript", "review.css": "text/css"}


def run(
    slugs: Sequence[str], timeout: float, port: int, open_browser: bool, everything: bool = False
) -> int:
    """Serve the review page for queue(`slugs`, `everything`) on 127.0.0.1:`port` (0 picks
    one) and block until Apply or `timeout` seconds; then print summarize() plus apply()'s
    result and `finished` as JSON. Decisions and edits persist in STATE_FILE as they are made;
    only Apply writes them. When apply() raises, the JSON says `error` (also sent to the page)
    and the run returns 1, else 0. UsageError when the queue is empty; exits without serving
    when a version in it lacks build/[<variant>/]16x9.svg or slots.json."""
    steps = queue(slugs, everything)
    if len(steps) == 0:
        if len(slugs) > 0 or everything:
            raise UsageError("nothing to review")
        raise UsageError("no drafts to review; name slugs or pass --all")
    missing = unbuilt(steps)
    if len(missing) > 0:
        todo = " ".join(dict.fromkeys(m.split(" ")[0] for m in missing))
        sys.exit(f"not built: {', '.join(missing)} (run walldye build {todo})")
    scope = {s.slug for s in steps}
    # Every version of a piece in the queue, so a named one can be compared with its default.
    names = {(s, n) for s in scope for n, _ in versions(metadata.load_meta(s))}
    nothing: dict[str, object] = {k: [] for k in RESULT_KEYS}

    lock, done = threading.Lock(), threading.Event()
    result: dict[str, object] = {}
    images: dict[str, bytes] = {}

    class Handler(BaseHTTPRequestHandler):
        @override
        def log_message(self, format: str, *args: object) -> None:
            pass

        def _send(self, code: int, body: bytes, ctype: str = "text/plain") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the page moved on before an image arrived

        def _json(self, data: object, code: int = 200) -> None:
            self._send(code, json.dumps(data, default=str).encode(), "application/json")

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                # </script> inside meta text must not end the inline script.
                cfg = json.dumps(config(steps), default=str).replace("</", "<\\/")
                page = (PAGE / "index.html").read_text().replace("__CONFIG__", cfg)
                return self._send(200, page.encode(), "text/html; charset=utf-8")
            if (name := self.path.lstrip("/")) in STATIC:
                return self._send(200, (PAGE / name).read_bytes(), STATIC[name])
            m = re.fullmatch(r"/img/([a-z0-9-]+)/([a-z0-9-]+)/([0-9.x]+)/([a-z-]+)\.svg", self.path)
            if m is not None and (m.group(1), m.group(2)) in names and m.group(4) in PRESETS:
                slug, variant, label, theme = m.groups()
                aspect = next((a for a in SITE_ASPECTS if aspect_label(a) == label), None)
                if aspect is not None:
                    if self.path not in images:
                        try:
                            svg = themed(slug, parse_seeds(theme), variant, aspect)
                        except (KeyError, OSError, ValueError):
                            return self._send(404, b"not built")
                        images[self.path] = svg.encode()
                    return self._send(200, images[self.path], "image/svg+xml")
            self._send(404, b"not found")

        def do_POST(self) -> None:
            length = self.headers.get("Content-Length")
            body = self.rfile.read(0 if length is None else int(length))
            try:
                data = metadata.as_dict(json.loads(body if len(body) > 0 else b"{}"))
            except ValueError:
                data = None
            if data is None:
                return self._send(400, b"bad json")
            if self.path == "/state":
                with lock:
                    state = load_state()
                    for s in scope:
                        entry = metadata.as_dict(data.get(s))
                        if entry is not None and len(entry) > 0:
                            state[s] = entry
                        else:
                            state.pop(s, None)
                    save_state(state)
                return self._send(200, b"ok")
            if self.path == "/lint":
                if (slug := text_field(data, "slug")) not in scope:
                    return self._send(404, b"not in this review")
                try:
                    return self._json(check_entry(slug, mapping(data.get("entry")), load_state()))
                except (OSError, ValueError, yaml.YAMLError) as e:
                    problem = f"{type(e).__name__}: {e}"
                    return self._json({"errors": [problem], "warnings": [], "fresh": [problem]})
            if self.path == "/apply":
                with lock:
                    if not done.is_set():
                        state = load_state()
                        result.update(summarize(steps, state))
                        try:
                            result.update(apply(steps, state), finished=True)
                        except (OSError, ValueError, yaml.YAMLError) as e:
                            # The wait must end, and the page must hear why.
                            result.update(nothing)
                            result.update(error=f"{type(e).__name__}: {e}", finished=False)
                        done.set()
                return self._json(result, 500 if "error" in result else 200)
            self._send(404, b"not found")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(
        f"review: {url}  ({len(steps)} to look at; waiting up to {timeout / 60:g} min)", flush=True
    )
    if open_browser:
        webbrowser.open(url)
    done.wait(timeout)
    with lock:  # an Apply racing the timeout either applies fully or not at all
        if not done.is_set():
            done.set()
            result.update(summarize(steps, load_state()))
            result.update(nothing, finished=False)
    server.shutdown()
    server.server_close()
    print(json.dumps(result, indent=1, default=str))
    return 1 if "error" in result else 0
