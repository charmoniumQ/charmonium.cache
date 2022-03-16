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
    html_list,
    html_path,
    html_table,
    small,
)
from .repo import Repo
from .run_experiment import CommitResult, ExecutionProfile, FuncCallProfile, RepoResult

T = TypeVar("T")

confidence = 0.9


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


executions: Mapping[str, html.TagLike] = {
    "orig": "Unmodified",
    "memo": "Memoized",
}

commit_result_headers: Sequence[html.TagLike] = [
    "Commit",
    "Warnings",
    "Tests work?",
    html.span()("Memoized output", html.br()(), "matches original?"),
    *[html.span()(execution, " time") for execution in executions.values()],
    "Detailed results",
]


def count(it: Iterable[T]) -> int:
    counter = 0
    for e in it:
        counter += 1
    return counter


def summarize_commit(repo: Repo, result: CommitResult) -> html.Tag:
    date_str = result.date.astimezone(datetime.timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    adds = count(re.finditer(rb"^[+] ", result.diff, flags=re.MULTILINE))
    subs = count(re.finditer(rb"^[-] ", result.diff, flags=re.MULTILINE))
    return html_table(
        [
            ["Date", disp_date(result.date)],
            [
                "Hash",
                html.a(href=repo.display_url.format(commit=result.commit))(
                    result.commit[:6]
                ),
            ],
            ["Diff", f"Diff +{adds}/-{subs}"],
        ]
    )


def color_cell(elem: html.TagLike, color: str) -> html.Tag:
    return html.span(style=css_string(background_color=color, display="block"))(elem)


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


def summarize_commit_result(repo: Repo, result: CommitResult) -> Sequence[html.TagLike]:
    inner_table = html_table(
        [
            [
                "Status",
                *[
                    color_cell("Success", "green")
                    if prof.success
                    else color_cell("Error", "red")
                    for prof in result.executions.values()
                ],
            ],
            [
                "Output",
                *[
                    highlighted_code("plaintext", prof.output)
                    for prof in result.executions.values()
                ],
            ],
            [
                "Warnings",
                *[
                    highlighted_code("plaintext", "\n".join(prof.warnings))
                    for prof in result.executions.values()
                ],
            ],
            [
                "Log",
                *[
                    highlighted_code("plaintext", prof.log)
                    for prof in result.executions.values()
                ],
            ],
            [
                "Time (s)",
                *[
                    disp_sec(prof.runexec.cputime)
                    for prof in result.executions.values()
                ],
            ],
            [
                "Overhead (s)",
                *[
                    disp_sec(get_process_overhead(prof))
                    for prof in result.executions.values()
                ],
            ],
            [
                "Function calls",
                *[
                    collapsed("Show", summarize_func_calls(prof.func_calls))
                    for prof in result.executions.values()
                ],
            ],
        ],
        ["", *[executions[label] for label in result.executions.keys()]],
    )
    tests_work = any(execution.success for execution in result.executions.values())
    warnings = [
        warning
        for execution in result.executions.values()
        for warning in execution.warnings
    ]
    return [
        summarize_commit(repo, result),
        collapsed(
            color_cell("Warnings", "red"),
            highlighted_code("plaintext", "\n".join(set(warnings))),
        )
        if warnings
        else color_cell("None", "green"),
        color_cell("Tests work", "green")
        if tests_work
        else color_cell("Tests don't work", "red"),
        color_cell("Output matches", "green")
        if not result_mismatch(result)
        else color_cell("Outputs don't match", "red"),
        *[
            disp_sec(
                result.executions[execution].runexec.cputime
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
        return html_table(
            [
                ["Manager", "Conda"],
                # [
                #     html.code()("environment.yaml"),
                #     collapsed("show", highlighted_code("yaml", environment.environment.read_text())),
                # ],
            ]
        )
    elif isinstance(environment, PoetryEnvironment):
        return html_table(
            [
                ["Manager", "Poetry"],
                # [
                #     html.code()("pyproject.toml"),
                #     collapsed("show", highlighted_code("toml", environment.pyproject.read_text())),
                # ],
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
        commit_result.executions
        for commit_result in repo_result.commit_results
        if all(
            tag in commit_result.executions
            and commit_result.executions[tag].runexec.cputime > 0
            for tag in tags
        )
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
            label, "green" if mid > 5 else "yellow" if mid > -5 else "red"
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
        return color_cell(label, "green" if mid > orig_time_cutoff else "yellow")


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


def result_mismatch(commit_result: CommitResult) -> bool:
    return (
        "memo" not in commit_result.executions
        or "orig" not in commit_result.executions
        or commit_result.executions["memo"].output
        != commit_result.executions["orig"].output
    )


def get_command(repo_result: RepoResult) -> Sequence[str]:
    if not repo_result.commit_results:
        return ["true"]
    first = repo_result.commit_results[0]
    if "orig" not in first.executions:
        return ["true"]
    return first.executions["orig"].command


def summarize_repo_result(result: RepoResult) -> Sequence[html.Tag]:
    warnings = list(
        set(
            warning
            for commit_result in result.commit_results
            for execution in commit_result.executions.values()
            for warning in execution.warnings
        )
    ) + list(result.warnings)

    if not result.commit_results:
        status = color_cell("Install failed", "orange")
    elif not any(
        commit_result.executions["orig"].success
        for commit_result in result.commit_results
    ):
        status = color_cell("Tests don't work", "orange")
    elif len(get_nonzero_executions(result, "memo", "orig")) < 2:
        status = color_cell("Not enough working commits", "orange")
    elif any(
        any(
            execution.runexec.termination_reason
            for execution in commit_result.executions.values()
        )
        for commit_result in result.commit_results
    ):
        status = color_cell("Limit exceeded", "orange")
    elif any(map(result_mismatch, result.commit_results)):
        status = color_cell("Result doesn't match", "red")
    elif warnings:
        status = color_cell("Completed with warnings", "green")
    else:
        status = color_cell("Success", "green")

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
                    ["Local path", html_path(result.repo.dir)],
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
                    summarize_commit_result(result.repo, commit_result)
                    for commit_result in result.commit_results
                ],
                commit_result_headers,
            ),
        ),
    ]


def sort_key(repo_result: RepoResult) -> Any:
    if not repo_result.commit_results:
        return (0,)
    elif not any(
        commit_result.executions["orig"].success
        for commit_result in repo_result.commit_results
    ):
        return (1,)
    elif len(get_nonzero_executions(repo_result, "memo", "orig")) < 2:
        return (2,)
    elif any(
        any(
            execution.runexec.termination_reason
            for execution in commit_result.executions.values()
        )
        for commit_result in repo_result.commit_results
    ):
        return (3,)
    elif any(map(result_mismatch, repo_result.commit_results)):
        return (-2,)
    else:
        return (4, int("green" in original_time(repo_result).attrib["style"]))


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
