"""
    atlas.code_operations
    ~~~~
    Commands that run on servers to deploy code.
"""
import logging
import os
import shutil
import subprocess

from git import Repo, Git

from atlas.config import (ENVIRONMENT, CODE_ROOT)
from atlas.config_servers import (SERVERDEFS)

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.code_operations')

LOCAL_CODE_ROOT = CODE_ROOT + '/atlas_cloned_repos'


def repository_clone(item):
    """
    Clone code to the local server.

    :param item:
    :return:
    """
    # TODO Do we need to setup dirs via ansible, either on Atlas or on deploy target nodes
    log.info('Code | Clone | Item - %s', item)
    code_dir = code_path(item)
    # Clone repo
    clone = Repo.clone_from(item['git_url'], code_dir)
    log.info('Code | Clone | Result - %s', clone)


def repository_checkout(item):
    """
    Checkout a code to the local server.

    :param item:
    :return:
    """
    # TODO Do we need to setup dirs via ansible, either on Atlas or on deploy target nodes
    log.info('Code | Checkout | Item - %s', item)
    # Checkout commit
    # TODO what happens when the commit is invalid
    repo = Repo(code_path(item))
    repo.remote().fetch()
    g = Git(code_path(item))
    g.checkout(item['commit_hash'])


def repository_remove(item):
    """
    Remove code from the local server.

    :param item:
    :return:
    """
    log.info('Code | Remove | Item - %s', item)
    shutil.rmtree(code_path(item))


def symlink_current(item):
    """
    Determine the path for a code item
    """
    code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
        LOCAL_CODE_ROOT,
        code_type_directory_name(item['meta']['code_type']),
        item['meta']['name'])
    return code_folder_current


def sync_code():
    """
    Use rsync to copy the code to all of the relevant nodes.
    """
    log.info('Code | Sync')
    # Sync code directory
    hosts = SERVERDEFS[ENVIRONMENT]['webservers'] + SERVERDEFS[ENVIRONMENT]['operations_server']
    for host in hosts:
        # -a archive mode; equals -rlptgoD
        # -z compress file data during the transfer
        # --delete delete extraneous files from dest dirs
        cmd = 'rsync -aqz {0} {1}:{2} --delete'.format(LOCAL_CODE_ROOT, host, CODE_ROOT)
        log.info('Code | Sync | Command - %s', cmd)
        output = subprocess.check_output(cmd, shell=True)
        log.info('Code | Sync | %s', output)


##
# Utility functions for code operations
##
def code_path(item):
    """
    Determine the path for a code item
    """
    code_dir = '{0}/{1}/{2}/{2}-{3}'.format(
        LOCAL_CODE_ROOT,
        code_type_directory_name(item['meta']['code_type']),
        item['meta']['name'],
        item['meta']['version']
    )
    return code_dir


def code_type_directory_name(code_type):
    """
    Determine the path for a code item
    """
    if code_type == 'library':
        return 'libraries'
    elif code_type == 'static':
        return 'static'

    return code_type + 's'
