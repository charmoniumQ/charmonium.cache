import asyncio
import os
import re
import subprocess
from pathlib import Path
import shlex
from typing import Mapping, Optional, Protocol, Tuple, List, cast

from charmonium.async_subprocess import run as async_run

from .repo import Repo

class Environment(Protocol):
    async def setup(self, repo: Repo) -> None:
        ...

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> Tuple[bytes, bool]:
        ...


class CondaEnvironment(Environment):
    def __init__(
            self,
            *,
            name: str,
            environment: Path,
    ) -> None:
        super().__init__()
        self.name = name
        self.environment = environment

    @staticmethod
    async def _conda(
            cmd: List[str],
            cwd: Path,
            env_override: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess[bytes]:
        proc = await async_run(
            [
                "conda-shell",
                "-c",
                shlex.join(cmd),
            ],
            env={
                **os.environ,
                **(env_override if env_override else {}),
            },
            cwd=cwd,
            check=True,
            text=False,
            capture_output=True,
        )
        return cast(subprocess.CompletedProcess[bytes], proc)

    async def setup(self, repo: Repo) -> None:
        out = (await self._conda(["conda", "env", "export", "--name", self.name], cwd=Path())).stdout
        if out != self.environment.read_bytes():
            await self._conda(["conda", "env", "remove", "--name", self.name], cwd=Path())
            await self._conda(["conda", "env", "create", "--name", self.name, "--file", str(self.environment)], cwd=Path())

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> Tuple[bytes, bool]:
        proc = asyncio.run(self._conda(
            ["conda", "run", "--name", self.name, *command],
            cwd=cwd,
            env_override=env_override,
        ))
        return proc.stdout, proc.returncode == 0


class PoetryEnvironment(Environment):
    def __init__(self, *, name: str, pyproject: Path) -> None:
        super().__init__()
        self.name = name
        self.pyproject = pyproject

    async def setup(self, repo: Repo) -> None:
        proc = await async_run(
            [
                "poetry",
                "install",
                "--no-dev",
            ],
            cwd=self.pyproject.parent,
            check=True,
            capture_output=True,
        )

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> Tuple[bytes, bool]:
        proc = subprocess.run(
            ["poetry", "run", "env", "-C", str(cwd), "sh", "-c", shlex.join(command)],
            check=False,
            cwd=self.pyproject.parent,
            env={
                **os.environ,
                **(env_override if env_override else {}),
            },
            capture_output=True,
        )
        return proc.stdout, proc.returncode == 0
