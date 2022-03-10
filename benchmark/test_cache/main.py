import asyncio

import typer

from .data2 import get_data
from .run_experiment import run_experiment
from .write_summary import write_summary


def main() -> None:
    """
LD_LIBRARY_PATH=$(nix eval --raw nixpkgs#libseccomp.lib)/lib:$(nix eval --raw nixpkgs#gcc-unwrapped.lib)/lib poetry run python -m test_cache.main ; notify-send Done
    """

    data = get_data()
    results = run_experiment(data)
    write_summary(results)

if __name__ == "__main__":
    typer.run(main)
