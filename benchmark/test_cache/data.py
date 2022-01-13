from pathlib import Path
from typing import List, Callable, Tuple

from .environment import Environment, PipenvEnvironment, PoetryEnvironment, CondaEnvironment
from .repo import Repo, GitRepo
from .action import Action, IpynbAction, CommandAction

ROOT = Path(__file__).parent.parent
RESOURCE_PATH = ROOT / "resources"

data: List[Tuple[Repo, Environment, Action]] = [
    (
        GitRepo(
            name="bollywood-data-science",
            patch=RESOURCE_PATH / "bollywood-data-science/patch",
            url="https://github.com/charmoniumQ/bollywood-data-science.git",
            all_commits=[
                "72c24046c73211ca52cebb52f3111a39bafce6ad",
                "ee6abc0358baeb6f3bf2e4f9cbeba2ad6a4eb4a7",
                "7a631bb4667641476ecaf14b01f5e8f8e4dadb98",
                "97ba6a8a3d7a8030c31400e60dd4ff550bc48a91",
                "789cc4a3b6a9974105ddd17b91ada2a8d4dc70a8",
                "dce395650cf789e6078e54eecdb307bedf2a2560",
                "4d7ecc19f1b651d48b70152b0f86e820ed541546",
                "9815ee7fdd02345acf3ed9732f13cf0818af086f",
                "8fdcaa96514fb03338b0f96bffe7ba6720e2fff3",
                "1fe33caa423bf72f1608bec324f9937c861b8292",
                "bce604083098301bd5d58ce8c2076c77b9473bc1",
                "9570a35589de4b37a99e2f9e7944837e2f778bfa",
                "97542111538d84d1621f039817375a6baefbb2a8",
            ],
        ),
        PoetryEnvironment(
            name="bollywood-data-science",
            pyproject=Path("pyproject.toml"),
            in_repo=True,
        ),
        CommandAction(
            run_cmds=[
                ["python3", "-m", "bollywood_data_science.main", "0", "50"],
            ],
        ),
    ),
]

ipynb_to_py_data: List[Tuple[Repo, Environment, Action]] = [
    (
        GitRepo(
            name="lightkurve",
            url="https://github.com/lightkurve/lightkurve.git",
            all_commits=[
                "70d1c4cd1ab30f24c83e54bdcea4dd16624bfd9c",
                "58778b9b2d3950e3cb9fff2b831fd95c74ceaeeb",
                "9ec3d41fe8f7d54ab320ed1cbf7d78baa5ac41ec",
            ],
        ),
        PipenvEnvironment(
            name="lightkurve",
            pipfile=RESOURCE_PATH / "lightkurve/pipfile.toml",
        ),
        IpynbAction([
            Path(f"docs/source/tutorials/3-science-examples/{name}")
            for name in [
            "asteroseismology-estimating-mass-and-radius.ipynb",
            # "asteroseismology-oscillating-star-periodogram.ipynb",
            # "exoplanets-identifying-transiting-planet-signals.ipynb",
            # "exoplanets-machine-learning-preprocessing.ipynb",
            # "exoplanets-recover-a-known-planet.ipynb",
            "exoplanets-recover-first-tess-candidate.ipynb",
            # "exoplanets-visualizing-periodic-signals-using-a-river-plot.ipynb",
            # "other-supernova-lightcurve.ipynb",
            # "periodograms-creating-periodograms.ipynb",
            # "periodograms-measuring-a-rotation-period.ipynb",
            # "periodograms-optimizing-the-snr.ipynb",
            # "periodograms-verifying-the-location-of-a-signal.ipynb",
        ]]),

    ),
]

old_data: List[Tuple[Repo, Environment, List[str]]] = [
    (
        GitRepo(
            name="exoplanet",
            url="https://github.com/exoplanet-dev/exoplanet.git",
            all_commits=[
                "a61076b173a32fc90f286176dc5f194395854e02",
                "9f7681301790276416c10f8139adb1b24f7a7d04",
                "10b4ec3a99f07f35ffa9a7abfef083399af2a2d2",
            ],
        ),
        CondaEnvironment(
            name="exoplanet",
            environment=RESOURCE_PATH / "exoplanet/environment.yaml",
        ),
        ["python", str(RESOURCE_PATH / "exoplanet/scripyt.py")],
    ),
]
