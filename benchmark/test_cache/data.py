import os
import subprocess
from pathlib import Path
from typing import List, Optional, Protocol, Tuple, Mapping, cast
from urllib.parse import urlparse

from charmonium.async_subprocess import run as async_run

ROOT = Path(__file__).parent.parent

CACHE_PATH = ROOT / ".cache/repos"

RESOURCE_PATH = ROOT / "resources"

class Repo(Protocol):
    async def setup(self) -> None:
        ...

    def get_commits(self) -> List[str]:
        return []

    def checkout(self, commit: str) -> None:
        ...

    dir: Path


class Action(Protocol):
    async def setup(self, repo: Repo) -> None:
        ...

    def run(self, repo: Repo, env_override: Optional[Mapping[str, str]] = None) -> Tuple[bytes, bool]:
        ...


class GitRepo(Repo):
    def __init__(
        self,
        *,
        name: str,
        url: str,
        start_commit: Optional[str] = None,
        stop_commit: Optional[str] = None,
        all_commits: Optional[List[str]] = None,
    ) -> None:
        super().__init__()
        self.url = url
        self.name = name
        self.dir = CACHE_PATH / self.name
        self.start_commit = start_commit
        self.stop_commit = stop_commit
        self.all_commits = all_commits

    async def setup(self) -> None:
        self.dir.mkdir(exist_ok=True, parents=True)
        if not list(self.dir.iterdir()):
            await async_run(["git", "clone", self.url, "."], cwd=self.dir, check=True)
        else:
            await async_run(["git", "clean", "-fdx", "."], cwd=self.dir, check=True)
        proc = await async_run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=self.dir,
            check=True,
            capture_output=True,
            text=True,
        )
        branch = cast(str, proc.stdout).strip().split("/")[-1]
        await async_run(["git", "checkout", branch], cwd=self.dir, check=True)

    def get_commits(self) -> List[str]:
        if self.all_commits is not None:
            assert self.start_commit is None and self.stop_commit is None
            return self.all_commits
        else:
            proc = subprocess.run(
                [
                    "git",
                    "log",
                    "--pretty=format:%H",
                    self.stop_commit if self.stop_commit else "HEAD",
                    *(["^" + self.start_commit] if self.start_commit else []),
                ],
                cwd=self.dir,
                check=True,
                capture_output=True,
                text=True,
            )
            return proc.stdout.split("\n")

    def checkout(self, commit: str) -> None:
        subprocess.run(["git", "checkout", commit], cwd=self.dir, check=True, capture_output=True)


class CondaAction(Action):
    def __init__(self, *, name: str, install_repo: bool = False) -> None:
        super().__init__()
        self.name = name
        self.environment = RESOURCE_PATH / self.name / "environment.yaml"
        self.script = RESOURCE_PATH / self.name / "script.py"
        self.install_repo = install_repo

    async def setup(self, repo: Repo) -> None:
        # await async_run(
        #     [
        #         "conda-shell",
        #         "-c",
        #         f"conda env create --name {self.name} --file {self.environment}",
        #     ],
        #     check=True,
        #     capture_output=True,
        # )
        await async_run(
            [
                "conda-shell",
                "-c",
                f"conda run --name {self.name} pip install git+https://github.com/charmoniumQ/charmonium.cache/",
            ],
            check=True,
        )
        if self.install_repo:
            await async_run(
                [
                    "conda-shell",
                    "-c",
                    f"conda run --name {self.name} pip install --editable {repo.dir}",
                ],
                check=True,
            )

    def run(self, repo: Repo, env_override: Optional[Mapping[str, str]] = None) -> Tuple[bytes, bool]:
        proc = subprocess.run(
            ["conda-shell", "-c", f"conda run --name {self.name} python {self.script}"],
            check=False,
            cwd=repo.dir,
            env={
                **os.environ,
                **(env_override if env_override else {}),
            },
        )
        return proc.stdout, proc.returncode == 0


repos = [
    (
        GitRepo(
            name="exoplanet",
            url="https://github.com/exoplanet-dev/exoplanet.git",
            all_commits=[
                "a61076b173a32fc90f286176dc5f194395854e02",
                "9f7681301790276416c10f8139adb1b24f7a7d04",
                "10b4ec3a99f07f35ffa9a7abfef083399af2a2d2",
            ],
        ),
        CondaAction(
            name="exoplanet",
            install_repo=True,
        ),
    ),
]
