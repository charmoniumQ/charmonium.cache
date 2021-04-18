from pathlib import Path
from types import TracebackType
from typing import Optional, Protocol, Union

class Lock(Protocol):
    def __enter__(self) -> Optional[bool]:
        ...

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        ...

class InterProcessReaderWriterLock:
    def __init__(self, path: Union[Path, str]) -> None: ...
    def read_lock(self) -> Lock: ...
    def write_lock(self) -> Lock: ...

class InterProcessLock(Lock):
    def __init__(self, path: Union[Path, str]) -> None: ...
