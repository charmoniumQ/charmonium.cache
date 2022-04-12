import datetime
import re
import shlex
from pathlib import Path
from typing import (
    Any,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
)

import bitmath  # type: ignore
import numpy as np
import scipy.stats  # type: ignore
from charmonium.determ_hash import determ_hash
from numpy.typing import NDArray

from . import html
from .environment import CondaEnvironment, Environment, PoetryEnvironment, VirtualEnv
from .html_helpers import (
    br_join,
    collapsed,
    css_string,
    disp_bool,
    highlighted_code,
    highlighted_head,
    html_fs_link,
    html_list,
    html_table,
    small,
)
from .repo import Repo
from .run_experiment import CommitInfo, ExecutionProfile, FuncCallProfile, RepoResult

T = TypeVar("T")

confidence = 0.9


def disp_date(date: datetime.datetime) -> html.Tag:
    return html.span()(date.strftime("%Y-%m-%d"))


def disp_hash(val: int) -> html.Tag:
    return html.code()(f"{val:x}"[:6])


def disp_sec(val: float) -> html.Tag:
    return html.span()(f"{val:.1f}s")


def disp_mem(val: int) -> html.Tag:
    value_str = bitmath.Byte(val).best_prefix().format("{value:.1f} {unit}")
    return html.span()(value_str)


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


execution_labels: Mapping[str, html.TagLike] = {
    "orig": "Unmodified",
    "memo": "Memoized",
}

commit_result_headers: Sequence[html.TagLike] = [
    "Commit",
    "Warnings",
    "Tests work?",
    html.span()("Memoized output", html.br()(), "matches original?"),
    *[html.span()(execution, " time") for execution in execution_labels.values()],
    *[html.span()(execution, " mem") for execution in execution_labels.values()],
    "Detailed results",
]


def count(it: Iterable[T]) -> int:
    counter = 0
    for e in it:
        counter += 1
    return counter


def summarize_commit_str(repo: Repo, commit: str) -> html.Tag:
    return html.a(href=repo.display_url.format(commit=commit))(commit[:6])

# def summarize_commit(repo: Repo, commit: CommitInfo) -> html.Tag:
#     date_str = commit.date.astimezone(datetime.timezone.utc).strftime(
#         "%Y-%m-%d %H:%M:%S UTC"
#     )
#     adds = count(re.finditer(rb"^[+] ", commit.diff, flags=re.MULTILINE))
#     subs = count(re.finditer(rb"^[-] ", commit.diff, flags=re.MULTILINE))
#     return html_table(
#         [
#             ["Date", disp_date(commit.date)],
#             [
#                 "Hash",
#                 html.a(href=repo.display_url.format(commit=commit.commit))(
#                     commit.commit[:6]
#                 ),
#             ],
#             ["Diff", f"Diff +{adds}/-{subs}"],
#         ]
#     )


def color_cell(elem: html.TagLike, color_class: str) -> html.Tag:
    return html.span(class_=f"color color-{color_class}")(elem)


def get_process_overhead(prof: ExecutionProfile) -> float:
    return sum(
        [
            prof.internal_stats.get("index_read", 0.0),
            prof.internal_stats.get("index_write", 0.0),
            prof.internal_stats.get("cascading_delete", 0.0),
            prof.internal_stats.get("evict", 0.0),
            prof.internal_stats.get("remove_orphan", 0.0),
            sum([func_call.total_overhead for func_call in prof.func_calls]),
        ]
    )


def summarize_commit_result(
    repo: Repo,
    commit: str,
    exes: Mapping[str, Optional[ExecutionProfile]],
) -> Sequence[html.TagLike]:
    inner_table = html_table(
        [
            [
                "Status",
                *[
                    color_cell("Success", "success") if exe and exe.success
                    else color_cell("Error", "error") if exe
                    else html.span()("")
                    for exe in exes.values()
                ],
            ],
            [
                "Output",
                *[
                    highlighted_code("plaintext", exe.output) if exe
                    else html.span()("")
                    for exe in exes.values()
                ],
            ],
            [
                "Warnings",
                *[
                    highlighted_code("plaintext", "\n".join(exe.warnings)) if exe
                    else html.span()("")
                    for exe in exes.values()
                ],
            ],
            [
                "Log",
                *[
                    highlighted_code("plaintext", exe.log) if exe
                    else html.span()("")
                    for exe in exes.values()
                ],
            ],
            [
                "Time (s)",
                *[
                    disp_sec(exe.runexec.cputime) if exe
                    else html.span()("")
                    for exe in exes.values()
                ],
            ],
            [
                "Overhead (s)",
                *[
                    disp_sec(get_process_overhead(exe)) if exe
                    else html.span()("")
                    for exe in exes.values()
                ],
            ],
            [
                "Function calls",
                *[
                    collapsed("Show", summarize_func_calls(exe.func_calls)) if exe
                    else html.span()("")
                    for exe in exes.values()
                ],
            ],
        ],
        ["", *[execution_labels[label] for label in exes.keys()]],
    )
    tests_work = any(exe.success for exe in exes.values() if exe)
    warnings = [
        warning
        for exe in exes.values()
        if exe
        for warning in exe.warnings
    ]
    return [
        summarize_commit_str(repo, commit),
        collapsed(
            color_cell("Warnings", "error"),
            highlighted_code("plaintext", "\n".join(set(warnings))),
        )
        if warnings
        else color_cell("None", "success"),
        color_cell("Tests work", "success")
        if tests_work
        else color_cell("Tests don't work", "error"),
        color_cell("Output matches", "success")
        if not result_mismatch(exes)
        else color_cell("Outputs don't match", "error"),
        *[
            disp_sec(
                exe.runexec.cputime if exe
                else 0.0
            )
            for exe in exes.values()
        ],
        *[
            disp_mem(
                exe.runexec.memory if exe
                else 0
            )
            for exe in exes.values()
        ],
        collapsed("Details", inner_table),
    ]


