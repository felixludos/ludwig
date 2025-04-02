#!/usr/bin/env python

from setuptools import find_packages, setup

# from https://www.reddit.com/r/Python/comments/3uzl2a/setuppy_requirementstxt_or_a_combination/

requires = [line.strip() for line in open("requirements.txt").readlines()]
requires = [r for r in requires if not r.startswith("#") and r != ""]

setup(
    name="ludwig",
    version="0.0",
    description="TODO",
    author="Maximilian Mordig",
    url="TODO",
    packages=find_packages("."),
    entry_points={
        "console_scripts": [
            # "cmd_name=ludwig.module_path:main",
        ]
    },
    scripts=[
        # bash scripts, only updates on reinstall
        # "path/to/bash/script/from/workspace/root/my_script", # call as: my_script
    ],
    install_requires=requires, #dependency_links=links,
)
