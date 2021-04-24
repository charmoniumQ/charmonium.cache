import pickle
from pathlib import Path
from typing import Any

import pytest

from charmonium.cache.determ_hash import hashable, determ_hash

recursive_list: list[Any] = [1]
recursive_list.append(recursive_list)

class Baz:
    def __determ_hash__(self) -> Any:
        return 3.1

class Bar:
    pass

foo: list[Any] = [
    recursive_list,
    Baz(),
    3+1j,
    2.0,
    "hello world",
    pickle,
    None,
    frozenset({3, 4, 5}),
    dict(a=1, b=2, c=dict(a=3)),
    {1, 6, 7},
    Path(),
    -1,
    Bar(),
]
expected = 252824171

def test_persistence() -> None:
    p = determ_hash(hashable(foo))
    assert p == expected, f"If you changed how persistent hash works, just change the `expected` to {p}."
    determ_hash(Baz())


def test_lambda_consts() -> None:
    assert hashable(lambda: 1) == hashable(lambda: 1), "Same function should have the same hash"
    assert hashable(lambda: 1) != hashable(lambda: 2), "Function with different constants should have different hash"

def test_closure() -> None:
    i = 0
    def func():
        return i
    func1 = hashable(func)
    i = 1
    func2 = hashable(func)
    assert func1 != func2, "Changing in closure should change hash"

def test_nonhashable() -> None:
    with pytest.raises(TypeError):
        determ_hash({})
