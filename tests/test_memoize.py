import tempfile

from charmonium.cache import memoize
# TODO: export in __init__
from charmonium.cache.core import MemoizedGroup, DEFAULT_MEMOIZED_GROUP
from charmonium.cache.obj_store import DirObjStore

calls: list[int] = []
@memoize()
def square(x: int):
    globals()["calls"].append(x)
    return x**2

def test_memoize() -> None:
    with tempfile.TemporaryDirectory() as path:
        DEFAULT_MEMOIZED_GROUP.fulfill(
            MemoizedGroup(  # type: ignore (pyright doesn't know about attrs __init__)
                obj_store=DirObjStore(path),  # type: ignore (pyright doesn't know about attrs __init__)
            )
        )
        assert [square(2), square(3), square(2)] == [4, 9, 4]
        assert calls == [2, 3]
