import datetime
import tempfile
import time
from pathlib import Path

from charmonium.cache import (
    DEFAULT_MEMOIZED_GROUP,
    DirObjStore,
    FileContents,
    MemoizedGroup,
    TTLInterval,
    memoize,
)


@memoize()
def square_file(filename: str) -> int:
    with open(filename) as file:
        return int(file.read().strip())**2

def test_filecontents() -> None:
    with tempfile.TemporaryDirectory() as path_:
        path = Path(path_)
        DEFAULT_MEMOIZED_GROUP.fulfill(
            MemoizedGroup(
                obj_store=DirObjStore(path),
            )
        )

        file1 = path / "file1"
        file2 = path / "file2"

        # test __cache_key__ of non-existent file contents
        FileContents(file1).__cache_key__()

        file1.write_text("3")
        # FileContents is masquerading as a str
        assert square_file(FileContents(file1)) == 9  # type: ignore

        file2.write_text("4")
        assert square_file(FileContents(file2)) == 16  # type: ignore

        assert square_file.would_hit(FileContents(file1))  # type: ignore
        assert square_file.would_hit(FileContents(file2))  # type: ignore
        file1.write_text("5")
        assert not square_file.would_hit(FileContents(file1))  # type: ignore
        assert square_file.would_hit(FileContents(file2))  # type: ignore

        assert square_file(FileContents(file1)) == 25  # type: ignore
        assert square_file(FileContents(str(file1))) == 25  # type: ignore


dt = datetime.timedelta(seconds=0.1)

@memoize(extra_func_state=TTLInterval(dt))
def get_now() -> datetime.datetime:
    return datetime.datetime.now()

def test_ttl() -> None:
    with tempfile.TemporaryDirectory() as path:
        DEFAULT_MEMOIZED_GROUP.fulfill(
            MemoizedGroup(
                obj_store=DirObjStore(path),
            )
        )
        assert datetime.datetime.now() - get_now() < dt
        time.sleep(dt.total_seconds())
        assert datetime.datetime.now() - get_now() < dt
