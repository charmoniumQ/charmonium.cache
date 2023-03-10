import datetime
import os
import time
from pathlib import Path
from typing import cast

from charmonium.cache import (
    DirObjStore,
    FileContents,
    MemoizedGroup,
    TTLInterval,
    memoize,
)
from charmonium.cache.util import temp_path


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
    path = temp_path()
    double.group = MemoizedGroup(obj_store=DirObjStore(path), temporary=True)

    file1 = cast(str, FileContents(path / "file1"))

    Path(file1).write_text("hello")

    outfile1 = double(file1)
    assert (
        Path(outfile1).read_text() == "hello hello"
    ), "reading and writing are transparent"
    assert double.would_hit(file1), "cache ver is same since file didn't change"

    Path(outfile1).write_text("blah blah")

    outfile1 = double(file1)
    assert Path(outfile1).read_text() == "hello hello", "recall from storage works"

    Path(file1).write_text("world")

    assert not double.would_hit(file1), "cache ver changes since file changed"


def test_filecontents_empty() -> None:
    path = temp_path()
    double.group = MemoizedGroup(obj_store=DirObjStore(path), temporary=True)
    file2 = cast(str, FileContents(path / "file2"))
    double(file2)


def test_filecontents_add() -> None:
    file2 = FileContents("abc")
    assert os.fspath("123" + file2) == "123abc"  # type: ignore
    assert os.fspath(file2 + "123") == "abc123"  # type: ignore


dt = datetime.timedelta(seconds=0.5)


@memoize(extra_func_state=TTLInterval(dt))
def get_now() -> datetime.datetime:
    return datetime.datetime.now()


def test_ttl() -> None:
    get_now.group = MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True)
    assert datetime.datetime.now() - get_now() < dt
    time.sleep(dt.total_seconds())
    assert datetime.datetime.now() - get_now() < dt
