import ast
from typing import Protocol, List, Mapping, Optional, Tuple, Iterable
from pathlib import Path
import json
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
            this_stdout, this_success = environment.run(
                ["python", str(repo.dir / notebook.with_suffix(".py"))],
                cwd=(repo.dir / notebook).parent,
            )
            stdout += this_stdout
            success |= this_success
            if success != 0:
                break
        return stdout, success == 0
