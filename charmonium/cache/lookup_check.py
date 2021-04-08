import atexit
import contextlib
import typing
from typing import Generic, TypeVar, Iterator, Callable, ContextManager, Protocol

Key = TypeVar("Key")
Val = TypeVar("Val")

class Index(Protocol[Key, Val]):
    def get(self, key: Key) -> Tuple[bool, Optional[Val]]: ...
    def merge(self, state: Any) -> None: ...
    def get_state(self) -> Any: ...
    def set_state(self, state: Any) -> None: ...
    def size(self) -> int: ...

class IndexMatch(Index[Key, Val]):
    def __init__(self, create: Callable[[Key], Val], delete: Callable[[Key, Val], None]) -> None:
        self.create = create
        self.delete = delete
        self.valid = False

    def __setitem__(self, key: Key, val: Val) -> None:
        self.delete(self.key, self.val)
        self.key = key
        self.val = val
        self.valid = True

    def get_or(self, key: Key, create: Callable[[Key], Val]) -> Val:
        if not key in self:
            self[key] = create(key)
        return self.val

    def __getitem__(self, key: Key) -> Val:
        return self.get_or(key, self.create)

    def __contains__(self, key: Key) -> None:
        return self.valid and self.key == key

    def get_state(self) -> None:
        return (self.key, self.val)

    def set_state(self, state: tuple[Key, Val]) -> None:
        self.key, self.val = state

    def merge(self, state: tuple[Key, Val]) -> None:
        pass

class IndexMap(Index[Key, Val]):
    def __init__(self, create: Callable[[Key], Val], delete: Callable[[Key, Val], None])

@attr.s
class Entry(Generic[T]):
    data_size: int
    compute_time: float
    last_use: datetime.datetime
    value: T

cache = Lookup[GlobalEnvironment, Check[FunctionName, Lookup[Function, Check[ArgsKey, Lookup[ArgsVersion]]]]]()

entry = cache[env_version][fn_name][fn_version][args].get_or(args_version, recompute_fn)


Lock = ContextManager[None]

@typing.runtime_checkable
class ReaderWriterLock(Protocol):
    def read_locked(self) -> Lock: ...
    def write_locked(self) -> Lock: ...

    @staticmethod
    def normalize(lock: PotentiallyReaderWriterLock) -> ReaderWriterLock:
        if isinstance(lock, ReaderWriterLock):
            return lock
        elif isinstance(lock, Lock):
            return NaiveReaderWriterLock(lock)
        else:
            raise TypeError(f"Don't know how to make a ReaderWriterLock out of {type(lock)} {lock}")

PotentiallyReaderWriterLock = Union[Lock, ReaderWriterLock]

class NaiveReaderWriterLock(ReaderWriterLock):
    def __init__(self, lock: Lock) -> None:
        self.lock = lock
    def read_locked(self) -> Lock:
        return self.lock
    def write_locked(self) -> Lock:
        return self.lock

PotentiallyPathLike = Union[bytes, str, PathLike]

@typing.runtime_checkable
class PathLike(Protocol):
    @staticmethod
    def normalize(path: PotentiallyPathLike) -> PathLike:
        if isinstance(path, (bytes, str)):
            return Path(path)
        elif isinstance(path, PathLike):
            return path
        else:
            raise TypeError(f"Don't know how to make a PathLike out of {type(path)} {path}")

CACHE_LOC = Path(".cache/index")

def random_bits(n_bits=64) -> int:
    return random.randint(0, 2**n_bits - 1)

class IndexContainer:
    def __init__(
            self,
            fine_grain_eviction: bool = False,
            fine_grain_persistence: bool = False,
            thread_lock: Lock = threading.Lock(),
            process_lock: PotentiallyReaderWriterLock = contextlib.nullcontext(),
    ) -> None:
        self._fine_grain_eviction = fine_grain_eviction
        self._fine_grain_persistence = fine_grain_persistence
        self._thread_lock = thread_lock
        self._process_lock = ReaderWriterLock.normalize(process_lock)
        self._intro()
        atexit.register(self._outro())

    def _intro(self) -> None:
        with self._thread_lock:
            if not self._fine_grain_persistence:
                self._load()

    def _lookup(self, key, thunk):
        with self._thread_lock:
            self._index_is_stored = False

            if self._fine_grain_persistence:
                self._load()

            self._index_is_stored = False
            assert self._index_is_loaded
            present, entry = self._index.get(key)
            if present:
                # entry was present in the index
                # It may be None, but this is a "real" Val None.
                entry = cast(Val, entry)
            else:
                entry = thunk()
                self._index[key] = entry

            if self._fine_grain_eviction:
                self._evict()

            if self._fine_grain_persistence:
                self._store(merge=True)

            return entry

    def _outro(self) -> None:
        with self._thread_lock:
            if not self._fine_grain_persistence:
                self._store(merge=True)
            assert self._index_is_stored

    def _load(self) -> None:
        self._index_is_loaded = True
        with self._process_lock.read_locked():
            state = load from self._index_path
        self._index.set_state(state)

    def _store(self, merge: bool) -> None:
        self._index_is_stored = True
        with self._process_lock.write_locked():
            if merge:
                state = load from self._index_path
                self._index.update(state)

            self._evict()
                state = self._index.get_state()
            self._index_path store state

    def _evict(self) -> None:
        while self._index.size() > self._limit:
            self._remove_one()

# https://github.com/micheles/decorator/blob/master/docs/documentation.md
# https://pypi.org/project/fasteners/

# The state of the system environment is a key-to-check.
# The name of the function being called is a key-to-lookup.
# The source-code, environment, and serialization of that function is a key-to-check.
# The arguments form a key-to-lookup.
# The version of each versioned resource argument form a key-to-check.
# Entry holds metadata and CoatCheckRef.
# Serializer, CoatCheck, and apply_coat_check
# The index is just a map from metadata to values, endowed with a process-safe save, load, and merge
# Storage is customizable; functionality is not.
# Modes:
# - Eager (every entry gets saved)
# - Lazy (startup and shutdown)

class CoatCheck(Protocol[Key, Val]):
    def __getitem__(self, key: Key) -> Val: ...
    def __setitem__(self, key: Key, val: Val) -> None: ...
    def clear(self) -> None: ...
    def size(self) -> None: ...
