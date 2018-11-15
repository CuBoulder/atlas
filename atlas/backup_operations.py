"""
    atlas.backup_operations
    ~~~~
    Commands that run on servers to create, restore, and remove backups.

    Instance methods:
    Delete - Local - Remove backup files.
"""
import logging
import os

from datetime import datetime
from time import time

from atlas import utilities
from atlas.config import (ENVIRONMENT, INSTANCE_ROOT, WEB_ROOT, CORE_WEB_ROOT_SYMLINKS,
                          NFS_MOUNT_FILES_DIR, NFS_MOUNT_LOCATION, SAML_AUTH,
                          SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD, VARNISH_CONTROL_KEY,
                          SMTP_PASSWORD, WEBSERVER_USER_GROUP, ATLAS_LOCATION, SITE_DOWN_PATH,
                          SSH_USER, BACKUP_PATH)
from atlas.config_servers import (SERVERDEFS, ATLAS_LOGGING_URLS, API_URLS,
                                  VARNISH_CONTROL_TERMINALS, BASE_URLS)

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.backup_operations')


def backup_delete(item):
    """Remove backup files from servers

    Arguments:
        item {string} -- Backup item to remove
    """
    log.debug('Backup | Delete | Item - %s', item)
    log.info('Backup | Delete | Item - %s ', item['_id'])

    instance = utilities.get_single_eve('sites', item['site'], item['site_version'])
    pretty_filename = '{0}_{1}'.format(
        instance['sid'], item['backup_date'].strftime("%Y-%m-%d-%H-%M-%S"))
    pretty_database_filename = '{0}.sql'.format(pretty_filename)
    database_path = '{0}/backups/{1}'.format(BACKUP_PATH, pretty_database_filename)
    pretty_files_filename = '{0}.tar.gz'.format(pretty_filename)
    files_path = '{0}/backups/{1}'.format(BACKUP_PATH, pretty_files_filename)

    os.remove(files_path)
    os.remove(database_path)

    log.info('Backup | Delete | Complete | Item - %s', item['_id'])
