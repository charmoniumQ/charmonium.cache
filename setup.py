from pathlib import Path
import importlib
import setuptools


# https://github.com/kennethreitz/setup.py/blob/master/setup.py
# https://the-hitchhikers-guide-to-packaging.readthedocs.io/en/latest/creation.html
# https://github.com/audreyr/cookiecutter-pypackage/blob/master/setup.cfg


source_dir = Path('.') # root of the namespace
main_package = 'charmonium.cache'
name = main_package
author = 'Samuel Grayson'
url = f'https://github.com/charmoniumQ/{name}'
python_requires = '>=3.6.0'
keywords = 'caching cache library'.split(' ')
description = 'Provides a decorator for caching a function and an equivalent command-line util.'
classifiers = [
    # Trove classifiers
    # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Natural Language :: English',
    'Operating System :: OS Independent',
    'Programming Language :: Python :: 3 :: Only',
    'Topic :: Software Development :: Libraries',
    'Typing :: Typed',
]
extras_require=dict(
    cli=[
        'click',
    ],
)
tests_require = [
    'mypy',
    'pylint',
    'pytest',
    'typing_extensions',
    'bumpversion',
]
install_requires = []


packages = setuptools.find_namespace_packages(
    exclude=('env', 'env.*'),
    where=source_dir,
)
assert main_package in packages

def path_from_parts(parts):
    base = Path('.')
    for part in parts:
        base = base / part
    return base

console_scripts = [
    f'{package}={package}.__main__:cli_main [cli]'
    for package in packages
    if (source_dir / path_from_parts(package.split('.')) / '__main__.py').exists()
]

entry_points = dict(console_scripts=console_scripts)

long_description = importlib.import_module(main_package).__doc__
assert description is not None
long_description = long_description.lstrip()
long_description_content_type = 'text/markdown'

license_map = {
    # https://pypi.org/classifiers/
    # 'first line of license': 'trove classifier for license'
    'Mozilla Public License Version 2.0': 'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)'
}

with open('LICENSE') as f:
    license = next(f).strip()
    classifiers.append(license_map[license])


if __name__ == '__main__':
    setuptools.setup(
        name=name,
        version='0.1.0',
        # this should technically be a Trove identifier
        license=license,
        packages=packages,
        description=description,
        long_description=long_description,
        # because GitHub's README.md can also render markdown
        # https://stackoverflow.com/questions/26737222/how-to-make-pypi-description-markdown-work
        long_description_content_type=long_description_content_type,
        install_requires=install_requires,
        tests_require=tests_require,
        extras_require=extras_require,
        python_requires=python_requires,
        entry_points=entry_points,
        classifiers=classifiers,
    )
