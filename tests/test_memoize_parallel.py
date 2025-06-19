from __future__ import annotations

import atexit
import itertools
import multiprocessing
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Type, TypeVar

import cloudpickle  # type: ignore
import dask  # type: ignore
import dask.bag  # type: ignore
import pytest

from charmonium.cache import DirObjStore, MemoizedGroup, memoize
from charmonium.cache.util import temp_path

if TYPE_CHECKING:
    from typing import Protocol
else:
    Protocol = object

random.seed(hash(sys.version))

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
    n_workers: int, n_overlap: int
) -> tuple[tuple[tuple[int, ...], ...], set[int]]:
    start = random.randint(0, 100000)
    unique_calls = list(range(start, start + n_workers))
    return (
        tuple(zip(*(cyclic_permutation(unique_calls, i) for i in range(n_overlap)))),
        set(unique_calls),
    )


@memoize(
    use_obj_store=False,
    use_metadata_size=True,
)
def square(x: int) -> int:
    # pylint: disable=eval-used
    # We use eval to sneak state in here intentionally
    (tmp_root / str(eval("__import__('random').randint(0, 10000)"))).write_text(str(x))
    os.sync()
    return x**2


def square_all(lst: list[int]) -> list[int]:
    return list(map(square, lst))


N_PROCS = 5
N_OVERLAP = 4


@pytest.mark.parametrize("ParallelType", [multiprocessing.Process, threading.Thread])
def test_parallelism(ParallelType: Type[Parallel]) -> None:
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)

    square.group = MemoizedGroup(
        obj_store=DirObjStore(temp_path()), fine_grain_persistence=True, temporary=True
    )

    calls, unique_calls = make_overlapping_calls(N_PROCS, N_OVERLAP)
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
    assert len(recomputed) < N_OVERLAP * N_PROCS
    assert set(recomputed) == unique_calls
    assert all(square.would_hit(x) for x in unique_calls)


def test_cloudpickle() -> None:
    """
    Memoize should be compatible with cloudpickle so that it can be parallelized with dask.
    """
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)
    square.group = MemoizedGroup(
        obj_store=DirObjStore(temp_path()), fine_grain_persistence=True, temporary=True
    )
    square(2)
    square2 = cloudpickle.loads(cloudpickle.dumps(square))
    assert square2.would_hit(2)


def test_dask_delayed() -> None:
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)
    square.group = MemoizedGroup(
        obj_store=DirObjStore(temp_path()), fine_grain_persistence=True, temporary=True
    )
    calls, unique_calls = make_overlapping_calls(N_PROCS, N_OVERLAP)
    square2 = dask.delayed(square, traverse=False)
    results = dask.compute(*[square2(x) for call in calls for x in call])
    recomputed = [int(log.read_text()) for log in tmp_root.iterdir()]
    assert len(recomputed) < N_OVERLAP * N_PROCS
    assert set(recomputed) == unique_calls
    assert all(square.would_hit(x) for x in unique_calls)
    assert results == tuple(x**2 for call in calls for x in call)


def test_dask_bag() -> None:
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)
    square.group = MemoizedGroup(
        obj_store=DirObjStore(temp_path()), fine_grain_persistence=True, temporary=True
    )
    calls, unique_calls = make_overlapping_calls(N_PROCS, N_OVERLAP)
    dask.bag.from_sequence(
        itertools.chain.from_iterable(calls),
        npartitions=N_PROCS,
    ).map(square).compute()
    recomputed = [int(log.read_text()) for log in tmp_root.iterdir()]
    assert len(recomputed) < N_OVERLAP * N_PROCS
    assert set(recomputed) == unique_calls
    subprocess.run(["sync", "--file-system", "."], check=True)
    calls_would_hit = [square.would_hit(x) for x in unique_calls]
    assert all(calls_would_hit)
