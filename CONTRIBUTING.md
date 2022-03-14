# How to setup the development environment

## With Nix

[Nix][nix] is a language-agnostic package manager that installs packages locally. [Nix Flakes][nix flakes] are a way of specifying dependencies to Nix declaraively. Currently, they are [installed separately][install nix flakes].

- `nix develop` to get a shell.
- `nix develop --command ipython` to run a command, such as `ipython`, in the project's environment.

[nix]: https://nixos.org/
[nix flakes]: https://nixos.wiki/wiki/Flakes
[install nix flakes]: https://nixos.wiki/wiki/Flakes#Installing_flakes

## With Nix and direnv

In addition to Nix, I suggest also installing [direnv][direnv] and [nix-direnv][nix-direnv]. Then simply `cd`ing to the project will activate the project-specific environment.

- `cd /path/to/project` to get a shell.
- `nix develop --command ipython` to run a command, such as `ipython`, in the project's environment.

Consider adding this line in your shell's initfile so you can see when `direnv` is activated. `PS1="\$PREPEND_TO_PS1$PS1"` Note that the sigil (dollar sign) in `$PREPEND_TO_PS1` is quoted but the one in `$PS1` is not, so `PS1` is evaluated when the shell initializes, but `PREPEND_TO_PS1` is evaluated before every prompt.

[direnv]: https://direnv.net/
[nix-direnv]: https://github.com/nix-community/nix-direnv

## With Poetry

Nix can be trouble to set up, so here is how to use the project without Nix. [Poetry][poetry] is a wrapper around `pip`/`virtualenv`, and it will manage dependencies from PyPI, but *you* have to manage external dependencies, e.g. installing the right version of Python, C libraries, etc. Poetry can be installed globally with `python -m pip install poetry`.

- `poetry shell` to get a shell.
- `poetry run ipython` to run a command, such as `ipython`, in the project's environment.

[poetry]: https://python-poetry.org/

# How to use development tools

Once in the development environment, use `./script.py` to run development tools. In the order of usefulness,

- `./script.py fmt` runs code formatters ([autoimport][autoimport], [isort][isort], [black][black]).

- `./script.py test` runs tests and code complexity analysis ([mypy][mypy], [pylint][pylint], [pytest][pytest], [coverage.py][coverage], [radon][radon] in parallel).

- `./script.py all-tests` runs the usual tests and more ([proselint][proselint], [rstcheck][rstcheck], [twine][twine], [tox][tox] (which runs [mypy][mypy] and [pytest][pytest] in each env)). This is intended for CI.

- `./script.py docs` builds the documentation locally ([proselint][proselint]).

- `./script.py publish` publishes the package to PyPI and deploys the documentation to GitHub pages (`./scripts.py all-tests`, [bump2version][bump2version], poetry publish, git push).

[autoimport]: https://lyz-code.github.io/autoimport/
[isort]: https://pycqa.github.io/isort/
[black]: https://black.readthedocs.io/en/stable/
[mypy]: https://mypy.readthedocs.io/en/stable/
[pylint]: https://pylint.org/
[pytest]: https://docs.pytest.org/en/7.0.x/
[coverage.py]: https://coverage.readthedocs.io/en/6.1.1/index.html
[radon]: https://radon.readthedocs.io/en/latest/
[proselint]: http://proselint.com/
[rstcheck]: https://github.com/myint/rstcheck
[twine]: https://twine.readthedocs.io/en/stable/
[tox]: https://tox.wiki/en/latest/
[bump2version]: https://github.com/c4urself/bump2version
