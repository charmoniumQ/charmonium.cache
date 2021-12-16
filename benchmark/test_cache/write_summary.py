from pathlib import Path
from typing import List, Tuple, Union
import datetime

from . import html
from .environment import Environment, CondaEnvironment, PoetryEnvironment
from .html_helpers import (
    collapsed,
    disp_bool,
    highlighted_code,
    highlighted_head,
    html_table,
)
from .repo import Repo
from .action import Action, IpynbAction
from .run_experiment import CommitResult, ExecutionProfile, FuncCallProfile, RepoResult


def disp_hash(val: int) -> html.Tag:
    return html.code()(str(val)[:6])


def disp_sec(val: float) -> html.Tag:
    return html.span()(f"{val:.1f}s")


def summarize_func_calls(func_calls: List[FuncCallProfile]) -> html.Tag:
    return html_table(
        [
            [
                func_call.name,
                disp_hash(func_call.args),
                disp_hash(func_call.ret),
                disp_bool(func_call.hit),
                disp_sec(func_call.outer_function),
                disp_sec(func_call.inner_function),
                disp_sec(func_call.hash),
                disp_sec(func_call.total_overhead - func_call.hash),
            ]
            for func_call in func_calls
        ],
        headers=[
            "name",
            "hash(args)",
            "hash(ret)",
            "hit",
            "outer",
            "inner",
            "hash time",
            "rest of overhead",
        ],
    )


def summarize_execution(title: str, prof: ExecutionProfile) -> html.Tag:
    if prof.empty:
        style = "yellow"
    elif prof.success:
        style = "green"
    else:
        style = "red"
    return html.div()(
        html.h3(color=style)(title),
        html_table(
            [
                ["total time", disp_sec(prof.total_time)],
                ["hash(stdout)", disp_hash(prof.stdout)],
                ["process overhead (s)", disp_sec(prof.process_overhead)],
            ]
        ),
        collapsed("Function calls", summarize_func_calls(prof.func_calls)),
    )


def summarize_commit_result(result: CommitResult) -> html.Tag:
    date_str = result.date.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return html.div()(
        html.h2()(f"Commit {result.commit[:6]} {date_str}"),
        collapsed("Diff from prev", highlighted_code("diff", result.diff)),
        summarize_execution("Original execution", result.orig),
        summarize_execution("First memoized execution", result.orig),
        summarize_execution("Second memoized execution", result.orig),
    )


def summarize_environment(environment: Environment) -> List[List[Union[html.Tag, str]]]:
    return [
        [
            html.code()("environment.yaml"),
            collapsed("show", highlighted_code("yaml", environment.environment.read_text())),
        ],
    ] if isinstance(environment, CondaEnvironment) else [
        [
            html.code()("pyproject.toml"),
            collapsed("show", highlighted_code("toml", environment.pyproject.read_text())),
        ],
    ] if isinstance(environment, PoetryEnvironment) else []

def summarize_repo_result(
    repo_result: RepoResult
) -> html.Tag:
    return html.div()(
        html.h1()(f"Repo {repo_result.repo.name}"),
        html_table(
            [
                ["dir", str(repo_result.repo.dir)],
                ["name", repo_result.repo.name],
                *summarize_environment(repo_result.environment),
            ]
        ),
        collapsed(
            "Results",
            *[
                summarize_commit_result(commit_result)
                for commit_result in repo_result.commit_results
            ],
        ),
    )


def summarize_repo_results(repo_results: List[RepoResult]) -> html.Tag:
    return html.div()(
        *map(summarize_repo_result, repo_results)
    )


def write_summary(repo_results: List[RepoResult]) -> None:
    Path("report.html").write_text(
        "<!DOCTYPE html>\n"
        + str(
            html.html(lang="en")(
                html.head()(
                    html.meta(charset="utf-8")(),
                    html.title()("Benchmark of charmonium.cache"),
                    *highlighted_head(["yaml", "python", "diff", "ini"]),
                    html.style()("""
table, th, td {
  border: 1px solid black;
  border-collapse: collapse;
}
                    """),
                ),
                html.body()(
                    summarize_repo_results(repo_results),
                ),
            )
        )
    )
