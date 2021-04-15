import itertools
import tempfile
import threading
from typing import cast

from charmonium.cache.util import KeyGen, PathLike, PathLike_from, Future
from charmonium.cache.readers_writer_lock import NaiveReadersWriterLock


def test_key_gen() -> None:
    n_samples = 10
    key_gen = KeyGen()
    assert len(set(itertools.islice(key_gen, n_samples))) == n_samples
    assert key_gen.probability_of_collision(n_samples) < 1e-9


def test_pathlike() -> None:
    # primarily test the type signature
    payload = b"abc"
    with tempfile.TemporaryDirectory() as path_:
        path: PathLike = PathLike_from(path_)
        path2: PathLike = path / "test"
        path2.write_bytes(payload)
        (path / "test").read_bytes() == payload


def test_future() -> None:
    future_int: int = Future[int].create()

    assert cast(Future[int], future_int).computed

    cast(Future[int], future_int).fulfill(3)

    assert str(future_int) == "3"
    assert cast(Future[int], future_int).computed

def test_lock() -> None:
    lock = NaiveReadersWriterLock(threading.Lock())
