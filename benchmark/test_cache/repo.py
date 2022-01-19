from abc import ABC
import asyncio
import datetime
from pathlib import Path
import shlex
import subprocess
import sys
from typing import List, Optional, Protocol, Tuple, cast

from charmonium.async_subprocess import run as async_run

ROOT = Path(__file__).parent.parent

CACHE_PATH = ROOT / ".cache/repos"


class Repo(ABC):
    def __init__(
            self,
            name: str,
            dir: Path,
            display_url: str,
            patch: Optional[str] = None,
            patch_cmds: List[List[str]] = [],
    ) -> None:
        self.name = name
        self.dir = dir
        self.display_url = display_url
        self.patch = patch
        self.patch_cmds = patch_cmds

    async def _setup(self) -> None:
        raise NotImplementedError()

    def apply_patch(self) -> None:
        for patch_cmd in self.patch_cmds:
            proc = subprocess.run(
                patch_cmd,
                cwd=self.dir,
                capture_output=True,
            )
            sys.stderr.buffer.write(proc.stderr)
            if proc.returncode != 0:
                sys.stdout.buffer.write(proc.stdout)
                raise RuntimeError(f"'{shlex.join(patch_cmd)}' returned {proc.returncode}")
        if self.patch is not None:
            cmd = [
                    "patch",
                    "--quiet",
                    "--strip=1",
                    f"--directory={self.dir!s}",
                    f"--input=/dev/stdin",
                ]
            proc = subprocess.run(
                cmd,
                input=self.patch.encode(),
                capture_output=True,
            )
            sys.stderr.buffer.write(proc.stderr)
            if proc.returncode != 0:
                sys.stdout.buffer.write(proc.stdout)
                raise RuntimeError(f"'{shlex.join(cmd)}' returned {proc.returncode}")

    async def setup(self) -> None:
        await self._setup()
        self.apply_patch()

    def _checkout(self, commit: str) -> Tuple[str, datetime.datetime]:
        raise NotImplementedError()

    def checkout(self, commit: str) -> Tuple[str, datetime.datetime]:
        ret = self._checkout(commit)
        self.apply_patch()
        return ret

    dir: Path
    name: str

class GitRepo(Repo):
    def __init__(
        self,
        *,
        name: str,
        url: str,
        display_url: str,
        patch: Optional[str] = None,
        patch_cmds: List[List[str]] = [],
        initial_commit: Optional[str] = None,
    ) -> None:
        super().__init__(
            name=name,
            dir=CACHE_PATH / name,
            display_url=display_url,
            patch=patch,
            patch_cmds=patch_cmds,
        )
        self.url = url
        self.initial_commit = initial_commit

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
        if self.initial_commit:
            await async_run(
                ["git", "checkout", self.initial_commit],
                cwd=self.dir,
                check=True,
            )

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
