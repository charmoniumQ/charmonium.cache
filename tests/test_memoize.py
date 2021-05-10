from __future__ import annotations

import pickle
from typing import Any

import pytest

from charmonium.cache import DirObjStore, MemoizedGroup, memoize
from charmonium.cache.util import temp_path

# import from __init__ because this is an integration test.

calls: list[int] = []


@pytest.mark.parametrize(
    "kwargs,group_kwargs",
    [
        ({"name": "test"}, {}),
        ({"lossy_compression": False}, {}),
        ({"use_metadata_size": True}, {}),
        ({"use_metadata_size": True, "use_obj_store": False}, {}),
        ({"pickler": pickle}, {}),
        ({"verbose": False}, {}),
        ({"extra_func_state": lambda func: 3}, {}),  # type: ignore
        ({}, {"size": 1000},),
        ({}, {"size": "10KiB"},),
        ({}, {"size": "10KiB"},),
        ({}, {"pickler": pickle}),
        ({}, {"fine_grain_persistence": True}),
        ({}, {"fine_grain_eviction": True}),
        ({}, {"extra_system_state": lambda: 3}),  # type: ignore
        ({}, {"temporary": False}),
    ],
)
def test_memoize(kwargs: dict[str, Any], group_kwargs: dict[str, Any]) -> None:
    calls.clear()
    kwargs["verbose"] = kwargs.get("verbose", False)
    group_kwargs["temporary"] = group_kwargs.get("temporary", True)

    @memoize(
        **kwargs,
        group=MemoizedGroup(obj_store=DirObjStore(temp_path()), **group_kwargs),
    )
    def square(x: int) -> int:
        # I don't want `calls` to be in the closure.
        globals()["calls"].append(x)
        return x ** 2

    assert [square(2), square(3), square(2)] == [4, 9, 4]
    assert calls == [2, 3]
    square.log_usage_report()
    str(square)


i = 0


def test_memoize_impure_closure() -> None:
    @memoize(
        verbose=False,
        group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),
    )
    def square(x: int) -> int:
        return x ** 2 + i

    assert square(2) == 4
    global i
    i = 1
    assert square(2) == 5, "when closure updates, function should recompute"


@pytest.mark.parametrize("use_obj_store", [True, False])
def test_eviction(use_obj_store: bool) -> None:
    @memoize(
        verbose=False,
        use_obj_store=use_obj_store,
        use_metadata_size=not use_obj_store,
        group=MemoizedGroup(
            obj_store=DirObjStore(temp_path()),
            fine_grain_eviction=True,
            size="1024B",
            temporary=True,
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
    assert not (big_fn.would_hit(510) and big_fn.would_hit(511))
    assert big_fn.would_hit(2)
    assert big_fn.would_hit(3)


def test_verbose(caplog: pytest.Caplog) -> None:
    @memoize(group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True))
    def square_loud(x: int) -> int:
        return x ** 2

    square_loud(2)
    assert "miss" in caplog.text
    square_loud(2)
    assert "hit" in caplog.text

    square_loud.disable_logging()

    with pytest.warns(UserWarning):

        @memoize(group=square_loud.group, use_metadata_size=False, use_obj_store=False)
        def foo() -> None:  # type: ignore
            pass

def test_composition() -> None:
    @memoize(
        verbose=False,
        group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),
    )
    def double(x: int) -> int:
        return x*2
    @memoize(
        verbose=False,
        group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),
    )
    def double_square(x: int) -> int:
        return double(x)**2

    double_square(3)
    assert double_square.would_hit(3)

def test_read_write_cycle() -> None:
    @memoize(
        verbose=False,
        group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),
    )
    def double(x: int) -> int:
        return x*2

    # This simulates call, write, get overwritten by different copy from a peer, read, call.

    double(2)

    # This will be the different copy.
    double.group._version += 1
    double.group._index_write()
    double.group._version -= 1

    # Call
    double(3)

    # Read
    double.group._index_read()

    # Call
    assert double.would_hit(2)
    assert double(2) == 4
    assert double.would_hit(3)
    assert double(3) == 6
    assert len(list(double.group._obj_store)) == 3
