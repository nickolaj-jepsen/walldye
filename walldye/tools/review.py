"""`walldye review` (decide drafts one version at a time, and edit their words and facets, in a
localhost page) and `walldye drop` (delete pieces)."""

import itertools
import json
import re
import shutil
import sys
import threading
import webbrowser
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import override

import yaml

from walldye._aspect import SITE_ASPECTS, canvas_size
from walldye._theme import SEEDS
from walldye.tools import metadata, paths
from walldye.tools.errors import UsageError
from walldye.tools.metadata import dump_yaml, write_meta
from walldye.tools.paths import aspect_label, template_name
from walldye.tools.sheet import themed
from walldye.tools.themes import PRESETS, parse_seeds

STATE_FILE = paths.ROOT / ".walldye-review.json"
LABELS = paths.ROOT / "src/lib/labels.ts"
PAGE = Path(__file__).with_name("review_page")
STATIC = {"review.js": "text/javascript", "review.css": "text/css"}
# facet: its legend on the page
FACETS = {"technique": "Technique", "subject": "Subject", "lineage": "Inspired by"}
# field: (its label on the page, rows in its text box)
TEXT = {"title": ("Title", 1), "description": ("Description", 3), "notes": ("Notes", 5)}
FACET_VALUE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
RESULT_KEYS = ("published", "published_variants", "unpublished", "refused", "edits", "new_facets")
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_LABEL_LINE = re.compile(r"    (?:'([^']+)'|([A-Za-z_$][\w$]*)): '((?:[^'\\]|\\.)*)',")

type State = dict[str, dict[str, object]]
type Labels = dict[str, dict[str, str]]


@dataclass(frozen=True)
class Step:
    """One version in the review queue; `published` when the site shows it now."""

    slug: str
    variant: str
    published: bool


def load_state() -> State:
    """Review state {slug: {versions?: {name: {status?: keep|edit|drop, note?}}, edits?: {title?,
    description?, notes?, technique?, subject?, lineage?, variants?: {name: {label?,
    description?}}}, facets?: {facet: {value: accept|decline}}, labels?: {facet: {value:
    label}}}}; {} if unreadable."""
    try:
        data: object = json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}
    state = metadata.as_dict(data)
    if state is None:
        return {}
    return {k: v for k, e in state.items() if (v := metadata.as_dict(e)) is not None}


