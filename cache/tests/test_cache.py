from typing import cast, List
from pathlib import Path
import threading
import time
import tempfile
from cache import Cache, MemoryStore, FileStore, DirectoryStore, make_file_state_fn
from cache.util import unix_ts_now, loop_for_duration


def test_cache() -> None:
    with tempfile.TemporaryDirectory() as work_dir_:
        work_dir = Path(work_dir_)
        calls: List[int] = []

        @Cache.decor(MemoryStore.create())
        def square1(x: int, a: int = 0) -> int: # pylint: disable=invalid-name
            calls.append(x)
            return x**2 + a

        @Cache.decor(FileStore.create(str(work_dir)))
        def square2(x: int, a: int = 0) -> int: # pylint: disable=invalid-name
            calls.append(x)
            return x**2 + a

        @Cache.decor(DirectoryStore.create(work_dir / 'cache'))
        def square3(x: int, a: int = 0) -> int: # pylint: disable=invalid-name
            calls.append(x)
            return x**2 + a

        for square in [square1, square2, square3]:
            calls.clear()

            assert square(7) == 49 # miss
            assert square(2) == 4 # miss

            # repeated values should not miss; they will not show up in
            # calls
            assert square(7) == 49
            assert square(2) == 4

            # clearing cache should make next miss
            square_ = cast(Cache, square)
            square_.clear()

            # clearing cache should remove the file
            if hasattr(square_, 'cache_path'):
                assert not getattr(square_, 'cache_path').exists()

            assert square(7) == 49 # miss
            assert square(2) == 4 # miss

            # adding a kwarg should make a miss
            assert square(7) == 49 # hit
            assert square(7, a=2) == 51 # miss

            # test del explicitly
            # no good way to test it no normal functionality
            del square_.obj_store[square_.obj_store.args2key((7,), {})]
            assert square(7) == 49

            # test disabling feature
            with square_.disabled():
                assert square(2) == 4 # miss
                assert square(2) == 4 # miss, even after regotten

            assert calls == [7, 2, 7, 2, 7, 7, 2, 2]


def test_multithreaded_cache() -> None:
    calls: List[int] = []

    @Cache.decor(MemoryStore.create())
    def square(x: int) -> int: # pylint: disable=invalid-name
        calls.append(x)
        return x**2

    def worker():
        for _ in loop_for_duration(2):
            seconds = int(unix_ts_now() * 10)
            # everyone will be trying to square the same thing,
            # at the same time
            square(seconds)
            # One thread should lock the others out while it computes
            # and caches the result. There should only be one miss.

    threads = [
        threading.Thread(target=worker) for _ in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # only one miss per elem, even though multiple simultaneous accesses
    assert len(set(calls)) == len(calls)


def test_files() -> None:
    with tempfile.TemporaryDirectory() as work_dir_:
        work_dir = Path(work_dir_)
        file_path = work_dir / 'file1'
        calls: List[str] = []

        @Cache.decor(
            MemoryStore.create(), state_fn=make_file_state_fn(work_dir)
        )
        def open_(filename: str) -> str: # pylint: disable=invalid-name
            calls.append(filename)
            with open(filename) as fil:
                return fil.read()

        with file_path.open('w') as fil:
            fil.write('text')

        assert open_(str(file_path)) == 'text' # miss
        assert open_(str(file_path)) == 'text' # hit

        time.sleep(0.5)

        with file_path.open('w') as fil:
            fil.write('more text')

        assert open_(str(file_path)) == 'more text' # miss
        assert open_(str(file_path)) == 'more text' # hit

        # I should only have to read the file twice
        assert len(calls) == 2

        # I should only have the newer-state version cached
        assert len(cast(Cache, open_).obj_store) == 1


if __name__ == '__main__':
    test_files()
