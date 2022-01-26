import datetime
from pathlib import Path
import re
import shlex
from typing import List, Tuple, Union, Mapping

from charmonium.determ_hash import determ_hash

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

def disp_date(date: datetime.datetime) -> html.Tag:
    return html.span()(date.strftime("%Y-%m-%d"))

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


def summarize_execution(prof: ExecutionProfile) -> html.Tag:
    return html_table(
        [

        ]
    )

executions: Mapping[str, html.TagLike] = {
    "orig": "Unmodified",
    "orig2": "Unmodified (2nd run)",
    "rr_record": html.code()("rr record"),
    "rr_replay": html.code()("rr replay"),
}

commit_result_headers: List[html.TagLike] = [
    "Commit date",
    "Commit hash",
    "Commit diff",
    *[
        html.span()(execution, " time")
        for execution in executions.values()
    ],
    # "Memoized output matches original",
    "Original is deterministic",
    html.span()(html.code()("rr"), " is deterministic"),
    "Results",
]

def summarize_commit_result(repo: Repo, result: CommitResult) -> List[html.TagLike]:
    def color_cell(elem: html.TagLike, color: str) -> html.Tag:
        return html.span(style=f"background-color: {color}; display: block;")(elem)
    def prof_status(prof: ExecutionProfile) -> html.TagLike:
        if prof.empty:
            return color_cell("Empty profile", "yellow")
        elif prof.success:
            return color_cell("Success", "green")
        else:
            return color_cell("Error", "red")
    date_str = result.date.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    adds = len(list(re.finditer(r"^[+] ", result.diff, flags=re.MULTILINE)))
    subs = len(list(re.finditer(r"^[-] ", result.diff, flags=re.MULTILINE)))

    inner_table = html_table(
        [
            ["Status", *[
                prof_status(prof)
                for prof in result.executions.values()
            ]],
            ["Output", *[
                collapsed(
                    disp_hash(determ_hash(prof.output)),
                    html.pre()(html.code()(prof.output.decode())),
                ) for prof in result.executions.values()
            ]],
            ["Time (s)", *[
                disp_sec(prof.total_time)
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
    orig_deterministic = result.executions["orig2"].output == result.executions["orig"].output
    rr_deterministic = result.executions["rr_record"].output == result.executions["rr_replay"].output
    return [
        disp_date(result.date),
        html.a(href=repo.display_url.format(commit=result.commit))(result.commit),
        collapsed(f"Diff +{adds}/-{subs}", highlighted_code("diff", result.diff)),
        *[
            disp_sec(result.executions[execution].total_time)
            for execution in executions
        ],
        color_cell("deterministic", "green") if orig_deterministic else color_cell("non-deterministic", "red"),
        color_cell("deterministic", "green") if rr_deterministic else color_cell("non-deterministic", "red"),
        collapsed("Details", inner_table),
    ]


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
                ["Name", repo_result.repo.name],
                ["Path", str(repo_result.repo.dir)],
                *summarize_environment(repo_result.environment),
                ["Command", html.code()(shlex.join(repo_result.cmd))],
                ["Results", html_table(
                    [
                        summarize_commit_result(repo_result.repo, commit_result)
                        for commit_result in repo_result.commit_results
                    ],
                    commit_result_headers,
                )],
            ]
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
