import pickle
import tempfile
import threading
import time
from pathlib import Path
from typing import List

from mypy_extensions import DefaultArg

from charmonium.cache import (
    DirectoryStore,
    FileStore,
    MemoryStore,
    cache_decor,
    make_file_state_fn,
)
from charmonium.cache.util import loop_for_duration, unix_ts_now


def test_cache() -> None:
    with tempfile.TemporaryDirectory() as work_dir_:
        work_dir = Path(work_dir_)
        calls: List[int] = []

        @cache_decor(MemoryStore.create())
        def square1(x: int, a: int = 0) -> int:
            calls.append(x)
            return x ** 2 + a

        @cache_decor(FileStore.create(str(work_dir), serializer=pickle))
        def square2(x: int, a: int = 0) -> int:
            calls.append(x)
            return x ** 2 + a

        @cache_decor(DirectoryStore.create(work_dir / "cache"))
        def square3(x: int, a: int = 0) -> int:
            calls.append(x)
            return x ** 2 + a

        for square in [square1, square2, square3]:
            calls.clear()

            assert square(7) == 49  # miss
            assert square(2) == 4  # miss

            # repeated values should not miss; they will not show up in
            # calls
            assert square(7) == 49
            assert square(2) == 4

            # clearing cache should make next miss
            square.clear()

            # clearing cache should remove the file
            if hasattr(square, "cache_path"):
                assert not getattr(square, "cache_path").exists()

            assert square(7) == 49  # miss
            assert square(2) == 4  # miss

            # adding a kwarg should make a miss
            assert square(7) == 49  # hit
            assert square(7, a=2) == 51  # miss

            # test del explicitly
            # no good way to test it no normal functionality
            del square.obj_store[square.obj_store.args2key((7,), {})]
            assert square(7) == 49

            # test disabling feature
            with square.disabled():
                assert square(2) == 4  # miss
                assert square(2) == 4  # miss, even after regotten

            assert calls == [7, 2, 7, 2, 7, 7, 2, 2]

            # should not throw
            str(square)


def test_multithreaded_cache() -> None:
    calls: List[int] = []

    @cache_decor(MemoryStore.create())
    def square(x: int) -> int:  # pylint: disable=invalid-name
        calls.append(x)
        return x ** 2

    def worker() -> None:
        for _ in loop_for_duration(2):
            seconds = int(unix_ts_now() * 10)
            # everyone will be trying to square the same thing,
            # at the same time
            square(seconds)
            # One thread should lock the others out while it computes
            # and caches the result. There should only be one miss.

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # only one miss per elem, even though multiple simultaneous accesses
    assert len(set(calls)) == len(calls)


def test_files() -> None:
    with tempfile.TemporaryDirectory() as work_dir_:
        work_dir = Path(work_dir_)
        file_path = work_dir / "file1"
        calls: List[Path] = []

        @cache_decor(MemoryStore.create(), state_fn=make_file_state_fn(work_dir))
        def read(path: Path) -> str:
            calls.append(path)
            with path.open("r") as fil:
                return fil.read()

        def write(path: Path, text: str) -> None:
            with path.open("w+") as fil:
                fil.write(text)

        write(file_path, "text")

        assert read(file_path) == "text"  # miss
        assert read(file_path) == "text"  # hit

        # On systems that trakc mod-time by seconds
        # We need to do a read at least one second later
        # So the file correctly appears out-of-date
        time.sleep(1)

        write(file_path, "more text")

        assert read(file_path) == "more text"  # miss
        assert read(file_path) == "more text"  # hit

        # I should only have to read the file twice
        assert len(calls) == 2

        # I should only have the newer-state version cached
        assert len(read.obj_store) == 1


def test_no_files() -> None:
    # ensure it works for the edge case where there are no files

    with tempfile.TemporaryDirectory() as work_dir_:
        work_dir = Path(work_dir_)
        file_path = work_dir / "file1"

        with file_path.open("w") as fil:
            fil.write("more text")

        calls: List[str] = []

        @cache_decor(MemoryStore.create(), state_fn=make_file_state_fn())
        def open_(filename: str) -> str:
            calls.append(filename)
            with open(filename) as fil:
                return fil.read()

        assert open_(str(file_path)) == "more text"  # miss
        assert open_(str(file_path)) == "more text"  # hit


# def test_cli() -> None:
#     def run(*args: str) -> int:
#         return subprocess.run(
#             [sys.executable, "-m", "cache", *args]
#         ).returncode

#     assert run("--help") == 0
#     assert run("printf", "hi") == 0
#     assert run("--verbose", "printf", "hi") == 0
#     assert run() != 0
