from __future__ import annotations

import itertools
import json
import os
import pickle
import re
import shlex
import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Generic,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
)

import toml

from .repo import Repo
from .util import format_command, merge_envs, raise_, relative_to, which


class Environment(Protocol):
    def setup(self) -> None:
        ...

    def install(self, package_list: Sequence[Union[str, Path]]) -> None:
        ...

    def run(
        self,
        command: Sequence[str],
        env: Mapping[str, str],
        cwd: Path,
    ) -> Tuple[List[str], Mapping[str, str], Path]:
        ...

    def has_package(self, name: str) -> bool:
        script = f"""
try:
    import {name}
except ImportError:
    print(0)
# Other exceptions will still bubble up.
else:
    print(1)
"""
        cmd, env, cwd = self.run(["python", "-c", script], env={}, cwd=Path())
        proc = subprocess.run(
            cmd,
            env=env,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return bool(int(proc.stdout.strip()))
        else:
            raise RuntimeError(proc.stderr)


conda_env = {
    "PATH": ":".join(
        [
            str(which("mamba").parent),
            str(which("conda").parent),
            str(which("bash").parent),
            str(which("dirname").parent),
        ]
    ),
    "CONDA_EXE": os.environ["CONDA_EXE"],
    "CONDA_PYTHON_EXE": os.environ["CONDA_PYTHON_EXE"],
}


class CondaEnvironment(Environment):
    def __init__(
        self,
        name: str,
        environment: Path,
    ) -> None:
        proc = subprocess.run(
            ["mamba"],
            capture_output=True,
            env=merge_envs(os.environ, conda_env),
        )
        if proc.returncode != 0:
            sys.stdout.buffer.write(proc.stdout)
            sys.stderr.buffer.write(proc.stderr)
            raise RuntimeError("Please install mamba and add it to your path.")
        super().__init__()
        self.name = name
        self.environment = environment

    @staticmethod
    def _conda(*cmd: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["mamba", *cmd],
            env=merge_envs(os.environ, conda_env),
            check=True,
            capture_output=True,
        )

    def setup(self) -> None:
        out = (self._conda("env", "export", "--name", self.name)).stdout
        if out != self.environment.read_bytes():
            if f"\n{self.name} ".encode() in self._conda("env", "list").stdout:
                self._conda("env", "remove", "--name", self.name)
            self._conda(
                "env", "create", "--name", self.name, "--file", str(self.environment)
            )

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
        env: Mapping[str, str],
        cwd: Path,
    ) -> Tuple[List[str], Mapping[str, str], Path]:
        return (
            ["conda", "run", "--no-capture-output", "--name", self.name, *command],
            merge_envs(conda_env, env),
            cwd,
        )


class PipenvEnvironment(Environment):
    def __init__(
        self,
        pipfile: Path,
    ) -> None:
        super().__init__()
        self.pipfile = pipfile
        self.pipenv_env = {
            "PATH": ":".join(
                [
                    str(which("pipenv").parent),
                ]
            ),
            "PIPENV_PIPFILE": str(self.pipfile),
        }

    def _pipenv(
        self,
        *cmd: str,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["pipenv", *cmd],
            env=merge_envs(os.environ, self.pipenv_env),
            check=True,
            capture_output=True,
        )

    def setup(self) -> None:
        self._pipenv("install", "--dev")

    def install(self, packages: Sequence[Union[str, Path]]) -> None:
        self._pipenv("install", *map(str, packages))

    def run(
        self,
        command: Sequence[str],
        env: Mapping[str, str],
        cwd: Path,
    ) -> Tuple[List[str], Mapping[str, str], Path]:
        return (
            ["pipenv", "run", *command],
            merge_envs(self.pipenv_env, env),
            cwd,
        )


poetry_env = {
    "PATH": ":".join(
        [
            str(which("poetry").parent),
        ]
    ),
}


class PoetryEnvironment(Environment):
    def __init__(self, pyproject: Path) -> None:
        super().__init__()
        self.pyproject = pyproject

    @staticmethod
    def has_poetry_pyproject(path: Path) -> bool:
        if (path / "pyproject.toml").exists():
            pyproject_spec = toml.loads((path / "pyproject.toml").read_text())
            build_backend = pyproject_spec.get("build-system", {}).get(
                "build-backend", None
            )
            return build_backend in {
                "poetry.core.masonry.api",
                "poetry.masonry.api",
            }
        else:
            return False

    def _poetry(self, *cmd: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["poetry", *cmd],
            cwd=self.pyproject.parent,
            check=True,
            capture_output=True,
        )

    def setup(self) -> None:
        self._poetry("install")

    def install(self, packages: Sequence[Union[str, Path]]) -> None:
        real_packages = [
            str(relative_to(package, self.pyproject.parent))
            if isinstance(package, Path)
            else package
            if isinstance(package, str)
            else raise_(TypeError())
            for package in packages
        ]
        self._poetry("run", "python", "-m", "pip", "install", *real_packages)

    def run(
        self,
        command: Sequence[str],
        env: Mapping[str, str],
        cwd: Path,
    ) -> Tuple[List[str], Mapping[str, str], Path]:
        return (
            ["poetry", "run", "env", "--chdir", str(cwd), *command],
            env,
            self.pyproject.parent,
        )