def summarize_environment(environment: Optional[Environment]) -> html.TagLike:
    if False:
        pass
    elif isinstance(environment, CondaEnvironment):
        return html_table(
            [
                ["Manager", "Conda"],
                ["environment.yaml", html_fs_link(environment.environment)],
                ["name", str(environment.name)],
            ]
        )
    elif isinstance(environment, PoetryEnvironment):
        return html_table(
            [
                ["Manager", "Poetry"],
                ["pyproject.toml", html_fs_link(environment.pyproject)],
            ]
        )
    elif isinstance(environment, VirtualEnv):
        return html_table(
            [
                ["Manager", "Virtualenv"],
                [
                    html.span()("Requirements"),
                    collapsed(
                        "show",
                        html_list(
                            [
                                html.code()(requirement)
                                for requirement in environment.requirements
                            ]
                        ),
                    ),
                ],
            ]
        )
    else:
        return html.span()("No info.")


def get_nonzero_executions(
    repo_result: RepoResult,
    *tags: str,
) -> Sequence[Mapping[str, ExecutionProfile]]:
    return [
        {
            tag: cast(ExecutionProfile, repo_result.executions[tag][i])
            for tag in tags
        }
        for i in range(len(repo_result.commits))
        if all(repo_result.executions[tag][i] for tag in tags)
    ]


def speedup_ratio(repo_result: RepoResult) -> html.Tag:
    nonzero_executions = get_nonzero_executions(repo_result, "orig", "memo")
    if len(nonzero_executions) < 2:
        return html.span()("Not enough data")
    else:
        ratios: NDArray[np.float64] = np.array(
            [
                executions["memo"].runexec.cputime / executions["orig"].runexec.cputime
                for executions in nonzero_executions
            ]
        )
        low, high = scipy.stats.bootstrap(
            (ratios,),
            scipy.stats.gmean,
            confidence_level=confidence,
        ).confidence_interval
        mid = scipy.stats.gmean([1 - low, 1 - high]) * 100
        label = f"{100*(1 - high):.0f}% – {100 * (1 - low):.0f}%"
        return color_cell(
            label, "success" if mid > 5 else "warning" if mid > -5 else "error"
        )


def original_time(repo_result: RepoResult) -> html.Tag:
    nonzero_executions = get_nonzero_executions(repo_result, "orig", "memo")
    if len(nonzero_executions) < 2:
        return html.span()("Not enough data")
    else:
        data: NDArray[np.float64] = np.array(
            [executions["orig"].runexec.cputime for executions in nonzero_executions]
        )
        low, high = scipy.stats.bootstrap(
            (data,),
            np.mean,
            confidence_level=confidence,
        ).confidence_interval
        mid = np.mean([low, high])
        label = f"{low:.1f}s – {high:.1f}s"
        return color_cell(label, "success" if mid > orig_time_cutoff else "warning")


orig_time_cutoff = 10.0


def total_speedup(
    repo_results: Sequence[RepoResult],
) -> Optional[Tuple[float, float, float, int]]:
    repos = []
    for repo_result in repo_results:
        nonzero_executions = get_nonzero_executions(repo_result, "orig", "memo")
        if len(nonzero_executions) >= 2:
            repos.append(nonzero_executions)
    memo_cputime: NDArray[np.float64] = np.array(
        [
            np.mean(
                [
                    executions["memo"].runexec.cputime
                    for executions in nonzero_executions
                ]
            )
            for nonzero_executions in repos
        ]
    )
    orig_cputime: NDArray[np.float64] = np.array(
        [
            np.mean(
                [
                    executions["orig"].runexec.cputime
                    for executions in nonzero_executions
                ]
            )
            for nonzero_executions in repos
        ]
    )
    mask = orig_cputime > orig_time_cutoff
    N = np.sum(mask)
    if N < 2:
        return None
    low, high = scipy.stats.bootstrap(
        ((memo_cputime / orig_cputime)[mask],),
        scipy.stats.gmean,
        confidence_level=confidence,
    ).confidence_interval
    mid = scipy.stats.gmean([low, high])
    return low, mid, high, N


def result_mismatch(executions: Mapping[str, Optional[ExecutionProfile]]) -> bool:
    return (
        executions["memo"] is not None
        and executions["orig"] is not None
        and executions["memo"].output != executions["orig"].output
    )


