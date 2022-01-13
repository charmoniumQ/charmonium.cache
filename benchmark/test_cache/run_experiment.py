from __future__ import annotations

import asyncio
import collections
import datetime
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple, Type
import logging

from charmonium.cache import DirObjStore, MemoizedGroup, memoize
from charmonium.determ_hash import determ_hash
from tqdm import tqdm  # type: ignore

from .environment import Environment
from .repo import Repo
from .action import Action

ROOT = Path(__file__).parent.parent


group = MemoizedGroup(obj_store=DirObjStore(ROOT / ".cache/functions"))

hash_logger = logging.getLogger("charmonium.freeze")
hash_logger.setLevel(logging.DEBUG)
hash_logger.addHandler(logging.FileHandler("freeze.log"))
hash_logger.propagate = False


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
            return self.outer_function - sum(
                [self.hash, self.obj_load, self.deserialize]
            )

    @property
    def misc_miss_overhead(self) -> float:
        if not self.hit:
            raise ValueError("Can't compute miss overhead for a hit.")
        else:
            return self.outer_function - sum(
                [self.hash, self.inner_function, self.serialize, self.obj_store]
            )

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
    empty: bool = False
    hash: float = 0

    @classmethod
    def create_empty(Class: Type[ExecutionProfile]) -> ExecutionProfile:
        return Class(
            func_calls=[],
            total_time=0,
            stdout=0,
            success=False,
            empty=True,
        )

    @property
    def function_overhead(self) -> float:
        return sum([func_call.total_overhead for func_call in self.func_calls])

    @property
    def process_overhead(self) -> float:
        return sum(
            [
                self.index_read,
                self.index_write,
                self.cascading_delete,
                self.evict,
                self.remove_orphan,
            ]
        )


@dataclass
class CommitResult:
    diff: str
    date: datetime.datetime
    commit: str
    orig: ExecutionProfile
    memo: ExecutionProfile
    memo2: ExecutionProfile


def parse_unmemoized_log(log_path: Path) -> Tuple[List[FuncCallProfile], Mapping[str, Any]]:
    lst = []
    with (log_path).open() as log:
        for line in log:
            record = json.loads(line)
            lst.append(
                FuncCallProfile(
                    name=record["name"],
                    args=record["args"],
                    ret=record["ret"],
                    hit=False,
                    hash=record["hash"],
                    outer_function=record["outer_function"],
                    inner_function=record["inner_function"],
                )
            )
    return lst, {}


def parse_memoized_log(log_path: Path) -> Tuple[List[FuncCallProfile], Mapping[str, Any]]:
    calls: Mapping[int, FuncCallProfile] = collections.defaultdict(
        FuncCallProfile.empty
    )
    process_kwargs: Dict[str, float] = collections.defaultdict(lambda: 0)
    with log_path.open() as perf_log:
        for line in perf_log:
            record = json.loads(line)
            if "call_id" in record:
                if "name" in record:
                    calls[record["call_id"]].name = record["name"]
                if "hit" in record:
                    calls[record["call_id"]].hit = record["hit"]
                if "duration" in record and "event" in record:
                    calls[record["call_id"]].__dict__[record["event"]] = record[
                        "duration"
                    ]
            elif "duration" in record and "event" in record:
                process_kwargs[record["event"]] += record["duration"]
            else:
                print(f"Unknown record {record}")
    return list(calls.values()), process_kwargs


log_dir = Path("/tmp/log")


def run_once(
        repo: Repo,
        environment: Environment,
        action: Action,
        memoize: bool
) -> ExecutionProfile:
    if log_dir.exists():
        shutil.rmtree(log_dir)
    log_dir.mkdir(parents=True)
    perf_log = log_dir / "perf.log"
    start = datetime.datetime.now()
    stdout, success = action.run(
        repo=repo,
        environment=environment,
        env_override={
            "CHARMONIUM_CACHE_DISABLE": "" if memoize else "1",
            "CHARMONIUM_CACHE_PERF_LOG": str(perf_log),
        },
    )
    stop = datetime.datetime.now()
    if memoize:
        calls, kwargs = parse_memoized_log(perf_log)
    else:
        # no profiling informatoin
        calls = []
        kwargs = {}
    return ExecutionProfile(
        func_calls=calls,
        success=success,
        total_time=(stop - start).total_seconds(),
        stdout=globals()["determ_hash"](stdout),
        **kwargs
    )


@memoize(group=group)
def get_commit_result(commit: str, repo: Repo, environment: Environment, action: Action) -> CommitResult:
    print(f"repo.checkout({commit!r})")
    diff, date = repo.checkout(commit)

    # print("environment.install(repo.dir)")
    # asyncio.run(environment.install(repo, [repo.dir]))
    print("action.comit_setup(repo, environment)")
    action.commit_setup(repo, environment)

    print("run memoized")
    memo = run_once(repo, environment, action, True)

    if memo.success:
        print("run memoized again")
        memo2 = run_once(repo, environment, action, True)
    else:
        memo2 = ExecutionProfile.create_empty()

    if memo2.success:
        print("run unmodified")
        orig = run_once(repo, environment, action, False)
    else:
        orig = ExecutionProfile.create_empty()

    print("done")

    return CommitResult(
        diff=diff,
        date=date,
        commit=commit,
        orig=orig,
        memo=memo,
        memo2=memo,
    )


@dataclass
class RepoResult:
    repo: Repo
    action: Action
    environment: Environment
    commit_results: List[CommitResult]

@memoize(group=group)
def get_repo_result(
        repo: Repo,
        environment: Environment,
        action: Action,
) -> RepoResult:
    commits = repo.get_commits()
    return RepoResult(
        repo=repo,
        environment=environment,
        action=action,
        commit_results=[
            get_commit_result(commit, repo, environment, action)
            for commit in tqdm(commits, total=len(commits), desc="Testing commit")
        ],
    )


@memoize(group=group)
def run_experiment(
        repo_env_actions: List[Tuple[Repo, Environment, Action]],
) -> List[RepoResult]:

    async def setup(repo_env_action: Tuple[Repo, Environment, Action]) -> None:
        repo, env, action = repo_env_action
        print(f"Setting up repo {repo.name}")
        await repo.setup()
        cache_dir = repo.dir / ".cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        print(f"Setting up env {repo.name}")
        await env.setup(repo)
        # print(f"Installing charmonium.cache")
        # await env.install(repo, ["https://github.com/charmoniumQ/charmonium.cache/archive/main.zip"])
        print(f"Setting up action {repo.name}")
        await action.setup(repo, env)
        print(f"Ready for {repo.name}")

    async def setup_all(repo_env_actions: List[Tuple[Repo, Environment, Action]]) -> None:
        await asyncio.gather(
            *[
                setup(repo_env_action)
                for repo_env_action in tqdm(repo_env_actions, total=len(repo_env_actions), desc="Repo setup")
            ]
        )

    asyncio.run(setup_all(repo_env_actions))

    return [
        get_repo_result(repo, env, action)
        for repo, env, action in tqdm(repo_env_actions, total=len(repo_env_actions), desc="Repo setup")
    ]
