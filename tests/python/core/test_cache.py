import importlib.util
import itertools
import random
import textwrap

import numpy as np
import pytest

from walldye import Vec, _cache
from walldye._noise import Noise

_names = itertools.count()

HEAD = """\
import numpy as np

from walldye import cached

CALLS = []
SCALE = 2.0
UNUSED = 1


def helper(x):
    return x * SCALE

"""


@pytest.fixture(autouse=True)
def fresh_cache():
    _cache.clear_memory()
    _cache.use_disk(None)
    yield
    _cache.clear_memory()
    _cache.use_disk(None)


def module(tmp_path, body: str, head: str = HEAD):
    """A fresh import of HEAD plus `body`, written to its own file."""
    path = tmp_path / f"mod{next(_names)}.py"
    path.write_text(head + textwrap.dedent(body))
    spec = importlib.util.spec_from_file_location(f"_cache_test_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SIM = """
@cached
def sim(rng, n, k=1.0):
    CALLS.append(n)
    return helper(rng.random(n)) * k
"""


def test_a_hit_skips_the_work_and_leaves_the_generator_where_a_call_would(tmp_path):
    m = module(tmp_path, SIM)
    g1, g2 = np.random.default_rng(5), np.random.default_rng(5)
    a = m.sim(g1, 4)
    b = m.sim(g2, 4)
    assert m.CALLS == [4]
    assert np.array_equal(a, b)
    assert g1.random() == g2.random()


def test_arguments_and_generator_state_key_the_result(tmp_path):
    m = module(tmp_path, SIM)
    g = np.random.default_rng(5)
    m.sim(g, 4)
    m.sim(g, 4)  # the generator has moved on
    m.sim(np.random.default_rng(5), 4, k=2.0)
    m.sim(np.random.default_rng(5), 5)
    assert m.CALLS == [4, 4, 4, 5]


def test_a_hit_returns_a_copy(tmp_path):
    m = module(tmp_path, SIM)
    a = m.sim(np.random.default_rng(1), 3)
    a[:] = 0
    assert m.sim(np.random.default_rng(1), 3).any()


def test_array_arguments_are_read_only(tmp_path):
    m = module(
        tmp_path,
        """
        @cached
        def scrub(a):
            a[0] = 0
            return a
        """,
    )
    with pytest.raises(ValueError, match="read-only"):
        m.scrub(np.ones(3))


def test_the_key_follows_what_the_function_reaches(tmp_path):
    def digest(head: str) -> str:
        return _cache._code_digest(module(tmp_path, SIM, head).sim.__wrapped__)

    base = digest(HEAD)
    assert digest(HEAD.replace("UNUSED = 1", "UNUSED = 2")) == base
    assert digest(HEAD.replace("SCALE = 2.0", "SCALE = 3.0")) != base
    assert digest(HEAD.replace("x * SCALE", "x * SCALE + 0")) != base


@pytest.mark.parametrize(
    "value",
    [
        None,
        (1, 2.5, "x", True),
        [Vec(1, 2), {"k": [np.float32(1.5)]}],
        {"a": np.arange(6).reshape(2, 3), "b": b"\x00\x01"},
        np.int64(7),
    ],
    ids=repr,
)
def test_results_round_trip(value):
    got = _cache._unpack(_cache._pack(value))
    assert type(got) is type(value)
    assert repr(got) == repr(value)


def test_python_and_noise_arguments(tmp_path):
    m = module(
        tmp_path,
        """
        @cached
        def mixed(r, noise):
            CALLS.append(1)
            return r.random() + noise(0.5, 0.5)
        """,
    )
    r1, r2 = random.Random(3), random.Random(3)
    assert m.mixed(r1, Noise(2)) == m.mixed(r2, Noise(2))
    assert r1.random() == r2.random()
    m.mixed(random.Random(3), Noise(4))
    assert m.CALLS == [1, 1]


def test_unsupported_types(tmp_path):
    m = module(
        tmp_path,
        """
        @cached
        def echo(x):
            return x


        @cached
        def as_set(n):
            return {n}
        """,
    )
    with pytest.raises(TypeError, match="cannot key"):
        m.echo(object())
    with pytest.raises(TypeError, match="cannot return a set"):
        m.as_set(2)
    with pytest.raises(TypeError, match="module-level def"):
        module(
            tmp_path,
            """
            def outer():
                @cached
                def inner():
                    return 1
                return inner
            outer()
            """,
        )


def test_disk_keeps_results_across_processes(tmp_path):
    m = module(tmp_path, SIM)
    _cache.use_disk(tmp_path / "cache", lambda: "toolchain-a")
    a = m.sim(np.random.default_rng(1), 3)
    _cache.clear_memory()
    g = np.random.default_rng(1)
    assert np.array_equal(m.sim(g, 3), a)
    assert g.random() == np.random.default_rng(1).random(4)[3]
    assert m.CALLS == [3]
    _cache.clear_memory()
    _cache.use_disk(tmp_path / "cache", lambda: "toolchain-b")
    m.sim(np.random.default_rng(1), 3)
    assert m.CALLS == [3, 3]


def test_a_damaged_file_is_a_miss(tmp_path):
    m = module(tmp_path, SIM)
    _cache.use_disk(tmp_path / "cache")
    m.sim(np.random.default_rng(1), 3)
    (path,) = (tmp_path / "cache").glob("*/*.npz")
    path.write_bytes(b"not a zip")
    _cache.clear_memory()
    m.sim(np.random.default_rng(1), 3)
    assert m.CALLS == [3, 3]
    assert path.read_bytes() != b"not a zip"


def test_disk_prunes_the_least_recently_used(tmp_path, monkeypatch):
    monkeypatch.setattr(_cache, "DISK_BYTES", 3000)
    m = module(tmp_path, SIM)
    _cache.use_disk(tmp_path / "cache")
    for n in (100, 101, 102, 103):  # 800 bytes of float64 each
        m.sim(np.random.default_rng(1), n)
    sizes = [p.stat().st_size for p in (tmp_path / "cache").glob("*/*.npz")]
    assert 0 < sum(sizes) <= 3000 * 3 // 4 + max(sizes)


def test_memory_stays_under_its_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(_cache, "MEMORY_BYTES", 2500)  # two entries with their states
    m = module(tmp_path, SIM)
    for n in (100, 101, 102):
        m.sim(np.random.default_rng(1), n)
    assert len(_cache._MEMORY) == 2
    m.sim(np.random.default_rng(1), 100)
    assert m.CALLS == [100, 101, 102, 100]
