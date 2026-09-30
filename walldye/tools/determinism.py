"""The determinism check's second opinion: the same draws made in a fresh process under
another PYTHONHASHSEED, whose hashes must match this process's."""

import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from walldye._design import RenderSpec
from walldye._document import Document
from walldye.tools import hashing, loader, metadata, paths, themes

HASH_SEED: Final = "4242"


def sample_sha(doc: Document, theme: themes.Theme) -> str:
    """The sha256 of `doc` serialized under `theme`."""
    return hashing.sha256(doc.to_svg(themes.tokens_of(theme)).encode())


def start_fresh(keys: Sequence[str]) -> subprocess.Popen[str]:
    """A running `python -m walldye _hashes` subprocess under PYTHONHASHSEED for `keys`; read
    it with communicate() and judge it with fresh_errors()."""
    return subprocess.Popen(
        [sys.executable, "-m", "walldye", "_hashes", str(paths.WALLPAPERS), *keys],
        env={**os.environ, "PYTHONHASHSEED": HASH_SEED},
        cwd=paths.ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def fresh_errors(run: subprocess.CompletedProcess[str], expected: Mapping[str, str]) -> list[str]:
    """Errors for the keys the finished start_fresh() subprocess `run` drew differently from
    `expected` {key: sha256}."""
    if run.returncode != 0:
        return [f"determinism subprocess failed: {run.stderr.strip()[-600:]}"]
    try:
        got = metadata.as_dict(json.loads(run.stdout))
    except ValueError:
        got = None
    if got is None:
        return [f"determinism subprocess printed {run.stdout[:200]!r}"]
    errors: list[str] = []
    for k, sha in expected.items():
        if got.get(k) != sha:
            _, _, aspect, regime = k.split("@")
            errors.append(
                f"{aspect} {regime}: a fresh process with PYTHONHASHSEED={HASH_SEED} draws it"
                " differently (iterating a set of strings? hash()?)"
            )
    return errors


def hashes_main(args: Sequence[str]) -> int:
    """`python -m walldye _hashes <wallpapers dir> <slug@variant@aspect@regime>...`: print a
    JSON object mapping each key to the sha256 of that draw serialized under the regime's
    sample theme, made in this process. Design errors propagate (non-zero exit)."""
    paths.WALLPAPERS = Path(args[0])
    out: dict[str, str] = {}
    for k in args[1:]:
        slug, variant, aspect, regime = k.split("@")
        if regime not in ("dark", "light"):
            raise ValueError(f"bad key {k!r}")
        piece = loader.load(slug)
        spec = RenderSpec(
            variant, piece.params(variant), aspect, "light" if regime == "light" else "dark"
        )
        out[k] = sample_sha(loader.draw(piece, spec, cache=False), themes.SAMPLE[spec.regime])
    print(json.dumps(out))
    return 0
