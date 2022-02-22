# FlaPy

[FlaPy][1] is a collection of scripts and a dataset.

- [`repos.csv`][7] is a CSV where each row contains project name, project url, and commit hash.
- [`./run_csv.sh`][2] parses the dataset of repositories and invokes `./run_execution.sh` on each one.
- [`./run_execution.sh`][3] clones the project in a temporary directory, runs `flakyanalysis`, and copies the results somewhere else.
- [`flakyanalysis`][4] finds the packages `requirements.txt` (or variations defined [here][5]) or `Pipfile.lock`, installs the packages to a virtual environment, and runs `pytest` with `benchexec` (exact arguments [here][6]), parses the test results, and finds flaky tests.

[1]: https://github.com/se2p/FlaPy
[2]: https://github.com/se2p/FlaPy/blob/71a55540493bc861325fe89e070cc1e90a102891/run_csv.sh
[3]: https://github.com/se2p/FlaPy/blob/71a55540493bc861325fe89e070cc1e90a102891/run_execution.sh
[4]: https://github.com/se2p/FlaPy/blob/71a55540493bc861325fe89e070cc1e90a102891/flapy/analysis.py#L886
[5]: https://github.com/se2p/FlaPy/blob/71a55540493bc861325fe89e070cc1e90a102891/flapy/analysis.py#L301
[6]: https://github.com/se2p/FlaPy/blob/71a55540493bc861325fe89e070cc1e90a102891/flapy/analysis.py#L382
[7]: https://github.com/se2p/FlaPy/blob/71a55540493bc861325fe89e070cc1e90a102891/repos.csv

# My Pipeline

By contrast, my pipeline (located [here][8]) contains just one script and a dataset.

- [`benchmark.run_experiment`][9]: clones each repository in the dataset, installs the necessary packages according to the dataset, checks out a sequence of commits according to the dataset, and for each commit, it runs a memoized and unmemoized command defined in the dataset.
- The dataset is a Python datastructure where each element contains a repo object, an environment object, a command, and a list of commits. The environment object contains the tool for acquiring dependencies and the file for specifying them (e.g. `poetry`/`pyproject.toml`, `pipenv`/`Pipfile.lock`, `conda`/`environment.yaml`).

[8]: https://github.com/charmoniumQ/charmonium.cache/tree/main/benchmark
[9]: https://github.com/charmoniumQ/charmonium.cache/blob/1b912ffe85ea7de6ba8e7346be48b4547a4103c5/benchmark/test_cache/run_experiment.py

# Differences and resolutions

**Difference:** In my pipeline, the dataset needs to say where to find the dependency files, whereas FlaPy is able to deduce this, but only for `Pipfile.lock` and `requirements.txt`. **Resolution:** Incorporate `FlaPy`'s heuristic for finding the dependency tool and configuration, and incorporate `FlaPy`'s mechanism for using `virtualenv`/`requirements.txt`.

**Difference:** In my pipeline, the command can be anything. In FlaPy's pipeline, the command is a specific pytest command. **Resolution:** I can make that pytest command the "default" unless some other is specified. With this and the prior resolution, I should be able to run all of repositories in FlaPy's dataset.

**Difference:** In my pipeline, I need to explicitly say which git commits to run on. FlaPy's dataset lists only one commit, but I need dozens to determine the performance of memoization. **Resolution:** I will write a heuristic that grabs the N most recent commits that have a significant impact on the code (would likely need to rerun tests). With this and the prior two resolutions, I should be able to run all of the repositories in FlaPy's dataset with and without memoization. In particular, FlaPy's experiment uses [BenchExec][10] to get stable measurements.

[10]: https://github.com/sosy-lab/benchexec

# Conclusion

In general, I think my pipeline is more efficient, because it only downloads the repositories once over subsequent runs; theirs would download again each time. Mine runs multiple commits of the same repository without creating copies of the repository. Mine only creates one virtualenv; theirs creates two.

I will maintain my own pipeline, but incorporate some functions from FlaPy into my code. I will, however, use FlaPy's dataset of repositories.
