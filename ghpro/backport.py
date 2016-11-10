#!/usr/bin/env python
"""
Backport pull requests to a particular branch.

Usage: backport_pr.py todo [org/repository] branch [PR] [PR2]

e.g.:

    backport-pr apply 123 155

to backport PRs #123 and #155 onto branch 0.13.1

or

    backport-pr todo --milestone=2.1

to see what PRs are marked for backport with milestone=2.1 that have yet to be applied
to branch 2.x

or

    backport-pr --project jupyter/notebook apply 0.13.1 123 155

to backport PRs #123 and #155 of the `jupyter/notebook` repo onto branch 0.13.1
of that repo.

"""

from __future__ import print_function

import argparse
from distutils.version import LooseVersion as V
import pipes
import re
import sys


import git
import mock

from .api import (
    get_issues_list,
    get_pull_request,
    get_pull_request_files,
    is_pull_request,
    get_milestone_id,
)

from .utils import guess_project


def backport_pr(path, branch, num, project):
    """Backport a pull request

    Uses git cherry-pick -m 1 <merge-sha> to apply changes.

    In case of failure, resolve conflicts and re-run.
    On second run, will finish `git cherry-pick --continue`
    and write the commit message.

    Parameters
    ----------

    path: path to the repo
    branch: branch on which to backport
    num: pull request number
    project: GitHub project (e.g. ipython/ipython)

    Returns exit code (0 on success, 1 on failure)
    """
    repo = git.Repo(path)
    current_branch = repo.active_branch.name
    if branch != current_branch:
        repo.git.checkout(branch)

    # pull if tracking
    if repo.git.for_each_ref('--format=%(upstream:short)', 'refs/heads/%s' % branch):
        repo.git.pull()
    else:
        print("Branch %s not tracking upstream." % branch, file=sys.stderr)

    pr = get_pull_request(project, num, auth=True)
    sha = pr['merge_commit_sha']
    title = pr['title']
    description = pr['body']

    # remove mentions from description, to avoid pings:
    description = description.replace('@', ' ').replace('#', ' ')
    
    status = repo.git.status()
    if 'cherry-picking' in status:
        if 'cherry-picking commit %s' % sha[:6] not in status:
            print("I do not appear to be resuming the cherry-pick of %s" % sha, file=sys.stderr)
            print(status, file=sys.stderr)
            return 1
        print("Continuing cherry-pick of %s" % sha)
        # finish interrupted cherry-pick
        args = ('--continue',)
    else:
        print("Cherry-picking %s" % sha)
        args = ('-m', '1', sha)
    
    try:
        with mock.patch.dict('os.environ', {'GIT_EDITOR': 'true'}):
            repo.git.cherry_pick(*args)
    except Exception as e:
        print('\n' + e.stderr.decode('utf8', 'replace'), file=sys.stderr)
        print('\n' + repo.git.status(), file=sys.stderr)
        cmd = ' '.join(pipes.quote(arg) for arg in sys.argv)
        print('\nPatch did not apply. Resolve conflicts (add, not commit), then re-run `%s`' % cmd, file=sys.stderr)
        return 1

    # write the commit message
    msg = "Backport PR #%i: %s" % (num, title) + '\n\n' + description
    repo.git.commit('--amend', '-m', msg)

    print("PR #%i applied, with msg:" % num)
    print()
    print(msg)
    print()

    if branch != current_branch:
        repo.git.checkout(current_branch)

    return 0


backport_re = re.compile(r"(?:[Bb]ackport|[Mm]erge).*?(\d+)(?:[^.])")


def already_backported(repo, branch, since_tag=None):
    """return set of PRs that have been backported already"""
    if since_tag is None:
        since_tag = repo.git.describe(branch, '--abbrev=0')
    lines = repo.git.log('%s..%s' % (since_tag, branch), '--oneline')

    return set(int(num) for num in backport_re.findall(lines))

