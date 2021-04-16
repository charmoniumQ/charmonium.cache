import itertools
import tempfile
from typing import Callable

import pytest

from charmonium.cache.util import KeyGen, PathLike, PathLike_from, Future, GetAttr, Constant


def test_key_gen() -> None:
    n_samples = 10
    key_gen = KeyGen()
    assert len(set(itertools.islice(key_gen, n_samples))) == n_samples
    assert key_gen.probability_of_collision(n_samples) < 1e-9

def test_pathlike() -> None:
    # primarily test the type signature
    payload = b"abc"
    with tempfile.TemporaryDirectory() as path_:
        path: PathLike = PathLike_from(PathLike_from(path_))
        path2: PathLike = path / "test"
        path2.write_bytes(payload)
        (path / "test").read_bytes() == payload

    with pytest.raises(TypeError):
        PathLike_from(3)

def test_future() -> None:
    future_int = Future[int]()

    assert not future_int.computed
    with pytest.raises(ValueError):
        future_int.unwrap()

    future_int.fulfill(3)

    assert future_int.computed
    assert future_int.unwrap() == 3 == future_int._
    with pytest.raises(ValueError):
        future_int.fulfill(4)

def test_getattr() -> None:

    class Class:

        attr1 = 11423

        def method1(self) -> int:
            return 2123

    obj = Class()
    assert GetAttr[int]()(obj, "attr1", 1, check_callable=False) == obj.attr1
    assert GetAttr[int]()(obj, "attr2", 2, check_callable=False) == 2
    
    with pytest.raises(AttributeError):
        GetAttr[int]()(obj, "attr2", check_callable=False)

    assert GetAttr[Callable[[], int]]()(obj, "method1")() == obj.method1()

    with pytest.raises(TypeError):
        GetAttr[Callable[[], int]]()(obj, "attr1")

def test_constant() -> None:
    c: Callable[[int, float], int] = Constant(3)
    assert c(4, 5.6) == 3
