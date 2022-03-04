import asyncio

import typer

from .data2 import get_data
from .run_experiment import run_experiment
from .write_summary import write_summary


def main() -> None:
    data = get_data()
    results = run_experiment(data)
    write_summary(results)

typer.run(main)
