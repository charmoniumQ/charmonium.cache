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
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Type, cast

import charmonium.time_block as ch_time_block
from benchexec import container  # type: ignore
from benchexec.runexecutor import RunExecutor  # type: ignore

# from charmonium.cache import MemoizedGroup, memoize
from charmonium.determ_hash import determ_hash
from tqdm import tqdm  # type: ignore

from .environment import Environment, EnvironmentChooser
from .repo import CommitChooser, Repo

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
            "exitcode walltime cputime memory blkio_read blkio_write cpuenergy".split(
                " "
            )
        )
        attrs = {key: result.get(key, None) for key in keys}
        attrs["termination_reason"] = result.get("terminationreason", None)
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


tmp_dir = ROOT / ".tmp"
limits = {
    "softtimelimit": 120,
    "hardtimelimit": 130,
    "memlimit": 2 ** 28,
}

# @ch_time_block.decor(print_start=False)
def run_once(
    repo: Repo, environment: Environment, cmd: Sequence[str], memoize: bool
) -> ExecutionProfile:
    warnings = []
    perf_log = tmp_dir / "perf.log"
    junit_xml_log = tmp_dir / "junit.xml"
    output_log = tmp_dir / "output.log"
    cmd, env, cwd = environment.run(
        [
            "python",
            "-m",
            "pytest",
            "--quiet",
            str(repo.dir),
            "--junitxml",
            str(junit_xml_log),
        ],
        {
            "CHARMONIUM_CACHE_DISABLE": "" if memoize else "1",
            "CHARMONIUM_CACHE_PERF_LOG": str(perf_log),
        },
        tmp_dir,
    )
    combined_cmd = [
        "env",
        "--chdir",
        str(cwd),
        *[key + "=" + val for key, val in env.items()],
        *cmd,
    ]
    runexecutor = RunExecutor(
        dir_modes={
            "/": container.DIR_READ_ONLY,
            # TODO: Ideally, I would use `--overlay-dir` with tmp_dir instead of --full--access-dir.
            # See https://github.com/sosy-lab/benchexec/issues/815
            "/home": container.DIR_OVERLAY,
            str(tmp_dir): container.DIR_FULL_ACCESS,
            str(repo.dir): container.DIR_FULL_ACCESS,
        },
    )

    def signal_handler_kill(signum: signal.Signals, _: types.FrameType) -> None:
        runexecutor.stop()

    signal.signal(signal.SIGTERM, signal_handler_kill)
    signal.signal(signal.SIGQUIT, signal_handler_kill)
    signal.signal(signal.SIGINT, signal_handler_kill)
    runexec = RunexecStats.create(
        runexecutor.execute_run(
            args=combined_cmd,
            # environments={
            #     "keepEnv": {},
            # },
            workingDir=cwd,
            output_filename=output_log,
            **limits,
        )
    )
    if runexec.termination_reason:
        warnings.append(
            f"Terminated for {runexec.termination_reason} out with {limits=}"
        )
    if perf_log.exists():
        calls, kwargs = parse_memoized_log(perf_log)
    else:
        if memoize:
            warnings.append("No perf log produced, despite enabling memoization.")
        # no profiling information
        calls = []
        kwargs = {}
    if junit_xml_log.exists():
        output_xml = xml.etree.ElementTree.parse(junit_xml_log)
        output: str = json.dumps(
            dict(
                sorted(
                    [
                        (key, val)
                        for key, val in output_xml.getroot().attrib.items()
                        if key != "time"
                    ]
                )
            )
        )
    else:
        warnings.append("No junit xml log produced, despite passing --junitxml.")
        output = ""
    return ExecutionProfile(
        output=output,
        command=cmd,
        log=output_log.read_text() if output_log.exists() else "",
        success=True,
        func_calls=calls,
        internal_stats=kwargs,
        runexec=runexec,
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
    command: Sequence[str],
    memoize: bool,
    short_circuit: bool,
) -> Sequence[ExecutionProfile]:
    repo.clean()

    if memoize:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir()
    conftest_dest = repo.dir / "conftest.py"
    if conftest_dest.exists():
        conftest_dest.unlink()
    shutil.copy(Path("that_conftest.py"), conftest_dest)

    executions = []
    for commit in tqdm(commits, total=len(commits), desc="Commits"):
        execution = run_once(repo, environment, command, memoize)
        executions.append(execution)
        if short_circuit and execution.runexec.termination_reason:
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


# @ch_time_block.decor(print_start=False)
def get_repo_result2(
    repo: Repo,
    commit_chooser: CommitChooser,
    environment_chooser: EnvironmentChooser,
    command: Sequence[str],
) -> RepoResult:
    warnings = []
    print(repo.name)
    # with ch_time_block.ctx("repo.setup()", print_start=False):
    if True:
        repo.setup()
    environment = environment_chooser.choose(repo)
    if environment is None:
        warnings.append(f"{environment_chooser!s} could not choose an environment.")
        return RepoResult(
            repo=repo,
            environment=environment,
            command=command,
            commit_results=[],
            warnings=warnings,
        )
    else:
        try:
            # with ch_time_block.ctx("environment.setup()"):
            if True:
                environment.setup()
                packages = [
                    "https://github.com/charmoniumQ/charmonium.cache/tarball/main"
                ]
                command, env, cwd = environment.run(
                    ["python", "-c", "import pytest"],
                    os.environ,
                    Path(),
                )
                proc = subprocess.run(
                    command,
                    env=env,
                    cwd=cwd,
                    check=False,
                    capture_output=True,
                )
                if proc.returncode != 0:
                    packages.append("pytest")
                environment.install(packages)
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
                command=command,
                commit_results=[],
                warnings=warnings,
            )
        else:
            commits = commit_chooser.choose(repo)
            if len(commits) < 2:
                warnings.append(f"Only {len(commits)} commit.")
            orig_executions = run_many(
                repo, environment, commits, command, memoize=False, short_circuit=True
            )
            working_commits = commits[: len(orig_executions)]
            memo_executions = run_many(
                repo, environment, commits, command, memoize=True, short_circuit=True
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
                command=command,
                commit_results=commit_results,
                warnings=warnings,
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
    repos = repos[:250]
    return [
        get_repo_result(*repo_info)
        for repo_info in tqdm(repos, total=len(repos), desc="Repos")
    ]
