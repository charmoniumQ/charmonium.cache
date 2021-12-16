#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import datetime
import multiprocessing
import os
import shlex
import shutil
import subprocess
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Awaitable,
    Callable,
    Iterable,
    List,
    Mapping,
    Optional,
    TypeVar,
    Union,
    cast,
)

import autoimport
import isort
import setuptools  # type: ignore
import toml  # type: ignore
import typer
from charmonium.async_subprocess import run
from termcolor import cprint  # type: ignore
from typing_extensions import ParamSpec

Params = ParamSpec("Parms")
Return = TypeVar("Return")


def coroutine_to_function(
    coroutine: Callable[Params, Awaitable[Return]]  # type: ignore
) -> Callable[Params, Return]:  # type: ignore
    @wraps(coroutine)
    def wrapper(*args: Params.args, **kwargs: Params.kwargs) -> Return:  # type: ignore
        return asyncio.run(coroutine(*args, **kwargs))  # type: ignore

    return wrapper


if TYPE_CHECKING:
    CompletedProc = subprocess.CompletedProcess[str]
else:
    CompletedProc = None


def default_checker(proc: CompletedProc) -> bool:
    return proc.returncode == 0


async def pretty_run(
    cmd: List[Union[Path, str]],
    checker: Callable[[CompletedProc], bool] = default_checker,
    env_override: Optional[Mapping[str, str]] = None,
) -> CompletedProc:
    start = datetime.datetime.now()
    proc = await run(
        cmd, capture_output=True, text=True, check=False, env_override=env_override
    )
    proc = cast(CompletedProc, proc)
    stop = datetime.datetime.now()
    delta = stop - start
    success = checker(proc)
    color = "green" if success else "red"
    cmd_str = shlex.join(map(str, cmd))
    cprint(
        f"$ {cmd_str}\nexited with status {proc.returncode} in {delta.total_seconds():.1f}s",
        color,
    )
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)
    if not success:
        raise RuntimeError()
    return proc


def most_recent_common_ancestor(packages: List[str]) -> str:
    common_ancestor = packages[0].split(".")
    for package in packages:
        new_common_ancestor = []
        for seg1, seg2 in zip(common_ancestor, package.split(".")):
            if seg1 != seg2:
                break
            new_common_ancestor.append(seg1)
        common_ancestor = new_common_ancestor
    return ".".join(common_ancestor)


def get_package_path(package: str) -> Path:
    return Path().joinpath(*package.split("."))


app = typer.Typer()
# TODO: don't use packages
tests_dir = Path("tests")
pyproject = toml.loads(Path("pyproject.toml").read_text())
extra_packages = [
    obj["include"] for obj in pyproject["tool"]["poetry"].get("packages", [])
]
src_packages = setuptools.find_packages() + extra_packages
main_package = most_recent_common_ancestor(src_packages)
assert main_package, f"No common ancestor of {src_packages}"
main_package_dir = get_package_path(main_package)
docsrc_dir = Path("docsrc")
build_dir = Path("build")
all_python_files = list(
    {
        *tests_dir.rglob("*.py"),
        *main_package_dir.rglob("*.py"),
        Path("script.py"),
        # docsrc_dir / "conf.py",
    }
)


def run_autoimport(path: Path) -> None:
    with path.open("r+") as file:
        autoimport.fix_files([file])  # type: ignore


T1 = TypeVar("T1")
T2 = TypeVar("T2")


@app.command()
@coroutine_to_function
async def fmt(parallel: bool = True) -> None:
    pool = multiprocessing.Pool()
    mapper = cast(
        Callable[[Callable[[T1], T2], Iterable[T1]], Iterable[T2]],
        pool.imap_unordered if parallel else map,
    )
    list(mapper(run_autoimport, all_python_files))
    list(mapper(isort.file, all_python_files))
    await pretty_run(["black", "--quiet", *all_python_files])


@app.command()
@coroutine_to_function
async def test() -> None:
    await asyncio.gather(
        pretty_run(
            ["dmypy", "run", "--", *all_python_files],
            env_override={"MYPY_FORCE_COLOR": "1"},
        ),
        pretty_run(
            [
                "pylint",
                "-j",
                "0",
                "--output-format",
                "colorized",
                "--score=y",
                *all_python_files,
            ],
            # see https://pylint.pycqa.org/en/latest/user_guide/run.html#exit-codes
            checker=lambda proc: proc.returncode & (1 | 2) == 0,
        ),
        pytest(use_coverage=True),
        pretty_run(
            [
                "radon",
                "cc",
                "--min",
                "b",
                "--show-complexity",
                "--no-assert",
                main_package_dir,
                tests_dir,
            ]
        ),
        pretty_run(
            [
                "radon",
                "mi",
                "--min",
                "b",
                "--show",
                "--sort",
                main_package_dir,
                tests_dir,
            ]
        ),
    )


@app.command()
@coroutine_to_function
async def per_env_tests() -> None:
    await asyncio.gather(
        pretty_run(
            # No daemon
            ["mypy", *all_python_files],
            env_override={"MYPY_FORCE_COLOR": "1"},
        ),
        pytest(use_coverage=False),
    )


@app.command()
@coroutine_to_function
async def docs() -> None:
    await docs_inner()


async def docs_inner() -> None:
    if docsrc_dir.exists():
        await asyncio.gather(
            pretty_run(["sphinx-build", "-W", "-b", "html", docsrc_dir, "docs"]),
            pretty_run(["proselint", "README.rst", *docsrc_dir.glob("*.rst")]),
        )
        print(f"See docs in: file://{(Path() / 'docs' / 'index.html').resolve()}")


@app.command()
@coroutine_to_function
async def all_tests() -> None:
    await all_tests_inner()


async def all_tests_inner() -> None:
    async def poetry_build() -> None:
        dist = Path("dist")
        if dist.exists():
            shutil.rmtree(dist)
        await pretty_run(["poetry", "build"])
        await pretty_run(["twine", "check", *dist.iterdir()])
        shutil.rmtree(dist)

    await asyncio.gather(
        poetry_build(),
        docs_inner(),
    )
    subprocess.run(
        ["tox", "--parallel", "auto"], env={**os.environ, "PY_COLORS": "1"}, check=True
    )


async def pytest(use_coverage: bool) -> None:
    if tests_dir.exists():
        await pretty_run(
            [
                "pytest",
                "--color=yes",
                "--exitfirst",
                "--workers=auto",
                "--doctest-modules",
                "--doctest-glob='*.rst'",
                *([f"--cov={main_package_dir!s}"] if use_coverage else []),
            ],
            checker=lambda proc: proc.returncode in {0, 5},
        )
        if use_coverage:
            await pretty_run(
                ["coverage", "html", "--directory", build_dir / "coverage"]
            )
            print(
                f"See code coverage in: file://{(build_dir / 'coverage' / 'index.html').resolve()}"
            )


class VersionPart(str, Enum):
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


@app.command()
@coroutine_to_function
async def publish(version_part: VersionPart, verify: bool = True) -> None:
    await (all_tests_inner() if verify else docs_inner())
    if (await pretty_run(["git", "status", "--porcelain"])).stdout:
        raise RuntimeError("git status is not clean")
    await pretty_run(["bump2version", version_part.value])
    await pretty_run(["poetry", "publish", "--build"])
    await pretty_run(["git", "push", "--tags"])
    # TODO: publish docs


if __name__ == "__main__":
    app()
