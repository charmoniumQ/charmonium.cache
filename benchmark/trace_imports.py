from typing import Any, Generator, List, Tuple
from pathlib import Path
import contextlib
import enum
import importlib
import importlib.util
import sys
import types

class FileType(enum.Enum):
    IMPORT = 0
    OPEN = 1


@contextlib.contextmanager
def trace_imports() -> Generator[List[Tuple[FileType, Path]], None, None]:
    files = []
    def hook(event: str, args: Tuple[Any, ...]) -> None:
        if files is not None:
            if event == "open":
                path_name = args[0]
                if isinstance(path_name, str):
                    path = Path(path_name)
                    if not path.is_absolute():
                        path = Path.cwd() / path
                    files.append((FileType.OPEN, path))
            elif event == "import":
                module_name = args[0]
                assert isinstance(module_name, str), f"{type(module_name)}: {module_name}"
                module = importlib.util.find_spec(module_name)
                if module:
                    if module.origin and module.origin != "built-in":
                        files.append((FileType.IMPORT, Path(module.origin)))

    sys.addaudithook(hook)
    yield files
    files = None

def main(script: Path, trace_log: Path) -> None:
    sys.path.append(str(script.resolve().parent))
    print(script.resolve().parent, script.stem)
    with trace_imports() as imports:
        importlib.import_module(script.stem)
    trace_log.write_text("\n".join([
        str(file)
        for _, file in imports
    ]) + "\n")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Record the trace of a Python program.")
    parser.add_argument("script", type=str, help="Script to import")
    parser.add_argument("trace_log", type=str, help="File in which to write the trace")

    args = parser.parse_args()
    script = Path(args.script)
    trace_log = Path(args.trace_log)

    main(script, trace_log)
