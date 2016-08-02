# GHPRO

A couple of utilities for working with **G**it**H**ub **PRO**jects (IPython/Jupyter-related, mostly).

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

For example, in your repo:

    github-stats --milestone 4.3
    
To get a report about GitHub contributions for milestone 4.3.

Or

    backport-pr todo --milestone 4.4

to see what PRs are marked for 4.4 that still need backporting,
or

    backport-pr apply 4.x 1234

to backport PR #1234 onto branch 4.x

## Origins

These scripts started as part of IPython (specifically `ipython/tools`),
and are forked as of ipython/ipython@99d29c2d556b9889b5040874e5e673ae2e5a032a.
