"""Common utilities"""
import re

import git

# match jupyter/notebook in:
# https://github.com/jupyter/notebook.git
# git@github.com:jupyter/notebook.git

_project_pat = re.compile('.*github.com[:/](.*)\.git', re.IGNORECASE)

def guess_project(path='.'):
    """Guess the GitHub project for a given repo
    
    First, check upstream for people who use:
    
    - upstream=project, origin=mine
    
    Then, use origin for:
    
    - origin=project, mine=mine
    
    """
    repo = git.Repo(path)
    remotes = [ r for r in repo.remotes if r.name == 'upstream' ]
    if not remotes:
        remotes = [ r for r in repo.remotes if r.name == 'origin' ]
    remote = remotes[0]
    project = _project_pat.match(remote.url).group(1)
    return project

