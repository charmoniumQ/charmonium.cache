from typing import Any, Generic, TypeVar, Hashable
import io
import os
import subprocess
import sys

import pandas as pd
import charmonium.cache

group = charmonium.cache.MemoizedGroup(
    size="10Gb",
)

orig_read_excel = pd.read_excel

print("Monkeypatching `pandas.read_excel` v2", file=sys.stderr)


T = TypeVar("T")
class DefinedHash(Generic[T]):
    def __init__(self, value: T, hash: Hashable) -> None:
        self.value = value
        self.hash = hash

    def __getfrozenstate__(self) -> Hashable:
        return self.hash


def read_excel(
        file: Any,
        *args: Any,
        **kwargs: Any,
) -> pd.DataFrame:
    print("Env vars", os.environ.get("CHARMONIUM_CACHE_DISABLE"), os.environ.get("CHARMONIUM_CACHE_PERF_LOG"), file=sys.stderr)
    print(f"read_excel({file!r}, *{args!r}, **{kwargs!r})", file=sys.stderr)
    if isinstance(file, (str, bytes)):
        file_hash = subprocess.run(
            ["cksum", file],
            check=True,
            capture_output=True
        ).stdout
        file = DefinedHash(file, file_hash)
    elif isinstance(file, io.FileIO):
        file_hash = subprocess.run(
            ["cksum", file.name],
            check=True,
            capture_output=True
        ).stdout
        file = DefinedHash(file, file_hash)
    elif isinstance(file, pd.io.excel._base.ExcelFile):
        file_hash = file._io
        file = DefinedHash(file, file_hash)
    else:
        # identity of file already reflected in determ_hash(file)
        pass
    return read_excel2(file, *args, **kwargs)

@charmonium.cache.memoize(group=group)
def read_excel2(
        file: Any,
        *args: Any,
        **kwargs: Any,
) -> pd.DataFrame:
    return orig_read_excel(file.value, *args, **kwargs)

pd.read_excel = read_excel
