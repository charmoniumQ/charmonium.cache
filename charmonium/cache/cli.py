from __future__ import annotations

from distutils.spawn import find_executable
from pathlib import Path

from .helpers import FileContents, KeyVer
from .memoize import MemoizedGroup, memoize
from .obj_store import DirObjStore

# pylint: disable=too-many-arguments
# This is a CLI; special case.

def main(
        command: list[str],
        obj_store: Path = Path(".cache"),
        env: str = "",
        key: str = "",
        ver: str = "",
        comparison: str = "crc32",
        replacement_policy: str = "gdsize",
        max_size: str = "1MiB",
        verbose: bool = False,
) -> None:
    actual_obj_store = DirObjStore(obj_store)
    group = MemoizedGroup(
        obj_store=actual_obj_store,
        replacement_policy=replacement_policy,
        size=max_size,
        extra_system_state=lambda: env,
    )
    executable_name = command[0]
    executable_path = find_executable(executable_name)
    if executable_path is not None:
        raise ValueError(f"{executable_name} does not exist in the path")
    executable_bytes = Path().read_bytes()

    key_ver = KeyVer(key, ver)  # type: ignore

    command_executed = False # pylint: disable=unused-variable

    @memoize(name=executable_name + "_io", verbose=verbose, group=group)
    def command_io(command: list[str], key_ver: KeyVer) -> tuple[list[Path], list[Path]]:    # pylint: disable=unused-argument
        # add executable_bytes to the closure
        executable_bytes # pylint: disable=pointless-statement
        # run with tracing
        locals()["command_executed"] = True
        return ([], [])

    input_files, output_files = command_io(command, key_ver)

    input_fcs = [FileContents(input_file, comparison) for input_file in input_files]
    output_fcs = [FileContents(output_file, comparison) for output_file in output_files] # pylint: disable=unused-variable

    @memoize(name=executable_name, verbose=verbose, group=group)
    def command_exec(command: list[str], key_ver: KeyVer, input_fcs: list[FileContents]) -> list[FileContents]:    # pylint: disable=unused-argument
        if not locals()["command_executed"]:
            pass
            # run with tracing
        return locals()["output_fcs"]

    command_exec(command, key_ver, input_fcs)

if __name__ == "__main__":
    import click
    @click.command()
    @click.option("-o", "--obj-store", type=click.Path(exists=True, dir_okay=True, path_type=Path), default=Path(".cache")) # type: ignore
    @click.option("-e", "--env", type=str, default="")
    @click.option("-k", "--key", type=str, default="")
    @click.option("-v", "--ver", type=str, default="")
    @click.option("-c", "--comparison", type=str, default="crc32")
    @click.option("-r", "--replacement-policy", type=str, default="gdsize")
    @click.option("-m", "--max-size", type=str, default="1MiB")
    @click.option("-v/-q", "--verbose/--quiet", type=bool, default=False)
    @click.argument("command", type=str, nargs=-1)
    def _main(**kwargs) -> None: # type: ignore
        main(**kwargs)
    _main()
