from typing import ContextManager

class InterProcessReaderWriterLock:
    def __init__(self, path: str) -> None:
        ...
    def read_lock(self) -> ContextManager[None]:
        ...
    def write_lock(self) -> ContextManager[None]:
        ...
