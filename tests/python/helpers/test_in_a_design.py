import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
from fixtures import toolchain

from walldye._design import Design, RenderSpec
from walldye._params import Params
from walldye.tools.themes import parse_theme

TYPING = Path(__file__).parent / "typing"
USES = TYPING / "uses.py"


def load() -> Design[Params]:
    spec = importlib.util.spec_from_file_location("_walldye_helpers_uses", USES)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert isinstance(mod.draw, Design)
    return mod.draw


def test_helper_calls_type_check_at_the_design_level():
    exe = toolchain.tool("pyrefly")
    assert exe is not None
    cmd = [str(exe), "check", "-c", str(toolchain.DESIGN_PYREFLY), "--output-format", "json"]
    out = subprocess.run([*cmd, str(USES)], capture_output=True, text=True, check=False)
    assert json.loads(out.stdout)["errors"] == []


@pytest.mark.parametrize("aspect", ["16:9", "9:19.5"])
def test_helper_calls_draw_the_same_twice(aspect):
    design = load()
    spec = RenderSpec("default", Params(), aspect, "dark")
    tokens = parse_theme("fireproof")
    first, second = design.draw(spec), design.draw(spec)
    assert first.to_svg(tokens) == second.to_svg(tokens)
    # one grid per pixel path, plus one: the glyphs path spanning both lines records both
    assert len(first.pixel_grids) == first.to_svg(tokens).count('class="px"') + 1
