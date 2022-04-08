from __future__ import annotations

import collections
import datetime
import itertools
import json
import logging
import os
import pickle
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import types
import warnings
import xml.etree.ElementTree
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Type, cast

import charmonium.time_block as ch_time_block
from benchexec import container  # type: ignore
from benchexec.runexecutor import RunExecutor  # type: ignore

# from charmonium.cache import MemoizedGroup, memoize
from charmonium.determ_hash import determ_hash
from tqdm import tqdm

from .environment import Environment, EnvironmentChooser
from .repo import CommitChooser, Repo
from .util import combine_cmd, runexec_catch_signals, capture_logs

ROOT = Path(__file__).resolve().parent.parent


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

    @staticmethod
    def empty() -> FuncCallProfile:
        return FuncCallProfile(
            name="unknown",
            args=0,
            ret=0,
            hit=False,
            outer_function=0,
        )

    @property
    def total_overhead(self) -> float:
        if self.hit:
            return self.outer_function
        else:
            return self.outer_function - self.inner_function


def parse_memoized_log(
    log_path: Path,
) -> Tuple[Sequence[FuncCallProfile], Mapping[str, Any]]:
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
                if "obj_key" in record:
                    calls[record["call_id"]].args = record["obj_key"]
            elif "duration" in record and "event" in record:
                process_kwargs[record["event"]] += record["duration"]
            else:
                warnings.warn(
                    f"Unknown record {record} on line {line_no} of {perf_log}."
                )
    return list(calls.values()), dict(process_kwargs)


@dataclass
class RunexecStats:
    exitcode: int
    walltime: float
    cputime: float
    memory: int
    blkio_read: Optional[int]
    blkio_write: Optional[int]
    cpuenergy: Optional[float]
    termination_reason: Optional[str]

    @staticmethod
    def create(result: Mapping[str, Any]) -> RunexecStats:
        keys = set(
            "walltime cputime memory blkio_read blkio_write cpuenergy".split(" ")
        )
        attrs = {key: result.get(key, None) for key in keys}
        attrs["termination_reason"] = result.get("terminationreason", None)
        attrs["exitcode"] = result["exitcode"].raw
        return RunexecStats(**attrs)


@dataclass
class ExecutionProfile:
    output: str
    log: str
    success: bool
    command: Sequence[str]
    func_calls: Sequence[FuncCallProfile]
    runexec: RunexecStats
    internal_stats: Mapping[str, float]
    warnings: Sequence[str]


def run_exec_cmd(
    environment: Environment,
    cmd: Sequence[str],
    env: Mapping[str, str],
    cwd: Path,
    dir_modes: Mapping[str, Any],
    tmp_dir: Path,
    time_limit: int,
    mem_limit: int,
) -> Tuple[Tuple[str, ...], RunexecStats, str, str]:
    stdout = tmp_dir / "info.log"
    if stdout.exists():
        stdout.unlink()
    stderr = tmp_dir / "error.log"
    if stderr.exists():
        stderr.unlink()
    combined_cmd = combine_cmd(*environment.run(cmd, env, cwd))
    stderr.write_text(" \\\n    ".join(shlex.quote(part) for part in combined_cmd) + "\n\n")
    run_executor = RunExecutor(
        use_namespaces=False,
        # dir_modes=dir_modes,
        # network_access=True,
        # Need to system config so DNS works.
        # container_system_config=True,
    )
    logger = logging.getLogger("root")
    with runexec_catch_signals(run_executor), capture_logs(logger, logging.WARNING) as logs:
        run_exec_run = run_executor.execute_run(
            args=combined_cmd,
            environments={
                "keepEnv": {},
            },
            workingDir="/",
            write_header=False,
            output_filename=stdout,
            error_filename=stderr,
            softtimelimit=time_limit,
            hardtimelimit=int(time_limit * 1.1),
            walltimelimit=int(time_limit * 1.2),
            memlimit=mem_limit,
        )
    return (
        combined_cmd,
        RunexecStats.create(run_exec_run),
        stdout.read_text(),
        stderr.read_text() + "\n".join(record.getMessage() for record in logs),
    )


# @ch_time_block.decor(print_start=False)
def run_once(
    repo: Repo,
    environment: Environment,
    env_vars: Mapping[str, str],
    script: Path,
    limits: Mapping[str, int],
    memoize: bool,
    trace: bool,
    tmp_dir: Path,
) -> ExecutionProfile:
    warnings = []
    perf_log = tmp_dir / "perf.log"
    command, runexec_stats, stdout, stderr = run_exec_cmd(
        environment,
        [
            "python",
            *(["trace.py", str(script), "trace.log", "function"] if trace else [str(script)]),
        ],
        {
            "CHARMONIUM_CACHE_ENABLE": "1" if memoize else "0",
            "CHARMONIUM_CACHE_PERF_LOG": str(perf_log),
            **env_vars,
        },
        tmp_dir,
        time_limit=limits["time"],
        mem_limit=limits["mem"],
        dir_modes={
            "/": container.DIR_READ_ONLY,
            # TODO: Ideally, I would use `--overlay-dir` with tmp_dir instead of --full--access-dir.
            # See https://github.com/sosy-lab/benchexec/issues/815
            "/home": container.DIR_OVERLAY,
            str(tmp_dir): container.DIR_FULL_ACCESS,
            str(repo.dir): container.DIR_READ_ONLY,
        },
        tmp_dir=tmp_dir,
    )

    if runexec_stats.termination_reason:
        warnings.append(
            f"Terminated for {runexec_stats.termination_reason} out with {limits['time']=} {limits['mem']=}"
        )
    if perf_log.exists():
        calls, kwargs = parse_memoized_log(perf_log)
    else:
        if memoize:
            warnings.append("No perf log produced, despite enabling memoization.")
        # no profiling information
        calls = []
        kwargs = {}
    return ExecutionProfile(
        output=stdout,
        command=command,
        log=stderr,
        success=runexec_stats.exitcode == 0,
        func_calls=calls,
        internal_stats=kwargs,
        runexec=runexec_stats,
        warnings=warnings,
    )


