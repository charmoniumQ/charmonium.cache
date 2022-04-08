from pathlib import Path
import contextlib
import enum
import importlib
import inspect
import sys
import trace
from typing import Any, Generator, List, Mapping, Optional, Sequence, Tuple, cast
import types


class Granularity(enum.Enum):
    FUNCTION = 1
    LINE = 2
    FILE = 3


@contextlib.contextmanager
def record_dynamic_trace(granularity: Granularity) -> Generator[Sequence[Tuple[str, str]], None, None]:
    old_trace_func = sys.gettrace()
    func_locations: Mapping[Tuple[str, str]] = {}
    frame_list: List[Tuple[str, Optional[int]]] = []
    def trace_func(frame: types.FrameType, event: str, arg: Any) -> None:
        print(event, frame)
        code = frame.f_code
        if granularity == Granularity.FILE and event == "call":
            frame_list.append((code.co_filename, ""))
        if granularity == Granularity.FUNCTION and event == "call":
            func_id = (code.co_filename, code.co_name)
            if func_id in func_locations:
                func_location = func_locations[func_id]
            else:
                lines, first_line = inspect.findsource(code)
                last_line = first_line + len(inspect.getblock(lines[first_line:]))
                func_location = (first_line + 1, last_line + 2)
                func_locations[func_id] = func_location
            frame_list.append((code.co_filename, f"{func_location[0]}-{func_location[1]}"))
        if granularity == Granularity.LINE and (event == "call" or event == "line"):
            frame_list.append((code.co_filename, str(frame.f_lineno)))
        if old_trace_func:
            old_trace_func(frames, event, arg)
    sys.settrace(trace_func)
    yield frame_list
    sys.settrace(old_trace_func)
    del frame_list[-1] # contextlib.__exit__
    del frame_list[-1] # record_dynamic_trace


def execute_with_trace(
        module: str,
        func: str,
        trace_log: Path,
        granularity: Granularity,
        args: List[str],
) -> None:
    module_obj = importlib.import_module(module)
    func_obj = getattr(module_obj, func)
    sys.argv = args
    with record_dynamic_trace(granularity) as dynamic_trace:
        func_obj()
    trace_log.write_text("\n".join(
        f"{filename}" + (f":{lineno}" if lineno is not None else "")
        for (filename, lineno) in dynamic_trace
    ) + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Record the trace of a Python program.")
    parser.add_argument("module", type=str, help="Module to load")
    parser.add_argument("function", type=str, help="Function to run in module")
    parser.add_argument("trace_log", type=str, help="File in which to write the trace")
    parser.add_argument("granularity", type=str, help="Granularity to capture the trace (\"file\", \"function\", or \"line\")")
    parser.add_argument("args", type=str, nargs="*", help="New argv")

    args = parser.parse_args()
    trace_log = Path(args.trace_log)
    granularity = Granularity[args.granularity.upper()]

    execute_with_trace(args.module, args.function, trace_log, granularity, args.args)
