import itertools
import multiprocessing
import random
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol, Type, TypeVar

import cloudpickle
import dask.bag  # type: ignore
import pytest

from charmonium.cache import DirObjStore, MemoizedGroup, memoize
from charmonium.cache.util import temp_path

tmp_root = Path(tempfile.gettempdir()) / "test_memoize_parallel"


@memoize(
    verbose=False,
    use_obj_store=False,
    use_metadata_size=True,
    group=MemoizedGroup(
        obj_store=DirObjStore(temp_path()), fine_grain_persistence=True, temporary=True
    ),
)
def square(x: int) -> int:
    (tmp_root / str(random.randint(0, 10000))).write_text(str(x))
    return x ** 2


def square_all(lst: list[int]) -> list[int]:
    return list(map(square, lst))


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


@pytest.mark.parametrize("ParallelType", [multiprocessing.Process, threading.Thread])
def test_parallelism(ParallelType: Type[Parallel]) -> None:
    n_procs = 5
    start = random.randint(0, 100000)
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir()
    unique_calls = list(range(start, start + n_procs))
    overlap = 4
    callss = zip(*(cyclic_permutation(unique_calls, i) for i in range(overlap)))
    procs = [ParallelType(target=square_all, args=(calls,),) for calls in callss]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()
    recomputed = [int(log.read_text()) for log in tmp_root.iterdir()]
    # Note thattwo parallel workers *can* sometimes compute redundant function values because they don't know that the other is in progress.
    # However, it would be improbable that *every* worker *always* is computing redundant values.
    assert len(recomputed) < overlap * n_procs
    assert set(recomputed) == set(unique_calls)
    assert all(square.would_hit(x) for x in unique_calls)


def test_cloudpickle() -> None:
    # I need to make Memoize compatible with cloudpickle so that it can be parallelized with dask.
    cloudpickle.dumps(square)


def test_dask_bag() -> None:
    n_procs = 5
    start = random.randint(0, 100000)
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir()
    unique_calls = list(range(start, start + n_procs))
    overlap = 4
    calls = itertools.chain.from_iterable(cyclic_permutation(unique_calls, i) for i in range(overlap))
    dask.bag.from_sequence(calls, npartitions=n_procs).map(square).compute()  # type: ignore
    recomputed = [int(log.read_text()) for log in tmp_root.iterdir()]
    # Note thattwo parallel workers *can* sometimes compute redundant function values because they don't know that the other is in progress.
    # However, it would be improbable that *every* worker *always* is computing redundant values.
    assert len(recomputed) < overlap * n_procs
    assert set(recomputed) == set(unique_calls)
    assert all(square.would_hit(x) for x in unique_calls)