def should_backport(project, milestone=None):
    """return set of PRs marked for backport"""
    milestone_id = get_milestone_id(project, milestone,
            auth=True)
    issues = get_issues_list(project,
            milestone=milestone_id,
            state='closed',
            auth=True,
    )

    should_backport = set()
    for issue in issues:
        if not is_pull_request(issue):
            continue
        pr = get_pull_request(project, issue['number'],
                auth=True)
        if not pr['merged']:
            print ("Marked PR closed without merge: %i" % pr['number'])
            continue
        should_backport.add(pr['number'])
    return should_backport


def tobackport(project, branch, milestone, since):
    already = already_backported(git.Repo('.'), branch, since)
    should = should_backport(project, milestone)
    todo = should.difference(already)
    shouldnt = already.difference(should)
    ok = already.intersection(should)
    if shouldnt:
        still_shouldnt = []
        for num in sorted(shouldnt):
            pr = get_pull_request(project, num, auth=True)
            if pr['milestone'] and V(pr['milestone']['title']) < V(milestone):
                # ok, marked for backport to an earlier release
                ok.add(num)
            else:
                still_shouldnt.append(num)
        if still_shouldnt:
            print("The following PRs have been backported, but perhaps shouldn't be:")
            for pr in still_shouldnt:
                print(pr)
    if ok:
        print("The following PRs have been backported")
        for pr in sorted(ok):
            print(pr)
    if todo:
        print ("The following PRs should be backported:")
        for pr in sorted(todo):
            print(pr)
    else:
        print("Everything appears up-to-date")

def backport():
    parser = argparse.ArgumentParser(""""
    Backport a pull request onto a particular branch.
    
    Usage:
    """)
    parser.add_argument('branch', help="The target branch for backporting. Default: milestone major version.x")
    parser.add_argument('pulls', nargs='+', type=int, help="The pull requests to backport")
    parser.add_argument('--project', '-p', help="The GitHub project name. If not specified, guess based on git upstream or origin remotes.")
    

def main():
    parser = argparse.ArgumentParser("""
        Backport pull requests from GitHub projects.
        
        Use `todo` to show PRs that need backporting.
        Use `apply` to apply backports
    """)
    parser.add_argument('--project', '-p', help="The GitHub project name. If not specified, guess based on git upstream or origin remotes.")
    subparsers = parser.add_subparsers(help='subcommand help', dest='action')
    todo_parser = subparsers.add_parser('todo', help="Show a list of pull requests that need backporting for a particular release.")
    todo_parser.add_argument('--milestone', '-m', help="The milestone to check for backporting", required=True)
    todo_parser.add_argument('--branch', '-b', help="The target branch for backporting. Default: milestone major version.x")
    todo_parser.add_argument('--since', help="The since-tag for checking whether pull requests have been backported `git describe` is used by default.")

    apply_parser = subparsers.add_parser('apply', help="Show a list of pull requests that need backporting for a particular release.")
    apply_parser.add_argument('branch', help="The target branch for backporting. Default: milestone major version.x")
    apply_parser.add_argument('pulls', nargs='+', type=int, help="The pull requests to backport")
    opts = parser.parse_args()
    if not opts.action:
        sys.exit("Specify one of `todo` or `action` to perform.")
    
    path = '.'
    if opts.branch:
        branch = opts.branch
    else:
        branch = opts.milestone.split('.')[0] + '.x'
    if opts.project:
        project = opts.project
    else:
        project = guess_project(path)
    
    if opts.action == 'apply':
        for pr in opts.pulls:
            print("Backport PR #{pr} onto {branch}".format(pr=pr, branch=branch))
            if backport_pr(path, branch, pr, project):
                sys.exit("Backporting PR#{pr} onto {branch} failed".format(pr=pr, branch=branch))
    elif opts.action == 'todo':
        tobackport(project=project, branch=branch, milestone=opts.milestone, since=opts.since)

if __name__ == '__main__':
    main()
