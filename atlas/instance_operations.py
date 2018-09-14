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
from atlas.config import (ENVIRONMENT, CODE_ROOT, LOCAL_CODE_ROOT, LOCAL_INSTANCE_ROOT, LOCAL_WEB_ROOT)
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
    core_path =
    profile_path =

    # Create structure in LOCAL_INSTANCE_ROOT
    if os.path.exists(instance_code_path_sid):
        raise Exception('Destinaton directory already exists')
    os.makedirs(instance_code_path_sid)

    # Add Drupal core
    for link in DRUPAL_CORE_PATHS:
        source_path = "{0}/{1}".format(core_path, link)
        target_path = "{0}/{1}".format(instance_code_path_sid, link)
        update_symlink(source_path, target_path)
    # Add profile
    # Add packages
    # Add NFS mount
    # Create setttings file
    # Correct file permissions
    # Create symlinks for current and for LOACL_WEB_ROOT
