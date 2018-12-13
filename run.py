"""
    atlas.run.py
    ~~~~~~~~~~~
    The API launch script.
"""
import os
import sys
import json
import logging
from logging.handlers import WatchedFileHandler
import ssl

from collections import Counter
from datetime import datetime
from eve import Eve
from eve.auth import requires_auth
from flask import jsonify, make_response, abort, request

from atlas import callbacks
from atlas import commands
from atlas import tasks
from atlas import utilities
from atlas.config import (ATLAS_LOCATION, VERSION_NUMBER, SSL_KEY_FILE, SSL_CRT_FILE, LOG_LOCATION,
                          ENVIRONMENT, API_URLS)


if ATLAS_LOCATION not in sys.path:
    sys.path.append(ATLAS_LOCATION)


# Load the settings file using a robust path so it works when
# the script is imported from the test suite.
THIS_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
SETTINGS_FILE = os.path.join(THIS_DIRECTORY, 'atlas/data_structure.py')

# Name our app (using 'import_name') so that we can easily create sub loggers.
# Use our HTTP Basic Auth class which checks against LDAP.
# Import the data structures and Eve settings.
app = Eve(import_name='atlas', auth=utilities.AtlasBasicAuth, settings=SETTINGS_FILE)
# TODO: Remove debug mode.
app.debug = True

