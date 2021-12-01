from __future__ import annotations

from tqdm import tqdm  # type: ignore
import asyncio
import collections
import datetime
from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
from typing import Any, Callable, Dict, List, Tuple, Type, TypeVar, Mapping

from .data import Action, Repo, repos

from charmonium.cache import memoize, MemoizedGroup, DirObjStore
from charmonium.determ_hash import determ_hash


root = Path(__file__).parent.parent


group = MemoizedGroup(obj_store=DirObjStore(root / ".cache/functions"))

import logging
logger = logging.getLogger("charmonium.freeze")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.FileHandler("freeze.log"))

@dataclass
class FuncCallProfile:
    name: str
    args: int
    ret: int
    hit: bool
    outer_function: float
    hash: float = 0
    inner_function: float = 0
    serialize: float = 0
    obj_store: float = 0
    obj_load: float = 0
    deserialize: float = 0

    @classmethod
    def empty(Class: Type[FuncCallProfile]) -> FuncCallProfile:
        return Class(
            name="unknown",
            args=0,
            ret=0,
            hit=False,
            outer_function=0,
        )

    @property
    def misc_hit_overhead(self) -> float:
        if not self.hit:
            raise ValueError("Can't compute hit overhead for a miss.")
        else:
            return self.outer_function - sum([self.hash, self.obj_load, self.deserialize])

    @property
    def misc_miss_overhead(self) -> float:
        if not self.hit:
            raise ValueError("Can't compute miss overhead for a hit.")
        else:
            return self.outer_function - sum([self.hash, self.inner_function, self.serialize, self.obj_store])

    @property
    def total_overhead(self) -> float:
        if self.hit:
            return self.outer_function
        else:
            return self.outer_function - self.inner_function

@dataclass
class ExecutionProfile:
    func_calls: List[FuncCallProfile]
    total_time: float
    stdout: int
    success: bool
    index_read: float = 0
    index_write: float = 0
    cascading_delete: float = 0
    evict: float = 0
    remove_orphan: float = 0

    @classmethod
    def empty(Class: Type[ExecutionProfile]) -> ExecutionProfile:
        return Class(
            func_calls=[],
            total_time=0,
            stdout=0,
            success=False,
        )

    @property
    def function_overhead(self) -> float:
        return sum([
            func_call.total_overhead
            for func_call in self.func_calls
        ])
    @property
    def process_overhead(self) -> float:
        return sum([
            self.index_read,
            self.index_write,
            self.cascading_delete,
            self.evict,
            self.remove_orphan
        ])

@dataclass
class CommitResult:
    commit: str
    orig: ExecutionProfile
    memo: ExecutionProfile
    memo2: ExecutionProfile


def parse_call_log(log_path: Path) -> Tuple[List[FuncCallProfile], Mapping[str, Any]]:
    lst = []
    with (log_path).open() as log:
        for line in log:
            record = json.loads(line)
            lst.append(FuncCallProfile(
                name=record["name"],
                args=record["args"],
                ret=record["ret"],
                hit=False,
                hash=record["hash"],
                outer_function=record["outer_function"],
                inner_function=record["inner_function"],
            ))
    return lst, {}

def parse_perf_log(log_path: Path) -> Tuple[List[FuncCallProfile], Mapping[str, Any]]:
    calls: Mapping[int,  FuncCallProfile] = collections.defaultdict(FuncCallProfile.empty)
    process_kwargs: Dict[str, float] = collections.defaultdict(lambda: 0)
    with log_path.open() as perf_log:
        for line in perf_log:
            record = json.loads(line)
            if "call_id" in record:
                if "name" in record:
                    calls[record["call_id"]].name = record["name"]
                if "hit" in record:
                    calls[record["call_id"]].hit = record["hit"]
                if "duration" in record:
                    calls[record["call_id"]].__dict__[record["event"]] = record["duration"]
            else:
                process_kwargs[record["event"]] += record["duration"]
    return list(calls.values()), process_kwargs


log_dir = Path("/tmp/log")

def run_once(repo: Repo, action: Action, memoize: bool = False) -> ExecutionProfile:
    start = datetime.datetime.now()
    stdout, success = action.run(
        repo=repo,
        env_override={
            "CHARMONIUM_CACHE": "enable",
            "CHARMONIUM_CACHE_PERF_LOG": str(log_dir / "perf.log"),
        } if memoize else {
            "FUNCTION_CALLS": str(log_dir / "calls.log"),
        },
    )
    stop = datetime.datetime.now()
    calls, kwargs = parse_perf_log(log_dir / "perf.log") if memoize else parse_call_log(log_dir / "calls.log")
    return ExecutionProfile(
        func_calls=calls,
        success=success,
        total_time=(stop - start).total_seconds(),
        stdout=determ_hash(stdout),
        **kwargs
    )

@memoize(group=group)
def get_commit_result(commit: str, repo: Repo, action: Action) -> CommitResult:
    repo.checkout(commit)
    if log_dir.exists():
        shutil.rmtree(log_dir)
    log_dir.mkdir(parents=True)

    orig = run_once(repo, action, False)

    if orig.success:
        memo = run_once(repo, action, True)
        memo2 = run_once(repo, action, True)
    else:
        memo = ExecutionProfile.empty()
        memo2 = ExecutionProfile.empty()

    return CommitResult(
        commit=commit,
        orig=orig,
        memo=memo,
        memo2=memo,
    )


@memoize(group=group)
def get_repo_result(repo: Repo, action: Action) -> List[CommitResult]:
    commits = repo.get_commits()
    return [
        get_commit_result(commit, repo, action)
        for commit in tqdm(commits, total=len(commits), desc="Testing commit")
    ]


async def test_cache() -> List[Tuple[Repo, List[CommitResult]]]:
    await asyncio.gather(*[
        repo.setup()
        for repo, _ in tqdm(repos, total=len(repos), desc="Repo setup")
    ])
    await asyncio.gather(*[
        action.setup(repo)
        for repo, action in tqdm(repos, total=len(repos), desc="Action setup")
    ])
    return [
        (repo, get_repo_result(repo, action))
        for repo, action in tqdm(repos, total=len(repos), desc="Testing repo")
    ]
