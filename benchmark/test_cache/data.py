import asyncio
import functools
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import List, Callable, Tuple
import warnings

from .environment import Environment, PipenvEnvironment, PoetryEnvironment, CondaEnvironment, InheritedEnvironment
from .repo import Repo, GitRepo
from .action import Action, IpynbAction, CommandAction
from .annotate_funcs import annotate_funcs_in_file

ROOT = Path(__file__).parent.parent
RESOURCE_PATH = ROOT / "resources"

def prepend_source(path: Path, text: str) -> None:
    source = path.read_text()
    first_line, nl, rest = source.partition("\n")
    # This protects the case where the source file begins `from __future__ import x`
    path.write_text(first_line + nl + text + nl + rest)

def pudl_patch(repo: Repo) -> None:
    print("Patching pudl")
    if "API_KEY_EIA" not in os.environ:
        raise RuntimeError("Please place API_KEY_EIA in os.environ")
    shutil.copy(RESOURCE_PATH / "pudl/read_excel.py", repo.dir / "src/pudl")
    prepend_source(repo.dir / "src/pudl/extract/excel.py"  , "from .. import read_excel")
    prepend_source(repo.dir / "src/pudl/glue/ferc1_eia.py" , "from .. import read_excel")
    prepend_source(repo.dir / "src/pudl/transform/ferc1.py", "from .. import read_excel")
    subprocess.run(["sed", "-i", 's/pkg_resources.get_distribution("catalystcoop.pudl").version/"foobar"/g', repo.dir / "src/pudl/__init__.py"], check=True)

def annotate_funcs_in_repo(repo: Repo, source_dir: Path = Path()) -> None:
    for source in (repo.dir / source_dir).glob("**/*.py"):
        try:
            annotate_funcs_in_file(source)
        except Exception:
            warnings.warn(f"Could not annotate {source}")

data: List[Tuple[Repo, Environment, List[str], List[str]]] = [
    (
        GitRepo(
            name="pudl",
            initial_commit="40d176313e60dfa9d2481f63842ed23f08f1ad5f",
            url="git@github.com:catalyst-cooperative/pudl.git",
            display_url="https://github.com/catalyst-cooperative/pudl/commit/{commit}",
            patch_func=pudl_patch,
        ),
        PipenvEnvironment(
            name="pudl",
            pipfile=RESOURCE_PATH / "pudl/Pipfile",
        ),
        # CondaEnvironment(
        #     name="pudl",
        #     environment=Path("devtools/environment.yml"),
        #     relative_to_repo=True,
        # ),
        [
            "python", "-m", "pudl.cli", str(RESOURCE_PATH / "pudl/settings/etl_fast.yml"), "--clobber",
        ],
        [
            "40d176313e60dfa9d2481f63842ed23f08f1ad5f",
            "eccddc9892f56904ef7159cb7156caa961c08fd5",
            "ca8c434d9dac4694e77623e85aa906d33fa26e36",
            "62d08068785cc1b4edaf2228be65be5105621223",
        ],
    ),
]

v1298tau_tess_repo = GitRepo(
    name="v1298tau_tess",
    initial_commit="b3b9f5e3e47822320b618cbd55246ddf792b124d",
    url="git@github.com:afeinstein20/v1298tau_tess.git",
    display_url="https://github.com/afeinstein20/v1298tau_tess/commit/{commit}",
    patch_func=functools.partial(annotate_funcs_in_repo, source_dir=Path("src")),
    # setup=paparazzi_setup,
)

showyourwork_data: List[Tuple[Repo, Environment, List[str], List[str]]] = [
    (
        v1298tau_tess_repo,
        CondaEnvironment(
            name="v1298tau_tess",
            environment=Path("environment.yml"),
            relative_to_repo=True,
        ),
        ["sh", "-c", "snakemake --cores=1 ms.pdf &> log && sha256sum ms.pdf > output"],
        [
            "b3b9f5e3e47822320b618cbd55246ddf792b124d",
            "9e709d469b710f40ae50b24f9c6f48c639d5791d",
            # "dcbeb4cc54849482352a94560ec5144bb5bb8e3b",
            # "f764bd1bbd8dadf332c2e6663c74ee3b01b152c8",
            # "f8307e978e08da42626890bd3d244e97a9db5baf",
            # "35be468da1dda413e4bd2fc8a4dbcc7f35de77b4",
            # "96d1e2cecd75f1d57ec06244a34605bf078493fb",
            # "fa9afe001279072345270f7a8be5ecd6e8f69757",
        ],
    ),
]

