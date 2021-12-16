import asyncio

import pandas as pd  # type: ignore
import typer

from .data import data
from .run_experiment import run_experiment
from .write_summary import write_summary


def main() -> None:
    write_summary(run_experiment(data))

typer.run(main)
