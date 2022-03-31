import warnings
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Type, cast
from pathlib import Path

from .environment import (
    CondaEnvironment,
    EnvironmentChooser,
    SmartEnvironmentChooser,
    StaticEnvironmentChooser,
)
from .repo import CommitChooser, GitHubRepo, RecentCommitChooser, Repo
from .environment import Environment, CondaEnvironment, EnvironmentChooser
from .run_experiment import run_exec_cmd, time_limit, mem_limit, tmp_dir
from benchexec import container  # type: ignore

def test_cmd(
        repo: Repo,
        environment: Environment,
        cmd: Sequence[str],
) -> None:
    runexec_stats, info = run_exec_cmd(
        environment,
        cmd,
        {},
        repo.dir,
        dir_modes={
            "/": container.DIR_READ_ONLY,
            # TODO: Ideally, I would use `--overlay-dir` with tmp_dir instead of --full--access-dir.
            # See https://github.com/sosy-lab/benchexec/issues/815
            "/home": container.DIR_OVERLAY,
            str(tmp_dir): container.DIR_FULL_ACCESS,
            str(repo.dir): container.DIR_FULL_ACCESS,
        },
    )
    print(info)
    if runexec_stats.termination_reason:
        warnings.warn(
            f"Terminated for {runexec_stats.termination_reason} out with {time_limit=} {mem_limit=}"
        )
    if runexec_stats.exitcode != 0:
        warnings.warn(
            f"Terminated with exitcode {runexec_stats.exitcode!r}"
        )

def setup(
        repo: Repo,
        environment_chooser: EnvironmentChooser,
) -> Optional[Environment]:
    repo.setup()
    environment = environment_chooser.choose(repo)
    if environment is None:
        warnings.warn(f"{repo} {environment_chooser} chose None.")
        return None
    environment.setup()
    packages = ["--editable", repo.dir]
    if not environment.has_package("charmonium.cache"):
        packages.append(
            ["https://github.com/charmoniumQ/charmonium.cache/tarball/main"]
        )
    environment.install(packages)
    return environment

benchmark_root = Path(__file__).parent.parent

venv_location = benchmark_root / Path(".my-venv/")

resources = benchmark_root / "resources"

if True:
    data: Sequence[Tuple[Repo, CommitChooser, EnvironmentChooser, Sequence[str]]] = [
        (
            GitHubRepo("https://github.com/astropy/astropy"),
            RecentCommitChooser(None, n=5),
            StaticEnvironmentChooser(
                CondaEnvironment(
                    "astropy", resources / "astropy/environment.yml"
                )
            ),
            [
                "env",
                "python",
                str(resources / "astropy/examples.py"),
            ],
        ),
    ]

if __name__ == "__main__":
    for repo, commit_chooser, environment_chooser, cmd in data:
        environment = setup(repo, environment_chooser)
        if environment:
            test_cmd(repo, environment, cmd)
