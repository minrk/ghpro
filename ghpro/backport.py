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
import os
import re
import sys

from subprocess import Popen, PIPE

import git
import requests

from .api import (
    get_issues_list,
    get_pull_request,
    get_pull_request_files,
    is_pull_request,
    get_milestone_id,
)

from .utils import guess_project


def find_rejects(root='.'):
    for dirname, dirs, files in os.walk(root):
        for fname in files:
            if fname.endswith('.rej'):
                yield os.path.join(dirname, fname)


def backport_pr(path, branch, num, project):
    repo = git.Repo(path)
    current_branch = repo.active_branch.name
    if branch != current_branch:
        repo.git.checkout(branch)
    repo.git.pull()
    pr = get_pull_request(project, num, auth=True)
    files = get_pull_request_files(project, num, auth=True)
    patch_url = pr['patch_url']
    title = pr['title']
    description = pr['body']
    
    # remove mentions from description, to avoid pings:
    description = description.replace('@', '_')
    
    fname = "PR%i.patch" % num
    if os.path.exists(fname):
        print("using patch from {fname}".format(**locals()))
        with open(fname, 'rb') as f:
            patch = f.read()
    else:
        r = requests.get(patch_url)
        r.raise_for_status()
        patch = r.content

    msg = "Backport PR #%i: %s" % (num, title) + '\n\n' + description
    check = Popen(['git', 'apply', '--check', '--verbose'], stdin=PIPE)
    a,b = check.communicate(patch)

    if check.returncode:
        print("patch did not apply, saving to {fname}".format(**locals()))
        print("edit {fname} until `cat {fname} | git apply --check` succeeds".format(**locals()))
        print("then run tools/backport_pr.py {num} again".format(**locals()))
        if not os.path.exists(fname):
            with open(fname, 'wb') as f:
                f.write(patch)
        return 1

    p = Popen(['git', 'apply'], cwd=path, stdin=PIPE)
    p.communicate(patch)

    filenames = [ f['filename'] for f in files ]
    repo.git.add(*filenames)
    repo.git.commit('-m', msg)

    print("PR #%i applied, with msg:" % num)
    print()
    print(msg)
    print()

    if branch != current_branch:
        repo.git.checkout(current_branch)

    return 0

backport_re = re.compile(r"(?:[Bb]ackport|[Mm]erge).*?(\d+)")


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
    milestone = opts.milestone
    if opts.branch:
        branch = opts.branch
    else:
        branch = milestone.split('.')[0] + '.x'
    if opts.project:
        project = opts.project
    else:
        project = guess_project(path)
    
    if opts.action == 'apply':
        for pr in opts.pulls:
            print("Backport PR#{pr} onto {branch}".format(pr=pr, branch=branch))
            if backport_pr(path, project, branch, pr):
                sys.exit("Backporting PR#{pr} onto {branch} failed".format(pr=pr, branch=branch))
    elif opts.action == 'todo':
        tobackport(project=project, branch=branch, milestone=milestone, since=opts.since)

if __name__ == '__main__':
    main()
