import datetime
from pathlib import Path
import re
import shlex
from typing import Sequence, Tuple, Union, Mapping, Optional, List, TypeVar, cast, Iterable
import scipy.stats  # type: ignore
import numpy as np

from charmonium.determ_hash import determ_hash

from . import html
from .environment import Environment, CondaEnvironment, PoetryEnvironment, VirtualEnv
from .html_helpers import (
    collapsed,
    disp_bool,
    highlighted_code,
    highlighted_head,
    html_table,
    html_list,
    html_path,
)
from .repo import Repo
from .action import Action, IpynbAction
from .run_experiment import CommitResult, ExecutionProfile, FuncCallProfile, RepoResult

T = TypeVar("T")

def disp_date(date: datetime.datetime) -> html.Tag:
    return html.span()(date.strftime("%Y-%m-%d"))

def disp_hash(val: int) -> html.Tag:
    return html.code()(str(val)[:6])


def disp_sec(val: float) -> html.Tag:
    return html.span()(f"{val:.1f}s")


def summarize_func_calls(func_calls: Sequence[FuncCallProfile]) -> html.Tag:
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


def summarize_execution(prof: ExecutionProfile) -> html.Tag:
    return html_table(
        [

        ]
    )

executions: Mapping[str, html.TagLike] = {
    "orig": "Unmodified",
    "memo": "Memoized",
}

commit_result_headers: Sequence[html.TagLike] = [
    "Commit",
    "Tests work?",
    html.span()("Memoized output", html.br()(), "matches original?"),
    *[
        html.span()(execution, " time")
        for execution in executions.values()
    ],
    "Detailed results",
]

def count(it: Iterable[T]) -> int:
    counter = 0
    for e in it:
        counter += 1
    return counter

def summarize_commit(repo: Repo, result: CommitResult) -> html.Tag:
    date_str = result.date.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    adds = count(re.finditer(rb"^[+] ", result.diff, flags=re.MULTILINE))
    subs = count(re.finditer(rb"^[-] ", result.diff, flags=re.MULTILINE))
    return html_table([
        ["Date", disp_date(result.date)],
        [
            "Hash",
            html.a(href=repo.display_url.format(commit=result.commit))(result.commit[:6])
        ],
        ["Diff", f"Diff +{adds}/-{subs}"],
    ])

def color_cell(elem: html.TagLike, color: str) -> html.Tag:
    return html.span(style=f"background-color: {color}; display: block;")(elem)

def summarize_commit_result(repo: Repo, result: CommitResult) -> Sequence[html.TagLike]:
    def prof_status(prof: ExecutionProfile) -> html.TagLike:
        if prof.empty:
            return color_cell("Empty profile", "yellow")
        elif prof.success:
            return color_cell("Success", "green")
        else:
            return color_cell("Error", "red")
    inner_table = html_table(
        [
            ["Status", *[
                prof_status(prof)
                for prof in result.executions.values()
            ]],
            ["Output", *[
                highlighted_code("plaintext", prof.output)
                for prof in result.executions.values()
            ]],
            ["Log", *[
                highlighted_code("plaintext", prof.log)
                for prof in result.executions.values()
            ]],
            ["Time (s)", *[
                disp_sec(prof.cpu_time)
                for prof in result.executions.values()
            ]],
            ["Overhead (s)", *[
                disp_sec(prof.process_overhead)
                for prof in result.executions.values()
            ]],
            ["Function calls", *[
                collapsed("Show", summarize_func_calls(prof.func_calls))
                for prof in result.executions.values()
            ]],
        ],
        ["", *[
            executions[label]
            for label in result.executions.keys()
        ]],
    )
    tests_work = any(
        execution.success
        for execution in result.executions.values()
    )
    matches = "memo" in result.executions and "orig" in result.executions and result.executions["memo"].output == result.executions["orig"].output
    return [
        summarize_commit(repo, result),
        color_cell("Tests work", "green") if tests_work else color_cell("Tests don't work", "red"),
        color_cell("Output matches", "green") if matches else color_cell("Outputs don't match", "red"),
        *[
            disp_sec(
                result.executions[execution].cpu_time
                if execution in result.executions
                else 0.0
            )
            for execution in executions
        ],
        collapsed("Details", inner_table),
    ]


def summarize_environment(environment: Optional[Environment]) -> html.TagLike:
    if False:
        pass
    elif isinstance(environment, CondaEnvironment):
        return html_table([
            [
                html.code()("environment.yaml"),
                collapsed("show", highlighted_code("yaml", environment.environment.read_text())),
            ],
        ])
    elif isinstance(environment, PoetryEnvironment):
        return html_table([
            [
                html.code()("pyproject.toml"),
                collapsed("show", highlighted_code("toml", environment.pyproject.read_text())),
            ],
        ])
    elif isinstance(environment, VirtualEnv):
        return html_table([
            [
                html.span()("Requirements"),
                collapsed("show", html_list([
                    html.code()(requirement)
                    for requirement in environment.requirements
                ])),
            ],
        ])
    else:
        return html.span()("No info.")

def summarize_series(series: Sequence[float]) -> html.TagLike:
    if len(series) > 1:
        result = scipy.stats.bootstrap((np.array(series),), np.mean, confidence_level=0.95)
        return f"{result.confidence_interval.low:.1f} -- {result.confidence_interval.high:.1f}"
    elif len(series) == 1:
        return f"{series[0]:.1f}"
    else:
        return "No data"

def summarize_repo_results(repo_results: Sequence[RepoResult]) -> html.Tag:
    return html_table(
        [
            [
                collapsed(
                    result.repo.name,
                    html_table([
                            ["Local path", html_path(result.repo.dir)],
                            ["Remote path", html.a(href=result.repo.url)("here")],
                            ["Command", html.code()(shlex.join(result.command))],
                            ["Environment", summarize_environment(result.environment)],
                            ["Warnings", html.code()(html.pre()("\n".join(result.warnings)))],
                    ]),
                ),
                color_cell("Install failed", "red") if not result.commit_results else color_cell("Tests don't work", "red") if not any(commit_result.executions["orig"].success for commit_result in result.commit_results) else color_cell("Not cachable", "red") if any("TypeError: cannot pickle" in commit_result.executions["memo"].log for commit_result in result.commit_results) else color_cell("Success", "green"),
                summarize_series([
                    commit_result.executions["orig"].cpu_time
                    for commit_result in result.commit_results
                    if "orig" in commit_result.executions
                ]),
                summarize_series([
                    commit_result.executions["memo"].cpu_time
                    for commit_result in result.commit_results
                    if "memo" in commit_result.executions
                ]),
                collapsed(
                    "Commit results", 
                    html_table(
                        [
                            summarize_commit_result(result.repo, commit_result)
                            for commit_result in result.commit_results
                        ],
                        commit_result_headers,
                    ),
                ),
            ]
            for result in repo_results
        ],
        [
            "Repo",
            "Success?",
            "Original",
            "Memoized",
            "Results",
        ],
    )


def write_summary(repo_results: Sequence[RepoResult]) -> None:
    Path("report.html").write_text(
        "<!DOCTYPE html>\n"
        + str(
            html.html(lang="en")(
                html.head()(
                    html.meta(charset="utf-8")(),
                    html.title()("Benchmark of charmonium.cache"),
                    *highlighted_head(["yaml", "python", "diff", "ini", "plaintext"]),
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
