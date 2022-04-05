import pytest

from charmonium.cache.index import Index, IndexKeyType
from charmonium.cache.util import Constant


def test_index() -> None:
    index = Index[int, str](
        (
            IndexKeyType.MATCH,
            IndexKeyType.LOOKUP,
            IndexKeyType.MATCH,
        )
    )
    index[(1, 2, 3)] = "hello"
    assert set(index.items()) == {((1, 2, 3), "hello")}

    index[(1, 2, 3)] = "hello2"
    assert set(index.items()) == {
        ((1, 2, 3), "hello2")
    }, "A different match var should overwrite the old entry"

    index[(1, 3, 2)] = "hello3"
    assert set(index.items()) == {
        ((1, 2, 3), "hello2"),
        ((1, 3, 2), "hello3"),
    }, "A different lookup var should be a new entry"

    index[(0, 3, 4)] = "hello4"
    assert set(index.items()) == {
        ((0, 3, 4), "hello4")
    }, "A different match var should invalidate children"


def test_index_del() -> None:
    index = Index[int, str](
        (
            IndexKeyType.MATCH,
            IndexKeyType.LOOKUP,
            IndexKeyType.MATCH,
        )
    )
    index[(0, 2, 4)] = "hello1"
    index[(0, 3, 4)] = "hello2"
    del index[(0, 3, 4)]
    del index[(1, 2, 5)]  # delete non-existent item
    del index[(0, 2, 5)]  # delete non-existent item
    assert set(index.items()) == {((0, 2, 4), "hello1")}, "__delitem__ works"


def test_thunk() -> None:
    index = Index[int, str](
        (
            IndexKeyType.MATCH,
            IndexKeyType.LOOKUP,
            IndexKeyType.MATCH,
        )
    )
    assert (
        index.get_or((0, 3, 4), Constant("hello3")) == "hello3"
    ), "Key not found; call the thunk"
    assert (
        index.get_or((0, 3, 4), Constant("hello4")) == "hello3"
    ), "Key found; don't call the thunk"
    assert set(index.items()) == {((0, 3, 4), "hello3")}


def test_contains() -> None:
    index = Index[int, str](
        (
            IndexKeyType.MATCH,
            IndexKeyType.LOOKUP,
            IndexKeyType.MATCH,
        )
    )
    index[(0, 3, 4)] = "hello2"
    assert (0, 3, 4) in index
    assert (0, 3, 5) not in index


def test_raises_wrong_schema() -> None:
    index = Index[int, str](
        (
            IndexKeyType.MATCH,
            IndexKeyType.LOOKUP,
            IndexKeyType.MATCH,
        )
    )
    with pytest.raises(ValueError):
        index[(1, 2)] = "hello5"

    index2 = Index[int, str]((IndexKeyType.MATCH, IndexKeyType.LOOKUP))
    with pytest.raises(ValueError):
        index.update(index2)


def test_update() -> None:
    old = Index[int, str](
        (
            IndexKeyType.MATCH,
            IndexKeyType.LOOKUP,
            IndexKeyType.MATCH,
        )
    )
    old[(1, 2, 3)] = "old"
    old[(1, 3, 3)] = "old"

    new = Index[int, str](old.schema)
    new[(1, 2, 3)] = "new"
    new[(1, 4, 3)] = "new"

    old.update(new)
    assert old[(1, 2, 3)] == "old", "update() should not overwrite when they conflict"
    assert old[(1, 3, 3)] == "old", "keys not in new are unaffected"
    assert old[(1, 4, 3)] == "new", "keys in new and not in old are brought over to old"