exoplanet_repo = GitRepo(
    name="exoplanet",
    initial_commit="48bf5d8da8696d03ddbbb7612b91fe9c7632f390",
    url="https://github.com/exoplanet-dev/exoplanet.git",
    display_url="https://github.com/exoplanet-dev/exoplanet/commit/{commit}",
)
# exoplanet_repo.setup()

exoplanet_data: List[Tuple[Repo, Environment, List[str], List[str]]] = [
    (
        exoplanet_repo,
        CondaEnvironment(
            name="exoplanet",
            environment=RESOURCE_PATH / "exoplanet/environment.yaml",
        ),
        [
            "python", str(RESOURCE_PATH / "exoplanet/script_theano.py")
        ],
        [],
        # exoplanet_repo.interesting_commits(Path("src/exoplanet"), 100)[:1],
    ),
]

pysyd_data: List[Tuple[Repo, Environment, Action, List[str]]] = [
    (
        GitRepo(
            name="pySYD",
            url="https://github.com/ashleychontos/pySYD.git",
            initial_commit="8dbed3c40113b77fcf82f0f0bde382f7f081a3f0",
            display_url="https://github.com/ashleychontos/pySYD/commit/{commit}",
            # patch_cmds=[
            #     ["sed", "-i", "s/functions.delta_nu/utils.delta_nu/g", "pysd/target.py"],
            #     ["sed", "-i", r"s/^\(.*\)\(def run_syd\)/\1@charmonium.cache.memoize()\n\1\2/g", "pysd/target.py"],
            #     ["sed", "-i", r"s/\(class Target\)/import charmonium.cache\n\1/g", "pysd/target.py"]
            # ],
        ),
        PipenvEnvironment(
            name="pySYD",
            pipfile=RESOURCE_PATH / "pySYD/Pipfile"
        ),
        CommandAction(
            run_cmds=[
                [
                    "env", "-C", "build", "pysyd", "run", "--star", "1435467"
                ],
            ],
        ),
        [],
    )
]

