from __future__ import annotations
from abc import ABC
import datetime
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import List, Optional, Protocol, Tuple, Callable, cast
from .util import BenchmarkError

ROOT = Path(__file__).parent.parent.resolve()

REPO_PATH = ROOT / ".repos"


class Repo(ABC):
    def __init__(
            self,
            name: str,
            url: str,
            dir: Path,
            display_url: str,
            patch: Optional[str] = None,
            patch_cmds: List[List[str]] = [],
            setup_func: Optional[Callable[[Repo], None]] = None,
            patch_func: Optional[Callable[[Repo], None]] = None,
    ) -> None:
        self.name = name
        self.url = url
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

    def setup(self, parent: Optional[Path] = None) -> None:
        if parent is not None:
            self.dir = parent / self.dir
        self._setup()
        self.apply_patch()
        if self.setup_func:
            self.setup_func(self)

    def _checkout(self, commit: str) -> None:
        raise NotImplementedError()

    def checkout(self, commit: str) -> None:
        self._checkout(commit)
        self.apply_patch()

    def info(slef, commit: str) -> Tuple[bytes, datetime.datetime]:
        raise NotImplementedError

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
        setup_func: Optional[Callable[[Repo], None]] = None,
        patch_func: Optional[Callable[[Repo], None]] = None,
    ) -> None:
        super().__init__(
            name=name,
            url=url,
            dir=REPO_PATH / name,
            display_url=display_url,
            patch=patch,
            setup_func=setup_func,
            patch_func=patch_func,
        )

    def __str__(self) -> str:
        return f"Repo({self.name!r}, {self.url!r}, ...)"

    def _setup(self) -> None:
        self.dir.mkdir(exist_ok=True, parents=True)
        if not list(self.dir.iterdir()):
            try:
                subprocess.run(
                    ["git", "clone", "--recursive", self.url, "."],
                    cwd=self.dir,
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                if e.stdout:
                    sys.stdout.buffer.write(e.stdout)
                if e.stderr:
                    sys.stderr.buffer.write(e.stderr)
                if e.output:
                    sys.stdout.buffer.write(e.output)
                raise e
        else:
            ref = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                cwd=self.dir,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            branch = ref.split("/")[-1]
            subprocess.run(
                ["git", "restore", "--", "."],
                cwd=self.dir,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "checkout", branch],
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

    def _checkout(self, commit: str) -> None:
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
        subprocess.run(
            ["git", "checkout", commit], cwd=self.dir, check=True, capture_output=True
        )

    def info(self, commit: str) -> Tuple[bytes, datetime.datetime]:
        date_str = subprocess.run(
            ["git", "show", "--no-patch", "--format=%ci", commit],
            cwd=self.dir,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        date = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S  %z")
        diff = subprocess.run(
            ["git", "show", "--format=", commit],
            cwd=self.dir,
            check=True,
            capture_output=True,
        ).stdout
        return diff, date

github_pattern = re.compile("https://github.com/[a-zA-Z0-9-.]+/(?P<name>[a-zA-Z0-9-.]+)")
class GitHubRepo(GitRepo):
    def __init__(
            self,
            url: str
    ) -> None:
        if url.endswith(".git"):
            url = url[:-4]
        parsed_url = github_pattern.match(url)
        if not parsed_url:
            raise BenchmarkError(f"{url!r} is does not match {github_pattern!r}.")
        super().__init__(
            name=parsed_url.group("name"),
            url=url,
            display_url=f"{url}/commit/{{commit}}",
            patch=None,
            setup_func=None,
            patch_func=None,
        )

class CommitChooser(Protocol):
    def choose(self, repo: Repo) -> List[str]: ...

class RecentCommitChooser(CommitChooser):
    def __init__(self, seed: str, n: int = 2) -> None:
        self.seed = seed
        self.n = n

    def choose(self, repo: Repo) -> List[str]:
        if isinstance(repo, GitRepo):
            subprocess.run(
                ["git", "checkout", self.seed],
                cwd=repo.dir,
                capture_output=True,
                check=True,
            )
            n = self.n
            cmd = ["git", "log", "--pretty=format:%H", "HEAD", f"^HEAD~{n - 1}"]
            while n > 0:
                commits_proc = subprocess.run(
                    cmd,
                    cwd=repo.dir,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if commits_proc.returncode != 0:
                    if "fatal: bad revision" in commits_proc.stderr:
                        n -= 1
                    else:
                        raise subprocess.CalledProcessError(
                            returncode=commits_proc.returncode,
                            cmd=cmd,
                            output=commits_proc.stdout + commits_proc.stderr,
                        )
                else:
                    break
            else:
                return [self.seed]
            commits = commits_proc.stdout.strip().split()[:n][:-1]
            return [*commits, self.seed]
        else:
            raise BenchmarkError(f"{self.__class__.__name__} doesn't know how to deal with {type(repo).__name__} as in {repo}.")
