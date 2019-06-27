import functools
import subprocess
from pathlib import Path
from typing import List, Callable, Tuple, Any, cast
import click
from .core import Cache, FileStore, make_file_state_fn
from .util import PotentiallyPathLike


def make_exec_cached(
        command: List[str],
        cache_path: PotentiallyPathLike,
        files: List[PotentiallyPathLike],
        extra_state: Any,
        verbose: bool,
) -> str:
    '''Executes `command` or recalls its cached output

This will reexecute the command if one of `files` have changed. If a
directory is passed, it will consider the latest modtime of its
transitively contained files.

`extra_state` can be used to trigger cache invalidation. For example,
you could pass $(date +%j) to trigger invalidation once per day.

    '''

    @Cache.decor(
        FileStore.create('./', suffix=False),
        name=str(cache_path),
        state_fn=make_file_state_fn(*files)
    )
    def exec_cached(
            command: List[str],
            extra_state: Any, # pylint: disable=unused-argument
    ) -> str:
        print('cache miss')
        return cast(str, subprocess.run(
            command, capture_output=True, text=True
        ).stdout)

    return exec_cached(command, extra_state)


def printy(func: Callable[..., str]) -> Callable[..., None]:
    @functools.wraps(func)
    def new_func(*args: Any, **kwargs: Any) -> None:
        print(func(*args, **kwargs), end='')
    return new_func


# pylint: disable=no-value-for-parameter
@click.command()
@click.argument(
    'command', nargs=-1, type=str,
)
@click.option(
    '--cache-path', type=click.Path(), default=Path('.exec_cache'),
    help=(
        'location to hold the cache (defaults to ".exec_cache"). '
        'Deleting this clears the cache.'
    ),
)
@click.option(
    '-f', '--file', multiple=True, type=click.Path(), default=(),
    help='invalidates the cache if any of these files are newer',
)
@click.option(
    '--extra-state', type=str, default='',
    help='invalidates the cache if this option is different',
)
@click.option(
    '-v', '--verbose', is_flag=True,
    help='prints when the command is a cache miss',
)
@functools.wraps(make_exec_cached)
def cli_main(
        command: List[str],
        cache_path: Path,
        file: Tuple[Path],
        extra_state: str,
        verbose: bool,
) -> None:
    if not command:
        raise ValueError('no command given')
    print(make_exec_cached(command, cache_path, list(file), extra_state, verbose))

if __name__ == '__main__':
    cli_main()
