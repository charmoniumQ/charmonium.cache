from pathlib import Path
from typing import List, Callable, Tuple

from .environment import Environment, PipenvEnvironment
from .repo import Repo, GitRepo
from .action import Action, IpynbAction

ROOT = Path(__file__).parent.parent
RESOURCE_PATH = ROOT / "resources"

exoplanet_min_commits = [
    "a61076b173a32fc90f286176dc5f194395854e02",
    "9f7681301790276416c10f8139adb1b24f7a7d04",
    "10b4ec3a99f07f35ffa9a7abfef083399af2a2d2",
]

exoplanet_max_commits = [
    *exoplanet_min_commits,
]

data: List[Tuple[Repo, Environment, Action]] = [
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
    # (
    #     GitRepo(
    #         name="exoplanet",
    #         url="https://github.com/exoplanet-dev/exoplanet.git",
    #         commits=exoplanet_min_commits,
    #     ),
    #     CondaEnvironment(
    #         name="exoplanet",
    #         environment=RESOURCE_PATH / "exoplanet/environment.yaml",
    #     ),
    #     ["python", RESOURCE_PATH / "exoplanet/scripyt.py"],
    # ),
]