bollywood_data: List[Tuple[Repo, Environment, Action, List[str]]] = [
    (
        GitRepo(
            name="bollywood-data-science",
            # patch_cmds=[
            #     ["sed", "-i", 's/^python =.*$/python = ">=3.7.1,<3.11"/g', "pyproject.toml"],
            #     ["sed", "-i", 's/^rdflib =.*$/rdflib = "^6.1.1"/g', "pyproject.toml"],
            #     ["sed", "-i", 's/^imdbpy =.*$/IMDbPY = "^2021.4.18"/g', "pyproject.toml"],
            #     ["sed", "-i", r's/^charmonium.cache =.*$/"charmonium.cache" = {url = "https:\/\/github.com\/charmoniumQ\/charmonium.cache\/archive\/main.zip"}/g', "pyproject.toml"],
            #     ["sed", "-i", '/name="cache_sparql_graph/d', "bollywood_data_science/sparql_graph.py"],
            #     ["sed", "-i", '/verbose=True/d', "bollywood_data_science/sparql_graph.py"],
            #     ["sed", "-i", '/),/d', "bollywood_data_science/sparql_graph.py"],
            #     ["sed", "-i", '/ch_cache.DirectoryStore/d', "bollywood_data_science/sparql_graph.py"],
            #     ["sed", "-i", '/ch_time_block.decor/d', "bollywood_data_science/sparql_graph.py"],
            #     ["sed", "-i", r's/ch_cache.decor(/ch_cache.memoize(/g', "bollywood_data_science/sparql_graph.py"],
            #     ["sh", "-c",
            #      shlex.join(["[", "-f", "bollywood_data_science/imdb_graph.py", "]"]) \
            #      + " && " + \
            #      shlex.join(["sed", "-i", r's/ch_cache.decor([^(]*([^)]*)[^)]*)/ch_cache.memoize()/g', "bollywood_data_science/imdb_graph.py"])
            #      + " || " + \
            #      "true"
            #      ],
            #     # ["patch", "--quiet", "bollywood_data_science/sparql_graph.py"]
            # ],
            url="https://github.com/charmoniumQ/bollywood-data-science.git",
            initial_commit="72c24046c73211ca52cebb52f3111a39bafce6ad",
            display_url="https://github.com/charmoniumQ/bollywood-data-science/commit/{commit}",
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
        [
            "72c24046c73211ca52cebb52f3111a39bafce6ad",
            "ee6abc0358baeb6f3bf2e4f9cbeba2ad6a4eb4a7",
            "7a631bb4667641476ecaf14b01f5e8f8e4dadb98",
            "97ba6a8a3d7a8030c31400e60dd4ff550bc48a91",
            "789cc4a3b6a9974105ddd17b91ada2a8d4dc70a8",
            "dce395650cf789e6078e54eecdb307bedf2a2560",
            "4d7ecc19f1b651d48b70152b0f86e820ed541546",
            "9815ee7fdd02345acf3ed9732f13cf0818af086f",
        ],
    ),
]

colmena_data: List[Tuple[Repo, Environment, Action, List[str]]] = [
    (
        GitRepo(
            name="colmena",
            url="https://github.com/exalearn/colmena.git",
            display_url="https://github.com/exalearn/colmena/commit/{commit}",
        ),
        CondaEnvironment(
            name="colmena",
            relative_to_repo=True,
            environment=Path("environment.yml"),
        ),
        CommandAction(
            run_cmds=[],
            # TODO: need to start a Redis server in another process, invoke the Colmena application, and then kill Redis.
        ),
        [
            "41ed6358c5054f3ae6a62609c6d35eaa9f81cf4a",
            "45f1f162d63020894553228a925e69c17e6430f8",
            "bc0237048c41c20b47cf1d204f75c9ecc2350765",
            "147ac73354090bedb8fc3ff99b5fc0b171a382f2",
            "6dcf426905dc411cca3046779c3b897de6958e4d",
            "d7c40036459f8047eb717536fa86e1179cd37078",
            "5d03607195d0d11155cf0c8575fc3cd19bca0cdd",
            "8aa3afd18cffa9612d57c807cbac62123bb20ab4",
            "c628e1468165322cfdcf31d23024a38a89ce0d5f",
            "8865e997914e196b482adbbe89792420bac5735e",
            "d8d48356e6ba5b907b013f5ebfca5d4a97e38806",
            "ef378981504020b8caee073699f2b747a59dad8a",
        ],
    ),
]

ipynb_to_py_data: List[Tuple[Repo, Environment, Action, List[str]]] = [
    (
        GitRepo(
            name="lightkurve",
            url="https://github.com/lightkurve/lightkurve.git",
            display_url="https://github.com/lightkurve/lightkurve/commit/{commit}",
        ),
        PipenvEnvironment(
            name="lightkurve",
            pipfile=RESOURCE_PATH / "lightkurve/Pipfile",
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
        [
            "70d1c4cd1ab30f24c83e54bdcea4dd16624bfd9c",
            "58778b9b2d3950e3cb9fff2b831fd95c74ceaeeb",
            "9ec3d41fe8f7d54ab320ed1cbf7d78baa5ac41ec",
        ],
    ),
]

old_data: List[Tuple[Repo, Environment, List[str], List[str]]] = [
    (
        GitRepo(
            name="exoplanet",
            url="https://github.com/exoplanet-dev/exoplanet.git",
            display_url="https://github.com/exoplanet-dev/exoplanet/commit/{commit}",
        ),
        CondaEnvironment(
            name="exoplanet",
            environment=RESOURCE_PATH / "exoplanet/environment.yaml",
        ),
        ["python", str(RESOURCE_PATH / "exoplanet/script.py")],
        [
            "a61076b173a32fc90f286176dc5f194395854e02",
            "9f7681301790276416c10f8139adb1b24f7a7d04",
            "10b4ec3a99f07f35ffa9a7abfef083399af2a2d2",
        ],
    ),
]
