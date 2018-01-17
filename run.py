"""
    atlas.run.py
    ~~~~~~~~~~~
    The API launch script.
"""
import os
import sys
import logging
from logging.handlers import WatchedFileHandler
import ssl

from eve import Eve
from eve.auth import requires_auth
from flask import jsonify, make_response, abort

from atlas import callbacks
from atlas import tasks
from atlas import utilities
from atlas.media_storage import FileSystemMediaStorage
from atlas.config import (ATLAS_LOCATION, VERSION_NUMBER, SSL_KEY_FILE, SSL_CRT_FILE, LOG_LOCATION,
                          ENVIRONMENT)


if ATLAS_LOCATION not in sys.path:
    sys.path.append(ATLAS_LOCATION)


# Load the settings file using a robust path so it works when
# the script is imported from the test suite.
THIS_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
SETTINGS_FILE = os.path.join(THIS_DIRECTORY, 'atlas/data_structure.py')

# Name our app (using 'import_name') so that we can easily create sub loggers.
# Use our HTTP Basic Auth class which checks against LDAP.
# Import the data structures and Eve settings.
app = Eve(import_name='atlas', auth=utilities.AtlasBasicAuth,
          settings=SETTINGS_FILE, media=FileSystemMediaStorage)
# TODO: Remove debug mode.
app.debug = True

# Enable logging to 'atlas.log' file.
LOG_HANDLER = WatchedFileHandler(LOG_LOCATION)
# The default log level is set to WARNING, so we have to explicitly set the logging level to Info.
app.logger.setLevel(logging.INFO)
if ENVIRONMENT == 'local':
    app.logger.setLevel(logging.DEBUG)
# Append the handler to the default application logger
app.logger.addHandler(LOG_HANDLER)

# Hook into the request flow early
@app.route('/backup/<string:backup_id>/restore', methods=['POST'])
@requires_auth('backup')
def restore_backup(backup_id):
    """
    Restore a backup to a new instance.
    :param machine_name: id of backup to restore
    """
    app.logger.debug('Backup | Restore | %s', backup_id)
    backup_record = utilities.get_single_eve('backup', backup_id)
    original_instance = utilities.get_single_eve('sites', backup_record['site'])
    # If packages are still active, add them; if not, find a current version
    # and add it; if none, error
    if 'packages' in original_instance['code']:
        # Start with an empty list
        package_list = None
        for package in original_instance['code']:
            package_result = utilities.get_single_eve('code', package)
            app.logger.debug(
                'Backup | Restore | Checking for packages | Request result - %s', package_result)
            if package_result['_deleted']:
                current_package = utilities.get_current_code(
                    package_result['name'], package_result['code_type'])
                if current_package:
                    package_list.append(current_package['_id'])
                else:
                    abort(409, 'There is no current version of {0}. This backup cannot be restored.'.format(
                        package_result['name']))
            else:
                package_list.append(package_result['_id'])
    else:
        package_list = None
    tasks.backup_restore.delay(backup_record, original_instance, package_list)
    response = make_response('Restore started')
    return response

@app.route('/sites/<string:site_id>/backup', methods=['POST'])
@requires_auth('backup')
def create_backup(site_id):
    """
    Create a backup of an instance.
    :param machine_name: id of instance to restore
    """
    app.logger.debug('Backup | Create | %s', site_id)
    site = utilities.get_single_eve('sites', site_id)
    # If packages are still active, add them; if not, find a current version and add it; if none, error
    tasks.backup_create.delay(site)
    response = make_response('Backup started')
    return response

# Specific callbacks.
# Use pre event hooks if there is a chance you want to abort.
# Use DB hooks if you want to modify data on the way in.

# Request event hooks.
app.on_pre_POST += callbacks.pre_post_callback
app.on_pre_POST_sites += callbacks.pre_post_sites_callback
app.on_pre_PATCH_sites += callbacks.pre_patch_sites_callback
app.on_pre_PUT_sites += callbacks.pre_patch_sites_callback
app.on_pre_DELETE_code += callbacks.pre_delete_code_callback
app.on_pre_DELETE_sites += callbacks.pre_delete_sites_callback
# Database event hooks.
app.on_insert_code += callbacks.on_insert_code_callback
app.on_insert_sites += callbacks.on_insert_sites_callback
app.on_inserted_sites += callbacks.on_inserted_sites_callback
app.on_update_code += callbacks.on_update_code_callback
app.on_update_sites += callbacks.on_update_sites_callback
app.on_update_commands += callbacks.on_update_commands_callback
app.on_updated_code += callbacks.on_updated_code_callback
app.on_delete_item_code += callbacks.on_delete_item_code_callback
app.on_insert += callbacks.pre_insert
app.on_update += callbacks.pre_update
app.on_replace += callbacks.pre_replace


@app.errorhandler(409)
def custom409(error):
    response = jsonify({'message': error.description})
    response.status_code = 409
    return response


@app.route('/version')
def version():
    response = make_response(VERSION_NUMBER)
    return response


# This config is only used when running via python, rather than mod_wsgi
if __name__ == '__main__':
    ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ctx.load_cert_chain(SSL_CRT_FILE, SSL_KEY_FILE)

    # This goes last.
    app.run(host='0.0.0.0', ssl_context=ctx)
