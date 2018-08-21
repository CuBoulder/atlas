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

from atlas.config import (ENVIRONMENT, CODE_ROOT, LOCAL_CODE_ROOT)
from atlas.config_servers import (SERVERDEFS)

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.code_operations')


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
    if os.path.exists(code_dir):
        raise Exception('Destinaton directory already exists')
    clone = Repo.clone_from(item['git_url'], code_dir)
    log.info('Code | Clone | Result - %s', clone)


def repository_checkout(item):
    """
    Checkout a code to the local server.

    :param item:
    :return:
    """
    log.info('Code | Checkout | Item - %s', item)
    # Fetch repo
    repo = Repo(code_path(item))
    repo.remote().fetch()
    # Checkout commit
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


def update_symlink_current(item):
    """
    Determine the path for a code item
    """
    code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
        LOCAL_CODE_ROOT,
        code_type_directory_name(item['meta']['code_type']),
        item['meta']['name'])
    # Remove symlink if it exists
    if os.path.exists(code_folder_current):
        os.unlink(code_folder_current)
    os.symlink(code_path(item), code_folder_current)
    log.debug('Code deploy | Symlink | %s', code_folder_current)



def sync_code():
    """
    Use rsync to copy the code to all of the relevant nodes.
    """
    log.info('Code | Sync')
    # TODO Check ownership on web and operations nodes
    # TODO Do we need to setup dirs via ansible, either on Atlas or on deploy target nodes
    # Sync code directory
    hosts = SERVERDEFS[ENVIRONMENT]['webservers'] + SERVERDEFS[ENVIRONMENT]['operations_server']
    # Recreate readme
    filename = LOCAL_CODE_ROOT + "/README.md"
    f= open(filename, "w+")
    f.write("The contents of this directory are rsynced from Atlas. Any changes will be overwritten.")
    f.close()
    for host in hosts:
        # -a archive mode; equals -rlptgoD
        # -z compress file data during the transfer
        # trailing slash on src copies the contents, not the parent dir itself.
        # --delete delete extraneous files from dest dirs
        cmd = 'rsync -aqz {0}/ {1}:{2} --delete'.format(LOCAL_CODE_ROOT, host, CODE_ROOT)
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