class VirtualEnv(Environment):
    def __init__(
        self,
        env_dir: Path,
        requirements: Sequence[str] = (),
        requirements_files: Sequence[Path] = (),
        requirements_cwd: Optional[Path] = None,
    ) -> None:
        self.env_dir = env_dir.resolve()
        self.requirements = requirements
        self.requirements_files = requirements_files
        self.requirements_cwd = requirements_cwd
        self.env_vars = {
            "PATH": ":".join(
                [
                    str(self.env_dir / "bin"),
                ]
            ),
            "VIRTUAL_ENV": str(self.env_dir),
            "PYTHONNOUSERSITE": "true",
        }

    @staticmethod
    def from_pipfile_lock(env_dir: Path, pipenv_lock: Path) -> VirtualEnv:
        lockfile = json.loads(pipenv_lock.read_text())
        requirements = []
        for name, info in (lockfile["default"] | lockfile["develop"]).items():
            requirements.append(name + info.get("version", ""))
        return VirtualEnv(
            env_dir,
            requirements=requirements,
        )

    def setup(self) -> None:
        if not self.env_dir.exists():
            self.env_dir.mkdir(parents=True)
            venv.create(self.env_dir, with_pip=True)
        path_proc = self._run_in_venv(
            "python", "-c" "import sys; print(sys.executable)"
        )
        assert Path(path_proc.stdout.strip().decode()) == self.env_dir / "bin/python"
        args = [
            "python",
            "-m",
            "pip",
            "install",
            *itertools.chain.from_iterable(
                [("-r", str(file)) for file in self.requirements_files]
            ),
            *self.requirements,
        ]
        self._run_in_venv(*args, cwd=self.requirements_cwd)

    def _run_in_venv(
        self,
        *cmd: str,
        cwd: Optional[Path] = None,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            cmd,
            check=True,
            env=merge_envs(os.environ, self.env_vars),
            capture_output=True,
            cwd=cwd,
        )

    def install(
        self,
        packages: Sequence[Union[str, Path]],
        cwd: Optional[Path] = None,
    ) -> None:
        if packages:
            self._run_in_venv(
                "python", "-m", "pip", "install", *map(str, packages), cwd=cwd
            )

    def run(
        self,
        command: Sequence[str],
        env: Mapping[str, str],
        cwd: Path,
    ) -> Tuple[List[str], Mapping[str, str], Path]:
        return (
            list(command),
            merge_envs(self.env_vars, env),
            cwd,
        )


class EnvironmentChooser(Protocol):
    def choose(self, repo: Repo) -> Optional[Environment]:
        raise NotImplementedError


class StaticEnvironmentChooser(EnvironmentChooser):
    def __init__(self, environment: Environment) -> None:
        self.environment = environment

    def choose(self, repo: Repo) -> Optional[Environment]:
        return self.environment


class SmartEnvironmentChooser(EnvironmentChooser):
    def __init__(self, venv_location: Path) -> None:
        self.venv_location = venv_location

    def choose(self, repo: Repo) -> Optional[Environment]:
        if False:
            pass
        elif (repo.dir / "setup.py").exists():
            requirements = ["--editable", f"{repo.dir}[dev,test]"]
            return VirtualEnv(
                self.venv_location / repo.name,
                requirements=requirements,
                requirements_cwd=repo.dir,
            )
        elif (repo.dir / "Pipfile.lock").exists():
            pipfile_lock = repo.dir / "Pipfile.lock"
            return VirtualEnv.from_pipfile_lock(
                self.venv_location / repo.name,
                pipfile_lock,
            )
            # PipenvEnvironment might require a Python which is different than the current one.
            # Virtualenv has no such restriction.
            # I expect the Python interpreter to be backwards compatible, so running 3.7 code in 3.9 interpreter should work.
            # return PipenvEnvironment(repo.dir / "Pipfile")
        elif (repo.dir / "environment.yaml").exists():
            return CondaEnvironment(repo.name, repo.dir / "environment.yaml")
        elif (repo.dir / "environment.yml").exists():
            return CondaEnvironment(repo.name, repo.dir / "environment.yml")
        elif PoetryEnvironment.has_poetry_pyproject(repo.dir):
            return PoetryEnvironment(repo.dir / "pyproject.toml")
        elif list(repo.dir.glob("*requirements*.txt")):
            requirements_files = list(repo.dir.glob("*requirements*.txt"))
            return VirtualEnv(
                self.venv_location / repo.name,
                requirements_files=requirements_files,
                requirements_cwd=repo.dir,
            )
        else:
            return None
