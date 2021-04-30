from __future__ import annotations

import multiprocessing
import pickle
import tempfile
from pathlib import Path
from typing import Any

import fasteners
import pytest

# import from __init__ because this is an integration test.
from charmonium.cache import (
    DirObjStore,
    FileRWLock,
    MemoizedGroup,
    NaiveRWLock,
    memoize,
)

calls: list[int] = []

used_dumps: bool = False
used_loads: bool = False


class _LoudPickle:
    def dumps(self, obj: Any) -> bytes:
        globals()["used_dumps"] = True
        return pickle.dumps(obj)

    def loads(self, buffer: bytes) -> Any:
        globals()["used_loads"] = True
        return pickle.loads(buffer)

    def __persistent_hash__(self) -> Any:
        return "_LoudPickle"


loud_pickle = _LoudPickle()


i = 0


@memoize(verbose=False, pickler=loud_pickle)
def square(x: int) -> int:
    # I don't want `calls` to be in the closure.
    globals()["calls"].append(x)
    return x ** 2 + i


def test_memoize() -> None:
    with tempfile.TemporaryDirectory() as path:
        square.group = MemoizedGroup(obj_store=DirObjStore(path))
        assert [square(2), square(3), square(2)] == [4, 9, 4]
        assert calls == [2, 3]
        square.log_usage_report()
        str(square)


def test_memoize_impure_closure() -> None:
    with tempfile.TemporaryDirectory() as path:
        square.group = MemoizedGroup(obj_store=DirObjStore(path))
        assert square(2) == 4
        global i
        i = 1
        assert square(2) == 5, "when closure updates, function should recompute"


@pytest.mark.parametrize("lock_type", ["naive", "file"])
def test_memoize_fine_grain_persistence(lock_type: str) -> None:
    with tempfile.TemporaryDirectory() as path_:
        path = Path(path_)
        square.group = MemoizedGroup(
            obj_store=DirObjStore(path),
            fine_grain_persistence=True,
            lock=(
                NaiveRWLock(fasteners.InterProcessLock(path / "lock"))
                if lock_type == "naive"
                else FileRWLock(path / "lock")
            ),
        )

        global used_dumps, used_loads
        used_dumps = False
        square(2)
        assert used_dumps

        used_loads = False
        square(2)
        assert used_loads

        assert square.would_hit(2)


@pytest.mark.parametrize("use_obj_store", [True, False])
def test_eviction(use_obj_store: bool) -> None:
    with tempfile.TemporaryDirectory() as path:

        @memoize(
            name="cool_name",
            verbose=False,
            use_obj_store=use_obj_store,
            use_metadata_size=not use_obj_store,
            lossy_compression=True,
            group=MemoizedGroup(
                obj_store=DirObjStore(path), fine_grain_eviction=True, size="1024B",
            ),
        )
        def big_fn(x: int) -> bytes:
            return b"\0" * x

        big_fn(2)
        big_fn(3)
        big_fn(510)
        big_fn(2)
        big_fn(3)
        big_fn(511)
        assert not big_fn.would_hit(502)
        assert big_fn.would_hit(2)
        assert big_fn.would_hit(3)


@memoize()
def square_loud(x: int) -> int:
    return x ** 2


def test_verbose(caplog: pytest.Caplog) -> None:
    with tempfile.TemporaryDirectory() as path:
        square_loud.group = MemoizedGroup(obj_store=DirObjStore(path),)
    square_loud(2)
    assert "miss" in caplog.text
    square_loud(2)
    assert "hit" in caplog.text

    square_loud.disable_logging()

    with pytest.warns(UserWarning):

        @memoize(use_metadata_size=False, use_obj_store=False)
        def foo() -> None:  # type: ignore
            pass


def square_all(lst: list[int]) -> tuple[list[int], list[int]]:
    calls.clear()
    ret: list[int] = []
    for elem in lst:
        ret.append(square(elem))
    return ret, calls


def test_multiprocessing() -> None:
    with tempfile.TemporaryDirectory() as path:
        square_loud.group = MemoizedGroup(
            obj_store=DirObjStore(path), fine_grain_persistence=True,
        )
        n_procs = 5
        procs = [
            multiprocessing.Process(target=square_all, args=([0, x, x + n_procs],))
            for x in range(n_procs)
        ]
        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join()
