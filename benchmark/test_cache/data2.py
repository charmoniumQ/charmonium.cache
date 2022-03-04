import random
import csv
from pathlib import Path
from typing import Sequence, Tuple
import warnings

from .util import BenchmarkError
from .repo import Repo, GitHubRepo, CommitChooser, RecentCommitChooser
from .environment import EnvironmentChooser, SmartEnvironmentChooser

data_path = Path("data.csv")
venv_location = Path(".my-venv/")

def get_data() -> Sequence[Tuple[Repo, CommitChooser, EnvironmentChooser, Sequence[str]]]:
    results = []
    with data_path.open() as data_file:
        data = list(csv.DictReader((
            line
            for line in data_file
            if not line.startswith("#")
        )))
    random.seed(0)
    subdata = random.sample(data, 20)
    for row in subdata:
        url = row["Project_URL"]
        commit = row["Project_Hash"]
        if True:
            try:
                repo = GitHubRepo(url)
            except BenchmarkError as e:
                warnings.warn(f"{url!r} isn't valid. {e!s}")
            else:
                results.append((
                    repo,
                    RecentCommitChooser(commit, n=10),
                    SmartEnvironmentChooser(venv_location),
                    ["python", "-m", "pytest", "--quiet"],
                ))
    return results
