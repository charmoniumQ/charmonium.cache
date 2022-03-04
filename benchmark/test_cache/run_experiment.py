from __future__ import annotations

import collections
from dataclasses import dataclass
import datetime
import json
import itertools
import logging
import subprocess
from pathlib import Path
import pickle
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Mapping, Tuple, Type, Optional, Sequence, cast
import warnings

import charmonium.time_block as ch_time_block
#from charmonium.cache import MemoizedGroup, memoize
from charmonium.determ_hash import determ_hash
from tqdm import tqdm  # type: ignore

from .environment import Environment, EnvironmentChooser
from .repo import Repo, CommitChooser
from .util import merge

ROOT = Path(__file__).parent.parent


# group = MemoizedGroup(
#     size="4GiB",
#     fine_grain_persistence=True,
# )

# hash_logger = logging.getLogger("charmonium.freeze")
# hash_logger.setLevel(logging.DEBUG)
# hash_logger.addHandler(logging.FileHandler("freeze.log"))
# hash_logger.propagate = False

# ops_logger = logging.getLogger("charmonium.cache.ops")
# ops_logger.setLevel(logging.DEBUG)
# ops_logger.addHandler(logging.FileHandler("ops.log"))
# ops_logger.propagate = False

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
    func_calls: Sequence[FuncCallProfile]
    cpu_time: float
    wall_time: float
    output: str
    log: str
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
            cpu_time=0,
            wall_time=0,
            output="",
            log="",
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

def parse_unmemoized_log(log_path: Path) -> Tuple[Sequence[FuncCallProfile], Mapping[str, Any]]:
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


def parse_memoized_log(log_path: Path) -> Tuple[Sequence[FuncCallProfile], Mapping[str, Any]]:
    calls: Mapping[int, FuncCallProfile] = collections.defaultdict(
        FuncCallProfile.empty
    )
    process_kwargs: Dict[str, float] = collections.defaultdict(lambda: 0)
    with log_path.open() as perf_log:
        for line_no, line in enumerate(perf_log):
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
                warnings.warn(f"Unknown record {record} on line {line_no} of {perf_log}.")
    return list(calls.values()), process_kwargs


log_dir = Path("/tmp/log")

@ch_time_block.decor(print_start=False)
def run_once(
        repo: Repo,
        environment: Environment,
        cmd: Sequence[str],
        memoize: bool
) -> ExecutionProfile:
    if log_dir.exists():
        shutil.rmtree(log_dir)
    log_dir.mkdir(parents=True)
    perf_log = log_dir / "perf.log"
    proc = environment.run(
        cmd,
        cwd=repo.dir,
        env_override={
            "CHARMONIUM_CACHE_DISABLE": "" if memoize else "1",
            "CHARMONIUM_CACHE_PERF_LOG": str(perf_log),
        },
    )
    sys.stderr.buffer.write(proc.stderr)
    # times = psutil.Process().cpu_times(proc.pid)
    if perf_log.exists():
        calls, kwargs = parse_memoized_log(perf_log)
    else:
        # no profiling informatoin
        calls = []
        kwargs = {}

    log_path = repo.dir / "log"
    log = log_path.read_text() if log_path.exists() else ""
    log += proc.stderr.decode() + proc.stdout.decode()

    output_path = repo.dir / "output"
    output = output_path.read_text() if output_path.exists() else ""

    return ExecutionProfile(
        func_calls=calls,
        success=proc.returncode == 0,
        wall_time=proc.wall_time,
        cpu_time=proc.cpu_time,
        log=log,
        output=output,
        **kwargs,
    )

@dataclass
class CommitResult:
    diff: bytes
    date: datetime.datetime
    commit: str
    executions: Mapping[str, ExecutionProfile]

    @staticmethod
    def from_commit(repo: Repo, commit: str, executions: Mapping[str, ExecutionProfile]) -> CommitResult:
        diff, date = repo.info(commit)
        return CommitResult(diff, date, commit, executions)

