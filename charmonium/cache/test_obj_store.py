import pytest

from charmonium.cache.obj_store import DirObjStore

def test_obj_store() -> None:
    os = DirObjStore(".cache_tmp")
    os[123] = b"123"
    os[567] = b"567"
    os[123] = b"987"

    assert os[567] == b"567"
    del os[567]

    assert os[123] == b"987"

    assert os.__size__() > 0

    os.clear()

    assert os.__size__() == 0

    with pytest.raises(KeyError):
        os[123]

    with pytest.raises(ValueError):
        DirObjStore(".")
