# ghtools

Utilities for working with GitHub (IPython/Jupyter-related, mostly).

This takes some utilities developed for the maintenance of [IPython](https://github.com/ipython/ipython),
and makes them a bit more reusable as a standalone package.

This is tailored for development practices in IPython and Jupyter projects,
in particular:

- all development is done through pull requests
- all pull requests and issues are given milestones
- backport branches have names like '4.x' and '1.3.x'

Tools include:

- summary stats about releases
- manage and apply backports of pull requests

## Origins

These scripts started as part of IPython (specifically `ipython/tools`),
and are forked as of ipython/ipython@99d29c2d556b9889b5040874e5e673ae2e5a032a.
