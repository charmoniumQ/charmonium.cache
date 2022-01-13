import subprocess
from abc import ABC
import asyncio
from pathlib import Path
import datetime
from typing import List, Optional, Protocol, Tuple, cast

from charmonium.async_subprocess import run as async_run

ROOT = Path(__file__).parent.parent

CACHE_PATH = ROOT / ".cache/repos"


class Repo(ABC):
    def __init__(
            self,
            name: str,
            dir: Path,
            patch: Optional[Path] = None,
    ) -> None:
        self.name = name
        self.dir = dir
        self.patch = patch

    async def _setup(self) -> None:
        raise NotImplementedError()

    async def apply_patch(self) -> None:
        if self.patch is not None:
            await async_run(
                [
                    "patch",
                    "--quiet",
                    "--strip=1",
                    f"--directory={self.dir!s}",
                    f"--input={self.patch!s}",
                ],
                check=True,
                capture_output=True,
            )

    async def setup(self) -> None:
        await self._setup()
        await self.apply_patch()

    def get_commits(self) -> List[str]:
        raise NotImplementedError()

    def _checkout(self, commit: str) -> Tuple[str, datetime.datetime]:
        raise NotImplementedError()

    def checkout(self, commit: str) -> Tuple[str, datetime.datetime]:
        ret = self._checkout(commit)
        asyncio.run(self.apply_patch())
        return ret

    dir: Path
    name: str

class GitRepo(Repo):
    def __init__(
        self,
        *,
        name: str,
        url: str,
        patch: Optional[Path] = None,
        start_commit: Optional[str] = None,
        stop_commit: Optional[str] = None,
        all_commits: Optional[List[str]] = None,
    ) -> None:
        super().__init__(name=name, dir=CACHE_PATH / name, patch=patch)
        self.url = url
        self.start_commit = start_commit
        self.stop_commit = stop_commit
        self.all_commits = all_commits
        self.commits: Optional[List[str]] = None

    async def _setup(self) -> None:
        self.dir.mkdir(exist_ok=True, parents=True)
        if not list(self.dir.iterdir()):
            await async_run(["git", "clone", "--recursive", self.url, "."], cwd=self.dir, check=True)
        else:
            await async_run(
                ["git", "restore", "--", "."],
                cwd=self.dir,
                check=True,
            )
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
        if self.all_commits is None:
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
            self.commits = proc.stdout.split("\n")[::-1]
        else:
            assert self.start_commit is None and self.stop_commit is None
            self.commits = self.all_commits
        await async_run(["git", "checkout", self.commits[0]], cwd=self.dir, check=True)

    def get_commits(self) -> List[str]:
        assert self.commits is not None
        return self.commits

    def _checkout(self, commit: str) -> Tuple[str, datetime.datetime]:
        subprocess.run(
            ["git", "restore", "--", "."],
            cwd=self.dir,
            check=True,
        )
        old_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        diff = subprocess.run(
            ["git", "diff", f"{old_commit}..{commit}"],
            cwd=self.dir,
            check=True,
            text=True,
            capture_output=True,
        ).stdout
        date_str = subprocess.run(
            ["git", "show", "--no-patch", "--format=%ci", commit],
            cwd=self.dir,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        date = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S  %z")
        subprocess.run(
            ["git", "checkout", commit], cwd=self.dir, check=True, capture_output=True
        )
        return diff, date
