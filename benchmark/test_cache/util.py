from __future__ import annotations

from dataclasses import dataclass
import datetime
import os
from pathlib import Path
from typing import NoReturn, Sequence, Optional, Mapping, Iterable, TypeVar, Dict, Set
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

@dataclass
class CalledProcessError(Exception):
    cmd: Sequence[str]
    env: Optional[Mapping[str, str]]
    cwd: Optional[Path]
    returncode: int
    stdout: str
    stderr: str

    def __init__(
            self,
            cmd: Sequence[str],
            env: Optional[Mapping[str, str]],
            cwd: Optional[Path],
            returncode: int,
            stdout: str,
            stderr: str,
    ) -> None:
        self.cmd = cmd
        self.env = env
        self.cwd = cwd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self) -> str:
        return f"$ {format_command(self.cmd, env=self.env, cwd=self.cwd)}\n{self.stdout}\n{self.stderr}\n\nFailed with {self.returncode}"

def timed_subprocess_run(
        cmd: Sequence[str],
        env: Optional[Mapping[str, str]] = None,
        cwd: Optional[Path] = None,
        check: bool = True,
) -> TimedCompletedProcess:
    start_wall = datetime.datetime.now()
    start = psutil.Process().cpu_times()
    proc = subprocess.Popen(
        list(cmd),
        env=(env if env is not None else os.environ),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        cwd=str(cwd) if cwd else ".",
    )
    pid = proc.pid
    stdout_bytes, stderr_bytes = proc.communicate()
    stdout, stderr = stdout_bytes.decode(), stderr_bytes.decode()
    stop = psutil.Process().cpu_times()
    stop_wall = datetime.datetime.now()
    if check and proc.returncode != 0:
        raise CalledProcessError(cmd=cmd, cwd=cwd, env=env, stdout=stdout, stderr=stderr, returncode=proc.returncode)
    return TimedCompletedProcess(
        cmd,
        proc.returncode,
        stdout,
        stderr,
        stop.children_user - start.children_user,
        stop.children_system - start.children_system,
        (stop_wall - start_wall).total_seconds(),
    )

def which(binary: str) -> Path:
    proc = subprocess.run(
        ["which", binary],
        text=True,
        capture_output=True,
        check=True,
        env={
            "PATH": os.environ.get("PATH", "")
        },
    )
    return Path(proc.stdout.strip())
    # if proc.returncode == 0:
    #     return Path(proc.stdout.strip())
    # elif proc.returncode == 1:
    #     return None
    # else:
    #     raise RuntimeError(f"`which {binary}` failed with {proc.returncode}.\n{proc.stdout}\n{proc.stderr}")

@dataclass
class TimedCompletedProcess:
    cmd: Sequence[str]
    returncode: int
    stdout: str
    stderr: str
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
        env: Optional[Mapping[str, str]] = None,
) -> str:
    if env_override and env:
        raise ValueError("Cannot pass `env_override` and `env`.")
    print_cwd = cwd and cwd != Path()
    actual_env = env if env else (env_override if env_override else None)
    return shlex.join([
        *(["env"] if env or print_cwd else []),
        *(["-C", str(cwd)] if print_cwd else []),
        *(["-"] if env else []),
        *([key + "=" + val for key, val in actual_env.items()] if actual_env else []),
        *cmd,
    ])

colon_variables = {
    "PATH",
    "LD_LIBRARY_PATH",
}

def merge_envs(*envs: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    merged_env: Dict[str, str] = {}
    for env in envs:
        if env:
            for key, val in env.items():
                if key in colon_variables and key in merged_env:
                    merged_env[key] = env[key] + ":" + merged_env[key]
                else:
                    merged_env[key] = env[key]
    return merged_env

def project(dct: Mapping[K, V], keys: Set[K]) -> Mapping[K, V]:
    return {
        key: val
        for key, val in dct.items()
        if key in keys
    }
