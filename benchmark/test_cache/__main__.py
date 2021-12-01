import asyncio
import typer
import pandas as pd  # type: ignore
from pathlib import Path
from dataclasses import asdict
from .test_cache import test_cache


ROOT = Path(__file__).parent.parent


def main() -> None:
    repo_results = asyncio.run(test_cache())

typer.run(main)
