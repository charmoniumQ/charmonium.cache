import pytest

from charmonium.cache.index import Index, IndexKeyType
from charmonium.cache.util import Constant

def test_index() -> None:
    index = Index[int, str]((
        IndexKeyType.MATCH,
        IndexKeyType.LOOKUP,
        IndexKeyType.MATCH,
    ))
    index[(1, 2, 3)] = "hello"
    assert set(index.items()) == {((1, 2, 3), "hello")}

    index[(1, 2, 3)] = "hello2"
    assert set(index.items()) == {((1, 2, 3), "hello2")}, "A different match var should overwrite the old entry"

    index[(1, 3, 2)] = "hello3"
    assert set(index.items()) == {((1, 2, 3), "hello2"), ((1, 3, 2), "hello3")}, "A different lookup var should be a new entry"

    index[(0, 3, 4)] = "hello4"
    assert set(index.items()) == {((0, 3, 4), "hello4")}, "A different match var should invalidate children"

    del index[(0, 3, 4)]
    assert set(index.items()) == set(), "__delitem__ works"

    assert index.get_or((0, 3, 4), Constant("hello3")) == "hello3", "Key not found; call the thunk"
    assert index.get_or((0, 3, 4), Constant("hello4")) == "hello3", "Key found; don't call the thunk"
    assert set(index.items()) == {((0, 3, 4), "hello3")}

    with pytest.raises(ValueError):
        index[(1, 2)] = "hello5"

    index = Index[int, str]((
        IndexKeyType.LOOKUP,
        IndexKeyType.MATCH,
        IndexKeyType.LOOKUP,
    ))
    index[(1, 2, 3)] = "hello"
    assert set(index.items()) == {((1, 2, 3), "hello")}

    index[(1, 2, 4)] = "hello2"
    assert set(index.items()) == {((1, 2, 3), "hello"), ((1, 2, 4), "hello2")}

    # index.write()

    # index = Index()
    # index.set_schema((
    #     IndexKeyType.MATCH,
    #     IndexKeyType.LOOKUP,
    #     IndexKeyType.MATCH,
    # ))
    # index[(1, 2, 3)] = "hello5"
    # index.read()

    # assert set(index.items()) == {((1, 2, 3), "hello5"), ((1, 3, 3), "hello2")}


    # with index.read_modify_write():
    #     pass
