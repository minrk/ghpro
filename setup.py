#!/usr/bin/env python

from setuptools import setup

setup(
    setup_requires=[
        'pbr>=1.9',
        'setuptools>=17.1',
        'keyring',
        'mock',
        'requests',
        'requests-cache',
        'gitpython',
        ],
    pbr=True,
)
