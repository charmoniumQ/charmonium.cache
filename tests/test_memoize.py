from __future__ import annotations

import logging
import pickle
from typing import Any
import copy
import logging

import pytest

from charmonium.cache import DEFAULT_FREEZE_CONFIG, DirObjStore, MemoizedGroup, memoize
from charmonium.cache.util import temp_path

# import from __init__ because this is an integration test.

calls: list[int] = []

logging.getLogger("charmonium.cache.perf").setLevel(logging.DEBUG)
logging.getLogger("charmonium.cache.ops").setLevel(logging.DEBUG)


@pytest.mark.parametrize(
    "kwargs,group_kwargs",
    [
        ({"name": "test"}, {}),
        ({"use_metadata_size": True}, {}),
        ({"use_metadata_size": True, "use_obj_store": False}, {}),
        ({"pickler": pickle}, {}),
        ({"extra_func_state": lambda func: 3}, {}),
        (
            {},
            {"size": 1000},
        ),
        (
            {},
            {"size": "10KiB"},
        ),
        ({}, {"pickler": pickle}),
        ({}, {"fine_grain_persistence": True}),
        ({}, {"fine_grain_eviction": True}),
        ({}, {"extra_system_state": lambda: 3}),
        ({}, {"temporary": False}),
    ],
)
def test_memoize(kwargs: dict[str, Any], group_kwargs: dict[str, Any]) -> None:
    calls.clear()
    group_kwargs["temporary"] = group_kwargs.get("temporary", True)

    @memoize(
        **kwargs,
        group=MemoizedGroup(obj_store=DirObjStore(temp_path()), **group_kwargs),
    )
    def square(x: int) -> int:
        # I don't want `calls` to be in the closure.
        globals()["calls"].append(x)
        return x**2

    assert [square(2), square(3), square(2)] == [4, 9, 4]
    assert calls == [2, 3]
    square.log_usage_report()
    str(square)


def test_memoize_impure_closure() -> None:
    i = 0

    @memoize(
        group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),
    )
    def square(x: int) -> int:
        return x**2 + i

    assert square(2) == 4
    i = 1
    assert square(2) == 5, "when closure updates, function should recompute"


@pytest.mark.parametrize("use_obj_store", [True, False])
def test_eviction(use_obj_store: bool) -> None:
    @memoize(
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


def test_verbose(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, "charmonium.cache.ops")

    @memoize(group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True))
    def square_loud(x: int) -> int:
        return x**2

    square_loud(2)
    assert "miss" in caplog.text
    square_loud(2)
    assert "hit" in caplog.text

    with pytest.warns(UserWarning):

        # `not use_obj_store and not use_metadata_size` should trigger warning.
        @memoize(group=square_loud.group, use_metadata_size=False, use_obj_store=False)
        def foo() -> None:
            pass


def test_composition(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="charmonium.freeze")
    freeze_config = copy.deepcopy(DEFAULT_FREEZE_CONFIG)
    freeze_config.recursion_limit = 15

    @memoize(
        group=MemoizedGroup(obj_store=DirObjStore(temp_path()), freeze_config=freeze_config, temporary=True),
    )
    def double(x: int) -> int:
        return x * 2

    @memoize(
        group=MemoizedGroup(obj_store=DirObjStore(temp_path()), freeze_config=freeze_config, temporary=True),
    )
    def double_square(x: int) -> int:
        return double(x) ** 2

    double_square(3)
    assert double_square.would_hit(3)


def test_read_write_cycle() -> None:
    @memoize(
        group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),
    )
    def double(x: int) -> int:
        return x * 2

    # This simulates call, write, get overwritten by different copy from a peer, read, call.

    double(2)

    # This will be the different copy.
    double.group._version += 1
    double.group._index_write(0)  # pylint: disable=protected-access
    double.group._version -= 1

    # Call
    double(3)

    # Read
    double.group._index_read(0)  # pylint: disable=protected-access

    # Call
    assert double.would_hit(2)
    assert double(2) == 4
    assert double.would_hit(3)
    assert double(3) == 6
