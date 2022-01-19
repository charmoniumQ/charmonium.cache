import asyncio
import os
import re
import subprocess
from pathlib import Path
import shlex
from typing import Mapping, Optional, Protocol, Tuple, List, Union, cast, NoReturn

from charmonium.async_subprocess import run as async_run

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

class Environment(Protocol):
    async def setup(self, repo: Repo) -> None: ...

    async def install(self, repo: Repo, package_list: List[Union[str, Path]]) -> None: ...

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess[bytes]:
        ...


class CondaEnvironment(Environment):
    def __init__(
            self,
            *,
            name: str,
            environment: Path,
            relative_to_repo: bool = False,
    ) -> None:
        super().__init__()
        self.name = name
        self.environment = environment
        self.relative_to_repo = relative_to_repo

    @staticmethod
    async def _conda(
            *cmd: str,
            cwd: Path = Path(),
            env_override: Optional[Mapping[str, str]] = None,
            check: bool = True,
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
            check=check,
            text=False,
            capture_output=True,
        )
        return cast(subprocess.CompletedProcess[bytes], proc)

    async def setup(self, repo: Repo) -> None:
        if self.relative_to_repo:
            self.environment = repo.dir / self.environment
        out = (await self._conda("conda", "env", "export", "--name", self.name)).stdout
        if out != self.environment.read_bytes():
            await self._conda("conda", "env", "remove", "--name", self.name)
            await self._conda("conda", "env", "create", "--name", self.name, "--file", str(self.environment))

    async def install(self, repo: Repo, packages: List[Union[str, Path]]) -> None:
        await self._conda("conda", "run", "--name", self.name, "pip", "install", *map(str, packages))

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess[bytes]:
        proc = asyncio.run(self._conda(
            "conda",
            "run",
            "--name",
            self.name,
            *command,
            cwd=cwd,
            env_override=env_override,
            check=False,
        ))
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

    async def setup(self, repo: Repo) -> None:
        await async_run(
            ["pipenv", "run", "true"],
            env={
                "PIPENV_PIPFILE": str(self.pipfile.parent),
                **os.environ,
            },
            check=True,
        )

    async def install(self, repo: Repo, packages: List[Union[str, Path]]) -> None:
        await async_run(
            ["pipenv", "install", *map(str, packages)],
            env={
                "PIPENV_PIPFILE": str(self.pipfile.parent),
                **os.environ,
            },
            check=True,
        )

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess[bytes]:
        proc = subprocess.run(
            ["pipenv", "run", *command],
            cwd=cwd,
            check=False,
            capture_output=True,
            env={
                "PIPENV_PIPFILE": str(self.pipfile.parent),
                **os.environ,
                **(env_override if env_override is not None else {}),
            },
        )
        return proc

class PoetryEnvironment(Environment):
    def __init__(self, *, name: str, pyproject: Path, in_repo: bool) -> None:
        super().__init__()
        self.name = name
        self.pyproject = pyproject
        self.in_repo = in_repo

    async def _poetry(
            self,
            *cmd: str,
            check: bool = True,
            env_override: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess[bytes]:
        env = {
            key: val
            for key, val in os.environ.items()
            if key not in {"VIRTUAL_ENV", "PLAT", "PYTHONNOUSERSITE"}
        }
        if env_override:
            env.update(env_override)
        Path("python_poetry.env").write_text(
            "\n".join(
                f"{key}={shlex.quote(val)}"
                for key, val in sorted(env.items())
            )
        )
        # env["PATH"] = ":".join(
        #     location
        #     for location in env["PATH"].split(":")
        #     if "/nix/store" not in location
        # )
        proc = await async_run(
            ["poetry", *cmd],
            cwd=self.pyproject.parent,
            capture_output=True,
            check=check,
            env=env,
        )
        return cast(subprocess.CompletedProcess[bytes], proc)

    async def setup(self, repo: Repo) -> None:
        if self.in_repo:
            self.pyproject = repo.dir / self.pyproject
        await self._poetry("update", "--no-dev", "--lock")
        await self._poetry("install", "--no-dev")

    async def install(self, repo: Repo, packages: List[Union[str, Path]]) -> None:
        real_packages = [
            str(relative_to(package, self.pyproject.parent))
            if isinstance(package, Path) else
            package
            if isinstance(package, str) else
            raise_(TypeError())
            for package in packages
        ]
        await self._poetry("add", *real_packages)

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess[bytes]:
        proc = asyncio.run(self._poetry(
            "run",
            "env",
            f"--chdir={cwd!s}",
            "sh",
            "-c",
            # invoke sh -c so that I can use '&&'
            shlex.join(command),
            check=False,
            env_override=env_override,
        ))
        return proc

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

    async def setup(self, repo: Repo) -> None:
        await async_run(
            ["nix", "develop", "--command", "true", "--file", str(self.flake)],
        )

    async def install(self, repo: Repo, packages: List[Union[str, Path]]) -> None:
        raise NotImplementedError()

    def run(
        self,
        command: List[str],
        cwd: Path,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess[bytes]:
        proc = subprocess.run(
            ["nix", "develop", "--command", "true", "--file", str(self.flake)],
            cwd=cwd,
            check=False,
            capture_output=True,
        )
        return proc
