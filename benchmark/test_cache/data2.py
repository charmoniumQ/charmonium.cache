import random
import csv
from pathlib import Path
from typing import Sequence, Tuple
import warnings

from .util import BenchmarkError
from .repo import Repo, GitHubRepo, CommitChooser, RecentCommitChooser
from .environment import EnvironmentChooser, SmartEnvironmentChooser

data_path = Path("repos.csv")
venv_location = Path(".my-venv/")

denylist = {
    "persefone",
    "celery",
    "python-lego-wireless-protocol",
    "onnx-caffe2",
    "enhancesa",
}

def get_data() -> Sequence[Tuple[Repo, CommitChooser, EnvironmentChooser, Sequence[str]]]:
    results = []
    with data_path.open() as data_file:
        data = list(csv.DictReader((
            line
            for line in data_file
            if not line.startswith("#")
        )))
    random.seed(0)
    random.shuffle(data)
    for row in data:
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
                    # TODO: Use benchexec
                    # TODO: Print report
                ))
    results = [
        result
        for result in results
        if result[0].name not in denylist
    ]
    return results
