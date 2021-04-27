from typing import Any, Protocol


class Pickler(Protocol):
    def loads(self, buffer: bytes) -> Any:
        ...

    def dumps(self, obj: Any) -> bytes:
        ...
