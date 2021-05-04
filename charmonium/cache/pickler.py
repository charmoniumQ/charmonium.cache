from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Protocol

else:
    Protocol = object


class Pickler(Protocol):
    def loads(self, buffer: bytes) -> Any:
        ...

    def dumps(self, obj: Any) -> bytes:
        ...


# TODO: switch this to file-based load/dump
