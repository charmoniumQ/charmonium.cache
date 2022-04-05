from __future__ import annotations

import atexit
import itertools
import multiprocessing
import os
import random
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Type, TypeVar

import cloudpickle
import dask  # type: ignore
import dask.bag  # type: ignore
import pytest

from charmonium.cache import DirObjStore, MemoizedGroup, memoize
from charmonium.cache.util import temp_path

if TYPE_CHECKING:
    from typing import Protocol

else:
    Protocol = object

# TODO: rewrite without tmp_root
tmp_root = (
    Path(tempfile.gettempdir())
    / "test_memoize_parallel"
    / str(random.randint(0, 10000) ^ os.getpid())
)
atexit.register(
    lambda: shutil.rmtree(tmp_root.parent) if tmp_root.parent.exists() else None
)


class Parallel(Protocol):
    def __init__(self, target: Callable[..., Any], args: tuple[Any, ...] = ()) -> None:
        ...

    def start(self) -> None:
        ...

    def join(self) -> None:
        ...


T = TypeVar("T")


def cyclic_permutation(iterable: Iterable[T], offset: int) -> Iterable[T]:
    it = iter(iterable)
    start = list(itertools.islice(it, offset))
    yield from it
    yield from start


def make_overlapping_calls(
    workers: int, overlap: int
) -> tuple[tuple[tuple[int, ...], ...], set[int]]:
    start = random.randint(0, 100000)
    unique_calls = list(range(start, start + n_procs))
    return (
        tuple(zip(*(cyclic_permutation(unique_calls, i) for i in range(overlap)))),
        set(unique_calls),
    )


n_procs = 5
overlap = 4


@memoize(
    use_obj_store=False,
    use_metadata_size=True,
)
def square(x: int) -> int:
    (tmp_root / str(random.randint(0, 10000))).write_text(str(x))
    return x**2


def square_all(lst: list[int]) -> list[int]:
    return list(map(square, lst))


@pytest.mark.parametrize("ParallelType", [multiprocessing.Process, threading.Thread])
def test_parallelism(ParallelType: Type[Parallel]) -> None:
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)

    square.group = MemoizedGroup(
        obj_store=DirObjStore(temp_path()), fine_grain_persistence=True, temporary=True
    )

    calls, unique_calls = make_overlapping_calls(n_procs, overlap)
    procs = [
        ParallelType(
            target=square_all,
            args=(call,),
        )
        for call in calls
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()
    recomputed = [int(log.read_text()) for log in tmp_root.iterdir()]
    # Note that two parallel workers *can* sometimes compute redundant function values because they don't know that the other is in progress.
    # However, it would be improbable that *every* worker *always* is computing redundant values.
    assert len(recomputed) < overlap * n_procs
    assert set(recomputed) == unique_calls
    assert all(square.would_hit(x) for x in unique_calls)


def test_cloudpickle() -> None:
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)
    # I need to make Memoize compatible with cloudpickle so that it can be parallelized with dask.
    global square
    square.group = MemoizedGroup(
        obj_store=DirObjStore(temp_path()), fine_grain_persistence=True, temporary=True
    )
    square(2)
    square2 = cloudpickle.loads(cloudpickle.dumps(square))
    assert square2.would_hit(2)


def test_dask_bag() -> None:
    square.group = MemoizedGroup(
        obj_store=DirObjStore(temp_path()), fine_grain_persistence=True, temporary=True
    )
    calls, unique_calls = make_overlapping_calls(n_procs, overlap)
    dask.bag.from_sequence(itertools.chain.from_iterable(calls), npartitions=n_procs).map(square).compute()  # type: ignore
    recomputed = [int(log.read_text()) for log in tmp_root.iterdir()]
    assert len(recomputed) < overlap * n_procs
    assert set(recomputed) == unique_calls
    subprocess.run(["sync", "--file-system", "."], check=True)
    calls_would_hit = [square.would_hit(x) for x in unique_calls]
    assert all(calls_would_hit)


def test_dask_delayed() -> None:
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)
    square.group = MemoizedGroup(
        obj_store=DirObjStore(temp_path()), fine_grain_persistence=True, temporary=True
    )
    calls, unique_calls = make_overlapping_calls(n_procs, overlap)
    square2 = dask.delayed(square)  # type: ignore
    results = dask.compute(*[square2(x) for call in calls for x in call])  # type: ignore
    recomputed = [int(log.read_text()) for log in tmp_root.iterdir()]
    assert len(recomputed) < overlap * n_procs
    assert set(recomputed) == unique_calls
    assert all(square.would_hit(x) for x in unique_calls)
