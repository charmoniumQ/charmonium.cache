from pathlib import Path
from typing import Sequence, Tuple, Mapping

from .environment import (
    CondaEnvironment,
    EnvironmentChooser,
    SmartEnvironmentChooser,
    StaticEnvironmentChooser,
)
from .repo import CommitChooser, GitHubRepo, RecentCommitChooser, Repo
from .util import BenchmarkError

benchmark_root = Path(__file__).parent.parent

venv_location = benchmark_root / Path(".my-venv/")

resources = benchmark_root / "resources"


def get_data() -> Sequence[
    Tuple[Repo, CommitChooser, EnvironmentChooser, Mapping[str, str], Path, Mapping[str, int]]
]:
    return [
        # (
        #     GitHubRepo("https://github.com/achael/eht-imaging"),
        #     RecentCommitChooser(None, n=2, path=Path("ehtim/obsdata.py")),
        #     StaticEnvironmentChooser(
        #         CondaEnvironment(
        #             "eht-imaging", resources / "eht-imaging/environment.yml"
        #         )
        #     ),
        #     {
        #         "eht_root": str(benchmark_root / ".repos/eht-imaging"),
        #     },
        #     resources / "eht-imaging/example.py",
        #     {
        #         "time": 600,
        #         "mem": 2**32,
        #     },
        # # ),
        # (
        #     GitHubRepo("https://github.com/astropy/astropy"),
        #     RecentCommitChooser(None, n=5),
        #     StaticEnvironmentChooser(
        #         CondaEnvironment("astropy", resources / "astropy/environment.yml")
        #     ),
        #     {},
        #     resources / "astropy/UVES.py",
        #     {
        #         "time": 80,
        #         "mem": 2**29,
        #     },
        # ),
        # (
        #     GitHubRepo("https://github.com/LBJ-Wade/coffea"),
        #     RecentCommitChooser("6ce872671c39d788fc9fe5e981862d4c6f7658f6", n=5),
        #     SmartEnvironmentChooser(venv_location),
        #     ["python", "-m", "pytest", "--quiet"],
        # )
    ]
