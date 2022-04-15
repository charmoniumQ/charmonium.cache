
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
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Type, cast

import charmonium.time_block as ch_time_block
from benchexec import container  # type: ignore
from benchexec.runexecutor import RunExecutor  # type: ignore

# from charmonium.cache import MemoizedGroup, memoize
from charmonium.determ_hash import determ_hash
from tqdm import tqdm

from .environment import Environment, EnvironmentChooser
from .repo import CommitChooser, Repo
from .util import combine_cmd, runexec_catch_signals, capture_logs, count

ROOT = Path(__file__).resolve().parent.parent

manual_cache = Path(".manual_cache")

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
    warnings: List[str]
    trace_data: Optional[List[str]]
    trace_rerun: bool = False


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

def run_once2(
    repo: Repo,
    environment: Environment,
    env_vars: Mapping[str, str],
    script: Path,
    limits: Mapping[str, int],
    memoize: bool,
    trace: bool,
    trace_imports: bool,
    tmp_dir: Path,
) -> ExecutionProfile:
    warnings = []
    perf_log = tmp_dir / "perf.log"
    trace_log = tmp_dir / "trace.log"
    coverage_file = tmp_dir / ".coverage"
    command, runexec_stats, stdout, stderr = run_exec_cmd(
        environment,
        [
            *(
                ["coverage", "run", str(script), "--data-file", str(coverage_file), "--rcfile=/dev/null"] if trace
                else ["python", str(ROOT / "trace_imports.py"), str(script), str(trace_log)] if trace_imports
                else ["python", str(script)]
            ),
        ],
        {
            "CHARMONIUM_CACHE_DISABLE": "0" if memoize else "1",
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

    trace_data = None
    if trace_imports:
        if runexec_stats.exitcode != 0:
            print(stdout)
            print(stderr)
            print(command)
            raise ValueError
        assert trace_log.exists()
        trace_data = sorted(list(set([
            str(unpyc(Path(line)))
            for line in trace_log.read_text().split("\n")
            if line.startswith("/") and Path(line).is_relative_to(repo.dir)
        ])))
        trace_log.unlink()

    if trace:
        if runexec_stats.exitcode != 0:
            print(stdout)
            print(stderr)
            print(command)
            raise ValueError
        assert coverage_file.exists()
        coverage_json = tmp_dir / "coverage.json"
        subprocess.run(["coverage", "json", "--data-file", str(coverage_file), "-o", str(coverage_json), "--rcfile=/dev/null"], cwd=tmp_dir)
        coverage_file.unlink()
        coverage_obj = json.loads(coverage_json.read_text())
        coverage_json.unlink()
        trace_data = []
        for file in sorted(coverage_obj["files"]):
            file_text = Path(file).read_text().split("\n")
            for line in coverage_obj["files"][file]["executed_lines"]:
                print(file, line)
                trace_data.append(file_text[line - 1])

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
        trace_data=trace_data,
    )


def run_once(
    repo: Repo,
    environment: Environment,
    key: str,
    env_vars: Mapping[str, str],
    script: Path,
    limits: Mapping[str, int],
    memoize: bool,
    trace: bool,
    trace_imports: bool,
    tmp_dir: Path,
) -> ExecutionProfile:
    cache_dest = manual_cache / repo.name / f"key={key},memoize={int(memoize)},trace={int(trace)},trace_imports={int(trace_imports)}.pkl"
    cache_dest.parent.mkdir(exist_ok=True, parents=True)
    if cache_dest.exists():
        return cast(ExecutionProfile, pickle.loads(cache_dest.read_bytes()))
    else:
        ret = run_once2(repo, environment, env_vars, script, limits, memoize, trace, trace_imports, tmp_dir)
        cache_dest.write_bytes(pickle.dumps(ret))
        return ret


@dataclass
class CommitInfo:
    diff: bytes
    date: datetime.datetime
    commit: str

    @staticmethod
    def from_commit(
        repo: Repo,
        commit: str,
    ) -> CommitInfo:
        diff, date = repo.info(commit)
        return CommitInfo(diff, date, commit)


tmp_dir = ROOT / ".tmp"
def run_many(
    repo: Repo,
    environment: Environment,
    commits: Sequence[str],
    env_vars: Mapping[str, str],
    script: Path,
    limits: Mapping[str, int],
    memoize: bool,
    trace: bool,
) -> Iterable[ExecutionProfile]:
    repo.clean()
    environment.install(["--editable", str(repo.dir)])
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir()
    for commit in tqdm(commits, unit="commit", leave=False):
        execution = run_once(repo, environment, commit, env_vars, script, limits, memoize, trace=trace, trace_imports=False, tmp_dir=tmp_dir)
        yield execution


pyc_suffix = re.compile(r"([^.]*)(?:\.cpython-\d+)?(?:\.pyc)(?:\.\d+)?")
def unpyc(path: Path) -> Path:
    parts = list(path.parts)
    if m := pyc_suffix.match(parts[-1]):
        parts[-1] = m.group(1) + ".py"
    if parts[-2] == "__pycache__":
        del parts[-2]
    return Path().joinpath(*parts)


# @ch_time_block.decor(print_start=False)
def get_repo_result2(
    repo: Repo,
    commit_chooser: CommitChooser,
    environment_chooser: EnvironmentChooser,
    env_vars: Mapping[str, str],
    script: Path,
    limits: Mapping[str, int],
) -> Iterable[RepoResult]:
    warnings: List[str] = []
    repo.setup()
    environment = environment_chooser.choose(repo)
    repo_result = RepoResult(
        repo=repo,
        environment=environment,
        script=script,
        commits=[],
        executions={},
        warnings=[],
    )
    if environment is None:
        repo_result.warnings.append(f"{environment_chooser!s} could not choose an environment.")
        yield repo_result
        return
    try:
        environment.setup()
        if not environment.has_package("charmonium.cache"):
            environment.install(
                ["https://github.com/charmoniumQ/charmonium.cache/tarball/main"]
            )
    except subprocess.CalledProcessError as e:
        repo_result.warnings.append(
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
        yield repo_result
        return

    environment.install(["--editable", str(repo.dir)])
    execution = run_once(repo, environment, repo.top_commit, env_vars, script, limits, memoize=False, trace=False, trace_imports=True, tmp_dir=tmp_dir)
    trace_data = execution.trace_data
    assert trace_data is not None
    assert trace_data
    relevant_files = list(map(Path, trace_data))

    repo_result.commits = commit_chooser.choose(repo, relevant_files)
    repo_result.executions = {
        "memo": [None] * len(repo_result.commits),
        "orig": [None] * len(repo_result.commits),
        "trace": [None] * len(repo_result.commits),
    }
    run_many_args = (repo, environment, repo_result.commits, env_vars, script, limits)

    for i, execution in enumerate(run_many(*run_many_args, memoize=True, trace=False)):
        repo_result.executions["memo"][i] = execution
        yield repo_result
        if execution.runexec.termination_reason:
            break

    num_good_commits = count(filter(bool, repo_result.executions["memo"]))

    # repo_result.commits = repo_result.commits[:num_good_commits]
    # repo_result.executions = {
    #     label: executions[:num_good_commits]
    #     for label, executions in repo_result.executions.items()
    # }

    if len(repo_result.commits) < 2:
        repo_result.warnings.append(f"Only {len(repo_result.commits)} commit.")

    for i, execution in enumerate(run_many(*run_many_args, memoize=False, trace=False)):
        repo_result.executions["orig"][i] = execution
        yield repo_result

    last_hash = None
    for i, execution in enumerate(run_many(*run_many_args, memoize=False, trace=True)):
        new_hash = execution.trace_data
        assert new_hash

        if new_hash != last_hash:
            execution.trace_rerun = True
            last_hash = new_hash
        else:
            execution.trace_rerun = False
        repo_result.executions["trace"][i] = execution
        yield repo_result


def get_repo_result(
    repo: Repo,
    commit_chooser: CommitChooser,
    environment_chooser: EnvironmentChooser,
    env_vars: Mapping[str, str],
    script: Path,
    limits: Mapping[str, int],
) -> Iterable[RepoResult]:
    cache_dest = manual_cache / repo.name / f"list.pkl"
    cache_dest.parent.mkdir(exist_ok=True, parents=True)
    if cache_dest.exists():
        yield cast(RepoResult, pickle.loads(cache_dest.read_bytes()))
    else:
        results_gen = get_repo_result2(repo, commit_chooser, environment_chooser, env_vars, script, limits)
        last_result = None
        for result in results_gen:
            last_result = result
            yield result
        if last_result is not None:
            cache_dest.write_bytes(pickle.dumps(last_result))


@dataclass
class RepoResult:
    repo: Repo
    script: Path
    environment: Optional[Environment]
    commits: List[str]
    executions: Mapping[str, List[Optional[ExecutionProfile]]]
    warnings: List[str]

# TODO: Mayhaps this should be a Mapping[Repo, RepoResult]
def run_experiment(
    repos: Sequence[Tuple[Repo, CommitChooser, EnvironmentChooser, Mapping[str, str], Path, Mapping[str, int]]],
) -> Iterable[Sequence[RepoResult]]:
    results: List[RepoResult] = []
    for repo_info in tqdm(repos, unit="repos", leave=False):
        last_result = None
        for result in get_repo_result(*repo_info):
            last_result = result
            yield [*results, result]
        if last_result is not None:
            results.append(last_result)
