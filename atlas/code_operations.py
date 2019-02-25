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
from atlas.config import (ENVIRONMENT, CODE_ROOT, WEB_ROOT, DEFAULT_PROFILE)
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
    Create symlink between version number directory and current
    """
    code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
        CODE_ROOT,
        utilities.code_type_directory_name(item['meta']['code_type']),
        item['meta']['name'])
    # Remove symlink if it exists
    if os.path.islink(code_folder_current):
        os.unlink(code_folder_current)
    # Only link item if it is current
    if item['meta']['is_current']:
        os.symlink(utilities.code_path(item), code_folder_current)
        log.debug('Code deploy | Symlink | %s', code_folder_current)


def check_for_profile_symlink_updates(item):
    """Symlink some code items into all versions of the default profile.

    Arguments:
        item {dict} -- Complete code object that is triggering the update.
    """
    if item['meta']['code_type'] == 'profile':
        # Query for existing current modules, libraries and themes
        package_query = 'where={"meta.code_type":{"$in":["module","library","theme"]},"meta.is_current":true}'
        package_items = utilities.get_eve('code', package_query)

        # Create package symlinks in profile
        if package_items:
            for package in package_items['_items']:
                log.info('Code deploy | Adding package %s symlink to profile %s %s', package['meta']['name'], item['meta']['name'], item['meta']['version'])
                # Item is a list with a single the profile object.
                update_default_profile_symlinks(package, item)
    elif item['meta']['code_type'] in ['module', 'library', 'theme']:
        # Query for all profiles
        profile_query = 'where={{"meta.name":"{0}","meta.code_type":"profile"}}'.format(
            DEFAULT_PROFILE)
        profile_items = utilities.get_eve('code', profile_query)

        if profile_items:
            for profile in profile_items['_items']:
                log.info('Code deploy | Profiles - %s', profile)
                # Symlink current versions of package into profile
                update_default_profile_symlinks(item, profile)


def update_default_profile_symlinks(item, profile):
    """Symlink code item into profiles that are in the provided list.

    Arguments:
        item {dict} -- Code object
        profile {dict} -- Profile objects
    """
    profile_path = utilities.code_path(profile)
    # Define path to packages directory
    item_profile_type_bundles_path = '{0}/{1}/packages'.format(
        profile_path, utilities.code_type_directory_name(item['meta']['code_type']))
    # Define path to specific code item e.g. ../packages/my_bundle
    item_profile_path = '{0}/{1}'.format(item_profile_type_bundles_path, item['meta']['name'])

    # Check to see if directory for code item exists in /packages
    if not os.path.exists(item_profile_type_bundles_path):
        # Make directory for code item
        os.makedirs(item_profile_type_bundles_path)

    # Only link item if it is current
    if item['meta']['is_current']:
        # Remove existing code item symlinks, if any
        if os.path.islink(item_profile_path):
            os.unlink(item_profile_path)
        # Create new symlink
        os.symlink(utilities.code_path(item), item_profile_path)
        log.debug('Update Default Profile Symlink | Updated Profile Symlink | %s', item_profile_path)

    # Case for when a code item is updated to is_current: false
    # If item is not current remove existing symlink
    else:
        log.debug('Update Default Profile Symlink | Removed Profile Symlink | %s', item_profile_path)
        os.unlink(item_profile_path)


def remove_symlink_profile(item):
    """Remove symlinks for code item into all default profiles

    Arguments:
        item {dict} -- Complete code object
    """
    # Remove symlink for versions of package into the default profiles
    profile_query = 'where={{"meta.name":"{0}","meta.code_type":"profile"}}'.format(
        DEFAULT_PROFILE)
    profile_items = utilities.get_eve('code', profile_query)
    if profile_items:
        for profile in profile_items['_items']:
            profile_path = utilities.code_path(profile)
            item_profile_path = '{0}/{1}/packages/{2}'.format(
                profile_path,
                utilities.code_type_directory_name(item['meta']['code_type']),
                item['meta']['name'])
            # Remove symlink if it exists
            if os.path.islink(item_profile_path):
                os.unlink(item_profile_path)
            log.debug('Code remove | Remove profile symlink | %s', item_profile_path)


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
