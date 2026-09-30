"""The review's state and logic: the queue of versions, the decisions and edits kept in
STATE_FILE, and applying them to meta.yaml and taxonomy.yaml."""

import itertools
import json
import re
import sys
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

import yaml

from walldye._aspect import SITE_ASPECTS, canvas_size
from walldye._theme import SEEDS
from walldye.tools import index, lint, metadata, paths
from walldye.tools.metadata import dump_yaml, write_meta
from walldye.tools.paths import template_name
from walldye.tools.themes import PRESETS

STATE_FILE = paths.ROOT / ".walldye-review.json"
# facet: its legend on the page
FACETS = {"technique": "Technique", "subject": "Subject", "lineage": "Inspired by"}
# field: (its label on the page, rows in its text box)
TEXT = {
    "title": ("Title", 1),
    "description": ("Description", 2),
    "alt": ("Alt text", 2),
    "notes": ("Notes", 5),
}
# A named version's own text fields; left empty, the piece's are shown.
VERSION_TEXT = ("description", "alt")
FACET_VALUE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
RESULT_KEYS = ("published", "published_variants", "unpublished", "refused", "edits", "new_facets")

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
    description?, alt?, notes?, technique?, subject?, lineage?, variants?: {name: {label?,
    description?, alt?}}}, facets?: {facet: {value: accept|decline}}, labels?: {facet: {value:
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
    from walldye.tools.lint.piece import license_of

    license = license_of(meta)
    if license is None:
        return "missing (walldye check says why)"
    if isinstance(meta.get("license"), str):
        return license
    return f"{license} (from franchise)" if "franchise" in meta else f"{license} (default)"


def text_field(entry: Mapping[str, object], key: str) -> str:
    """`entry[key]` when it is a string, else ""."""
    value = entry.get(key)
    return value if isinstance(value, str) else ""


def mapping(value: object) -> dict[str, object]:
    """`value` as a dict with str keys, {} when it is not a mapping."""
    d = metadata.as_dict(value)
    return {} if d is None else d


def _list(value: object) -> list[object]:
    items = metadata.as_list(value)
    return [] if items is None else items


def _strs(value: object) -> list[str]:
    return [str(v) for v in _list(value)]


def _typed_labels(state: State) -> Labels:
    """The labels typed in review for new facet values, across every piece in `state`."""
    out: Labels = {}
    for entry in state.values():
        for facet, values in mapping(entry.get("labels")).items():
            for value, label in mapping(values).items():
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
    edits = mapping(entry.get("edits"))
    for key in TEXT:
        if isinstance(value := edits.get(key), str):
            text = _clean(value, key == "notes")
            if key == "notes" and text == "":
                m.pop(key, None)
            else:
                m = _put(
                    m, key, text, after="alt" if key == "notes" and "alt" in m else "description"
                )
    for facet in FACETS:
        if facet in edits:
            m[facet] = _strs(edits.get(facet))
    decided = mapping(entry.get("facets"))
    proposed = mapping(meta.get("proposed_facets"))
    if len(decided) > 0 and len(proposed) > 0:
        left: dict[str, object] = {}
        for facet, values in proposed.items():
            undecided: list[object] = []
            for v in _list(values):
                d = mapping(decided.get(facet)).get(str(v))
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
    changes = mapping(edits.get("variants"))
    if own is not None and len(changes) > 0:
        out: dict[str, object] = {}
        for name, value in own.items():
            e, c = metadata.as_dict(value), mapping(changes.get(name))
            if e is None:
                out[name] = value
                continue
            if isinstance(label := c.get("label"), str):
                e["label"] = _clean(label, False)
            for key, after in zip(VERSION_TEXT, ("label", "description"), strict=True):
                if name != "default" and isinstance(d := c.get(key), str):
                    if (text := _clean(d, False)) != "":
                        e = _put(e, key, text, after=after if after in e else "label")
                    else:
                        e.pop(key, None)
            out[name] = e
        m["variants"] = out
    return m


def _new_values(
    m: metadata.Meta, known: Mapping[str, Collection[str]], labels: Labels
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
    taxonomy: lint.piece.Taxonomy,
    labels: Labels,
) -> tuple[list[str], list[str], list[str]]:
    """(errors, warnings, fresh) from lint.piece.meta for `after`, the meta.yaml of `slug` as
    edited from `before`, with its new facet values counted as known. fresh holds the errors
    `before` lacks, plus one for each new value that is malformed or has no label in `labels`."""
    new = _new_values(after, taxonomy.facets, labels)
    facets = {f: dict(taxonomy.facets.get(f, {})) for f in FACETS}
    for f, v, label in new:
        facets[f][v] = label
    grown = lint.piece.Taxonomy(facets, taxonomy.models)
    names = ["default", *variants(before)]
    old, _ = lint.piece.meta(slug, before, grown, names)
    errors, warnings = lint.piece.meta(slug, after, grown, names)
    fresh = [e for e in errors if e not in old]
    for f, v, label in new:
        if FACET_VALUE.fullmatch(v) is None:
            fresh.append(f"{f}: {v!r} must be lowercase words joined by hyphens")
        elif label == "":
            fresh.append(f"{f}: {v} needs the words visitors see")
    return errors, warnings, fresh


def _taxonomy() -> lint.piece.Taxonomy:
    """taxonomy.yaml, with no facets or models when it does not exist; ValueError when it is
    malformed."""
    taxonomy = lint.piece.load_taxonomy()
    return lint.piece.Taxonomy({f: {} for f in FACETS}, {}) if taxonomy is None else taxonomy


def _statuses(entry: Mapping[str, object]) -> dict[str, str]:
    return {k: text_field(mapping(v), "status") for k, v in mapping(entry.get("versions")).items()}


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
        entry = mapping(state.get(slug))
        decided = mapping(entry.get("versions"))
        dropped = _dropped(group, _statuses(entry))
        for step in group:
            d = mapping(decided.get(step.variant))
            status, note = text_field(d, "status"), text_field(d, "note")
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
    rewrite) with its label. A piece is refused, and nothing of it
    written, when an edit adds a lint error, a new facet value is malformed or has no label, or
    it would be published with proposed facets undecided. Everything is decided before the
    first write; index.json is rewritten after.

    Returns {published, published_variants: [{slug, variant}], unpublished: [{slug,
    variant}], refused: [{slug, reason}], edits: [{slug, variant, field, before, after}],
    new_facets: [{facet, value, label}]}. ValueError if taxonomy.yaml is malformed or a
    meta.yaml is unreadable.
    """
    taxonomy = _taxonomy()
    merged = _merged(taxonomy.facets, _typed_labels(state))
    added: Labels = {}
    changed: dict[str, metadata.Meta] = {}
    written: list[str] = []
    unpublished: list[Step] = []
    sent_back: list[Step] = []
    out: dict[str, list[object]] = {k: [] for k in RESULT_KEYS if k != "new_facets"}
    for slug, group in _grouped(steps).items():
        entry = mapping(state.get(slug))
        meta = metadata.load_meta(slug)
        m = edited(meta, entry)
        status = _statuses(entry)
        known_now = lint.piece.Taxonomy(
            {f: {**taxonomy.facets.get(f, {}), **added.get(f, {})} for f in FACETS},
            taxonomy.models,
        )
        _, _, reasons = _problems(slug, meta, m, known_now, merged)
        results: dict[str, list[object]] = {k: [] for k in out}
        mine: list[Step] = []
        back: list[Step] = []
        dropped = _dropped(group, status)
        own = mapping(m.get("variants"))
        for step in group:
            s = status.get(step.variant, "")
            item = {"slug": slug, "variant": step.variant}
            if s == "edit":
                if step.variant == "default" or not dropped:
                    back.append(step)
                continue
            if step.variant == "default":
                if not step.published and s == "keep":
                    proposed = mapping(m.pop("proposed_facets", None))
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
        for f, v, label in _new_values(m, known_now.facets, merged):
            added.setdefault(f, {})[v] = label
        results["edits"] = _diff(slug, meta, m)
        for k, items in results.items():
            out[k] += items
        written.append(slug)
        unpublished += mine
        sent_back += back
        if m != meta:
            changed[slug] = m
    if len(added) > 0:
        text = paths.TAXONOMY.read_text() if paths.TAXONOMY.exists() else ""
        data = metadata.as_dict(yaml.safe_load(text))
        data = {} if data is None else data
        for f, vs in added.items():
            data[f] = {**taxonomy.facets.get(f, {}), **vs}
        lines = text.splitlines(keepends=True)
        header = "".join(itertools.takewhile(lambda line: line.startswith("#"), lines))
        paths.TAXONOMY.write_text(header + dump_yaml(data, flow_lists=False))
    for slug, meta in changed.items():
        write_meta(slug, meta)
    if len(changed) > 0:
        index.write()
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
    old_v, new_v = mapping(before.get("variants")), mapping(after.get("variants"))
    for name, value in new_v.items():
        a, b = mapping(old_v.get(name)), mapping(value)
        for key in ("label", *VERSION_TEXT):
            if (old := text_field(a, key)) != (new := text_field(b, key)):
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
        decided = mapping(state.get(step.slug, {}).get("versions"))
        version = mapping(decided.get(step.variant))
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
        if len(mapping(entry.get("versions"))) == 0:
            entry.pop("versions", None)
        if len(entry) == 0:
            del state[slug]
    save_state(state)


def unbuilt(steps: Sequence[Step]) -> list[str]:
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
        entry = mapping(mapping(meta.get("variants")).get(name))
        d = paths.build_dir(slug, name)
        shown[name] = {
            "label": text_field(entry, "label"),
            **{k: text_field(entry, k) for k in VERSION_TEXT},
            "aspects": [a for a in SITE_ASPECTS if (d / template_name(a)).exists()],
        }
    return {
        **{k: text_field(meta, k) for k in TEXT},
        **{f: _strs(meta.get(f)) for f in FACETS},
        "proposed": {f: _strs(vs) for f, vs in mapping(meta.get("proposed_facets")).items()},
        "sources": _list(meta.get("sources")),
        "license": _license(meta),
        "versions": shown,
    }


def config(steps: Sequence[Step]) -> dict[str, object]:
    """The page's data: steps, pieces, the facets and text fields it edits, taxonomy, labels,
    themes, canvas sizes and state."""
    try:
        known = _taxonomy().facets
    except ValueError:
        known: Labels = {}
    return {
        "steps": [{"slug": s.slug, "variant": s.variant, "published": s.published} for s in steps],
        "pieces": {slug: _piece(slug, metadata.load_meta(slug)) for slug in _grouped(steps)},
        "facets": [[f, legend] for f, legend in FACETS.items()],
        "text": [[k, label, rows] for k, (label, rows) in TEXT.items()],
        "taxonomy": {f: sorted(known.get(f, [])) for f in FACETS},
        "labels": known,
        "themes": [{"name": n, **{k: PRESETS[n][k] for k in SEEDS}} for n in PRESETS],
        "canvas": {a: canvas_size(a) for a in SITE_ASPECTS},
        "state": load_state(),
    }


def check_entry(slug: str, entry: Mapping[str, object], state: State) -> dict[str, object]:
    """{errors, warnings, fresh} for `slug` as review state `entry` edits it (_problems);
    labels typed for any piece in `state` count."""
    meta = metadata.load_meta(slug)
    merged = _merged(_taxonomy().facets, _typed_labels({**state, slug: dict(entry)}))
    errors, warnings, fresh = _problems(slug, meta, edited(meta, entry), _taxonomy(), merged)
    return {"errors": errors, "warnings": warnings, "fresh": fresh}