def get_command(repo_result: RepoResult) -> Sequence[str]:
    return repo_result.executions["memo"][0].command if repo_result.executions.get("memo") and repo_result.executions["memo"][0] is not None else ["true"]


def summarize_repo_result(result: RepoResult) -> Sequence[html.Tag]:
    warnings = list(
        set(
            warning
            for exes in result.executions.values()
            for exe in exes
            if exe
            for warning in exe.warnings
        )
    ) + list(result.warnings)

    if not result.executions:
        status = color_cell("Install failed", "orange")
    elif not all(
        execution and execution.success
        for execution in result.executions["memo"]
    ):
        status = color_cell("Tests don't work", "orange")
    elif len(get_nonzero_executions(result, "memo", "orig")) < 2:
        status = color_cell("Not enough working commits", "orange")
    elif any(
        exe.runexec.termination_reason
        for exes in result.executions.values()
        for exe in exes
        if exe
    ):
        status = color_cell("Limit exceeded", "orange")
    elif any(map(result_mismatch, [
            {label: exes[i] for label, exes in result.executions.items()}
            for i in range(len(result.commits))
    ])):
        status = color_cell("Result doesn't match", "error")
    elif warnings:
        status = color_cell("Completed with warnings", "success")
    else:
        status = color_cell("Success", "success")

    warnings_tag = (
        collapsed("Show warnings", highlighted_code("plaintext", "\n".join(warnings)))
        if warnings
        else html.span()()
    )

    return [
        collapsed(
            result.repo.name,
            html_table(
                [
                    ["Local path", html_fs_link(result.repo.dir)],
                    [
                        "Remote path",
                        html.a(href=result.repo.url)(html.code()(result.repo.url)),
                    ],
                    ["Command", html.code()(shlex.join(get_command(result)))],
                    ["Environment", summarize_environment(result.environment)],
                ]
            ),
        ),
        br_join([status, warnings_tag]),
        speedup_ratio(result),
        original_time(result),
        # speedup_difference(result),
        collapsed(
            "Commit results",
            html_table(
                [
                    summarize_commit_result(result.repo, result.commits[i], {
                        label: results[i]
                        for label, results in result.executions.items()
                    })
                    for i in range(len(result.commits))
                ],
                commit_result_headers,
            ),
        ),
    ]


def sort_key(repo_result: RepoResult) -> Any:
    if not list(exe for exes in repo_result.executions.values() for exe in exes):
        return (0,)
    elif any(
        not exe.success
        for exe in repo_result.executions["orig"]
        if exe
    ):
        return (1,)
    elif len(get_nonzero_executions(repo_result, "memo", "orig")) < 2:
        return (2,)
    elif any(
        exe.runexec.termination_reason
        for exes in repo_result.executions.values()
        for exe in exes
        if exe
    ):
        return (3,)
    elif any(map(result_mismatch, [
            {label: exes[i] for label, exes in repo_result.executions.items()}
            for i in range(len(repo_result.commits))
    ])):
        return (-2,)
    else:
        return (4, int("success" in original_time(repo_result).attrib["class"]))


def summarize_repo_results(repo_results: Sequence[RepoResult]) -> html.Tag:
    repo_results = sorted(repo_results, key=sort_key, reverse=True)
    return html_table(
        [summarize_repo_result(repo_result) for repo_result in repo_results],
        [
            "Repo",
            br_join(
                [
                    "Success?",
                    small("Red requires human attention."),
                    small("Orange just means it didn't work."),
                ]
            ),
            br_join(["Speedup ratio", small("Positive iff caching is faster.")]),
            br_join(
                [
                    "Original time",
                    small("Green iff time is large (amenable to caching)."),
                    small("Orange otherwise."),
                ]
            ),
            # br_join(["Speedup difference", small("Positive iff caching is faster.")]),
            "Details",
        ],
    )


def write_summary(repo_results: Sequence[RepoResult]) -> None:
    result = total_speedup(repo_results)
    if result:
        low, mid, high, N = result
        label = f"Speedup ratio is {100 * (1 - high):.0f}% – {100*(1 - low):.0f}% on {N} selected repositories."
    else:
        label = "Not enough data for global speedup ratio."
    Path("report.html").write_text(
        "<!DOCTYPE html>\n"
        + str(
            html.html(lang="en")(
                html.head()(
                    html.meta(charset="utf-8")(),
                    html.title()("Benchmark of charmonium.cache"),
                    *highlighted_head(["yaml", "python", "diff", "ini", "plaintext"]),
                    html.style()(
                        """
table, th, td {
  border: 1px solid black;
  border-collapse: collapse;
}
.color {
  display: block;
}
.color-nothing {
}
.color-success {
  background-color: lightgreen;
}
.color-warning {
  background-color: wheat;
}
.color-error {
  background-color: pink;
}
                    """
                    ),
                ),
                html.body()(
                    html.p(style=css_string(font_size="16pt"))(label),
                    summarize_repo_results(repo_results),
                ),
            )
        )
    )
