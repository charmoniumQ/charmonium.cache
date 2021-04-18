from typing import Any, Callable, ContextManager, TypeVar

def raises(exc: type[BaseException]) -> ContextManager[None]: ...
def warns(exc: type[Warning]) -> ContextManager[None]: ...

_T = TypeVar("_T")

class _Mark:
    def parametrize(
            self, args: str, vals: Any,
    ) -> Callable[[_T], _T]: ...

mark: _Mark = ...

class Caplog:
    text: str
