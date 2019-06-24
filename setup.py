import sys
import os
from pathlib import Path
import importlib
from setuptools import setup, find_packages


packages = find_packages()
if len(packages) != 1:
    raise ValueError(f'must have 1 package; got: {packages}')
package = [find_packages()[0]]

description = importlib.import_module(package).__doc__

name = description.split('\n')[0].split('# ')[1]

with open('requirements.txt', 'r') as f:
    requirements_str = f.read()
requirements = requirements_str.split('\n')

with open('dev-requirements.txt', 'r') as f:
    dev_requirements_str = f.read()
dev_requirements = dev_requirements_str.split('\n')


setup(
    name=name,
    version='0.1', # TODO: look into versioneer
    packages=packages,
    description=description,
    requirements=requirements,
    dev_requirements=dev_requirements,
)
