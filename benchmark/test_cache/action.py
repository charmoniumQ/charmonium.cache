import ast
from typing import Protocol, List, Mapping, Optional, Tuple, Iterable
from pathlib import Path
import json
import shlex
import sys

from charmonium.async_subprocess import run as async_run

from .repo import Repo
from .environment import Environment
from .add_memoization import add_memoization

from .ipynb_to_script import ipynb_to_cells, cells_to_stmts

def stmt_to_str(stmt: ast.stmt) -> str:
    stmt.lineno = 0
    try:
        return ast.unparse(stmt)
    except AttributeError as e:
        raise RuntimeError(ast.dump(stmt)) from e

def stmts_to_str(stmts: Iterable[ast.stmt]) -> str:
    return "\n\n".join(map(stmt_to_str, stmts))

def write_text(path: Path, text: str) -> None:
    path.write_text(text)

def read_text(path: Path) -> str:
    return path.read_text()

class Action(Protocol):
    async def setup(self, repo: Repo, environment: Environment) -> None: ...
    def commit_setup(self, repo: Repo, environment: Environment) -> None: ...
    def run(
            self,
            repo: Repo,
            environment: Environment,
            env_override: Optional[Mapping[str, str]] = None,
    ) -> Tuple[bytes, bool]: ...

class IpynbAction(Action):
    def __init__(self, notebooks: List[Path]) -> None:
        self.notebooks = notebooks

    async def setup(self, repo: Repo, _: Environment) -> None:
        pass

    def commit_setup(self, repo: Repo, _: Environment) -> None:
        for notebook in self.notebooks:
            write_text(
                repo.dir / notebook.with_suffix(".py"),
                stmts_to_str(
                    add_memoization(
                        cells_to_stmts(
                            ipynb_to_cells(
                                json.loads(
                                    read_text(
                                        repo.dir / notebook.with_suffix(".ipynb")
                                    )
                                )
                            )
                        )
                    )
                ),
            )

    def run(
            self,
            repo: Repo,
            environment: Environment,
            env_override: Optional[Mapping[str, str]] = None,
    ) -> Tuple[bytes, bool]:
        stdout = b""
        success = 0
        for notebook in self.notebooks:
            proc = environment.run(
                ["python", str(repo.dir / notebook.with_suffix(".py"))],
                cwd=(repo.dir / notebook).parent,
            )
            sys.stderr.buffer.write(proc.stderr)
            stdout += proc.stdout
            success |= proc.returncode
            if success != 0:
                break
        return stdout, success == 0

class CommandAction(Action):
    def __init__(
            self,
            setup_cmds: List[List[str]] = [],
            commit_setup_cmds: List[List[str]] = [],
            run_cmds: List[List[str]] = [],
    ) -> None:
        self.setup_cmds = setup_cmds
        self.commit_setup_cmds = commit_setup_cmds
        self.run_cmds = run_cmds

    async def setup(self, repo: Repo, environment: Environment) -> None:
        for cmd in self.setup_cmds:
            proc = environment.run(
                cmd,
                cwd=repo.dir,
            )
            sys.stderr.buffer.write(proc.stderr)

    def commit_setup(self, repo: Repo, environment: Environment) -> None:
        for cmd in self.commit_setup_cmds:
            proc = environment.run(
                cmd,
                cwd=repo.dir,
            )
            sys.stderr.buffer.write(proc.stderr)

    def run(
            self,
            repo: Repo,
            environment: Environment,
            env_override: Optional[Mapping[str, str]] = None,
    ) -> Tuple[bytes, bool]:
        stdout = b""
        success = 0
        for cmd in self.run_cmds:
            proc = environment.run(
                cmd,
                cwd=repo.dir,
                env_override=env_override,
            )
            sys.stderr.buffer.write(proc.stderr)
            stdout += proc.stderr + proc.stdout
            success |= proc.returncode
            if success != 0:
                break
        return stdout, success == 0