def run_many(
        repo: Repo,
        environment: Environment,
        commits: Sequence[str],
        command: Sequence[str],
        memoize: bool,
        short_circuit: bool,
) -> Sequence[ExecutionProfile]:
    repo.clean()

    if memoize:
        cache_dir = repo.dir / ".cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        conftest = repo.dir / "conftest.py"
        conftest.touch(exist_ok=True)
        conftest.write_text("\n\n".join([
            conftest.read_text(),
            Path("that_conftest.py").read_text(),
        ]))

    executions = []
    for commit in commits:
        execution = run_once(repo, environment, command, memoize)
        executions.append(execution)
        if short_circuit and not execution.success:
            break

    return executions

manual_cache = Path(".manual_cache")
def get_repo_result(
        repo: Repo,
        commit_chooser: CommitChooser,
        environment_chooser: EnvironmentChooser,
        command: Sequence[str],
) -> RepoResult:
    manual_cache.mkdir(exist_ok=True)
    cache_dest = manual_cache / f"{repo.name}.pkl"
    if cache_dest.exists():
        return cast(RepoResult, pickle.loads(cache_dest.read_bytes()))
    else:
        ret = get_repo_result2(repo, commit_chooser, environment_chooser, command)
        cache_dest.write_bytes(pickle.dumps(ret))
        return ret

@ch_time_block.decor(print_start=False)
def get_repo_result2(
        repo: Repo,
        commit_chooser: CommitChooser,
        environment_chooser: EnvironmentChooser,
        command: Sequence[str],
) -> RepoResult:
    print(repo.name)
    with ch_time_block.ctx("repo.setup()", print_start=False):
        repo.setup()
    environment = environment_chooser.choose(repo)
    if environment is None:
        warning = f"{environment_chooser!s} could not choose an environment."
        warnings.warn(warning)
        return RepoResult(
            repo=repo,
            environment=environment,
            command=command,
            commit_results=[],
            warnings=[warning],
        )
    else:
        try:
            with ch_time_block.ctx("environment.setup()", print_start=False):
                environment.setup()
                packages = ["https://github.com/charmoniumQ/charmonium.cache/tarball/main"]
                proc = environment.run(
                    ["python", "-c", "import pytest"],
                    cwd=None,
                )
                if proc.returncode != 0:
                    packages.append("pytest")
                environment.install(packages)
        except subprocess.CalledProcessError as e:
            warning = "\n".join([
                f"{environment!s} could not setup {repo!s}.",
                "$ " + shlex.join(e.cmd),
                str(e.stdout),
                str(e.stderr),
            ])
            warnings.warn(warning)
            return RepoResult(
                repo=repo,
                environment=None,
                command=command,
                commit_results=[],
                warnings=[warning],
            )
        else:
            commits = commit_chooser.choose(repo)

            orig_executions = run_many(repo, environment, commits, command, memoize=False, short_circuit=False)
            #working_commits = commits[:len(orig_executions)]
            memo_executions = run_many(repo, environment, commits, command, memoize=True, short_circuit=False)

            commit_results = [
                CommitResult.from_commit(repo, commit, {
                    "orig": orig_execution,
                    "memo": memo_execution,
                })
                for commit, orig_execution, memo_execution in zip(commits, orig_executions, memo_executions)
            ]

            return RepoResult(
                repo=repo,
                environment=environment,
                command=command,
                commit_results=commit_results,
                warnings=[],
            )

@dataclass
class RepoResult:
    repo: Repo
    command: Sequence[str]
    environment: Optional[Environment]
    commit_results: Sequence[CommitResult]
    warnings: Sequence[str]

def run_experiment(
        repos: Sequence[Tuple[Repo, CommitChooser, EnvironmentChooser, Sequence[str]]],
) -> Sequence[RepoResult]:
    return [
        get_repo_result(*repo_info)
        for repo_info in tqdm(repos, total=len(repos), desc="Repos")
    ]
