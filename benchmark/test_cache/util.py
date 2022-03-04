from __future__ import annotations

from dataclasses import dataclass
import datetime
import os
from pathlib import Path
from typing import NoReturn, Sequence, Optional, Mapping, Iterable, TypeVar
import shlex
import subprocess
import sys

import psutil  # type: ignore

class BenchmarkError(Exception):
    """Errors that originate from the benchmark code, rather than included libraries."""
    pass


K = TypeVar("K")
V = TypeVar("V")
def merge(dcts: Iterable[Mapping[K, V]]) -> Mapping[K, V]:
    result = {}
    for dct in dcts:
        for key, val in dct.items():
            result[key] = val
    return dct

def raise_(exception: Exception) -> NoReturn:
    raise exception

def relative_to(dest: Path, source: Path) -> Path:
    if not dest.is_absolute():
        raise TypeError(f"dest ({dest}) should be absolute.")
    if not source.is_absolute():
        raise TypeError(f"source ({source}) should be absolute.")
    if dest.is_relative_to(source):
        ret = dest.relative_to(source)
        assert (source / ret).resolve() == dest and not ret.is_absolute()
        return ret
    else:
        ret = Path("..") / relative_to(dest, source.parent.resolve())
        assert (source / ret).resolve() == dest
        return ret

def timed_subprocess_run(
        cmd: Sequence[str],
        cwd: Optional[Path] = None,
        env_override: Optional[Mapping[str, str]] = None,
        check: bool = True,
) -> TimedCompletedProcess:
    start_wall = datetime.datetime.now()
    start = psutil.Process().cpu_times()
    proc = subprocess.Popen(
        list(cmd),
        env={
            **os.environ,
            **(env_override if env_override else {}),
        },
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        cwd=str(cwd) if cwd else ".",
    )
    pid = proc.pid
    stdout, stderr = proc.communicate()
    stop = psutil.Process().cpu_times()
    stop_wall = datetime.datetime.now()
    if check and proc.returncode != 0:
        sys.stderr.buffer.write(stderr)
        sys.stdout.buffer.write(stdout)
        print(proc.returncode, cmd)
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return TimedCompletedProcess(
        cmd,
        proc.returncode,
        stdout,
        stderr,
        stop.children_user - start.children_user,
        stop.children_system - start.children_system,
        (stop_wall - start_wall).total_seconds(),
    )

@dataclass
class TimedCompletedProcess:
    cmd: Sequence[str]
    returncode: int
    stdout: bytes
    stderr: bytes
    user_time: float
    system_time: float
    wall_time: float

    @property
    def cpu_time(self) -> float:
        return self.user_time + self.system_time

def format_command(
        cmd: Sequence[str],
        cwd: Optional[Path] = None,
        env_override: Optional[Mapping[str, str]] = None,
) -> str:
    return shlex.join([
        *(["env", "-C", str(cwd)] if cwd and cwd != Path() else []),
        *([key + "=" + val for key, val in env_override.items()] if env_override else []),
        *cmd,
    ])
