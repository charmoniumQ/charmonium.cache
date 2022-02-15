from __future__ import annotations
from dataclasses import dataclass
import os
import re
import subprocess
from pathlib import Path
import shlex
import sys
from typing import Mapping, Optional, Protocol, Tuple, List, Union, cast, NoReturn, TypeVar, Generic

import psutil  # type: ignroe

from .repo import Repo

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

def subprocess_run(
        cmd: List[str],
        cwd: Optional[Path] = None,
        env_override: Optional[Mapping[str, str]] = None,
        check: bool = True,
) -> CompletedProcess:
    start = psutil.Process().cpu_times()
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env={
            **os.environ,
            **(env_override if env_override else {}),
        },
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )
    pid = proc.pid
    stdout, stderr = proc.communicate()
    stop = psutil.Process().cpu_times()
    if check and proc.returncode != 0:
        sys.stderr.buffer.write(stderr)
        sys.stdout.buffer.write(stdout)
        print(proc.returncode, cmd)
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return CompletedProcess(
        cmd,
        proc.returncode,
        stdout,
        stderr,
        stop.children_user - start.children_user,
        stop.children_system - start.children_system,
    )

@dataclass
class CompletedProcess:
    cmd: List[str]
    returncode: int
    stdout: bytes
    stderr: bytes
    user_time: float
    system_time: float

    @property
    def time(self) -> float:
        return self.user_time + self.system_time

class Environment(Protocol):
    def setup(self, repo: Repo) -> None: ...

    def install(self, repo: Repo, package_list: List[Union[str, Path]]) -> None: ...

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> CompletedProcess:
        ...


class CondaEnvironment(Environment):
    def __init__(
            self,
            *,
            name: str,
            environment: Path,
            relative_to_repo: bool = False,
    ) -> None:
        proc = subprocess.run(
            ["mamba"],
            capture_output=True,
        )
        if proc.returncode != 0:
            sys.stdout.buffer.write(proc.stdout)
            sys.stderr.buffer.write(proc.stderr)
            raise RuntimeError("Please install mamba and add it to your path.")
        super().__init__()
        self.name = name
        self.environment = environment
        self.relative_to_repo = relative_to_repo

    @staticmethod
    def _conda(
            *cmd: str,
            cwd: Path = Path(),
            env_override: Optional[Mapping[str, str]] = None,
            check: bool = True,
    ) -> CompletedProcess:
        proc = subprocess_run(
            [
                # "conda-shell",
                # "-c",
                # shlex.join(["conda", *cmd]),
                "mamba",
                *cmd,
            ],
            env_override={
                "PYTHONPATH": "",
                **(env_override if env_override else {}),
            },
            cwd=cwd,
            check=check,
        )
        return proc

    def setup(self, repo: Repo) -> None:
        if self.relative_to_repo:
            self.environment = repo.dir / self.environment
        # out = (self._conda("env", "export", "--name", self.name)).stdout
        # if out != self.environment.read_bytes():
        #     self._conda("env", "remove", "--name", self.name)
        #     self._conda("env", "create", "--name", self.name, "--file", str(self.environment))

    def install(self, repo: Repo, packages: List[Union[str, Path]]) -> None:
        self._conda(
            "run",
            "--no-capture-output",
            "--name",
            self.name,
            "pip",
            "install",
            "--user",
            *map(str, packages),
        )

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> CompletedProcess:
        proc = self._conda(
            "run",
            "--no-capture-output",
            "--name",
            self.name,
            *command,
            cwd=cwd,
            env_override=env_override,
            check=False,
        )
        return proc

class PipenvEnvironment(Environment):
    def __init__(
            self,
            *,
            name: str,
            pipfile: Path,
    ) -> None:
        super().__init__()
        self.name = name
        self.pipfile = pipfile

    def _pipenv(
            self,
            *cmd: str,
            cwd: Path = Path(),
            env_override: Optional[Mapping[str, str]] = None,
            check: bool = True,
    ) -> CompletedProcess:
        return subprocess_run(
            ["pipenv", *cmd],
            cwd=cwd,
            env_override={
                "PIPENV_PIPFILE": str(self.pipfile),
                "PYTHONPATH": "",
                **(env_override if env_override else {}),
            },
        )

    def setup(self, repo: Repo) -> None:
        self._pipenv("run", "true")

    def install(self, repo: Repo, packages: List[Union[str, Path]]) -> None:
        self._pipenv("install", *map(str, packages))

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> CompletedProcess:
        return self._pipenv("run", *command, cwd=cwd, check=False, env_override=env_override)

class PoetryEnvironment(Environment):
    def __init__(self, *, name: str, pyproject: Path, in_repo: bool) -> None:
        super().__init__()
        self.name = name
        self.pyproject = pyproject
        self.in_repo = in_repo

    def _poetry(
            self,
            *cmd: str,
            check: bool = True,
            env_override: Optional[Mapping[str, str]] = None,
    ) -> CompletedProcess:
        return subprocess_run(
            ["poetry", *cmd],
            cwd=self.pyproject.parent,
            env_override={
                **(env_override if env_override is not None else {}),
                "VIRTUAL_ENV": "",
                "PLAT": "",
                "PYTHONNOUSERSITE": "",
                "PYTHONPATH": "",
            },
            check=check,
        )

    def setup(self, repo: Repo) -> None:
        if self.in_repo:
            self.pyproject = repo.dir / self.pyproject
        self._poetry("update", "--no-dev", "--lock")
        self._poetry("install", "--no-dev")

    def install(self, repo: Repo, packages: List[Union[str, Path]]) -> None:
        real_packages = [
            str(relative_to(package, self.pyproject.parent))
            if isinstance(package, Path) else
            package
            if isinstance(package, str) else
            raise_(TypeError())
            for package in packages
        ]
        self._poetry("add", *real_packages)

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> CompletedProcess:
        return self._poetry(
            "run",
            # The cwd has to be the directory containing pyproject.toml
            # Instead, we will use `env --chdir {dir} cmd` to switch dirs.
            "env",
            f"--chdir={cwd!s}",
            "sh",
            "-c",
            # invoke sh -c so that I can use '&&'
            shlex.join(command),
            check=False,
            env_override=env_override,
        )

class NixEnvironment(Environment):
    def __init__(
            self,
            *,
            name: str,
            flake: Path,
    ) -> None:
        super().__init__()
        self.name = name
        self.flake = flake

    def _run_in_nix(
            self,
            *cmd: str,
            cwd: Optional[Path] = None,
            check: bool = True,
            env_override: Optional[Mapping[str, str]] = None,
    ) -> CompletedProcess:
        return subprocess_run(
            ["nix", "develop", "--file", str(self.flake), "--command", *cmd],
            check=check,
            env_override=env_override,
            cwd=cwd,
        )

    def setup(self, repo: Repo) -> None:
        self._run_in_nix("true")

    def install(self, repo: Repo, packages: List[Union[str, Path]]) -> None:
        raise NotImplementedError()

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> CompletedProcess:
        return self._run_in_nix(
            *command,
            cwd=cwd,
            check=False,
            env_override=env_override,
        )

class InheritedEnvironment(Environment):
    def setup(self, repo: Repo) -> None:
        pass

    def install(self, repo: Repo, packages: List[Union[str, Path]]) -> None:
        raise NotImplementedError()

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> CompletedProcess:
        return subprocess_run(
            command,
            cwd=cwd,
            check=False,
            env_override=env_override,
        )