def save_state(state: Mapping[str, object]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")


def variants(meta: metadata.Meta) -> dict[str, dict[str, object]]:
    """The named variants of meta.yaml `meta` in file order, as {name: entry}."""
    return {k: v for k, v in metadata.meta_variants(meta).items() if k != "default"}


def versions(meta: metadata.Meta) -> list[tuple[str, bool]]:
    """(name, published) for each version of meta.yaml `meta`, "default" first: published
    when the piece is not a draft and, for a named variant, its entry is not `draft: true`."""
    shown = not metadata.is_draft(meta)
    named = [(n, shown and e.get("draft") is not True) for n, e in variants(meta).items()]
    return [("default", shown), *named]


def drafts() -> list[str]:
    """Slugs whose meta.yaml says `draft: true` or has a draft variant; an unreadable meta.yaml
    is skipped with a note on stderr."""
    return list(dict.fromkeys(s.slug for s in queue([])))


def queue(slugs: Sequence[str], everything: bool = False) -> list[Step]:
    """Every version of `slugs`, in their order; without slugs, the unpublished versions of
    every piece, or with `everything` all versions, unpublished ones first. Each piece's
    versions keep meta.yaml order. An unreadable meta.yaml is skipped with a note on stderr."""
    steps: list[Step] = []
    for slug in slugs if len(slugs) > 0 else paths.slugs():
        try:
            meta = metadata.load_meta(slug)
        except (OSError, ValueError) as e:
            print(f"review: skipped {slug}: {e}", file=sys.stderr)
            continue
        steps += [Step(slug, name, shown) for name, shown in versions(meta)]
    if len(slugs) > 0:
        return steps
    hidden = [s for s in steps if not s.published]
    return hidden + [s for s in steps if s.published] if everything else hidden


def _license(meta: metadata.Meta) -> str:
    from walldye.tools.lint import license_of

    license = license_of(meta)
    if license is None:
        return "missing (walldye check says why)"
    if isinstance(meta.get("license"), str):
        return license
    return f"{license} (from franchise)" if "franchise" in meta else f"{license} (default)"


def _text(entry: Mapping[str, object], key: str) -> str:
    value = entry.get(key)
    return value if isinstance(value, str) else ""


def _dict(value: object) -> dict[str, object]:
    d = metadata.as_dict(value)
    return {} if d is None else d


def _list(value: object) -> list[object]:
    items = metadata.as_list(value)
    return [] if items is None else items


def _strs(value: object) -> list[str]:
    return [str(v) for v in _list(value)]


def facet_labels(text: str) -> Labels:
    """The FACET_LABELS table of src/lib/labels.ts source `text`, as {facet: {value: label}};
    {} when the table is missing."""
    start = text.find("export const FACET_LABELS")
    if start < 0:
        return {}
    out: Labels = {}
    facet: str | None = None
    for line in text[start:].splitlines()[1:]:
        if line.startswith("}"):
            break
        if (m := re.fullmatch(r"  ([\w-]+): \{", line)) is not None:
            facet = m.group(1)
            out[facet] = {}
        elif facet is not None and (m := _LABEL_LINE.fullmatch(line)) is not None:
            key = m.group(1) if m.group(1) is not None else m.group(2)
            out[facet][key] = re.sub(r"\\(.)", r"\1", m.group(3))
    return out


def add_labels(text: str, new: Mapping[str, Mapping[str, str]]) -> str:
    """labels.ts source `text` with each of `new` {facet: {value: label}} appended to its
    facet's block of FACET_LABELS. ValueError when that block is not found."""
    lines = text.splitlines(keepends=True)
    start = next((i for i, x in enumerate(lines) if x.startswith("export const FACET_LABELS")), -1)
    for facet, values in new.items():
        rows = range(max(start, 0), len(lines))
        head = next((i for i in rows if lines[i] == f"  {facet}: {{\n"), -1)
        end = next((i for i in range(head + 1, len(lines)) if lines[i] == "  },\n"), -1)
        if start < 0 or head < 0 or end < 0:
            raise ValueError(f"{LABELS}: no {facet} block in FACET_LABELS")
        added: list[str] = []
        for value, label in values.items():
            key = value if _IDENT.fullmatch(value) is not None else f"'{value}'"
            quoted = label.replace("\\", "\\\\").replace("'", "\\'")
            added.append(f"    {key}: '{quoted}',\n")
        lines[end:end] = added
    return "".join(lines)


def _labels() -> Labels:
    return facet_labels(LABELS.read_text()) if LABELS.exists() else {}


def _typed_labels(state: State) -> Labels:
    """The labels typed in review for new facet values, across every piece in `state`."""
    out: Labels = {}
    for entry in state.values():
        for facet, values in _dict(entry.get("labels")).items():
            for value, label in _dict(values).items():
                if isinstance(label, str) and label.strip() != "":
                    out.setdefault(facet, {}).setdefault(value, " ".join(label.split()))
    return out


def _merged(*tables: Labels) -> Labels:
    return {f: {k: v for t in tables for k, v in t.get(f, {}).items()} for f in FACETS}


def _put(d: dict[str, object], key: str, value: object, after: str) -> dict[str, object]:
    """`d` with `key` set to `value`; a new key goes right after `after` (or at the end)."""
    if key in d or after not in d:
        return {**d, key: value}
    out: dict[str, object] = {}
    for k, v in d.items():
        out[k] = v
        if k == after:
            out[key] = value
    return out


def _drafted(m: metadata.Meta, draft: bool) -> metadata.Meta:
    """`m` published, with no draft key, or when `draft` with `draft: true` placed after the
    credit and license keys, where `walldye new` writes it."""
    rest = {k: v for k, v in m.items() if k != "draft"}
    if not draft:
        return rest
    after = next((k for k in ("franchise", "license", "model", "author") if k in rest), "")
    return _put(rest, "draft", True, after=after)


def _clean(value: str, block: bool) -> str:
    """Typed text as meta.yaml keeps it: trimmed, and on one line unless `block`, where
    multi-line text ends in a newline."""
    if not block:
        return " ".join(value.split())
    text = "\n".join(line.rstrip() for line in value.strip().splitlines())
    return text + "\n" if "\n" in text else text


def edited(meta: metadata.Meta, entry: Mapping[str, object]) -> metadata.Meta:
    """`meta` with the edits and proposed-facet decisions of review state `entry`, draft flags
    untouched. An accepted proposed value joins its facet, and decided values leave
    proposed_facets, which goes once empty. Emptied notes are removed."""
    m = dict(meta)
    edits = _dict(entry.get("edits"))
    for key in TEXT:
        if isinstance(value := edits.get(key), str):
            text = _clean(value, key == "notes")
            if key == "notes" and text == "":
                m.pop(key, None)
            else:
                m = _put(m, key, text, after="description")
    for facet in FACETS:
        if facet in edits:
            m[facet] = _strs(edits.get(facet))
    decided = _dict(entry.get("facets"))
    proposed = _dict(meta.get("proposed_facets"))
    if len(decided) > 0 and len(proposed) > 0:
        left: dict[str, object] = {}
        for facet, values in proposed.items():
            undecided: list[object] = []
            for v in _list(values):
                d = _dict(decided.get(facet)).get(str(v))
                if d == "accept":
                    have = _list(m.get(facet))
                    m[facet] = have if v in have else [*have, v]
                elif d != "decline":
                    undecided.append(v)
            if len(undecided) > 0:
                left[facet] = undecided
        if len(left) > 0:
            m["proposed_facets"] = left
        else:
            m.pop("proposed_facets", None)
    own = metadata.as_dict(m.get("variants"))
    changes = _dict(edits.get("variants"))
    if own is not None and len(changes) > 0:
        out: dict[str, object] = {}
        for name, value in own.items():
            e, c = metadata.as_dict(value), _dict(changes.get(name))
            if e is None:
                out[name] = value
                continue
            if isinstance(label := c.get("label"), str):
                e["label"] = _clean(label, False)
            if name != "default" and isinstance(d := c.get("description"), str):
                if (text := _clean(d, False)) != "":
                    e = _put(e, "description", text, after="label")
                else:
                    e.pop("description", None)
            out[name] = e
        m["variants"] = out
    return m


def _new_values(
    m: metadata.Meta, known: Mapping[str, Sequence[str]], labels: Labels
) -> list[tuple[str, str, str]]:
    """(facet, value, label) for each value of `m`'s facets missing from `known`, with its
    label from `labels` ("" when it has none)."""
    return [
        (f, v, labels.get(f, {}).get(v, ""))
        for f in FACETS
        for v in _strs(m.get(f))
        if v not in known.get(f, ())
    ]


def _problems(
    slug: str,
    before: metadata.Meta,
    after: metadata.Meta,
    known: Mapping[str, Sequence[str]],
    labels: Labels,
) -> tuple[list[str], list[str], list[str]]:
    """(errors, warnings, fresh) from lint.meta for `after`, the meta.yaml of `slug` as edited
    from `before`, with the new facet values counted as known. fresh holds the errors `before`
    lacks, plus one for each new value that is malformed or has no label in `labels`."""
    from walldye.tools import lint

    new = _new_values(after, known, labels)
    taxonomy = {
        f: {*known.get(f, ()), *(v for g, v, _ in new if g == f)} for f in {*known, *FACETS}
    }
    names = ["default", *variants(before)]
    old, _ = lint.meta(slug, before, taxonomy, names)
    errors, warnings = lint.meta(slug, after, taxonomy, names)
    fresh = [e for e in errors if e not in old]
    for f, v, label in new:
        if FACET_VALUE.fullmatch(v) is None:
            fresh.append(f"{f}: {v!r} must be lowercase words joined by hyphens")
        elif label == "":
            fresh.append(f"{f}: {v} needs the words visitors see")
    return errors, warnings, fresh


def _taxonomy() -> tuple[str, dict[str, object], dict[str, list[str]]]:
    """(taxonomy.yaml text, parsed, {facet: values}); ValueError when a facet is not a list."""
    text = paths.TAXONOMY.read_text() if paths.TAXONOMY.exists() else ""
    parsed = _dict(yaml.safe_load(text))
    known: dict[str, list[str]] = {}
    for facet, values in parsed.items():
        if (items := metadata.as_list(values)) is None:
            raise ValueError(f"{paths.TAXONOMY}: {facet} must be a list of values")
        known[facet] = [str(v) for v in items]
    return text, parsed, known


def _statuses(entry: Mapping[str, object]) -> dict[str, str]:
    return {k: _text(_dict(v), "status") for k, v in _dict(entry.get("versions")).items()}


def _grouped(steps: Sequence[Step]) -> dict[str, list[Step]]:
    out: dict[str, list[Step]] = {}
    for step in steps:
        out.setdefault(step.slug, []).append(step)
    return out


def _dropped(group: Sequence[Step], status: Mapping[str, str]) -> bool:
    """Whether the unpublished piece of `group` is dropped, so its named versions are moot."""
    return any(s.variant == "default" and not s.published for s in group) and (
        status.get("default") == "drop"
    )


def summarize(steps: Sequence[Step], state: State) -> dict[str, object]:
    """The decisions in `state` for `steps`: approved, rejected ([{slug, note}]) and undecided
    over the unpublished default versions; notes ([{slug, variant, note}]) over every step;
    edit ([{slug, variant, published, note}]) over every step sent back for changes;
    variants: {approved, rejected, undecided} ([{slug, variant, note?}]) over the unpublished
    named versions. The named versions of a rejected piece are in none of these but notes."""
    pieces: dict[str, list[object]] = {"approved": [], "rejected": [], "undecided": []}
    named: dict[str, list[dict[str, str]]] = {"approved": [], "rejected": [], "undecided": []}
    notes: list[dict[str, str]] = []
    edit: list[dict[str, object]] = []
    for slug, group in _grouped(steps).items():
        entry = _dict(state.get(slug))
        decided = _dict(entry.get("versions"))
        dropped = _dropped(group, _statuses(entry))
        for step in group:
            d = _dict(decided.get(step.variant))
            status, note = _text(d, "status"), _text(d, "note")
            if note != "":
                notes.append({"slug": slug, "variant": step.variant, "note": note})
            moot = dropped and step.variant != "default"
            if status == "edit" and not moot:
                item = {"slug": slug, "variant": step.variant, "published": step.published}
                edit.append({**item, "note": note})
            if step.published or status == "edit":
                continue
            kind = {"keep": "approved", "drop": "rejected"}.get(status, "undecided")
            if step.variant == "default":
                pieces[kind].append({"slug": slug, "note": note} if kind == "rejected" else slug)
            elif not dropped:
                item = {"slug": slug, "variant": step.variant}
                named[kind].append({**item, "note": note} if kind == "rejected" else item)
    return {**pieces, "notes": notes, "edit": edit, "variants": named}


def apply(steps: Sequence[Step], state: State) -> dict[str, object]:
    """Write what `state` decides for `steps`, then settle the state file (_settle()).

    Per piece: its edits and proposed-facet decisions (edited()); a kept unpublished version
    loses its draft key (on the piece for the default, on its variants: entry for a named one),
    and a dropped published one gets `draft: true`; nothing else changes a draft flag. A new
    facet value is appended to taxonomy.yaml (only its leading comment lines survive the
    rewrite) and its label to FACET_LABELS in labels.ts. A piece is refused, and nothing of it
    written, when an edit adds a lint error, a new facet value is malformed or has no label, or
    it would be published with proposed facets undecided. Everything is decided before the
    first write; index.json is rewritten after.

    Returns {published, published_variants: [{slug, variant}], unpublished: [{slug,
    variant}], refused: [{slug, reason}], edits: [{slug, variant, field, before, after}],
    new_facets: [{facet, value, label}]}. ValueError if a taxonomy.yaml facet is not a list,
    labels.ts has no block for a facet, or a meta.yaml is unreadable.
    """
    tax_text, taxonomy, known = _taxonomy()
    labels_text = LABELS.read_text() if LABELS.exists() else ""
    labels = facet_labels(labels_text)
    merged = _merged(labels, _typed_labels(state))
    added: Labels = {}
    changed: dict[str, metadata.Meta] = {}
    written: list[str] = []
    unpublished: list[Step] = []
    sent_back: list[Step] = []
    out: dict[str, list[object]] = {k: [] for k in RESULT_KEYS if k != "new_facets"}
    for slug, group in _grouped(steps).items():
        entry = _dict(state.get(slug))
        meta = metadata.load_meta(slug)
        m = edited(meta, entry)
        status = _statuses(entry)
        known_now = {f: [*known.get(f, []), *added.get(f, {})] for f in {*known, *added}}
        _, _, reasons = _problems(slug, meta, m, known_now, merged)
        results: dict[str, list[object]] = {k: [] for k in out}
        mine: list[Step] = []
        back: list[Step] = []
        dropped = _dropped(group, status)
        own = _dict(m.get("variants"))
        for step in group:
            s = status.get(step.variant, "")
            item = {"slug": slug, "variant": step.variant}
            if s == "edit":
                if step.variant == "default" or not dropped:
                    back.append(step)
                continue
            if step.variant == "default":
                if not step.published and s == "keep":
                    proposed = _dict(m.pop("proposed_facets", None))
                    pending = [f"{f}: {v}" for f, vs in proposed.items() for v in _list(vs)]
                    if len(pending) > 0:
                        reasons.append("proposed facets undecided: " + ", ".join(pending))
                    m = _drafted(m, False)
                    results["published"].append(slug)
                elif step.published and s == "drop":
                    m = _drafted(m, True)
                    results["unpublished"].append(item)
                    mine.append(step)
                continue
            if (e := metadata.as_dict(own.get(step.variant))) is None or dropped:
                continue
            if not step.published and s == "keep":
                own[step.variant] = {k: v for k, v in e.items() if k != "draft"}
                results["published_variants"].append(item)
            elif step.published and s == "drop":
                own[step.variant] = {**e, "draft": True}
                results["unpublished"].append(item)
                mine.append(step)
        if len(own) > 0:
            m["variants"] = own
        if len(reasons) > 0:
            out["refused"].append({"slug": slug, "reason": "; ".join(reasons)})
            continue
        for f, v, label in _new_values(m, known_now, merged):
            added.setdefault(f, {})[v] = label
        results["edits"] = _diff(slug, meta, m)
        for k, items in results.items():
            out[k] += items
        written.append(slug)
        unpublished += mine
        sent_back += back
        if m != meta:
            changed[slug] = m
    fresh = {
        f: {v: x for v, x in vs.items() if v not in labels.get(f, {})} for f, vs in added.items()
    }
    fresh = {f: vs for f, vs in fresh.items() if len(vs) > 0}
    labels_out = add_labels(labels_text, fresh) if len(fresh) > 0 else labels_text
    if len(added) > 0:
        for f, vs in added.items():
            taxonomy[f] = [*known.get(f, []), *vs]
        lines = tax_text.splitlines(keepends=True)
        header = "".join(itertools.takewhile(lambda line: line.startswith("#"), lines))
        paths.TAXONOMY.write_text(header + dump_yaml(taxonomy, flow_lists=False))
    if labels_out != labels_text:
        LABELS.write_text(labels_out)
    for slug, meta in changed.items():
        write_meta(slug, meta)
    if len(changed) > 0:
        from walldye.tools.build import write_index

        write_index()
    _settle(state, written, unpublished, sent_back)
    new_facets = [
        {"facet": f, "value": v, "label": x} for f, vs in added.items() for v, x in vs.items()
    ]
    return {**out, "new_facets": new_facets}


def _diff(slug: str, before: metadata.Meta, after: metadata.Meta) -> list[object]:
    """{slug, variant, field, before, after} for each changed text, facet or version text."""
    rows: list[object] = []
    for key in (*TEXT, *FACETS):
        if (old := before.get(key, "")) != (new := after.get(key, "")):
            rows.append(
                {"slug": slug, "variant": "default", "field": key, "before": old, "after": new}
            )
    old_v, new_v = _dict(before.get("variants")), _dict(after.get("variants"))
    for name, value in new_v.items():
        a, b = _dict(old_v.get(name)), _dict(value)
        for key in ("label", "description"):
            if (old := _text(a, key)) != (new := _text(b, key)):
                rows.append(
                    {"slug": slug, "variant": name, "field": key, "before": old, "after": new}
                )
    return rows


def _settle(
    state: State, written: Sequence[str], unpublished: Sequence[Step], sent_back: Sequence[Step]
) -> None:
    """Drop the applied edits, facet decisions and labels of the `written` pieces from `state`,
    the status of each version in `unpublished` and the status and note of each in
    `sent_back`, then save it."""
    for step in [*unpublished, *sent_back]:
        decided = _dict(state.get(step.slug, {}).get("versions"))
        version = _dict(decided.get(step.variant))
        version.pop("status", None)
        if step in sent_back:
            version.pop("note", None)
        if len(version) > 0:
            decided[step.variant] = version
        else:
            decided.pop(step.variant, None)
        if step.slug in state:
            state[step.slug]["versions"] = decided
    for slug in written:
        entry = state.get(slug)
        if entry is None:
            continue
        for key in ("edits", "facets", "labels"):
            entry.pop(key, None)
        if len(_dict(entry.get("versions"))) == 0:
            entry.pop("versions", None)
        if len(entry) == 0:
            del state[slug]
    save_state(state)


def _missing(steps: Sequence[Step]) -> list[str]:
    """`slug` or `slug (name)` for the versions in `steps` without build/[name/]16x9.svg and
    slots.json."""
    files = ("16x9.svg", "slots.json")
    return [
        s.slug if s.variant == "default" else f"{s.slug} ({s.variant})"
        for s in steps
        if not all((paths.build_dir(s.slug, s.variant) / f).exists() for f in files)
    ]


def _piece(slug: str, meta: metadata.Meta) -> dict[str, object]:
    """What the page shows and edits of one piece."""
    shown: dict[str, object] = {}
    for name, _ in versions(meta):
        entry = _dict(_dict(meta.get("variants")).get(name))
        d = paths.build_dir(slug, name)
        shown[name] = {
            "label": _text(entry, "label"),
            "description": _text(entry, "description"),
            "aspects": [a for a in SITE_ASPECTS if (d / template_name(a)).exists()],
        }
    return {
        **{k: _text(meta, k) for k in TEXT},
        **{f: _strs(meta.get(f)) for f in FACETS},
        "proposed": {f: _strs(vs) for f, vs in _dict(meta.get("proposed_facets")).items()},
        "sources": _list(meta.get("sources")),
        "license": _license(meta),
        "versions": shown,
    }


def config(steps: Sequence[Step]) -> dict[str, object]:
    """The page's data: steps, pieces, the facets and text fields it edits, taxonomy, labels,
    themes, canvas sizes and state."""
    try:
        known = _taxonomy()[2]
    except ValueError:
        known: dict[str, list[str]] = {}
    return {
        "steps": [{"slug": s.slug, "variant": s.variant, "published": s.published} for s in steps],
        "pieces": {slug: _piece(slug, metadata.load_meta(slug)) for slug in _grouped(steps)},
        "facets": [[f, legend] for f, legend in FACETS.items()],
        "text": [[k, label, rows] for k, (label, rows) in TEXT.items()],
        "taxonomy": {f: sorted(known.get(f, [])) for f in FACETS},
        "labels": _labels(),
        "themes": [{"name": n, **{k: PRESETS[n][k] for k in SEEDS}} for n in PRESETS],
        "canvas": {a: canvas_size(a) for a in SITE_ASPECTS},
        "state": load_state(),
    }


def check_entry(slug: str, entry: Mapping[str, object], state: State) -> dict[str, object]:
    """{errors, warnings, fresh} for `slug` as review state `entry` edits it (_problems);
    labels typed for any piece in `state` count."""
    meta = metadata.load_meta(slug)
    merged = _merged(_labels(), _typed_labels({**state, slug: dict(entry)}))
    errors, warnings, fresh = _problems(slug, meta, edited(meta, entry), _taxonomy()[2], merged)
    return {"errors": errors, "warnings": warnings, "fresh": fresh}


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
    missing = _missing(steps)
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
                if (slug := _text(data, "slug")) not in scope:
                    return self._send(404, b"not in this review")
                try:
                    return self._json(check_entry(slug, _dict(data.get("entry")), load_state()))
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


def unfeature(slugs: Sequence[str]) -> list[str]:
    """Remove the `- <slug>` lines of `slugs` from featured.yaml, keeping every other line;
    returns the slugs that were on it."""
    if not paths.FEATURED.exists():
        return []
    lines = paths.FEATURED.read_text().splitlines(keepends=True)
    entry = re.compile(r"-\s+['\"]?([a-z0-9-]+)['\"]?\s*(?:#.*)?$")
    kept: list[str] = []
    gone: list[str] = []
    for line in lines:
        m = entry.match(line.strip())
        if m is not None and m.group(1) in slugs:
            gone.append(m.group(1))
        else:
            kept.append(line)
    if len(gone) > 0:
        paths.FEATURED.write_text("".join(kept))
    return gone


def drop(slugs: Sequence[str], yes: bool) -> int:
    """Delete wallpapers/<slug>/ for each of `slugs` after a y/N prompt (skipped with `yes`),
    then take them off featured.yaml, regenerate index.json and forget their review state.
    Returns 1 when the prompt is declined."""
    dirs = [paths.piece_dir(s) for s in slugs]
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
    for slug in unfeature(slugs):
        print(f"took {slug} off {paths.FEATURED.name}")
    state = load_state()
    if any(s in state for s in slugs):
        save_state({k: v for k, v in state.items() if k not in slugs})
    from walldye.tools.build import write_index

    write_index()
    return 0
