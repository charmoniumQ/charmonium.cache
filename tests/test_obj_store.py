import pytest

from charmonium.cache.obj_store import DirObjStore

def test_obj_store() -> None:
    os = DirObjStore(".cache_tmp")  # type: ignore (pyright doesn't know attrs __init__)

    os[123] = b"123"
    assert os[123] == b"123"

    os[123] = b"987"
    assert os[123] == b"987", "Value was not replaced"

    os[567] = b"567"
    assert os[567] == b"567", "Value for different key was not inserted"

    del os[567]

    assert os[123] == b"987", "Value was not deleted"

    assert os.__size__() > 0, "Size is not right"

    os.clear()

    assert os.__size__() == 0, "clear() or size did not work"

    with pytest.raises(KeyError):
        os[123], "clear() does not work"

    with pytest.raises(ValueError):
        # .cache_tmp is not empty.
        os2 = DirObjStore(".")  # type: ignore (pyright doesn't know attrs __init__)
