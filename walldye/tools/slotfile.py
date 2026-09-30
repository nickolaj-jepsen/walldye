"""slots.json: a built version's templates with their slot coefficients, and the stamps that
say what they were built from."""

import importlib.metadata
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace

from walldye.tools import coefs, metadata, paths


class Entry(coefs.Entry):
    """One template's entry in slots.json."""

    sha256: str


def version() -> str:
    """The walldye version, which slots.json records as `checked`."""
    return importlib.metadata.version("walldye")


def dump(slots: Mapping[str, object]) -> str:
    """slots.json text: one top-level key per line, each value compact JSON."""
    lines = [f"{json.dumps(k)}: {json.dumps(v, separators=(',', ':'))}" for k, v in slots.items()]
    return "{\n" + ",\n".join(lines) + "\n}\n"


@dataclass(frozen=True)
class Slots:
    """A parsed slots.json: its stamps and other fields, and its template entries keyed
    "<aspect>/<regime>"."""

    fields: dict[str, object]
    entries: dict[str, Entry]

    def text(self, key: str) -> str | None:
        """Field `key` when it is a string, else None."""
        value = self.fields.get(key)
        return value if isinstance(value, str) else None

    def probes(self) -> dict[str, str]:
        """The probe render hashes by name; {} without any."""
        probes = metadata.as_dict(self.fields.get("probes"))
        return {} if probes is None else {k: str(v) for k, v in probes.items()}

    def current(self, design_sha: str, render_lib: str | None = None) -> bool:
        """Whether these slots were checked by this walldye version for `design_sha`, and,
        when given, under the render inputs `render_lib`."""
        return (
            self.text("design_sha") == design_sha
            and self.text("checked") == version()
            and (render_lib is None or self.text("render_lib") == render_lib)
        )

    def restamped(self, **fields: object) -> "Slots":
        """These slots with `fields` replaced or added, keeping the key order."""
        return replace(self, fields={**self.fields, **fields})

    def to_dict(self) -> dict[str, object]:
        """The slots.json object: the fields in order, then the entries."""
        return {**self.fields, **self.entries}

    def dump(self) -> str:
        return dump(self.to_dict())


def parse(data: Mapping[str, object]) -> Slots:
    """`data`, a slots.json object, as Slots; keys with a "/" are template entries. ValueError
    for a malformed entry."""
    fields: dict[str, object] = {}
    entries: dict[str, Entry] = {}
    for k, value in data.items():
        if "/" not in k:
            fields[k] = value
            continue
        e = metadata.as_dict(value)
        rows = metadata.as_list(None if e is None else e.get("coefs"))
        occ = metadata.as_list(None if e is None else e.get("occ"))
        if e is None or rows is None or occ is None:
            raise ValueError(f"slots.json: {k} is not a template entry")
        file, sha, n = e.get("file"), e.get("sha256"), e.get("n")
        table = [
            [float(v) for v in r if isinstance(v, (int, float))]
            for r in map(metadata.as_list, rows)
            if r is not None
        ]
        if not isinstance(file, str) or not isinstance(sha, str) or not isinstance(n, int):
            raise ValueError(f"slots.json: {k} needs file, sha256 and n")
        if len(table) != len(rows) or any(len(r) != 6 for r in table):
            raise ValueError(f"slots.json: {k} coefs are rows of six numbers")
        indices = [i for i in occ if isinstance(i, int) and 0 <= i < len(table)]
        if len(indices) != len(occ):
            raise ValueError(f"slots.json: {k} occ indexes coefs")
        entries[k] = {"file": file, "sha256": sha, "n": n, "coefs": table, "occ": indices}
    return Slots(fields, entries)


def load(slug: str, variant: str = "default") -> Slots | None:
    """The slots.json of a version, None when absent; ValueError naming the file unless it
    holds a well-formed JSON object."""
    path = paths.build_dir(slug, variant) / "slots.json"
    if not path.exists():
        return None
    try:
        data: object = json.loads(path.read_text())
    except ValueError as e:
        raise ValueError(f"{path}: not valid JSON: {e}") from e
    obj = metadata.as_dict(data)
    if obj is None:
        raise ValueError(f"{path}: not a JSON object")
    try:
        return parse(obj)
    except ValueError as e:
        raise ValueError(f"{path}: {e}") from e