# Enable logging to 'atlas.log' file.
LOG_HANDLER = WatchedFileHandler(LOG_LOCATION)
LOG_HANDLER.setFormatter(logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s'))

# The default log level is set to WARNING, so we have to explicitly set the logging level to Info.
app.logger.setLevel(logging.INFO)
if ENVIRONMENT == 'local':
    app.logger.setLevel(logging.DEBUG)
# Append the handler to the default application logger
app.logger.addHandler(LOG_HANDLER)


# We will use Flask to serve the Commands endpoint.
@app.route('/commands', methods=['GET'])
def get_commands():
    """Get a list of available commands."""
    return jsonify({'commands': commands.COMMANDS})


@app.route('/commands/<string:machine_name>', methods=['GET', 'POST'])
def get_command(machine_name):
    """
    Get a single command.
    :param machine_name: command to return a definition for.
    """
    command = [command for command in commands.COMMANDS if command['machine_name'] == machine_name]
    if not command:
        abort(404)
    else:
        command = command[0]['machine_name']
    if request.method == 'GET':
        return jsonify({'command': command})
    elif request.method == 'POST':
        # Loop through the commands list and grab the one we want
        app.logger.debug('Command | Execute | %s', command)
        if command == 'clear_php_cache':
            tasks.clear_php_cache.delay()
        elif command == 'import_code':
            # Grab payload, it is a JSON string from the request
            payload = json.loads(request.data)
            if not payload.get('env'):
                abort(409, 'This command requires a payload containing a target `env`.')
            tasks.import_code.delay(payload['env'])
        elif command == 'rebalance_update_groups':
            tasks.rebalance_update_groups.delay()
        elif command == 'update_homepage_files':
            tasks.update_homepage_files.delay()
        elif command == 'update_settings_files':
            sites = utilities.get_eve('sites')
            timestamp = datetime.now()
            count = 0
            total = sites['_meta']['total']
            for instance in sites['_items']:
                count += 1
                tasks.update_settings_file.delay(instance, timestamp, count, total)
                continue
            tasks.clear_php_cache.delay()
        elif command == 'heal_code':
            code_items = utilities.get_eve('code')
            tasks.code_heal.delay(code_items)
        elif command == 'heal_instances':
            instances = utilities.get_eve('sites')
            tasks.instance_heal.delay(instances)
        elif command == 'sync_instances':
            tasks.instance_sync.delay()
        elif command == 'correct_file_permissions':
            instances = utilities.get_eve('sites')
            for instance in instances['_items']:
                tasks.correct_file_permissions.delay(instance)
                continue
        elif command == 'backup_all_instances':
            tasks.backup_instances_all.delay(backup_type='on_demand')
        elif command == 'remove_extra_backups':
            tasks.remove_extra_backups.delay()
        return make_response('Command "{0}" has been initiated.'.format(command))


@app.route('/backup/import', methods=['POST'])
@requires_auth('backup')
def import_backup():
    """
    Import a backup to a new instance on the current version of core, profile, and any packages
    that are present. If a current version of a package is not available, the import will abort.
    """
    backup_request = request.get_json()
    app.logger.debug('Backup | Import | %s', backup_request)
    # Get the backup and then the site records.
    # TODO Get the list of env from the config files.
    # TODO Verify import is from different env, recommend restore if it is the same env.
    if not (backup_request.get('env') and backup_request.get('id')):
        abort(409, 'Error: Missing env (local, dev, test, prod) and id.')
    elif not backup_request.get('env'):
        abort(409, 'Error: Missing env (local, dev, test, prod).')
    elif not backup_request.get('id'):
        abort(409, 'Error: Missing id.')
    elif backup_request['env'] not in ['local', 'dev', 'test', 'prod']:
        abort(409, 'Error: Invalid env choose from [local, dev, test, prod]')

    backup_record = utilities.get_single_eve(
        'backup', backup_request['id'], env=backup_request['env'])
    app.logger.debug('Backup | Import | Backup record - %s', backup_record)
    remote_site_record = utilities.get_single_eve(
        'sites', backup_record['site'], backup_record['site_version'], env=backup_request['env'])
    app.logger.debug('Backup | Import | Site record - %s', remote_site_record)

    # Get a list of packages to include
    try:
        package_list = utilities.package_import_cross_env(
            remote_site_record, env=backup_request['env'])
    except Exception as error:
        abort(500, error)

    app.logger.info('Backup | Import | Package list - %s', package_list)

    # Try to get the p1 record.
    local_p1_instance_record = utilities.get_single_eve('sites', remote_site_record['sid'])
    app.logger.debug('Backup | Import | Local instance record - %s', local_p1_instance_record)
    # Try to get the path record if the site is launched.
    local_path_instance_record = False
    if remote_site_record['path'] != remote_site_record['sid']:
        query_string = 'where={{"path":"{0}"}}'.format(remote_site_record['path'])
        local_path_instance_records = utilities.get_eve('sites', query_string)
        app.logger.info('Backup | Import | Local path instance record - %s',
                        local_path_instance_records)
        if local_path_instance_records['_meta']['total'] == 1:
            local_path_instance_record = True
    if local_p1_instance_record['_error'] and local_p1_instance_record['_error']['code'] == 404 and not local_path_instance_record:
        # Create an instance with the same sid
        payload = {
            "status": remote_site_record['status'],
            "sid": remote_site_record['sid'],
            "path": remote_site_record['path']
        }
        response_string = 'the same'
    else:
        app.logger.info('Backup | Import | Instance sid or path exists')
        payload = {
            "status": "installed"
        }
        response_string = 'a new'

    # Add package list to payload if it exists
    if package_list:
        payload['code'] = {"package": package_list}
    # Set install
    payload['install'] = False

    new_instance = utilities.post_eve('sites', payload)
    app.logger.debug('Backup | Import | New instance record - %s', new_instance)

    env = backup_request['env']
    backup_id = backup_request['id']
    target_instance = new_instance['_id']

    tasks.import_backup.apply_async([env, backup_id, target_instance], countdown=30)

    return make_response('Attempting to import backup to {0} sid'.format(response_string))


@app.route('/backup/<string:backup_id>/restore', methods=['POST'])
# TODO: Test what happens with 404 for backup_id
@requires_auth('backup')
def restore_backup(backup_id):
    """
    Restore a backup to a new instance.
    :param machine_name: id of backup to restore
    """
    app.logger.debug('Backup | Restore | %s', backup_id)
    backup_record = utilities.get_single_eve('backup', backup_id)
    original_instance = utilities.get_single_eve(
        'sites', backup_record['site'], backup_record['site_version'])
    # If packages are still active, add them; if not, find a current version
    # and add it; if none, error
    try:
        package_list = utilities.package_import(original_instance)
    except Exception as error:
        abort(409, error)

    tasks.backup_restore.delay(backup_record, original_instance, package_list)
    response = make_response('Restore started')
    return response


@app.route('/sites/<string:site_id>/backup', methods=['POST'])
# TODO: Test what happens with 404 for site_id
@requires_auth('backup')
def create_backup(site_id):
    """
    Create a backup of an instance.
    :param machine_name: id of instance to restore
    """
    app.logger.debug('Backup | Create | Site ID - %s', site_id)
    site = utilities.get_single_eve('sites', site_id)
    app.logger.debug('Backup | Create | Site Response - %s', site)
    tasks.backup_create.delay(site=site, backup_type='on_demand')
    response = make_response('Backup started')
    return response


@app.route('/sites/aggregation', methods=['GET'])
@app.route('/sites/agg', methods=['GET'])
@requires_auth('sites')
def sites_statistics():
    """
    Give some basic aggregations about site objects
    """
    app.logger.debug('Sites | Aggregations')
    express_result = utilities.get_eve('sites')
    app.logger.debug('Sites | Aggregations | Express Result - %s', express_result)
    # Express sites
    express_sites = express_result['_items']
    agg = {}
    count = Counter()
    group = Counter()
    # Total by state
    for site in express_sites:
        count[site['status']] += 1
        group[site['update_group']] += 1
    agg['express'] = {
        'status': dict(count),
        'update_group': dict(group)
    }
    # Total
    agg['express']['status']['total'] = express_result['_meta']['total']

    response = make_response(jsonify(agg))
    return response


@app.route('/sites/<string:site_id>/file_permissions', methods=['POST'])
# TODO: Test what happens with 404 for site_id
@requires_auth('sites')
def correct_file_permissions(site_id):
    """
    Correct file permissions for an instance's NFS files.
    :param machine_name: id of instance to fix
    """
    app.logger.debug('Site | Correct file permissions | Site ID - %s', site_id)
    instance = utilities.get_single_eve('sites', site_id)
    tasks.correct_file_permissions.delay(instance)
    return make_response('Fixing permissions for NFS mounted files.')


@app.route('/drush/<string:drush_id>/execute', methods=['POST'])
# TODO: Test what happens with 404 for drush_id
@requires_auth('drush')
def execute_drush(drush_id):
    """
    Execute a drush command.
    :param machine_name: id of instance to restore
    """
    tasks.drush_prepare.delay(drush_id)
    response = make_response('Drush command started, check the logs for outcomes.')
    return response


# Specific callbacks.
# Use pre event hooks if there is a chance you want to abort.
# Use DB hooks if you want to modify data on the way in.

# Request event hooks.
app.on_pre_POST += callbacks.pre_post
app.on_pre_POST_sites += callbacks.pre_post_sites
app.on_pre_PATCH_sites += callbacks.pre_patch_sites
app.on_pre_PUT_sites += callbacks.pre_patch_sites
app.on_pre_DELETE_code += callbacks.pre_delete_code
app.on_pre_DELETE_sites += callbacks.pre_delete_sites
# Database event hooks.
app.on_insert_code += callbacks.on_insert_code
app.on_insert_sites += callbacks.on_insert_sites
app.on_inserted_sites += callbacks.on_inserted_sites
app.on_update_code += callbacks.on_update_code
app.on_update_sites += callbacks.on_update_sites
app.on_updated_code += callbacks.on_updated_code
app.on_delete_item_code += callbacks.on_delete_item_code
app.on_insert += callbacks.pre_insert
app.on_update += callbacks.pre_update
app.on_replace += callbacks.pre_replace
app.on_delete_item += callbacks.on_delete_item
app.on_deleted_sites += callbacks.on_deleted_item_sites
app.on_delete_item_backup += callbacks.on_delete_item_backup


@app.errorhandler(409)
def custom409(error):
    response = jsonify({'message': error.description})
    response.status_code = 409
    return response


@app.route('/version')
def version():
    response = make_response(VERSION_NUMBER)
    return response


@app.route('/saml/create', methods=['GET', 'POST'])
@requires_auth('sites')
def saml_create():
    if request.method == 'POST':
        response = make_response("Started SAML database creation")
        tasks.saml_create.delay()
    else:
        response = make_response("Did you mean to POST?")
    return response


@app.route('/saml/delete', methods=['GET', 'POST'])
@requires_auth('sites')
def saml_delete():
    if request.method == 'POST':
        response = make_response("Started SAML database delete")
        tasks.saml_delete.delay()
    else:
        response = make_response("Did you mean to POST?")
    return response


# This config is only used when running via python, rather than mod_wsgi
if __name__ == '__main__':
    ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ctx.load_cert_chain(SSL_CRT_FILE, SSL_KEY_FILE)

    # This goes last.
    app.run(host='0.0.0.0', ssl_context=ctx)
