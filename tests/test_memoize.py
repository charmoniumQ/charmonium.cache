from __future__ import annotations

import pickle
import tempfile
from pathlib import Path
from typing import Any

import fasteners
import pytest

# import from __init__ because this is an integration test.
from charmonium.cache import (
    DEFAULT_MEMOIZED_GROUP,
    DirObjStore,
    FileRWLock,
    MemoizedGroup,
    NaiveRWLock,
    memoize,
)

calls: list[int] = []


@memoize(verbose=False)
def square(x: int) -> int:
    # I don't want `calls` to be in the closure.
    globals()["calls"].append(x)
    return x ** 2

def test_memoize() -> None:
    # TODO: make this easier
    with tempfile.TemporaryDirectory() as path:
        DEFAULT_MEMOIZED_GROUP.fulfill(
            MemoizedGroup(
                obj_store=DirObjStore(path),
            )
        )
        assert [square(2), square(3), square(2)] == [4, 9, 4]
        assert calls == [2, 3]
        square.log_usage_report()
        str(square)

calls2: list[int] = []

i = 0

@memoize(verbose=False, use_obj_store=False, use_metadata_size=True)
def square_impure_closure(x: int) -> int:
    # I don't want `calls` to be in the closure.
    globals()["calls2"].append(x)
    return x ** 2 + i


def test_memoize_impure_closure() -> None:
    with tempfile.TemporaryDirectory() as path:
        DEFAULT_MEMOIZED_GROUP.fulfill(
            MemoizedGroup(
                obj_store=DirObjStore(path),
            )
        )
        assert square_impure_closure(2) == 4
        global i
        i = 1
        assert square_impure_closure(2) == 5, "when closure updates, function should recompute"

used_dumps: bool = False
used_loads: bool = False

class _LoudPickle:

    def dumps(self, obj: Any) -> bytes:
        globals()["used_dumps"] = True
        return pickle.dumps(obj)

    def loads(self, buffer: bytes) -> Any:
        globals()["used_loads"] = True
        return pickle.loads(buffer)

loud_pickle = _LoudPickle()


@memoize(verbose=False, pickler=loud_pickle)
def square_loud_pickle(x: int) -> int:
    return x ** 2


@pytest.mark.parametrize("lock_type", ["naive", "file"])
def test_memoize_fine_grain_persistence(lock_type: str) -> None:
    with tempfile.TemporaryDirectory() as path_:
        path = Path(path_)
        DEFAULT_MEMOIZED_GROUP.fulfill(
            MemoizedGroup(
                obj_store=DirObjStore(path),
                fine_grain_persistence=True,
                lock=(
                    NaiveRWLock(fasteners.InterProcessLock(path / "lock")) if lock_type == "naive" else FileRWLock(path / "lock")
                )
            )
        )

        global used_dumps, used_loads
        used_dumps = False
        square_loud_pickle(2)
        assert used_dumps

        used_loads = False
        square_loud_pickle(2)
        assert used_loads

        assert square_loud_pickle.would_hit(2)


@memoize(name="cool_name", verbose=False)
def big_fn(x: int) -> bytes:
    return b'\0' * x

@pytest.mark.xfail
def test_eviction() -> None:
    with tempfile.TemporaryDirectory() as path:
        DEFAULT_MEMOIZED_GROUP.fulfill(
            MemoizedGroup(
                obj_store=DirObjStore(path),
                fine_grain_eviction=True,
                size="500B",
            )
        )
        big_fn(2)
        big_fn(3)
        big_fn(1000)
        assert not big_fn.would_hit(1000)
        assert big_fn.would_hit(2)
        assert big_fn.would_hit(3)

@memoize(lossy_compression=False)
def square_loud(x: int) -> int:
    return x**2

def test_verbose(caplog: pytest.Caplog) -> None:
    with tempfile.TemporaryDirectory() as path:
        DEFAULT_MEMOIZED_GROUP.fulfill(
            MemoizedGroup(
                obj_store=DirObjStore(path),
            )
        )
    square_loud(2)
    assert "miss" in caplog.text
    square_loud(2)
    assert "hit" in caplog.text

    square_loud.disable_logging()

    with pytest.warns(UserWarning):
        @memoize(use_metadata_size=False, use_obj_store=False)
        def foo() -> None: # type: ignore
            pass

# Test multiprocessing
