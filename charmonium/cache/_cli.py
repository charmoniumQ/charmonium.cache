import functools
import subprocess
from pathlib import Path
from typing import Any, Callable, List, Tuple, cast

import click

from .core import FileStore, cache_decor, make_file_state_fn
from .util import PotentiallyPathLike


def cli_cached(
    command: List[str],
    cache_path: PotentiallyPathLike,
    files: List[PotentiallyPathLike],
    extra_state: Any = None,
    verbose: bool = False,
) -> str:
    """Executes `command` or recalls its cached output

This will reexecute the command if one of `files` have changed. If a
directory is passed, it will consider the latest modtime of its
transitively contained files.

`extra_state` can be used to trigger cache invalidation. For example,
you could pass $(date +%j) to trigger invalidation once per day.

    """

    @cache_decor(
        FileStore.create("./", suffix=False),
        name=str(cache_path),
        state_fn=make_file_state_fn(*files),
    )
    def this_cli_cached(
        command: List[str], extra_state: Any,  # pylint: disable=unused-argument
    ) -> str:
        if verbose:
            print("cache miss")
        return subprocess.run(
            command, capture_output=True, text=True, check=True
        ).stdout

    return cast(Callable[[List[str], Any], str], this_cli_cached)(command, extra_state)


# pylint: disable=no-value-for-parameter
@click.command()
@click.argument(
    "command", nargs=-1, type=str,
)
@click.option(
    "--cache-path",
    type=click.Path(),
    default=Path(".exec_cache"),
    help=(
        'location to hold the cache (defaults to ".exec_cache"). '
        "Deleting this clears the cache."
    ),
)
@click.option(
    "-f",
    "--file",
    multiple=True,
    type=click.Path(),
    default=(),
    help="invalidates the cache if any of these files are newer",
)
@click.option(
    "--extra-state",
    type=str,
    default="",
    help="invalidates the cache if this option is different",
)
@click.option(
    "-v", "--verbose", is_flag=True, help="prints when the command is a cache miss",
)
@functools.wraps(cli_cached)
def main(
    command: List[str],
    cache_path: Path,
    file: Tuple[Path],
    extra_state: str,
    verbose: bool,
) -> None:
    if not command:
        raise ValueError("no command given")
    print(cli_cached(command, cache_path, list(file), extra_state, verbose))
