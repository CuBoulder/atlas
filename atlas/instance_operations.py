"""
    atlas.instance_operations
    ~~~~
    Commands that run on servers to deploy instances.

    Instance methods:
    Create - Local - All symlinks are in place, DB exists, NFS mount is attached
    Install - Remote - Drupal install command runs
    Update - Local and Remote - Update code or configuration; optionally clear caches, rebuild
        registry, and/or run database update script.
    Repair - Check that only intended code exists in instance, add any missing code. If extra code
        is found, raise an exception and open a ticket.
    Delete - Remove instance symlinks, settings file, NFS files, and database.
    Backup - Create a database and NFS files backup of the instance.
    Restore - Restore backup to a new `sid`
"""
import logging
import os

from atlas import utilities
from atlas.config import (ENVIRONMENT, CODE_ROOT, LOCAL_CODE_ROOT, LOCAL_INSTANCE_ROOT, LOCAL_WEB_ROOT, CORE_WEB_ROOT_SYMLINKS)
from atlas.config_servers import (SERVERDEFS)

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.instance_operations')


def instance_create(instance):
    """Create database, symlink structure, settings file, and NFS space for an instance.

    Arguments:
        instance {dict} -- complete instance dict from POST request
    """
    log.info('Instance | Provision | Instance ID - %s', instance['_id'])
    log.debug('Instance | Provision | Instance ID - %s | Instance - %s', instance['_id'], instance)
    # Setup path variables
    instance_code_path_sid = '{0}/{1}/{1}'.format(LOCAL_INSTANCE_ROOT, instance['sid'])
    instance_code_path_current = '{0}/{1}/current'.format(LOCAL_INSTANCE_ROOT, instance['sid'])
    instance_web_path_sid = '{0}/{1}'.format(LOCAL_WEB_ROOT, instance['sid'])
    # Setup code assets
    profile = utilities.get_single_eve('code', instance['code']['profile'])
    core = utilities.get_code_name_version(instance['code']['core'])
    # Setup code paths
    core_path = utilities.code_path(core)
    profile_path = utilities.code_path(profile)

    # Create structure in LOCAL_INSTANCE_ROOT
    if os.path.exists(instance_code_path_sid):
        raise Exception('Destinaton directory already exists')
    os.makedirs(instance_code_path_sid)
    ## Add Core
    # Get a list of files in the Core source directory
    core_files = os.listdir(core_path)
    # Iterate through the source files and symlink when applicable.
    for core_file in core_files:
        if core_file in ['sites', 'profiles']:
            continue
        if utilities.ignore_code_file(core_file):
            continue
        source_path = core_path + '/' + core_file
        destination_path = instance_code_path_sid + '/' + core_file
        os.symlink(source_path, destination_path)
   # Create Instance specific directory structure
    directories_to_create = ['sites',
                             'sites/all',
                             'sites/all/modules',
                             'sites/all/libraries',
                             'sites/all/themes',
                             'sites/default',
                             'sites/default/files',
                             'profiles']
    for directory in directories_to_create:
        target_dir = instance_code_path_sid + '/' + directory
        os.mkdir(target_dir)
    # TODO Do we want to copy over default settings file? I don't really see a reason to
    # TODO Do we want to include links to the profiles that we are not using?
    # TODO Will we use core profiles for testing or benchmarking purposes?
    ## Add profile
    destination_path = instance_code_path_sid + '/profiles/' + profile['meta']['name']
    os.symlink(profile_path, destination_path)
    ## Add packages
    ## Add NFS mount
    ## Create setttings file
    ## Correct file permissions
    ## Create symlinks for current and for LOACL_WEB_ROOT
