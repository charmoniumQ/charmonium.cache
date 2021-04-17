import tempfile

import pytest

from charmonium.cache.obj_store import DirObjStore


def test_obj_store() -> None:
    with tempfile.TemporaryDirectory() as path:
        os = DirObjStore(path)  # type: ignore (pyright doesn't know attrs __init__)

        os[123] = b"123"
        assert os[123] == b"123"

        os[123] = b"987"
        assert os[123] == b"987", "Value was not replaced"

        os[567] = b"567"
        assert os[567] == b"567", "Value for different key was not inserted"

        del os[567]

        assert os[123] == b"987", "Value was not deleted"

        os.clear()

        with pytest.raises(KeyError):
            os[123], "clear() does not work"

        with pytest.raises(ValueError):
            os2 = DirObjStore(".")  # type: ignore (pyright doesn't know attrs __init__)
