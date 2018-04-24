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
            # Grab payload
            payload = request.data
            if not payload.get('env'):
                abort(409, 'This command requires a payload containing a target `env`.')
            tasks.import_code.delay(payload['env'])
        elif command == 'rebalance_update_groups':
            tasks.rebalance_update_groups.delay()
        elif command == 'update_homepage_files':
            tasks.update_homepage_files.delay()
        elif command == 'update_settings_file':
            query = 'where={"type":"express"}&max_results=2000'
            sites = utilities.get_eve('sites', query)
            timestamp = datetime.now()
            count = 0
            total = sites['_meta']['max_results']
            for instance in sites['_items']:
                count += 1
                tasks.update_settings_file.delay(instance, timestamp, count, total)
                continue
            tasks.clear_php_cache.delay()
        elif command == 'heal_code':
            code_items = utilities.get_eve('code')
            for code in code_items['_items']:
                tasks.heal_code.delay(code)
                continue
        elif command == 'heal_instances':
            instance_query = 'where={"type":"express","f5only":false}'
            instances = utilities.get_eve('sites', instance_query)
            for instance in instances['_items']:
                tasks.heal_instance.delay(instance)
                continue
        return make_response('Command "{0}" has been initiated.'.format(command))


@app.route('/backup/import', methods=['POST'])
@requires_auth('backup')
def import_backup():
    """
    Import a backup to a new instance.
    """
    backup_request = request.get_json()
    app.logger.debug('Backup | Import | %s', backup_request)
    # Get the backup and then the site records.
    if not (backup_request.get('env') and backup_request.get('id')):
        abort(409, 'Error: Missing env (local, dev, test, prod, o-dev, o-test, o-prod) and id.')
    elif not backup_request.get('env'):
        abort(409, 'Error: Missing env (local, dev, test, prod, o-dev, o-test, o-prod).')
    elif not backup_request.get('id'):
        abort(409, 'Error: Missing id.')
    elif backup_request['env'] not in ['local', 'dev', 'test', 'prod', 'o-dev', 'o-test', 'o-prod']:
        abort(409, 'Error: Invalid env choose from [local, dev, test, prod, o-dev, o-test, o-prod].')
    elif not backup_request.get('target_id'):
        abort(409, 'Error: Missing target_instance.')
    ####
    #### Taking this part out for now. This is required for cloning between env, not for the migration.
    ####
    # backup_record = utilities.get_single_eve(
    #     'backup', backup_request['id'], env=backup_request['env'])
    # app.logger.debug('Backup | Import | Backup record - %s', backup_record)
    # site_record = utilities.get_single_eve(
    #     'sites', backup_record['site'], backup_record['site_version'], env=backup_request['env'])
    # app.logger.debug('Backup | Import | Site record - %s', site_record)

    # try:
    #     package_list = utilities.package_import(site_record, env=backup_request['env'])
    # except Exception as error:
    #     abort(500, error)

    tasks.import_backup.delay(
        env=backup_request['env'], backup_id=backup_request['id'], target_instance=backup_request['target_id'])

    return make_response('I am trying')



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


@app.route('/backup/<string:backup_id>/download', methods=['GET'])
# TODO: Test what happens with 404 for backup_id
@requires_auth('backup')
def download_backup(backup_id):
    """
    Return URLs to download the database and files
    """
    app.logger.info('Backup | Download | ID - %s', backup_id)
    backup_record = utilities.get_single_eve('backup', backup_id)
    app.logger.debug('Backup | Download | Backup record - %s', backup_record)
    urls = {
        'files': '{0}/download/{1}'.format(API_URLS[ENVIRONMENT], backup_record['files']),
        'db': '{0}/download/{1}'.format(API_URLS[ENVIRONMENT], backup_record['database'])
    }
    return jsonify(result=urls)


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


@app.route('/sites/<string:site_id>/heal', methods=['POST'])
# TODO: Test what happens with 404 for site_id
@requires_auth('sites')
def heal_instance(site_id):
    """
    Create a backup of an instance.
    :param machine_name: id of instance to restore
    """
    app.logger.debug('Site | Heal | Site ID - %s', site_id)
    instance = utilities.get_single_eve('sites', site_id)
    tasks.heal_instance.delay(instance)
    return make_response('Instance heal has been initiated.')


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


@app.route('/f5')
@requires_auth('sites')
def f5():
    """
    Generate output for f5 config.
    """
    app.logger.debug('f5 data requested')
    query = 'where={"type":"legacy"}&max_results=2000'
    legacy_sites = utilities.get_eve('sites', query)
    app.logger.debug('f5 | Site Response - %s', legacy_sites)
    f5_list = []
    for site in legacy_sites['_items']:
        if 'path' in site:
            # In case a path was saved with a leading slash
            path = site["path"] if site["path"][0] == '/' else '/' + site["path"]
            f5_list.append('"{0}" := "legacy",'.format(path))
    response = make_response('\n'.join(f5_list))
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
