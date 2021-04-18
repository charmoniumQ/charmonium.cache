from typing import Any
from charmonium.cache.persistent_hash import persistent_hash

class Baz:
    def __persistent_hash__(self) -> Any:
        return 3.1

class Bar:
    _x = 2
    _y = "hello world"
    _z = Baz()

class Foo:
    _val = Bar()

foo = Foo()

def test_persistent_hash() -> None:
    # print(persistent_hash(foo))
    assert persistent_hash(foo) == 904017879
