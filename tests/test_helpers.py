import datetime
import tempfile
import time
from pathlib import Path
from typing import cast

from charmonium.cache import (
    DirObjStore,
    FileContents,
    KeyVer,
    MemoizedGroup,
    TTLInterval,
    memoize,
)


@memoize()
def double(infilename: str) -> str:
    outfilename = infilename + "doubled"
    with open(outfilename, "w") as outfile:
        try:
            with open(infilename, "r") as infile:
                buffer = infile.read()
        except FileNotFoundError:
            buffer = ""
        outfile.write(buffer + " " + buffer)
    return outfilename

def test_filecontents() -> None:
    with tempfile.TemporaryDirectory() as path_:
        path = Path(path_)
        double.group = MemoizedGroup(obj_store=DirObjStore(path))

        file1 = cast(str, FileContents(path / "file1"))

        Path(file1).write_text("hello")

        outfile1 = double(file1)
        assert Path(outfile1).read_text() == "hello hello", "reading and writing are transparent"
        assert double.would_hit(file1), "cache ver is same since file didn't change"

        Path(outfile1).write_text("blah blah")

        outfile1 = double(file1)
        assert Path(outfile1).read_text() == "hello hello", "recall from storage works"

        Path(file1).write_text("world")

        assert not double.would_hit(file1), "cache ver changes since file changed"

def test_filecontents_empty() -> None:
    with tempfile.TemporaryDirectory() as path_:
        path = Path(path_)
        double.group = MemoizedGroup(obj_store=DirObjStore(path))
        file2 = cast(str, FileContents(path / "file2"))
        double(file2)

def test_filecontents_add() -> None:
    file2 = FileContents("abc")
    assert ("123" + file2).__fspath__() == "123abc"
    assert (file2 + "123").__fspath__() == "abc123"

dt = datetime.timedelta(seconds=0.01)

@memoize(extra_func_state=TTLInterval(dt))
def get_now() -> datetime.datetime:
    return datetime.datetime.now()

def test_ttl() -> None:
    with tempfile.TemporaryDirectory() as path:
        get_now.group = MemoizedGroup(obj_store=DirObjStore(path))
        assert datetime.datetime.now() - get_now() < dt
        time.sleep(dt.total_seconds())
        assert datetime.datetime.now() - get_now() < dt

@memoize()
def function(key_ver: KeyVer) -> str:
    return key_ver.key + key_ver.ver

def test_key_ver() -> None:
    with tempfile.TemporaryDirectory() as path:
        function.group = MemoizedGroup(obj_store=DirObjStore(path))
        function(KeyVer(3, 4))
        function(KeyVer(3, 5))
        function(KeyVer(2, 5))
        assert not function.would_hit(KeyVer(3, 4))
        assert function.would_hit(KeyVer(3, 5))
        assert function.would_hit(KeyVer(3, 5))
