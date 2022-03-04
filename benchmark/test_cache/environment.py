from __future__ import annotations
from dataclasses import dataclass
import json
import itertools
import os
import re
from pathlib import Path
import pickle
import shlex
import subprocess
import sys
from typing import Mapping, Optional, Protocol, Sequence, Tuple, Union, cast, TypeVar, Generic
import venv

import toml

from .util import timed_subprocess_run, TimedCompletedProcess, relative_to, raise_, format_command
from .repo import Repo

class Environment(Protocol):
    def setup(self) -> None: ...

    def install(self, package_list: Sequence[Union[str, Path]]) -> None: ...

    def run(
        self,
        command: Sequence[str],
        cwd: Optional[Path] = None,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> TimedCompletedProcess:
        ...


class CondaEnvironment(Environment):
    def __init__(
            self,
            name: str,
            environment: Path,
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

    @staticmethod
    def _conda(
            *cmd: str,
            cwd: Optional[Path] = None,
            env_override: Optional[Mapping[str, str]] = None,
            check: bool = True,
    ) -> TimedCompletedProcess:
        proc = timed_subprocess_run(
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

    def setup(self) -> None:
        out = (self._conda("env", "export", "--name", self.name)).stdout
        if out != self.environment.read_bytes():
            self._conda("env", "remove", "--name", self.name)
            self._conda("env", "create", "--name", self.name, "--file", str(self.environment))

    def install(self, packages: Sequence[Union[str, Path]]) -> None:
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
        command: Sequence[str],
        cwd: Optional[Path] = None,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> TimedCompletedProcess:
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
            pipfile: Path,
    ) -> None:
        super().__init__()
        self.pipfile = pipfile

    def _pipenv(
            self,
            *cmd: str,
            cwd: Optional[Path] = None,
            env_override: Optional[Mapping[str, str]] = None,
            check: bool = True,
    ) -> TimedCompletedProcess:
        return timed_subprocess_run(
            ["pipenv", *cmd],
            cwd=cwd,
            env_override={
                "PIPENV_PIPFILE": str(self.pipfile),
                "PYTHONPATH": "",
                **(env_override if env_override else {}),
            },
        )

    def setup(self) -> None:
        self._pipenv("install", "--dev")

    def install(self, packages: Sequence[Union[str, Path]]) -> None:
        self._pipenv("install", *map(str, packages))

    def run(
        self,
        command: Sequence[str],
        cwd: Optional[Path] = None,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> TimedCompletedProcess:
        return self._pipenv("run", *command, cwd=cwd, check=False, env_override=env_override)

class PoetryEnvironment(Environment):
    def __init__(self, pyproject: Path) -> None:
        super().__init__()
        self.pyproject = pyproject

    @staticmethod
    def has_poetry_pyproject(path: Path) -> bool:
        if (path / "pyproject.toml").exists():
            pyproject_spec = toml.loads((path / "pyproject.toml").read_text())
            build_backend = pyproject_spec["build-system"]["build-backend"]
            return build_backend in {
                "poetry.core.masonry.api",
                "poetry.masonry.api",
            }
        else:
            return False

    def _poetry(
            self,
            *cmd: str,
            check: bool = True,
            env_override: Optional[Mapping[str, str]] = None,
    ) -> TimedCompletedProcess:
        env_override = {
            **(env_override if env_override is not None else {}),
            "POETRY_ACTIVE": "",
            # "VIRTUAL_ENV": "",
            "PLAT": "",
            "PYTHONNOUSERSITE": "",
            "PYTHONPATH": "",
        }
        return timed_subprocess_run(
            ["poetry", *cmd],
            cwd=self.pyproject.parent,
            env_override=env_override,
            check=check,
        )

    def setup(self) -> None:
        self._poetry("install")

    def install(self, packages: Sequence[Union[str, Path]]) -> None:
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
        command: Sequence[str],
        cwd: Optional[Path] = None,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> TimedCompletedProcess:
        return self._poetry(
            "run",
            # The cwd has to be the directory containing pyproject.toml
            # Instead, we will use `env --chdir {dir} cmd` to switch dirs.
            "env",
            *([f"--chdir={cwd!s}"] if cwd else []),
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
            flake: Path,
    ) -> None:
        super().__init__()
        self.flake = flake

    def _run_in_nix(
            self,
            *cmd: str,
            cwd: Optional[Path] = None,
            check: bool = True,
            env_override: Optional[Mapping[str, str]] = None,
    ) -> TimedCompletedProcess:
        return timed_subprocess_run(
            ["nix", "develop", "--file", str(self.flake), "--command", *cmd],
            check=check,
            env_override=env_override,
            cwd=cwd,
        )

    def setup(self) -> None:
        self._run_in_nix("true")

    def install(self, packages: Sequence[Union[str, Path]]) -> None:
        raise NotImplementedError()

    def run(
        self,
        command: Sequence[str],
        cwd: Optional[Path] = None,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> TimedCompletedProcess:
        return self._run_in_nix(
            *command,
            cwd=cwd,
            check=False,
            env_override=env_override,
        )

class InheritedEnvironment(Environment):
    def setup(self) -> None:
        pass

    def install(self, packages: Sequence[Union[str, Path]]) -> None:
        raise NotImplementedError()

    def run(
        self,
        command: Sequence[str],
        cwd: Optional[Path] = None,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> TimedCompletedProcess:
        return timed_subprocess_run(
            command,
            cwd=cwd,
            check=False,
            env_override=env_override,
        )

class VirtualEnv(Environment):
    def __init__(
            self,
            env_dir: Path,
            requirements: Sequence[str],
            requirements_cwd: Optional[Path] = None,
    ) -> None:
        self.env_dir = env_dir.resolve()
        self.requirements = requirements
        self.requirements_cwd = requirements_cwd

    @staticmethod
    def from_pipfile_lock(env_dir: Path, pipenv_lock: Path) -> VirtualEnv:
        lockfile = json.loads(pipenv_lock.read_text())
        requirements = []
        for name, info in (lockfile["default"] | lockfile["develop"]).items():
            requirements.append(name + info.get("version", ""))
        return VirtualEnv(
            env_dir,
            requirements,
        )

    def setup(self) -> None:
        if not self.env_dir.exists():
            self.env_dir.mkdir(parents=True)
            # subprocess.run(["python", "-m", "venv", str(self.env_dir)])
            venv.create(self.env_dir, with_pip=True)
        which_python = self._run_in_venv("which", "python").stdout
        which_python_path = Path(which_python.strip().decode())
        assert which_python_path == self.env_dir / "bin/python"
        self.install(self.requirements, self.requirements_cwd)

    def _run_in_venv(
            self,
            *cmd: str,
            cwd: Optional[Path] = None,
            check: bool = True,
            env_override: Optional[Mapping[str, str]] = None,
    ) -> TimedCompletedProcess:
        env_paths = [
            path
            for path in os.environ.get("PATH", "").split(":")
            #if path.is_relative_to(Path().resolve())
        ]
        env_override = env_override if env_override is not None else {}
        env_override = {
            **(env_override if env_override else {}),
            "PATH": ":".join([
                str(self.env_dir / "bin"),
                *env_paths
            ]),
            "VIRTUAL_ENV": str(self.env_dir),
            "PYTHONNOUSERSITE": "true",
        }
        return timed_subprocess_run(
            cmd,
            check=check,
            env_override=env_override,
            cwd=cwd,
        )

    def install(
            self,
            packages: Sequence[Union[str, Path]],
            cwd: Optional[Path] = None,
    ) -> None:
        if packages:
            self._run_in_venv("python", "-m", "pip", "install", *map(str, packages), cwd=cwd)

    def run(
        self,
        command: Sequence[str],
        cwd: Optional[Path] = None,
        env_override: Optional[Mapping[str, str]] = None,
    ) -> TimedCompletedProcess:
        return self._run_in_venv(
            *command,
            cwd=cwd,
            check=False,
            env_override=env_override,
        )

class EnvironmentChooser(Protocol):
    def choose(self, repo: Repo) -> Optional[Environment]: ...

def parse_requirements(requirements: str) -> Sequence[str]:
    parsed_requirements = []
    for line in requirements.split("\n"):
        if "#" in line:
            line, _, _ = line.partition("#")
        line = line.strip()
        if line:
            parsed_requirements.extend(line.split(" "))
    return parsed_requirements

class SmartEnvironmentChooser(EnvironmentChooser):
    def __init__(self, venv_location: Path) -> None:
        self.venv_location = venv_location

    def choose(self, repo: Repo) -> Optional[Environment]:
        if False:
            pass
        elif (repo.dir / "Pipfile.lock").exists():
            pipfile_lock = repo.dir / "Pipfile.lock"
            return VirtualEnv.from_pipfile_lock(
                self.venv_location / repo.name,
                pipfile_lock,
            )
            # PipenvEnvironment might require a Python which is different than the current one.
            # Virtualenv has no such restriction.
            # I expect the Python interpreter to be backwards compatible, so running 3.7 code in 3.9 interpreter should work.
            #return PipenvEnvironment(repo.dir / "Pipfile")
        elif (repo.dir / "environment.yaml").exists():
            return CondaEnvironment(repo.name, repo.dir / "environment.yaml")
        elif (repo.dir / "environment.yml").exists():
            return CondaEnvironment(repo.name, repo.dir / "environment.yml")
        elif PoetryEnvironment.has_poetry_pyproject(repo.dir):
            return PoetryEnvironment(repo.dir / "pyproject.toml")
        elif list(repo.dir.glob("*requirements*.txt")):
            requirements = list(itertools.chain.from_iterable(
                parse_requirements(requirements_file.read_text())
                for requirements_file in repo.dir.glob("*requirements*.txt")
            ))
            return VirtualEnv(
                self.venv_location / repo.name,
                requirements,
                requirements_cwd=repo.dir,
            )
        elif (repo.dir / "setup.py").exists():
            requirements = ["--editable", f"{repo.dir}[dev,test]"]
            return VirtualEnv(
                self.venv_location / repo.name,
                requirements,
                requirements_cwd=repo.dir,
            )
        else:
            return None