@dataclass
class CommitResult:
    diff: bytes
    date: datetime.datetime
    commit: str
    executions: Mapping[str, ExecutionProfile]

    @staticmethod
    def from_commit(
        repo: Repo, commit: str, executions: Mapping[str, ExecutionProfile]
    ) -> CommitResult:
        diff, date = repo.info(commit)
        return CommitResult(diff, date, commit, executions)


def run_many(
    repo: Repo,
    environment: Environment,
    commits: Sequence[str],
    env_vars: Mapping[str, str],
    script: Path,
    limits: Mapping[str, int],
    memoize: bool,
    short_circuit: bool,
) -> Sequence[ExecutionProfile]:
    repo.clean()
    tmp_dir = ROOT / ".tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir()
    executions = []
    for commit in tqdm(commits, unit="commit", leave=False):
        execution = run_once(repo, environment, env_vars, script, limits, memoize, trace=False, tmp_dir=tmp_dir)
        executions.append(execution)
        if short_circuit and execution.runexec.termination_reason:
            break
    return executions


manual_cache = Path(".manual_cache")


def get_repo_result(
    repo: Repo,
    commit_chooser: CommitChooser,
    environment_chooser: EnvironmentChooser,
    env_vars: Mapping[str, str],
    script: Path,
    limits: Mapping[str, int],
) -> RepoResult:
    manual_cache.mkdir(exist_ok=True)
    cache_dest = manual_cache / f"{repo.name}.pkl"
    if cache_dest.exists():
        return cast(RepoResult, pickle.loads(cache_dest.read_bytes()))
    else:
        ret = get_repo_result2(repo, commit_chooser, environment_chooser, env_vars, script, limits)
        cache_dest.write_bytes(pickle.dumps(ret))
        return ret


# @ch_time_block.decor(print_start=False)
def get_repo_result2(
    repo: Repo,
    commit_chooser: CommitChooser,
    environment_chooser: EnvironmentChooser,
    env_vars: Mapping[str, str],
    script: Path,
    limits: Mapping[str, int],
) -> RepoResult:
    warnings = []
    repo.setup()
    environment = environment_chooser.choose(repo)
    if environment is None:
        warnings.append(f"{environment_chooser!s} could not choose an environment.")
        return RepoResult(
            repo=repo,
            environment=environment,
            script=script,
            commit_results=[],
            warnings=warnings,
        )
    else:
        try:
            environment.setup()
            if not environment.has_package("charmonium.cache"):
                environment.install(
                    ["https://github.com/charmoniumQ/charmonium.cache/tarball/main"]
                )
        except subprocess.CalledProcessError as e:
            warnings.append(
                "\n".join(
                    [
                        f"{environment!s} could not setup {repo!s}.",
                        str(e),
                        e.stdout.decode()
                        if isinstance(e.stdout, bytes)
                        else "No stdout",
                        e.stderr.decode()
                        if isinstance(e.stderr, bytes)
                        else "No stderr",
                    ]
                )
            )
            return RepoResult(
                repo=repo,
                environment=None,
                script=script,
                commit_results=[],
                warnings=warnings,
            )
        else:
            commits = commit_chooser.choose(repo)
            if len(commits) < 2:
                warnings.append(f"Only {len(commits)} commit.")
            orig_executions = run_many(
                repo, environment, commits, env_vars, script, limits, memoize=False, short_circuit=True
            )
            working_commits = commits[: len(orig_executions)]
            memo_executions = run_many(
                repo, environment, commits, env_vars, script, limits, memoize=True, short_circuit=True
            )
            commit_results = [
                CommitResult.from_commit(
                    repo,
                    commit,
                    {
                        "orig": orig_execution,
                        "memo": memo_execution,
                    },
                )
                for commit, orig_execution, memo_execution in zip(
                    commits, orig_executions, memo_executions
                )
            ]
            return RepoResult(
                repo=repo,
                environment=environment,
                script=script,
                commit_results=commit_results,
                warnings=warnings,
            )


@dataclass
class RepoResult:
    repo: Repo
    script: Path
    environment: Optional[Environment]
    commit_results: Sequence[CommitResult]
    warnings: Sequence[str]


def run_experiment(
    repos: Sequence[Tuple[Repo, CommitChooser, EnvironmentChooser, Mapping[str, str], Path, Mapping[str, int]]],
) -> Sequence[RepoResult]:
    repos = repos[:250]
    return [
        get_repo_result(*repo_info)
        for repo_info in tqdm(repos, unit="repos", leave=False)
    ]
