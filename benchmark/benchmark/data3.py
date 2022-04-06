from pathlib import Path
from typing import Sequence, Tuple

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
    Tuple[Repo, CommitChooser, EnvironmentChooser, Sequence[str]]
]:
    return [
        (
            GitHubRepo("https://github.com/achael/eht-imaging"),
            RecentCommitChooser(None, n=2, path=Path("ehtim/obsdata.py")),
            StaticEnvironmentChooser(
                CondaEnvironment(
                    "eht-imaging", resources / "eht-imaging/environment.yml"
                )
            ),
            [
                "env",
                f"PYTHONPATH={benchmark_root / '.repos/eht-imaging'!s}",
                "python",
                str(resources / "eht-imaging/example.py"),
                str(benchmark_root / ".repos/eht-imaging"),
            ],
        ),
        (
            GitHubRepo("https://github.com/astropy/astropy"),
            RecentCommitChooser(None, n=5),
            StaticEnvironmentChooser(
                CondaEnvironment("astropy", resources / "astropy/environment.yml")
            ),
            [
                "python",
                str(resources / "astropy/examples.py"),
            ],
        ),
        # (
        #     GitHubRepo("https://github.com/LBJ-Wade/coffea"),
        #     RecentCommitChooser("6ce872671c39d788fc9fe5e981862d4c6f7658f6", n=5),
        #     SmartEnvironmentChooser(venv_location),
        #     ["python", "-m", "pytest", "--quiet"],
        # )
    ]
