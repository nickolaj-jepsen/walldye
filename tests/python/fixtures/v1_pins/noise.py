"""Pin v1's Noise outputs to noise.json, for the v2 comparison in tests/python/core/.

v1 is loaded from `git show ad9da3d:walldye/__init__.py` as a throwaway submodule of walldye,
so its relative imports resolve to walldye._theme, whose behaviour v2 kept. Rerun only to add cases:
`uv run python tests/python/fixtures/v1_pins/noise.py`.
"""

import importlib.util
import json
import random
import subprocess
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[3]
SEEDS = (0, 5, 42, 1234, "11:5")


def v1() -> types.ModuleType:
    """The v1 walldye module at commit ad9da3d."""
    src = subprocess.run(
        ["git", "show", "ad9da3d:walldye/__init__.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "v1.py"
        path.write_text(src)
        # A submodule name, so v1's relative imports resolve inside the walldye package.
        spec = importlib.util.spec_from_file_location("walldye._v1_pin", path)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def cases() -> list[tuple[float, float, float]]:
    """Sample points: random ones, lattice points, negatives and a far one."""
    r = random.Random(2026)
    pts = [(r.uniform(-300, 300), r.uniform(-300, 300), r.uniform(-40, 40)) for _ in range(60)]
    return [*pts, (0.0, 0.0, 0.0), (1.0, -1.0, 2.0), (255.5, 256.0, -0.5), (1e6 + 0.3, -7.25, 3.5)]


def main() -> None:
    mod = v1()
    out = []
    for seed in SEEDS:
        n = mod.Noise(seed)
        out.append(
            {
                "seed": seed,
                "points": [
                    {
                        "xyz": [x, y, z],
                        "n2": n(x, y),
                        "n3": n.n3(x, y, z),
                        "fbm": n.fbm(x / 50, y / 50),
                        "fbm_3_2.5_0.4": n.fbm(x / 50, y / 50, 3, 2.5, 0.4),
                    }
                    for x, y, z in cases()
                ],
            }
        )
    (HERE / "noise.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
