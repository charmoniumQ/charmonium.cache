from __future__ import annotations
from abc import ABC
import datetime
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import List, Optional, Protocol, Tuple, Callable, cast

ROOT = Path(__file__).parent.parent

CACHE_PATH = ROOT / ".repos"


class Repo(ABC):
    def __init__(
            self,
            name: str,
            dir: Path,
            display_url: str,
            patch: Optional[str] = None,
            patch_cmds: List[List[str]] = [],
            setup_func: Optional[Callable[[Repo], None]] = None,
            patch_func: Optional[Callable[[Repo], None]] = None,
    ) -> None:
        self.name = name
        self.dir = dir
        self.display_url = display_url
        self.patch = patch
        self.patch_cmds = patch_cmds
        self.setup_func = setup_func
        self.patch_func = patch_func

    def clean(self) -> None:
        self._clean()
        self.apply_patch()

    def _clean(self) -> None:
        raise NotImplementedError()

    def _setup(self) -> None:
        raise NotImplementedError()

    def apply_patch(self) -> None:
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
        if self.patch_func:
            self.patch_func(self)

    def setup(self) -> None:
        self._setup()
        self.apply_patch()
        if self.setup_func:
            self.setup_func(self)

    def _checkout(self, commit: str) -> Tuple[bytes, datetime.datetime]:
        raise NotImplementedError()

    def checkout(self, commit: str) -> Tuple[bytes, datetime.datetime]:
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
        initial_commit: Optional[str] = None,
        setup_func: Optional[Callable[[Repo], None]] = None,
        patch_func: Optional[Callable[[Repo], None]] = None,
    ) -> None:
        super().__init__(
            name=name,
            dir=CACHE_PATH / name,
            display_url=display_url,
            patch=patch,
            setup_func=setup_func,
            patch_func=patch_func,
        )
        self.url = url
        self.initial_commit = initial_commit

    def _setup(self) -> None:
        self.dir.mkdir(exist_ok=True, parents=True)
        if not list(self.dir.iterdir()):
            subprocess.run(["git", "clone", "--recursive", self.url, "."], cwd=self.dir, check=True, capture_output=True)
        else:
            subprocess.run(
                ["git", "restore", "--", "."],
                cwd=self.dir,
                check=True,
                capture_output=True,
            )
        if self.initial_commit:
            subprocess.run(
                ["git", "checkout", self.initial_commit],
                cwd=self.dir,
                check=True,
                capture_output=True,
            )

    def _clean(self) -> None:
        subprocess.run(
            ["git", "clean", "--force", "-d", "-x", "."],
            cwd=self.dir,
            check=True,
            capture_output=True,
        )

    def interesting_commits(self, path: Path, min_diff: int) -> List[str]:
        """
for commit in $(git log --pretty=%h .); do
    total=0
    total+=$(git show --numstat --pretty='' $commit | cut --fields=1 | tr -d - | python -c "import sys; print(sum([int(line.strip()) for line in sys.stdin if line.strip()]))")
    total+=$(git show --numstat --pretty='' $commit | cut --fields=2 | tr -d - | python -c "import sys; print(sum([int(line.strip()) for line in sys.stdin if line.strip()]))")
    echo $total $commit
done | sort --numeric-sort > log
        """
        commits = subprocess.run(
            ["git", "log", "--pretty=%h", str(path)],
            cwd=self.dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip().split("\n")
        def filter_pred(commit: str) -> bool:
            total_changed = 0
            for line in subprocess.run(
                ["git", "show", "--numstat", "--pretty=", commit],
                cwd=self.dir,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip().split("\n"):
                if m := re.match("(\\d+)\t(\\d+)\t", line):
                    total_changed += int(m.group(1)) + int(m.group(2))
            return total_changed >= min_diff
        return list(filter(filter_pred, commits))

    def _checkout(self, commit: str) -> Tuple[bytes, datetime.datetime]:
        subprocess.run(
            ["git", "restore", "--", "."],
            cwd=self.dir,
            check=True,
        )
        subprocess.run(
            ["git", "submodule", "update", "--recursive"],
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
