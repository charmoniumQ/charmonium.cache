from pathlib import Path
import pickle
from typing import Any

from charmonium.cache.persistent_hash import persistent_hash, hashable


a = [1]
a.append(a)

class Baz:
    def __persistent_hash__(self) -> Any:
        return 3.1

foo = dict(
    a=a,
    b=Baz(),
    c=3+1j,
    d=2.0,
    e="hello world",
    f=pickle,
    g=None,
    h=frozenset({3, 4, 5}),
    i=[1, 2, 3],
    j={1, 6, 7},
    k=Path(),
)
expected = 1055205790

def test_persistent_hash() -> None:
    if persistent_hash(foo) != expected:
        print("If you changed how persistent hash works, just copy the next line into `expected`:")
        print(persistent_hash(foo))
    assert persistent_hash(foo) == expected
    hash(hashable(foo))
