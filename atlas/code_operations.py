"""
    atlas.code_operations
    ~~~~
    Commands that run on servers to deploy code.
"""
import logging
import os
import shutil
import subprocess
import git

from atlas import utilities
from atlas.config import (ENVIRONMENT, CODE_ROOT, WEB_ROOT)
from atlas.config_servers import (SERVERDEFS)

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.code_operations')


def repository_clone(item):
    """
    Clone code to the local server.

    :param item:
    :return:
    """
    log.info('Code | Clone | URL - %s', item['git_url'])
    log.debug('Code | Clone | Item - %s', item)
    code_dir = utilities.code_path(item)
    # Clone repo
    if os.path.exists(code_dir):
        raise Exception('Destinaton directory already exists')
    os.makedirs(code_dir)
    clone = git.Repo.clone_from(item['git_url'], code_dir)
    log.info('Code | Clone | Result - %s', clone)


def repository_checkout(item):
    """
    Checkout a code to the local server.

    :param item:
    :return:
    """
    log.info('Code | Checkout | Hash - %s', item['commit_hash'])
    log.debug('Code | Checkout | Item - %s', item)
    # Inializa and fetch repo
    repo = git.Repo(utilities.code_path(item))
    repo.remote().fetch()
    # Point HEAD to the correct commit and reset
    repo.head.reference = repo.commit(item['commit_hash'])
    repo.head.reset(index=True, working_tree=True)


def repository_remove(item):
    """
    Remove code from the local server.

    :param item:
    :return:
    """
    log.info('Code | Remove | Item - %s', item['_id'])
    log.debug('Code | Remove | Item - %s', item)
    shutil.rmtree(utilities.code_path(item))


def update_symlink_current(item):
    """
    Determine the path for a code item
    """
    code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
        CODE_ROOT,
        utilities.code_type_directory_name(item['meta']['code_type']),
        item['meta']['name'])
    # Remove symlink if it exists
    if os.path.islink(code_folder_current):
        os.unlink(code_folder_current)
    os.symlink(utilities.code_path(item), code_folder_current)
    log.debug('Code deploy | Symlink | %s', code_folder_current)


def sync_code():
    """Copy the code to all of the relevant nodes.
    """
    log.info('Code | Sync')
    hosts = SERVERDEFS[ENVIRONMENT]['webservers'] + SERVERDEFS[ENVIRONMENT]['operations_server']
    # Sync code root
    utilities.sync(CODE_ROOT, hosts, CODE_ROOT)
    # Sync static items
    utilities.sync(WEB_ROOT + '/static', hosts, WEB_ROOT + '/static')


def deploy_static(item):
    """Deploy static asset to the web root
    
    Arguments:
        item {dict} -- Item record for static asset to deploy
    """
    log.info('Code | Deploy static')
    # Create symlink in web root
    web_root_static_name = WEB_ROOT + '/static/' + item['meta']['name']
    # Make static directories if needed.
    if not os.path.isdir(web_root_static_name):
        os.makedirs(web_root_static_name)
    # Remove symlink if it exists
    web_root_path = web_root_static_name + '/' + item['meta']['version']
    if os.path.islink(web_root_path):
        os.unlink(web_root_path)
    os.symlink(utilities.code_path(item), web_root_path)


def remove_static(item, other_static_assets=True):
    """Remove static asset from the web root

    Arguments:
        item {dict} -- Item record for static asset to deploy

    Keyword Arguments:
        other_static_assets {bool} -- If false, remove directory for asset name (default: {True})
    """

    log.info('Code | Remove static')
    web_root_static_name = WEB_ROOT + '/static/' + item['meta']['name']
    web_root_path = web_root_static_name + '/' + item['meta']['version']
    # Remove symlink if it exists
    if os.path.islink(web_root_path):
        os.unlink(web_root_path)
    if not other_static_assets and os.path.isdir(web_root_static_name):
        os.rmdir(web_root_static_name)
