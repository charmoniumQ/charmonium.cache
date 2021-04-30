from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Protocol
else:
    Protocol = object


class Pickler(Protocol):
    def loads(self, buffer: bytes) -> Any:
        ...

    def dumps(self, obj: Any) -> bytes:
        ...
